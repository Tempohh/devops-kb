# KB Update - Modalita' Infinita
# Loop continuo. Su rate limit attende il ripristino.
# Ctrl+C per interrompere (stato sempre salvato su disco).

$Host.UI.RawUI.WindowTitle = "KB Update - Infinito"

$ProjectRoot  = Split-Path -Parent $PSScriptRoot
$AutoDir      = $PSScriptRoot
$PromptFile   = Join-Path $AutoDir "run-prompt.md"
$TaskFile     = Join-Path $AutoDir "current-task.json"
$LogFile      = Join-Path $AutoDir "runs.log"
$StatePy      = Join-Path $AutoDir "manage-state.py"

Set-Location $ProjectRoot

# -- Configurazione ----------------------------------------------------------

$RunInterval   = 120   # secondi tra run normali
$RateLimitWait = 5400  # secondi attesa rate limit (90 min)
$ErrorWait     = 300   # secondi attesa errore generico

# -- Rilevamento claude.exe --------------------------------------------------

$claudeBin = "claude"
if (-not (Get-Command "claude" -ErrorAction SilentlyContinue)) {
    $found = Get-ChildItem "$env:USERPROFILE\.vscode\extensions\anthropic.claude-code-*\resources\native-binary\claude.exe" -ErrorAction SilentlyContinue |
             Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
    if ($found) { $claudeBin = $found }
    else {
        Write-Host "  ERRORE: claude.exe non trovato." -ForegroundColor Red
        Read-Host "  Premi INVIO per chiudere"; exit 1
    }
}

$pythonBin = if (Get-Command "python3" -ErrorAction SilentlyContinue) { "python3" } else { "python" }

# check-mkdocs e' costoso (~20s). Eseguilo ogni N run, non ogni run.
$MkdocsCheckInterval = 3

# -- UI iniziale -------------------------------------------------------------

Clear-Host
Write-Host ""
Write-Host "  KB Update - Modalita' Infinita" -ForegroundColor Magenta
Write-Host "  Ctrl+C per interrompere (stato sempre salvato)" -ForegroundColor DarkGray
Write-Host "  --------------------------------------------------------" -ForegroundColor DarkGray
Write-Host "  Progetto   : $ProjectRoot" -ForegroundColor DarkGray
Write-Host "  Avvio      : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor DarkGray
Write-Host "  Intervallo : ${RunInterval}s tra run | ${RateLimitWait}s su rate limit" -ForegroundColor DarkGray
Write-Host ""

# -- Contatori sessione ------------------------------------------------------

$sessionRuns        = 0
$sessionTokens      = 0
$sessionOk          = 0
$sessionSkipped     = 0
$sessionErrors      = 0

$rateLimitPatterns  = @("rate.limit","rate limit","overloaded","too many requests","usage limit","quota exceeded","529")

# -- Funzione riepilogo sessione (chiamata su Ctrl+C via finally) -------------

function Show-SessionSummary {
    $elapsed = [int]((Get-Date) - $script:sessionStart).TotalSeconds
    $mins    = [int]($elapsed / 60)
    Write-Host ""
    Write-Host "  ========================================" -ForegroundColor Cyan
    Write-Host "  RIEPILOGO SESSIONE" -ForegroundColor Cyan
    Write-Host "  ========================================" -ForegroundColor Cyan
    Write-Host "  Durata     : ${mins} minuti (${elapsed}s)" -ForegroundColor White
    Write-Host "  Run totali : $script:sessionRuns" -ForegroundColor White
    Write-Host "  OK         : $script:sessionOk" -ForegroundColor Green
    Write-Host "  Skipped    : $script:sessionSkipped" -ForegroundColor DarkGray
    Write-Host "  Errori     : $script:sessionErrors" -ForegroundColor $(if ($script:sessionErrors -gt 0) {"Red"} else {"DarkGray"})
    Write-Host "  Token ~tot : $script:sessionTokens" -ForegroundColor DarkCyan
    Write-Host "  ========================================" -ForegroundColor Cyan
    Write-Host ""
}

$script:sessionStart = Get-Date

# -- Loop principale ---------------------------------------------------------

