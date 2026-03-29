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
$LockFile     = Join-Path $AutoDir "kb-infinite.lock"

Set-Location $ProjectRoot

# -- Single-instance lock ----------------------------------------------------
# Impedisce il doppio avvio. Se il lock esiste e il processo e' ancora vivo,
# esce con un messaggio chiaro. Se il processo e' morto (crash/spegnimento),
# il lock e' stale: viene sovrascritto silenziosamente.

if (Test-Path $LockFile) {
    $existingPid = Get-Content $LockFile -ErrorAction SilentlyContinue
    if ($existingPid -match '^\d+$') {
        $existingProcess = Get-Process -Id ([int]$existingPid) -ErrorAction SilentlyContinue
        if ($existingProcess) {
            Write-Host ""
            Write-Host "  *** KB Update e' gia' in esecuzione (PID $existingPid) ***" -ForegroundColor Red
            Write-Host "  Chiudi prima quella finestra, poi rilancia questo script." -ForegroundColor Yellow
            Write-Host ""
            Read-Host "  Premi INVIO per chiudere"
            exit 1
        }
        # Processo non trovato = lock stale (crash o spegnimento improvviso)
        Write-Host "  [i] Lock stale trovato (PID $existingPid non attivo) - ripresa normale." -ForegroundColor DarkGray
    }
}

# Scrivi il PID corrente nel lock file
$PID | Out-File -FilePath $LockFile -Encoding ASCII -NoNewline

# -- Configurazione ----------------------------------------------------------

$RunInterval        = 30    # secondi tra run normali (ridotto da 120 → 30)
$RateLimitWaitStart = 300   # primo tentativo dopo 5 min
$RateLimitWaitMax   = 1800  # massimo 30 min tra tentativi
$ErrorWait          = 60    # secondi attesa errore generico (ridotto da 300 → 60)

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

# check-mkdocs e' costoso (~20s). Eseguilo ogni N run.
$MkdocsCheckInterval = 3

# -- UI iniziale -------------------------------------------------------------

Clear-Host
Write-Host ""
Write-Host "  KB Update - Modalita' Infinita" -ForegroundColor Magenta
Write-Host "  Ctrl+C per interrompere (stato sempre salvato)" -ForegroundColor DarkGray
Write-Host "  --------------------------------------------------------" -ForegroundColor DarkGray
Write-Host "  Progetto   : $ProjectRoot" -ForegroundColor DarkGray
Write-Host "  Avvio      : $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor DarkGray
Write-Host "  Intervallo : ${RunInterval}s tra run | backoff ${RateLimitWaitStart}s-${RateLimitWaitMax}s su rate limit" -ForegroundColor DarkGray
Write-Host ""

# -- Stats iniziali da state.yaml --------------------------------------------

$initStats = & $pythonBin $StatePy stats 2>&1
try {
    $initStatsObj = $initStats | ConvertFrom-Json
    Write-Host "  Stato KB   : $($initStatsObj.total_ops) operazioni totali | $($initStatsObj.total_pending) task in coda" -ForegroundColor DarkCyan
    if ($initStatsObj.pending_by_priority.PSObject.Properties.Name.Count -gt 0) {
        $priStr = ($initStatsObj.pending_by_priority.PSObject.Properties | ForEach-Object { "$($_.Name):$($_.Value)" }) -join "  "
        Write-Host "  Priorita'  : $priStr" -ForegroundColor DarkCyan
    }
    if ($initStatsObj.interrupted_task) {
        Write-Host "  RESUME     : task interrotto $($initStatsObj.interrupted_task.id) sara' ripreso (recovery da spegnimento/Ctrl+C)" -ForegroundColor Yellow
    }
} catch {}
Write-Host ""

# -- Contatori sessione ------------------------------------------------------

$sessionRuns        = 0
$sessionTokens      = 0
$sessionOk          = 0
$sessionSkipped     = 0
$sessionErrors      = 0

$rateLimitPatterns  = @("rate.limit","rate limit","overloaded","too many requests","usage limit","quota exceeded","hit your limit","resets \d")

# -- Funzione riepilogo sessione (chiamata su Ctrl+C via finally) -------------

function Show-SessionSummary {
    $elapsed = [int]((Get-Date) - $script:sessionStart).TotalSeconds
    $mins    = [int]($elapsed / 60)
    Write-Host ""
    Write-Host "  ========================================" -ForegroundColor Cyan
    Write-Host "  RIEPILOGO SESSIONE" -ForegroundColor Cyan
    Write-Host "  ========================================" -ForegroundColor Cyan
    Write-Host "  Durata     : ${mins} min (${elapsed}s)" -ForegroundColor White
    Write-Host "  Run totali : $script:sessionRuns" -ForegroundColor White
    Write-Host "  OK         : $script:sessionOk" -ForegroundColor Green
    Write-Host "  Skipped    : $script:sessionSkipped" -ForegroundColor DarkGray
    Write-Host "  Errori     : $script:sessionErrors" -ForegroundColor $(if ($script:sessionErrors -gt 0) {"Red"} else {"DarkGray"})
    Write-Host "  Token ~tot : ~$script:sessionTokens" -ForegroundColor DarkCyan

    # Stato coda finale
    $finalStats = & $pythonBin $StatePy stats 2>&1
    try {
        $fs = $finalStats | ConvertFrom-Json
        Write-Host "  Pending    : $($fs.total_pending) task rimanenti" -ForegroundColor $(if ($fs.total_pending -gt 0) {"Yellow"} else {"Green"})
    } catch {}

    Write-Host "  ========================================" -ForegroundColor Cyan
    Write-Host ""
}

