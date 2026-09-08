# KB Update - Modalita' Sicura
# Wrapper sottile attorno a run_once.py: processa 1 task dalla queue, poi si ferma.
# La logica (selezione modello per tipo, pre-flight, rate-limit, commit) vive in run_once.py,
# condivisa con la pipeline GitHub Actions.

$Host.UI.RawUI.WindowTitle = "KB Update - Sicuro"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$RunOnce     = Join-Path $PSScriptRoot "run_once.py"
Set-Location $ProjectRoot

# -- Rilevamento Python funzionante (gli alias Store rispondono a Get-Command ma falliscono all'uso) --
$pythonBin = $null
foreach ($candidate in @("py", "python", "python3")) {
    $test = & $candidate --version 2>&1
    if ($LASTEXITCODE -eq 0 -and $test -match "Python \d") { $pythonBin = $candidate; break }
}
if (-not $pythonBin) {
    Write-Host "  ERRORE: nessun interprete Python funzionante trovato (py/python/python3)." -ForegroundColor Red
    Read-Host "  Premi INVIO per chiudere"; exit 1
}

Clear-Host
Write-Host ""
Write-Host "  KB Update - Modalita' Sicura" -ForegroundColor Cyan
Write-Host "  1 task dalla queue, poi stop. Logica condivisa con la CI (run_once.py)." -ForegroundColor DarkGray
Write-Host "  ----------------------------------------" -ForegroundColor DarkGray
Write-Host ""

& $pythonBin $RunOnce --max-tasks 1 @args
$code = $LASTEXITCODE

Write-Host ""
Write-Host "  Log: _automation/runs.log" -ForegroundColor DarkGray
Write-Host ""
Read-Host "  Premi INVIO per chiudere"
exit $code
