"""Ristruttura kb-infinite.ps1: sposta il check rate limit PRIMA di force-complete."""
from pathlib import Path

path = Path(__file__).parent / "kb-infinite.ps1"
content = path.read_text(encoding="utf-8")

# Marker di inizio e fine del blocco da sostituire
START = "        $elapsed  = [int]((Get-Date) - $startTime).TotalSeconds"
END   = "        Start-Countdown -Seconds $RunInterval -PendingInfo $pendingCount\n        }"

start_idx = content.find(START)
end_idx   = content.find(END) + len(END)

if start_idx == -1:
    print("START marker not found"); exit(1)
if end_idx < len(END):
    print("END marker not found"); exit(1)

new_block = r"""        $elapsed  = [int]((Get-Date) - $startTime).TotalSeconds

        # -- Aggiorna contatori run (sempre, prima di qualsiasi analisi) ------

        & $pythonBin $StatePy update-run | Out-Null

        # -- Check rate limit PRIMA di force-complete (BUG FIX CRITICO) ------
        # Se rate limit: NON chiamare force-complete. Il task deve restare
        # pending (interrupted_task lo tiene) per essere ritentato dopo recovery.
        # Chiamare force-complete su rate limit marcherebbe il task come skipped
        # e verrebbe perso definitivamente senza essere mai completato.

        $isRateLimited = $rateLimitPatterns | Where-Object { $output -imatch $_ }

        if ($isRateLimited -or $exitCode -eq 529) {

            $sessionErrors++
            Add-Content -Path $LogFile -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [INF #$sessionRuns] RATE_LIMIT task=$($task.id)" -Encoding UTF8

            # Exponential backoff: 5min -> 10min -> 20min -> 30min (max)
            $retryWait = $RateLimitWaitStart
            $attempt   = 0
            $recovered = $false
            while (-not $recovered) {
                $attempt++
                $resumeTime = (Get-Date).AddSeconds($retryWait).ToString("HH:mm")
                Write-Host "  [!] Rate limit. Tentativo $attempt tra $([int]($retryWait/60)) min (~ $resumeTime)" -ForegroundColor Yellow

                $remaining = $retryWait
                while ($remaining -gt 0) {
                    $mins = [int]($remaining / 60)
                    $secs = $remaining % 60
                    Write-Host "  ... ${mins}m ${secs}s al tentativo $attempt   " -ForegroundColor DarkGray -NoNewline
                    Write-Host "`r" -NoNewline
                    Start-Sleep -Seconds 30
                    $remaining -= 30
                }

                Write-Host "  Probe tentativo $attempt...                    " -ForegroundColor DarkGray
                $probeOut  = "" | & $claudeBin --dangerously-skip-permissions -p "OK" 2>&1
                $probeExit = $LASTEXITCODE
                $stillLimited = $rateLimitPatterns | Where-Object { $probeOut -imatch $_ }

                if (-not $stillLimited -and $probeExit -eq 0) {
                    Write-Host "  [+] Token ripristinati al tentativo $attempt." -ForegroundColor Green
                    Add-Content -Path $LogFile -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [INF] RATE_LIMIT_RECOVERED attempt=$attempt" -Encoding UTF8
                    $recovered = $true
                } else {
                    Write-Host "  Ancora limitato. Prossimo tentativo tra $([int]([Math]::Min($retryWait*2,$RateLimitWaitMax)/60)) min." -ForegroundColor DarkGray
                    $retryWait = [Math]::Min($retryWait * 2, $RateLimitWaitMax)
                }
            }

        } elseif ($exitCode -ne 0) {

            & $pythonBin $StatePy force-complete $task.id | Out-Null
            $sessionErrors++
            Write-Host "  [X] Errore exit=$exitCode. Attendo $([int]($ErrorWait/60))min..." -ForegroundColor Red
            ($output -split "`n" | Select-Object -Last 5) | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkRed }
            Add-Content -Path $LogFile -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [INF #$sessionRuns] ERROR exit=$exitCode task=$($task.id)" -Encoding UTF8
            Start-Sleep -Seconds $ErrorWait

        } else {

            # Successo: force-complete normalizza lo stato se l'agente non lo ha aggiornato
            & $pythonBin $StatePy force-complete $task.id | Out-Null

            # -- Token estimation --------------------------------------------
            $promptChars = $prompt.Length
            $outputChars = ($output | Out-String).Length
            $tokenJson   = & $pythonBin $StatePy estimate-tokens $task.path $promptChars $outputChars 2>&1
            try { $tokens = $tokenJson | ConvertFrom-Json } catch { $tokens = $null }
            if ($tokens) { $sessionTokens += $tokens.total_tokens }

            # -- Validazione struttura MkDocs --------------------------------
            $pathsJson = ConvertTo-Json @($task.path) -Compress
            $valJson   = & $pythonBin $StatePy validate-all $pathsJson 2>&1
            try { $valResult = $valJson | ConvertFrom-Json } catch { $valResult = $null }

            # -- Check MkDocs warnings (ogni MkdocsCheckInterval run) -------
            $mkdocsCheck = ""
            if ($sessionRuns % $MkdocsCheckInterval -eq 0) {
                Write-Host "  [MkDocs] Verifica broken links..." -ForegroundColor DarkGray
                $mkdocsCheck = & $pythonBin $StatePy check-mkdocs 2>&1
            }

            # -- Pruning -----------------------------------------------------
            & $pythonBin $StatePy prune | Out-Null

            # -- Dimensione file creato --------------------------------------
            $fileLines = 0
            $fileKb    = 0
            $createdPath = Join-Path $ProjectRoot $task.path
            if (Test-Path $createdPath) {
                $fileLines = (Get-Content $createdPath -Encoding UTF8 | Measure-Object -Line).Lines
                $fileKb    = [Math]::Round((Get-Item $createdPath).Length / 1KB, 1)
            }

            $fileWasCreated = $fileLines -gt 0

            if ($fileWasCreated) {
                $sessionOk++
                Write-Host "  [OK] ${elapsed}s - $($task.id)" -ForegroundColor Green
                Write-Host "  [~] File: $fileLines righe | ${fileKb}KB" -ForegroundColor DarkGreen
            } else {
                $sessionSkipped++
                Write-Host "  [SKIP] ${elapsed}s - $($task.id) (nessun file creato)" -ForegroundColor DarkGray
            }

            if ($tokens) {
                Write-Host "  [~] Token: ~$($tokens.total_tokens) (sessione: ~$sessionTokens)" -ForegroundColor DarkCyan
            }

            # Output claude (ultime 10 righe non vuote)
            $outputLines = ($output -split "`n" | Where-Object { $_.Trim() } | Select-Object -Last 10)
            if ($outputLines) {
                Write-Host "  --- output ---" -ForegroundColor DarkGray
                $outputLines | ForEach-Object { Write-Host "  $_" -ForegroundColor White }
                Write-Host "  --------------" -ForegroundColor DarkGray
            }

            if ($valResult -and -not $valResult.ok) {
                Write-Host "  [!] Struttura MkDocs incompleta:" -ForegroundColor Yellow
                $valResult.missing | ForEach-Object { Write-Host "      - $_" -ForegroundColor Yellow }
            }

            if ($mkdocsCheck -match "aggiunti") {
                Write-Host "  [W] Nuovi P0 dalla build: $mkdocsCheck" -ForegroundColor Yellow
            }

            $pendingCount = ""
            $statsNow = & $pythonBin $StatePy stats 2>&1
            try {
                $sn = $statsNow | ConvertFrom-Json
                $pendingCount = "($($sn.total_pending) task rimasti)"
            } catch {}

            $logVerb    = if ($fileWasCreated) { "CREATED" } else { "SKIP" }
            $tokenCount = if ($tokens) { $tokens.total_tokens } else { 0 }
            Add-Content -Path $LogFile -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [INF #$sessionRuns] $logVerb task=$($task.id) elapsed=${elapsed}s tokens=$tokenCount lines=$fileLines" -Encoding UTF8

            Start-Countdown -Seconds $RunInterval -PendingInfo $pendingCount
        }"""

content = content[:start_idx] + new_block + content[end_idx:]
path.write_text(content, encoding="utf-8")
print(f"OK - {path.name} rewritten ({len(content)} chars)")