$script:sessionStart = Get-Date

# -- Funzione countdown prossima run -----------------------------------------

function Start-Countdown {
    param([int]$Seconds, [string]$PendingInfo = "")
    Write-Host "  Prossima run tra ${Seconds}s... $PendingInfo" -ForegroundColor DarkGray
    $remaining = $Seconds
    while ($remaining -gt 0) {
        Start-Sleep -Seconds 1
        $remaining--
        if ($remaining -eq 60) {
            Write-Host "  Prossima run tra 60 secondi... $PendingInfo" -ForegroundColor DarkGray
        }
        if ($remaining -eq 10) {
            Write-Host "  Prossima run tra 10 secondi... $PendingInfo" -ForegroundColor DarkGray
        }
    }
}

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

            # Controlla se serve una nuova analisi KB
            $analysisJson = & $pythonBin $StatePy analysis-status 2>&1
            try   { $analysisObj = $analysisJson | ConvertFrom-Json }
            catch { $analysisObj = $null }

            if ($analysisObj -and $analysisObj.needs_analysis) {
                Write-Host "  [ANALISI] $($analysisObj.reason) - avvio scansione KB..." -ForegroundColor Cyan
                $initJson = & $pythonBin $StatePy init-analysis 2>&1
                try { $initObj = $initJson | ConvertFrom-Json } catch { $initObj = $null }
                if ($initObj -and $initObj.status -eq "ok") {
                    Write-Host "  [ANALISI] $($initObj.tasks_created) task creati: $($initObj.audit_tasks) audit + $($initObj.proposal_tasks) proposal su $($initObj.total_kb_files) file" -ForegroundColor Cyan
                    Add-Content -Path $LogFile -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [INF #$sessionRuns] ANALYSIS_INIT tasks=$($initObj.tasks_created) files=$($initObj.total_kb_files)" -Encoding UTF8
                } else {
                    Write-Host "  [!] init-analysis fallito. Output: $initJson" -ForegroundColor Red
                }
                # Rilancia il loop: la coda e' ora popolata con task di analisi
                continue
            }

            # Analisi non necessaria: mostra eventuali proposte pendenti
            $proposalsJson = & $pythonBin $StatePy list-proposals 2>&1
            try { $proposalsObj = $proposalsJson | ConvertFrom-Json } catch { $proposalsObj = $null }

            if ($proposalsObj -and $proposalsObj.count -gt 0) {
                Write-Host ""
                Write-Host "  ===== $($proposalsObj.count) PROPOSTE IN ATTESA DI APPROVAZIONE =====" -ForegroundColor Yellow
                foreach ($prop in $proposalsObj.proposals) {
                    Write-Host "  [$($prop._file)]  $($prop.title)" -ForegroundColor White
                    Write-Host "    File     : $($prop.path)  |  Tipo: $($prop.type)  |  Priorita': $($prop.priority)" -ForegroundColor DarkGray
                    $desc = if ($prop.description) { ($prop.description -split "`n" | Select-Object -First 2) -join " " } else { "" }
                    if ($desc) { Write-Host "    Dettaglio: $desc" -ForegroundColor DarkGray }
                    Write-Host ""
                }
                Write-Host "  Approva : python _automation/manage-state.py approve-proposal <id>" -ForegroundColor DarkGray
                Write-Host "  Rifiuta : python _automation/manage-state.py reject-proposal <id>" -ForegroundColor DarkGray
                Write-Host "  ========================================================" -ForegroundColor Yellow
                Write-Host ""
            }

            Write-Host "  [DONE] Queue vuota - KB aggiornata." -ForegroundColor Green
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

        # Scrivi task su file (evita troncamento da -replace su YAML multiriga)
        $taskJson | Out-File -FilePath $TaskFile -Encoding UTF8 -NoNewline

        Write-Host "  Task : [$($task.priority)] $($task.id) - $($task.path)" -ForegroundColor White

        # -- Pre-flight: controllo esistenza file (dipende dal tipo task) ------
        $taskFilePath = if ($task.path) { Join-Path $ProjectRoot $task.path } else { "" }

        if ($task.type -eq "new_topic" -or -not $task.type) {
            # new_topic: skip se il file esiste gia' (zero token spesi)
            if ($task.path -and (Test-Path $taskFilePath)) {
                Write-Host "  [SKIP] File gia' presente su disco - zero token spesi" -ForegroundColor DarkGray
                & $pythonBin $StatePy force-complete $task.id | Out-Null
                $sessionSkipped++
                Add-Content -Path $LogFile -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [INF #$sessionRuns] PRE_SKIP task=$($task.id) path=$($task.path)" -Encoding UTF8
                continue
            }
        } elseif ($task.type -in @("audit", "expand")) {
            # audit/expand: skip se il file NON esiste (niente da auditare/espandere)
            if ($task.path -and -not (Test-Path $taskFilePath)) {
                Write-Host "  [SKIP] File non trovato - task $($task.type) non applicabile" -ForegroundColor DarkGray
                & $pythonBin $StatePy force-complete $task.id | Out-Null
                $sessionSkipped++
                Add-Content -Path $LogFile -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [INF #$sessionRuns] PRE_SKIP_MISSING task=$($task.id) type=$($task.type)" -Encoding UTF8
                continue
            }
        }
        # proposal: nessun pre-flight (la directory _automation/proposals esiste ma non e' un file di contenuto)

        # -- Pre-flight qualita' per audit (0 token) --------------------------
        # Prima di chiamare claude, valuta il file localmente.
        # Se supera gia' tutti i criteri -> completato senza spendere token.
        if ($task.type -eq "audit" -and $task.path) {
            $pfJson = & $pythonBin $StatePy audit-preflight $task.path 2>&1
            try { $pfObj = $pfJson | ConvertFrom-Json } catch { $pfObj = $null }
            if ($pfObj -and $pfObj.pass) {
                Write-Host "  [AUDIT-OK] Qualita' sufficiente - 0 token spesi" -ForegroundColor DarkGreen
                & $pythonBin $StatePy force-complete $task.id | Out-Null
                $sessionSkipped++
                Add-Content -Path $LogFile -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [INF #$sessionRuns] AUDIT_PASS task=$($task.id) lines=$($pfObj.lines) blocks=$($pfObj.code_blocks)" -Encoding UTF8
                continue
            }
            if ($pfObj -and $pfObj.issues) {
                Write-Host "  [AUDIT] Issues: $($pfObj.issues -join ' | ')" -ForegroundColor Yellow
            }
        }

        # Checkpoint
        & $pythonBin $StatePy mark-started $task.id | Out-Null

        # -- Esegui ----------------------------------------------------------

        # Selezione prompt in base al tipo di task
        $activePromptFile = switch ($task.type) {
            "audit"    { Join-Path $AutoDir "audit-prompt.md" }
            "expand"   { Join-Path $AutoDir "expand-prompt.md" }
            "proposal" { Join-Path $AutoDir "proposal-prompt.md" }
            default    { $PromptFile }
        }
        if (-not (Test-Path $activePromptFile)) { $activePromptFile = $PromptFile }
        Write-Host "  Prompt   : $(Split-Path $activePromptFile -Leaf)" -ForegroundColor DarkGray

        $prompt    = Get-Content $activePromptFile -Raw -Encoding UTF8
        $startTime = Get-Date

        # Pipe stringa vuota come stdin per evitare il warning "no stdin data received"
        $output   = "" | & $claudeBin --dangerously-skip-permissions -p $prompt 2>&1
        $exitCode = $LASTEXITCODE

        $elapsed  = [int]((Get-Date) - $startTime).TotalSeconds

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

            # -- Verifica risultato (dipende dal tipo task) -------------------
            $fileLines = 0
            $fileKb    = 0
            $fileWasCreated = $false

            if ($task.type -eq "proposal") {
                # proposal: successo se esistono file .yaml in proposals/pending/
                $pendingPropDir = Join-Path $AutoDir "proposals\pending"
                $propFiles = if (Test-Path $pendingPropDir) { (Get-ChildItem $pendingPropDir -Filter "*.yaml").Count } else { 0 }
                $fileWasCreated = $propFiles -gt 0
                $fileLines = $propFiles   # riuso campo come contatore proposte
                if ($propFiles -gt 0) {
                    Write-Host "  [PROP] $propFiles nuove proposte generate - in attesa di approvazione" -ForegroundColor Yellow
                }
            } else {
                # new_topic / audit / expand: conta righe del file target
                $createdPath = Join-Path $ProjectRoot $task.path
                if (Test-Path $createdPath) {
                    $fileLines = (Get-Content $createdPath -Encoding UTF8 | Measure-Object -Line).Lines
                    $fileKb    = [Math]::Round((Get-Item $createdPath).Length / 1KB, 1)
                }
                if ($task.type -in @("audit", "expand")) {
                    $fileWasCreated = $true  # il file esiste per definizione (pre-flight lo ha verificato)
                } else {
                    $fileWasCreated = $fileLines -gt 0
                }
            }

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
        }
    }

} finally {
    # Eseguito sempre su Ctrl+C, chiusura finestra, o termine normale

    # Rimuovi il lock file (libera il lock per la prossima istanza)
    if (Test-Path $LockFile) {
        $lockPid = Get-Content $LockFile -ErrorAction SilentlyContinue
        if ($lockPid -eq $PID) {
            Remove-Item $LockFile -Force -ErrorAction SilentlyContinue
        }
    }

    Show-SessionSummary
}
