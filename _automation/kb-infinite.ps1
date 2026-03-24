# KB Update - Modalita' Infinita
# Loop continuo: estrae un task, lo esegue, attende, ripete.
# Su rate limit attende il ripristino e riprende automaticamente.
# Ctrl+C o chiudi la finestra per interrompere (stato sempre salvato).

$Host.UI.RawUI.WindowTitle = "KB Update - Infinito"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$AutoDir     = $PSScriptRoot
$PromptFile  = Join-Path $AutoDir "run-prompt.md"
$StateFile   = Join-Path $AutoDir "state.yaml"
$LogFile     = Join-Path $AutoDir "runs.log"
$StatePy     = Join-Path $AutoDir "manage-state.py"

Set-Location $ProjectRoot

# -- Configurazione ----------------------------------------------------------

$RunInterval   = 120   # secondi tra run normali
$RateLimitWait = 5400  # secondi di attesa su rate limit (90 min)
$ErrorWait     = 300   # secondi di attesa su errore generico

# -- Rilevamento claude.exe --------------------------------------------------

$claudeBin = "claude"
if (-not (Get-Command "claude" -ErrorAction SilentlyContinue)) {
    $found = Get-ChildItem "$env:USERPROFILE\.vscode\extensions\anthropic.claude-code-*\resources\native-binary\claude.exe" -ErrorAction SilentlyContinue |
             Sort-Object FullName -Descending |
             Select-Object -First 1 -ExpandProperty FullName
    if ($found) {
        $claudeBin = $found
    } else {
        Write-Host "  ERRORE: claude.exe non trovato." -ForegroundColor Red
        Read-Host "  Premi INVIO per chiudere"
        exit 1
    }
}

# -- Controllo python --------------------------------------------------------

if (-not (Get-Command "python3" -ErrorAction SilentlyContinue) -and
    -not (Get-Command "python"  -ErrorAction SilentlyContinue)) {
    Write-Host "  ERRORE: Python non trovato nel PATH." -ForegroundColor Red
    Read-Host "  Premi INVIO per chiudere"
    exit 1
}
$pythonBin = if (Get-Command "python3" -ErrorAction SilentlyContinue) { "python3" } else { "python" }

# -- UI iniziale -------------------------------------------------------------

Clear-Host
Write-Host ""
Write-Host "  KB Update - Modalita' Infinita" -ForegroundColor Magenta
Write-Host "  Loop continuo - Ctrl+C per interrompere (stato sempre salvato)" -ForegroundColor DarkGray
Write-Host "  --------------------------------------------------------" -ForegroundColor DarkGray
Write-Host "  Progetto   : $ProjectRoot" -ForegroundColor DarkGray
Write-Host "  Avvio      : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor DarkGray
Write-Host "  Intervallo : ${RunInterval}s tra run | ${RateLimitWait}s su rate limit" -ForegroundColor DarkGray
Write-Host ""

# -- Patterns rate limit -----------------------------------------------------

$rateLimitPatterns = @("rate.limit","rate limit","overloaded","too many requests","usage limit","quota exceeded","529")

# -- Loop principale ---------------------------------------------------------

$runCount = 0

