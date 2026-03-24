# KB Update - Modalita' Sicura
# Esegue UN singolo task dalla queue, poi si ferma.
# Lascia margine di token per uso personale di Claude.

$Host.UI.RawUI.WindowTitle = "KB Update - Sicuro"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$AutoDir     = $PSScriptRoot
$PromptFile  = Join-Path $AutoDir "run-prompt.md"
$StateFile   = Join-Path $AutoDir "state.yaml"
$LogFile     = Join-Path $AutoDir "runs.log"
$StatePy     = Join-Path $AutoDir "manage-state.py"

Set-Location $ProjectRoot

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

# -- UI ----------------------------------------------------------------------

Clear-Host
Write-Host ""
Write-Host "  KB Update - Modalita' Sicura" -ForegroundColor Cyan
Write-Host "  1 task dalla queue, poi stop automatico" -ForegroundColor DarkGray
Write-Host "  ----------------------------------------" -ForegroundColor DarkGray
Write-Host ""

# -- Estrai prossimo task ----------------------------------------------------

Write-Host "  Lettura queue..." -ForegroundColor Yellow
$taskJson = & $pythonBin $StatePy next-task 2>&1

if ($taskJson -eq "null" -or [string]::IsNullOrWhiteSpace($taskJson)) {
    Write-Host ""
    Write-Host "  [OK] Queue vuota - nessun lavoro da fare." -ForegroundColor Green
    Write-Host "  Tutti i task sono stati completati." -ForegroundColor DarkGray
    $logEntry = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [SAFE] QUEUE_EMPTY"
    Add-Content -Path $LogFile -Value $logEntry -Encoding UTF8
    Write-Host ""
    Read-Host "  Premi INVIO per chiudere"
    exit 0
}

# Parse task JSON
try {
    $task = $taskJson | ConvertFrom-Json
} catch {
    Write-Host "  ERRORE: impossibile parsare il task JSON." -ForegroundColor Red
    Write-Host "  Output: $taskJson" -ForegroundColor DarkRed
    Read-Host "  Premi INVIO per chiudere"
    exit 1
}

Write-Host "  Task      : [$($task.priority)] $($task.id) - $($task.path)" -ForegroundColor White
Write-Host "  Tipo      : $($task.type)" -ForegroundColor DarkGray
Write-Host "  Avvio     : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor DarkGray
Write-Host ""

# Imposta checkpoint PRIMA di chiamare claude
& $pythonBin $StatePy mark-started $task.id | Out-Null

# -- Costruisci prompt -------------------------------------------------------

$promptTemplate = Get-Content $PromptFile -Raw -Encoding UTF8
$prompt = $promptTemplate -replace "\{\{TASK_JSON\}\}", $taskJson

# -- Esecuzione --------------------------------------------------------------

Write-Host "  Elaborazione in corso..." -ForegroundColor Yellow
Write-Host "  (Ctrl+C per interrompere - checkpoint salvato)" -ForegroundColor DarkGray
Write-Host ""

$startTime = Get-Date
$output = & $claudeBin --dangerously-skip-permissions -p $prompt 2>&1
$exitCode = $LASTEXITCODE
$elapsed  = [int]((Get-Date) - $startTime).TotalSeconds

# -- Validazione struttura directory -----------------------------------------

$pathsToCheck = ConvertTo-Json @($task.path) -Compress
$validation   = & $pythonBin $StatePy validate-all $pathsToCheck 2>&1
try {
    $valResult = $validation | ConvertFrom-Json
} catch {
    $valResult = $null
}

# -- Pruning state -----------------------------------------------------------

& $pythonBin $StatePy prune | Out-Null

# -- Analisi esito -----------------------------------------------------------

$rateLimitPatterns = @("rate.limit","rate limit","overloaded","too many requests","usage limit","quota exceeded","529")
$isRateLimited = $rateLimitPatterns | Where-Object { $output -imatch $_ }

Write-Host ""
Write-Host "  ----------------------------------------" -ForegroundColor DarkGray
Write-Host ""

if ($isRateLimited) {
    Write-Host "  [!] Token esauriti. Riprova piu' tardi (~5h per ripristino Pro)." -ForegroundColor Yellow
    $logEntry = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [SAFE] RATE_LIMIT task=$($task.id)"
} elseif ($exitCode -ne 0) {
    Write-Host "  [X] Errore (exit: $exitCode)" -ForegroundColor Red
    $lastLines = ($output -split "`n" | Select-Object -Last 5) -join " | "
    Write-Host "  $lastLines" -ForegroundColor DarkRed
    $logEntry = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [SAFE] ERROR exit=$exitCode task=$($task.id)"
} else {
    Write-Host "  [OK] Completato in ${elapsed}s" -ForegroundColor Green
    Write-Host ""
    # Mostra le ultime righe del report
    $reportLines = ($output -split "`n" | Select-Object -Last 10)
    foreach ($line in $reportLines) {
        if ($line.Trim()) { Write-Host "  $line" -ForegroundColor White }
    }

    # Avviso struttura mancante
    if ($valResult -and -not $valResult.ok) {
        Write-Host ""
        Write-Host "  [!] ATTENZIONE: struttura MkDocs incompleta:" -ForegroundColor Yellow
        foreach ($m in $valResult.missing) {
            Write-Host "      Mancante: $m" -ForegroundColor Yellow
        }
        Write-Host "  Correggere prima della prossima run per evitare regressioni." -ForegroundColor Yellow
    }

    $logEntry = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [SAFE] OK task=$($task.id) path=$($task.path) elapsed=${elapsed}s"
}

Add-Content -Path $LogFile -Value $logEntry -Encoding UTF8

Write-Host ""
Write-Host "  Log: _automation/runs.log" -ForegroundColor DarkGray
Write-Host ""
Read-Host "  Premi INVIO per chiudere"
