# KB Update - Modalita' Sicura
# Esegue UN singolo task dalla queue, poi si ferma.

$Host.UI.RawUI.WindowTitle = "KB Update - Sicuro"

$ProjectRoot  = Split-Path -Parent $PSScriptRoot
$AutoDir      = $PSScriptRoot
$PromptFile   = Join-Path $AutoDir "run-prompt.md"
$TaskFile     = Join-Path $AutoDir "current-task.json"
$LogFile      = Join-Path $AutoDir "runs.log"
$StatePy      = Join-Path $AutoDir "manage-state.py"

Set-Location $ProjectRoot

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

# -- UI ----------------------------------------------------------------------

Clear-Host
Write-Host ""
Write-Host "  KB Update - Modalita' Sicura" -ForegroundColor Cyan
Write-Host "  1 task dalla queue, poi stop automatico" -ForegroundColor DarkGray
Write-Host "  ----------------------------------------" -ForegroundColor DarkGray
Write-Host ""

# -- Estrai e scrivi task ----------------------------------------------------

$taskJson = & $pythonBin $StatePy next-task 2>&1

if ($taskJson -eq "null" -or [string]::IsNullOrWhiteSpace($taskJson)) {
    Write-Host "  [OK] Queue vuota - nessun lavoro da fare." -ForegroundColor Green
    Add-Content -Path $LogFile -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [SAFE] QUEUE_EMPTY" -Encoding UTF8
    Write-Host ""; Read-Host "  Premi INVIO per chiudere"; exit 0
}

try { $task = $taskJson | ConvertFrom-Json }
catch {
    Write-Host "  ERRORE parsing task JSON: $taskJson" -ForegroundColor Red
    Read-Host "  Premi INVIO per chiudere"; exit 1
}

# Scrivi il task in un file separato (evita troncamento da -replace su stringhe lunghe)
$taskJson | Out-File -FilePath $TaskFile -Encoding UTF8 -NoNewline

Write-Host "  Task   : [$($task.priority)] $($task.id) - $($task.path)" -ForegroundColor White
Write-Host "  Avvio  : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor DarkGray
Write-Host ""

# -- Pre-flight: il file esiste gia'? Skip senza chiamare claude -------------
if ($task.path -and (Test-Path (Join-Path $ProjectRoot $task.path))) {
    Write-Host "  [SKIP] File gia' presente su disco — zero token spesi." -ForegroundColor DarkGray
    & $pythonBin $StatePy force-complete $task.id | Out-Null
    Add-Content -Path $LogFile -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [SAFE] PRE_SKIP task=$($task.id)" -Encoding UTF8
    Write-Host ""; Read-Host "  Premi INVIO per chiudere"; exit 0
}

# Checkpoint prima di chiamare claude
& $pythonBin $StatePy mark-started $task.id | Out-Null

# -- Esecuzione --------------------------------------------------------------

$prompt    = Get-Content $PromptFile -Raw -Encoding UTF8
$startTime = Get-Date

Write-Host "  Elaborazione..." -ForegroundColor Yellow
$output    = & $claudeBin --dangerously-skip-permissions -p $prompt 2>&1 < /dev/null
$exitCode  = $LASTEXITCODE
$elapsed   = [int]((Get-Date) - $startTime).TotalSeconds

# -- Fallback: forza completamento se agente non ha aggiornato state ---------

& $pythonBin $StatePy force-complete $task.id | Out-Null

# -- Token estimation --------------------------------------------------------

$promptChars = $prompt.Length
$outputChars = ($output | Out-String).Length
$tokenJson   = & $pythonBin $StatePy estimate-tokens $task.path $promptChars $outputChars 2>&1
try { $tokens = $tokenJson | ConvertFrom-Json } catch { $tokens = $null }

# -- Validazione struttura directory -----------------------------------------

$pathsJson = ConvertTo-Json @($task.path) -Compress
$valJson   = & $pythonBin $StatePy validate-all $pathsJson 2>&1
try { $valResult = $valJson | ConvertFrom-Json } catch { $valResult = $null }

# -- Check MkDocs warnings ---------------------------------------------------

Write-Host "  Verifica broken links MkDocs..." -ForegroundColor DarkGray
$mkdocsCheck = & $pythonBin $StatePy check-mkdocs 2>&1

# -- Pruning -----------------------------------------------------------------

& $pythonBin $StatePy prune | Out-Null

# -- Output ------------------------------------------------------------------

$rateLimitPatterns = @("rate.limit","rate limit","overloaded","too many requests","usage limit","quota exceeded","529")
$isRateLimited = $rateLimitPatterns | Where-Object { $output -imatch $_ }

Write-Host ""
Write-Host "  ----------------------------------------" -ForegroundColor DarkGray

if ($isRateLimited) {
    Write-Host "  [!] Token esauriti. Riprova tra ~5h." -ForegroundColor Yellow
    Add-Content -Path $LogFile -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [SAFE] RATE_LIMIT task=$($task.id)" -Encoding UTF8
} elseif ($exitCode -ne 0) {
    Write-Host "  [X] Errore exit=$exitCode" -ForegroundColor Red
    ($output -split "`n" | Select-Object -Last 4) | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkRed }
    Add-Content -Path $LogFile -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [SAFE] ERROR exit=$exitCode task=$($task.id)" -Encoding UTF8
} else {
    Write-Host ""
    Write-Host "  [OK] Completato in ${elapsed}s" -ForegroundColor Green

    if ($tokens) {
        Write-Host "  [~] Token stimati: input=$($tokens.input_tokens) output=$($tokens.output_tokens) tot=$($tokens.total_tokens)" -ForegroundColor DarkCyan
    }

    ($output -split "`n" | Select-Object -Last 8) | ForEach-Object {
        if ($_.Trim()) { Write-Host "  $_" -ForegroundColor White }
    }

    if ($valResult -and -not $valResult.ok) {
        Write-Host ""
        Write-Host "  [!] Struttura MkDocs incompleta:" -ForegroundColor Yellow
        $valResult.missing | ForEach-Object { Write-Host "      $_" -ForegroundColor Yellow }
    }

    if ($mkdocsCheck -match "aggiunti") {
        Write-Host "  [W] $mkdocsCheck" -ForegroundColor Yellow
    }

    Add-Content -Path $LogFile -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [SAFE] OK task=$($task.id) elapsed=${elapsed}s tokens=$($tokens.total_tokens)" -Encoding UTF8
}

Write-Host ""
Write-Host "  Log: _automation/runs.log" -ForegroundColor DarkGray
Write-Host ""
Read-Host "  Premi INVIO per chiudere"