while ($true) {

    $runCount++
    $timestamp = Get-Date -Format "HH:mm:ss"

    Write-Host ""
    Write-Host "  [$timestamp] Run #$runCount" -ForegroundColor Cyan

    # -- Estrai prossimo task ------------------------------------------------
    $taskJson = & $pythonBin $StatePy next-task 2>&1

    if ($taskJson -eq "null" -or [string]::IsNullOrWhiteSpace($taskJson)) {
        Write-Host "  [DONE] Queue vuota - tutti i task completati." -ForegroundColor Green
        $logEntry = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [INF #$runCount] QUEUE_EMPTY"
        Add-Content -Path $LogFile -Value $logEntry -Encoding UTF8

        Write-Host "  Attendo ${RunInterval}s prima di ricontrollare la queue..." -ForegroundColor DarkGray
        Start-Sleep -Seconds $RunInterval
        continue
    }

    try {
        $task = $taskJson | ConvertFrom-Json
    } catch {
        Write-Host "  [X] Errore parsing task JSON: $taskJson" -ForegroundColor Red
        Start-Sleep -Seconds $ErrorWait
        continue
    }

    Write-Host "  Task : [$($task.priority)] $($task.id) - $($task.path)" -ForegroundColor White

    # Checkpoint prima di iniziare
    & $pythonBin $StatePy mark-started $task.id | Out-Null

    # -- Costruisci prompt ---------------------------------------------------
    $promptTemplate = Get-Content $PromptFile -Raw -Encoding UTF8
    $prompt = $promptTemplate -replace "\{\{TASK_JSON\}\}", $taskJson

    # -- Esegui -------------------------------------------------------------
    $startTime = Get-Date
    $output    = & $claudeBin --dangerously-skip-permissions -p $prompt 2>&1
    $exitCode  = $LASTEXITCODE
    $elapsed   = [int]((Get-Date) - $startTime).TotalSeconds

    # -- Validazione struttura -----------------------------------------------
    $pathsToCheck = ConvertTo-Json @($task.path) -Compress
    $validation   = & $pythonBin $StatePy validate-all $pathsToCheck 2>&1
    try { $valResult = $validation | ConvertFrom-Json } catch { $valResult = $null }

    # -- Pruning state -------------------------------------------------------
    & $pythonBin $StatePy prune | Out-Null

    # -- Analisi esito -------------------------------------------------------
    $isRateLimited = $rateLimitPatterns | Where-Object { $output -imatch $_ }

    if ($isRateLimited -or $exitCode -eq 529) {

        $resumeTime = (Get-Date).AddSeconds($RateLimitWait).ToString("HH:mm")
        Write-Host "  [!] Token esauriti. Ripresa ~ $resumeTime" -ForegroundColor Yellow

        $logEntry = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [INF #$runCount] RATE_LIMIT task=$($task.id) wait=${RateLimitWait}s"
        Add-Content -Path $LogFile -Value $logEntry -Encoding UTF8

        # Countdown ogni 5 minuti
        $remaining = $RateLimitWait
        while ($remaining -gt 0) {
            $mins = [int]($remaining / 60)
            Write-Host "  ... $mins min al ripristino   " -ForegroundColor DarkGray -NoNewline
            Write-Host "`r" -NoNewline
            $wait = [Math]::Min(300, $remaining)
            Start-Sleep -Seconds $wait
            $remaining -= $wait
        }
        Write-Host "  Ripresa...                    " -ForegroundColor Green

    } elseif ($exitCode -ne 0) {

        Write-Host "  [X] Errore exit=$exitCode. Attendo $([int]($ErrorWait/60)) min..." -ForegroundColor Red
        $lastLines = ($output -split "`n" | Select-Object -Last 3) -join " | "
        Write-Host "  $lastLines" -ForegroundColor DarkRed

        $logEntry = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [INF #$runCount] ERROR exit=$exitCode task=$($task.id)"
        Add-Content -Path $LogFile -Value $logEntry -Encoding UTF8
        Start-Sleep -Seconds $ErrorWait

    } else {

        Write-Host "  [OK] ${elapsed}s - task $($task.id) completato" -ForegroundColor Green

        # Mostra ultime righe del report
        $reportLines = ($output -split "`n" | Select-Object -Last 6)
        foreach ($line in $reportLines) {
            if ($line.Trim()) { Write-Host "       $line" -ForegroundColor White }
        }

        # Avviso struttura mancante
        if ($valResult -and -not $valResult.ok) {
            Write-Host "  [!] Struttura MkDocs incompleta - verifica:" -ForegroundColor Yellow
            foreach ($m in $valResult.missing) {
                Write-Host "      $m" -ForegroundColor Yellow
            }
        }

        $logEntry = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [INF #$runCount] OK task=$($task.id) path=$($task.path) elapsed=${elapsed}s"
        Add-Content -Path $LogFile -Value $logEntry -Encoding UTF8

        # Countdown con avvisi a 60s e 10s
        $remaining = $RunInterval
        $notified60 = $false
        $notified10 = $false
        Write-Host "  Prossima run tra ${remaining}s..." -ForegroundColor DarkGray
        while ($remaining -gt 0) {
            Start-Sleep -Seconds 1
            $remaining--
            if ($remaining -eq 60 -and -not $notified60) {
                Write-Host "  Prossima run tra 60 secondi..." -ForegroundColor DarkGray
                $notified60 = $true
            }
            if ($remaining -eq 10 -and -not $notified10) {
                Write-Host "  Prossima run tra 10 secondi..." -ForegroundColor DarkGray
                $notified10 = $true
            }
        }
    }
}