try {
    while ($true) {

        $sessionRuns++
        $timestamp = Get-Date -Format "HH:mm:ss"
        Write-Host ""
        Write-Host "  [$timestamp] Run #$sessionRuns" -ForegroundColor Cyan

        # -- Estrai e scrivi task --------------------------------------------

        $taskJson = & $pythonBin $StatePy next-task 2>&1

        if ($taskJson -eq "null" -or [string]::IsNullOrWhiteSpace($taskJson)) {
            Write-Host "  [DONE] Queue vuota." -ForegroundColor Green
            Add-Content -Path $LogFile -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [INF #$sessionRuns] QUEUE_EMPTY" -Encoding UTF8
            Write-Host "  Attendo ${RunInterval}s prima di ricontrollare..." -ForegroundColor DarkGray
            Start-Sleep -Seconds $RunInterval
            continue
        }

        try { $task = $taskJson | ConvertFrom-Json }
        catch {
            Write-Host "  [X] Errore parsing task JSON" -ForegroundColor Red
            $sessionErrors++
            Start-Sleep -Seconds $ErrorWait
            continue
        }

        # Scrivi task su file (evita troncamento da -replace)
        $taskJson | Out-File -FilePath $TaskFile -Encoding UTF8 -NoNewline

        Write-Host "  Task : [$($task.priority)] $($task.id) - $($task.path)" -ForegroundColor White

        # -- Pre-flight: il file esiste gia'? Skip senza chiamare claude -----
        if ($task.path -and (Test-Path (Join-Path $ProjectRoot $task.path))) {
            Write-Host "  [SKIP] File gia' presente su disco — zero token spesi" -ForegroundColor DarkGray
            & $pythonBin $StatePy force-complete $task.id | Out-Null
            $sessionSkipped++
            Add-Content -Path $LogFile -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [INF #$sessionRuns] PRE_SKIP task=$($task.id) path=$($task.path)" -Encoding UTF8
            continue
        }

        # Checkpoint
        & $pythonBin $StatePy mark-started $task.id | Out-Null

        # -- Esegui ----------------------------------------------------------

        $prompt    = Get-Content $PromptFile -Raw -Encoding UTF8
        $startTime = Get-Date
        # Redirect stdin da NUL evita il 3s warning "no stdin data received"
        $output    = & $claudeBin --dangerously-skip-permissions -p $prompt 2>&1 < /dev/null
        $exitCode  = $LASTEXITCODE
        $elapsed   = [int]((Get-Date) - $startTime).TotalSeconds

        # -- Fallback force-complete -----------------------------------------

        & $pythonBin $StatePy force-complete $task.id | Out-Null

        # -- Token estimation ------------------------------------------------

        $promptChars = $prompt.Length
        $outputChars = ($output | Out-String).Length
        $tokenJson   = & $pythonBin $StatePy estimate-tokens $task.path $promptChars $outputChars 2>&1
        try { $tokens = $tokenJson | ConvertFrom-Json } catch { $tokens = $null }
        if ($tokens) { $sessionTokens += $tokens.total_tokens }

        # -- Validazione struttura -------------------------------------------

        $pathsJson = ConvertTo-Json @($task.path) -Compress
        $valJson   = & $pythonBin $StatePy validate-all $pathsJson 2>&1
        try { $valResult = $valJson | ConvertFrom-Json } catch { $valResult = $null }

        # -- Check MkDocs warnings (ogni MkdocsCheckInterval run) -----------

        if ($sessionRuns % $MkdocsCheckInterval -eq 0) {
            $mkdocsCheck = & $pythonBin $StatePy check-mkdocs 2>&1
        } else {
            $mkdocsCheck = ""
        }

        # -- Pruning ---------------------------------------------------------

        & $pythonBin $StatePy prune | Out-Null

        # -- Analisi esito ---------------------------------------------------

        $isRateLimited = $rateLimitPatterns | Where-Object { $output -imatch $_ }

        if ($isRateLimited -or $exitCode -eq 529) {

            $sessionErrors++
            $resumeTime = (Get-Date).AddSeconds($RateLimitWait).ToString("HH:mm")
            Write-Host "  [!] Token esauriti. Ripresa ~ $resumeTime" -ForegroundColor Yellow
            Add-Content -Path $LogFile -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [INF #$sessionRuns] RATE_LIMIT task=$($task.id) wait=${RateLimitWait}s" -Encoding UTF8

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

            $sessionErrors++
            Write-Host "  [X] Errore exit=$exitCode. Attendo $([int]($ErrorWait/60))min..." -ForegroundColor Red
            ($output -split "`n" | Select-Object -Last 3) | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkRed }
            Add-Content -Path $LogFile -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [INF #$sessionRuns] ERROR exit=$exitCode task=$($task.id)" -Encoding UTF8
            Start-Sleep -Seconds $ErrorWait

        } else {

            $sessionOk++
            Write-Host "  [OK] ${elapsed}s - $($task.id)" -ForegroundColor Green

            if ($tokens) {
                Write-Host "  [~] Token: ~$($tokens.total_tokens) (tot sessione: ~$sessionTokens)" -ForegroundColor DarkCyan
            }

            ($output -split "`n" | Select-Object -Last 6) | ForEach-Object {
                if ($_.Trim()) { Write-Host "       $_" -ForegroundColor White }
            }

            if ($valResult -and -not $valResult.ok) {
                Write-Host "  [!] Struttura MkDocs incompleta:" -ForegroundColor Yellow
                $valResult.missing | ForEach-Object { Write-Host "      $_" -ForegroundColor Yellow }
            }

            if ($mkdocsCheck -match "aggiunti") {
                Write-Host "  [W] Nuovi P0 dalla build: $mkdocsCheck" -ForegroundColor Yellow
            }

            Add-Content -Path $LogFile -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [INF #$sessionRuns] OK task=$($task.id) elapsed=${elapsed}s tokens=$($tokens.total_tokens)" -Encoding UTF8

            # -- Countdown prossima run --------------------------------------
            $remaining2  = $RunInterval
            $notified60  = $false
            $notified10  = $false
            Write-Host "  Prossima run tra ${remaining2}s..." -ForegroundColor DarkGray
            while ($remaining2 -gt 0) {
                Start-Sleep -Seconds 1
                $remaining2--
                if ($remaining2 -eq 60 -and -not $notified60) {
                    Write-Host "  Prossima run tra 60 secondi..." -ForegroundColor DarkGray
                    $notified60 = $true
                }
                if ($remaining2 -eq 10 -and -not $notified10) {
                    Write-Host "  Prossima run tra 10 secondi..." -ForegroundColor DarkGray
                    $notified10 = $true
                }
            }
        }
    }

} finally {
    # Eseguito sempre su Ctrl+C o chiusura finestra
    Show-SessionSummary
}
