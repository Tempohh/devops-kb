# KB Update - Modalita' Infinita
# Loop continuo. Su rate limit attende il ripristino.
# Ctrl+C per interrompere (stato sempre salvato su disco).
#
# NOTA: da questa revisione la modalita' raccomandata e' la pipeline GitHub Actions
# (.github/workflows/kb-maintenance.yml), che gira "a PC spento" ed esegue una
# iterazione bounded via _automation/run_once.py. Questo script resta valido per
# l'uso locale intensivo su Windows ma NON applica la policy modello di config.yaml.
# Vedi _automation/AUTOMATION.md.

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
        if ($existingProcess -and $existingProcess.ProcessName -match '^(pwsh|powershell)$') {
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

# Trova Python verificando che funzioni davvero (gli alias Store rispondono a Get-Command ma falliscono all'uso)
$pythonBin = $null
foreach ($candidate in @("py", "python", "python3")) {
    $test = & $candidate --version 2>&1
    if ($LASTEXITCODE -eq 0 -and $test -match "Python \d") {
        $pythonBin = $candidate
        break
    }
}
if (-not $pythonBin) {
    Write-Host "  ERRORE: nessun interprete Python funzionante trovato (py/python/python3)." -ForegroundColor Red
    Read-Host "  Premi INVIO per chiudere"; exit 1
}

# check-mkdocs e' costoso (~20s). Eseguilo ogni N run.
$MkdocsCheckInterval = 3
# maintain: rotazione log e pulizia proposte. Eseguilo ogni 30 run (quasi gratuito).
$MaintainInterval = 30

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
    # Run consecutive con proposte pendenti: finestra per decidere a mano prima
    # dell'auto-approvazione. Tutto il resto del lavoro a coda vuota lo decide
    # la cascata `manage-state.py next-work` (vedi AUTOMATION.md).
    $emptyRuns               = 0
    $EmptyBeforeAutoApprove  = 3    # 3 run con proposte pending → auto-approva (~90s finestra utente)
    $idleNotified            = $false # stampa il messaggio IDLE una volta sola per periodo di inattivita'

    function Show-RunHeader {
        # Stampata solo quando c'e' davvero qualcosa da riportare — durante
        # l'attesa silenziosa in IDLE non va chiamata, altrimenti si torna
        # a un "Run #N" vuoto ogni 30s senza nessuna informazione utile.
        Write-Host ""
        Write-Host "  [$(Get-Date -Format 'HH:mm:ss')] Run #$sessionRuns" -ForegroundColor Cyan
    }

    function Invoke-KbCommit {
        # Commit dedicato per scritture di bookkeeping (state.yaml, spostamenti
        # proposals/) che avvengono FUORI dal ciclo normale di un task — es.
        # auto-approve-proposals. Se non le si committa subito qui, restano
        # scoperte nel working tree e finiscono nel PROSSIMO `git add -A` del
        # task successivo, taggate con l'id del task sbagliato (criticita'
        # osservata: commit "(auto #NNN)" il cui diff era solo state.yaml o
        # solo un prop-NNN.yaml spostato, senza alcun contenuto del task NNN).
        param([string]$Message)
        try {
            & git -C $ProjectRoot add -A 2>&1 | Out-Null
            & git -C $ProjectRoot diff --cached --quiet
            if ($LASTEXITCODE -ne 0) {
                & git -C $ProjectRoot commit -q -m $Message -m "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>" 2>&1 | Out-Null
                & git -C $ProjectRoot pull -q --rebase 2>&1 | Out-Null
                if ($LASTEXITCODE -ne 0) {
                    & git -C $ProjectRoot rebase --abort 2>&1 | Out-Null
                    Write-Host "  [GIT] rebase in conflitto - annullato, commit bookkeeping solo locale" -ForegroundColor Yellow
                } else {
                    & git -C $ProjectRoot push -q origin HEAD:master 2>&1 | Out-Null
                }
            }
        } catch {
            Write-Host "  [GIT] errore commit bookkeeping: $($_.Exception.Message)" -ForegroundColor Yellow
        }
    }

    while ($true) {

        $sessionRuns++
        $timestamp = Get-Date -Format "HH:mm:ss"

        # -- Estrai prossimo task --------------------------------------------

        $rawNext  = & $pythonBin $StatePy next-task 2>&1
        # Isola solo la riga JSON valida (gestisce warnings/deprecations su stderr catturate da 2>&1)
        $taskJson = ($rawNext | Out-String).Trim()
        # Se output contiene righe multiple, prendi solo quella che inizia con { o e' "null"
        $lines    = $taskJson -split "`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" }
        $jsonLine = $lines | Where-Object { $_ -eq "null" -or $_ -match '^\{' } | Select-Object -Last 1
        if ($jsonLine) { $taskJson = $jsonLine }

        if ($taskJson -eq "null" -or [string]::IsNullOrWhiteSpace($taskJson)) {

            # ── Coda vuota: cascata next-work (manage-state.py) ───────────
            # Le fonti di lavoro sono misurate in Python (0 token). Qui resta solo
            # la finestra interattiva sulle proposte pendenti; tutto il resto
            # (lifecycle, gate, review, currency, esplorazione per sottocategoria)
            # lo decide next-work. Se non c'e' nulla da fare risponde 'idle' con
            # l'orario in cui qualcosa tornera' disponibile: si dorme fino ad allora.
            $workRaw = & $pythonBin $StatePy next-work --no-approve 2>&1
            $workLine = (($workRaw | Out-String) -split "`n" | ForEach-Object { $_.Trim() } |
                         Where-Object { $_ -match '^\{' } | Select-Object -Last 1)
            try { $work = $workLine | ConvertFrom-Json } catch { $work = $null }

            if (-not $work) {
                Show-RunHeader
                Write-Host "  [!] next-work illeggibile: $workRaw" -ForegroundColor Red
                Add-Content -Path $LogFile -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [ERR] NEXT_WORK_FAIL raw=[$workRaw]" -Encoding UTF8
                $sessionErrors++
                Start-Sleep -Seconds $ErrorWait
                continue
            }

            if ($work.action -eq "proposals_pending") {
                # Finestra utente: EmptyBeforeAutoApprove run prima dell'auto-approvazione
                $emptyRuns++
                $idleNotified = $false
                $runsLeft = $EmptyBeforeAutoApprove - $emptyRuns
                $rawProposals  = & $pythonBin $StatePy list-proposals 2>&1
                $allLines      = ($rawProposals | Out-String) -split "`n"
                $jsonStart     = -1
                for ($i = 0; $i -lt $allLines.Count; $i++) {
                    if ($allLines[$i].Trim() -match '^\{') { $jsonStart = $i; break }
                }
                $proposalsJson = if ($jsonStart -ge 0) { ($allLines[$jsonStart..($allLines.Count-1)] -join "`n").Trim() } else { "" }
                try { $proposalsObj = $proposalsJson | ConvertFrom-Json } catch { $proposalsObj = $null }

                Show-RunHeader
                Write-Host ""
                Write-Host "  ===== $($work.count) PROPOSTE IN ATTESA =====" -ForegroundColor Yellow
                if ($proposalsObj) {
                    foreach ($prop in $proposalsObj.proposals) {
                        Write-Host "  >> $($prop.title)" -ForegroundColor White
                        Write-Host "     $($prop.priority)  $($prop.type)  $($prop.target_file)" -ForegroundColor DarkGray
                    }
                }
                Write-Host ""

                if ($runsLeft -le 0) {
                    Write-Host "  [AUTO-APPROVA] Approvazione automatica in corso..." -ForegroundColor Magenta
                    $autoResult = & $pythonBin $StatePy auto-approve-proposals 2>&1
                    try { $autoObj = $autoResult | ConvertFrom-Json } catch { $autoObj = $null }
                    $approved = if ($autoObj -and $autoObj.approved) { $autoObj.approved } else { 0 }
                    Write-Host "  [AUTO-APPROVA] $approved proposte approvate — task aggiunti alla coda" -ForegroundColor Magenta
                    Add-Content -Path $LogFile -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [INF #$sessionRuns] AUTO_APPROVE count=$approved" -Encoding UTF8
                    Invoke-KbCommit "kb: auto-approve $approved proposte (bookkeeping)"
                    $emptyRuns = 0
                    continue
                }
                Write-Host "  Auto-approvazione tra $runsLeft run (~$($runsLeft * $RunInterval)s) — review-proposals.bat per decidere ora." -ForegroundColor DarkGray
                Start-Sleep -Seconds $RunInterval
                continue
            }

            $emptyRuns = 0

            if ($work.action -eq "injected") {
                $idleNotified = $false
                Show-RunHeader
                $ids = ($work.tasks | ForEach-Object { if ($_.scope) { "$($_.id):$($_.scope)" } else { "$($_.id):$($_.type)" } }) -join " "
                Write-Host "  [CASCATA] $($work.source): $($work.count) task iniettati ($($work.remaining_in_source) restanti nella fonte)" -ForegroundColor Magenta
                Write-Host "            $ids" -ForegroundColor DarkGray
                Add-Content -Path $LogFile -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [INF #$sessionRuns] CASCADE source=$($work.source) count=$($work.count)" -Encoding UTF8
                continue
            }

            if ($work.action -eq "idle") {
                # KB completa per lo scope attuale: nessuna chiamata al modello, nessun
                # commit. Sonno a blocchi da max 10 min (poi si rivaluta: costa ~1s).
                if (-not $idleNotified) {
                    Show-RunHeader
                    Write-Host "  [IDLE] $($work.reason)" -ForegroundColor Green
                    Write-Host "  [IDLE] Prossimo lavoro previsto: $($work.next_check_at) — silenzio fino ad allora" -ForegroundColor DarkGray
                    Add-Content -Path $LogFile -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [INF #$sessionRuns] KB_IDLE next=$($work.next_check_at)" -Encoding UTF8
                    $idleNotified = $true
                }
                Start-Sleep -Seconds ([Math]::Min(600, [Math]::Max(60, [int]$work.wait_seconds)))
                continue
            }

            # queue_not_empty (race con un'altra scrittura): riprova subito
            Start-Sleep -Seconds 5
            continue
        }

        # Task trovato: reset contatore empty
        $emptyRuns = 0
        Show-RunHeader

        try { $task = $taskJson | ConvertFrom-Json }
        catch {
            $preview = ($taskJson | Out-String).Substring(0, [Math]::Min(300, ($taskJson | Out-String).Length)).Trim()
            Write-Host "  [X] Errore parsing task JSON: $preview" -ForegroundColor Red
            Add-Content -Path $LogFile -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [ERR] JSON_PARSE_FAIL raw=[$preview]" -Encoding UTF8
            $sessionErrors++
            & $pythonBin $StatePy force-complete "UNKNOWN" | Out-Null
            Start-Sleep -Seconds $ErrorWait
            continue
        }

        # Scrivi task su file — UTF8NoBOM per evitare BOM che rompe il parser JSON
        [System.IO.File]::WriteAllText($TaskFile, $taskJson, [System.Text.UTF8Encoding]::new($false))

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
            "audit"       { Join-Path $AutoDir "audit-prompt.md" }
            "expand"      { Join-Path $AutoDir "expand-prompt.md" }
            "proposal"    { Join-Path $AutoDir "proposal-prompt.md" }
            "review"      { Join-Path $AutoDir "review-prompt.md" }
            "currency"    { Join-Path $AutoDir "currency-prompt.md" }
            "consolidate" { Join-Path $AutoDir "consolidate-prompt.md" }
            default       { $PromptFile }
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

            # -- Manutenzione periodica (log rotation, proposals cleanup) -----
            if ($sessionRuns % $MaintainInterval -eq 0) {
                $maintainOut = & $pythonBin $StatePy maintain 2>&1
                try {
                    $maintainObj = $maintainOut | ConvertFrom-Json
                    if ($maintainObj.rotated_log -or $maintainObj.proposals_pruned -gt 0) {
                        foreach ($action in $maintainObj.actions) {
                            Write-Host "  [MAINTAIN] $action" -ForegroundColor DarkGray
                        }
                    }
                } catch { }
            }

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

            # -- Commit + push automatico (best-effort, mai bloccante) --------
            # Committa dopo ogni task cosi' il lavoro non resta solo nel working tree.
            # Su conflitto di rebase (es. state.yaml toccato dalla CI) annulla il rebase e
            # lascia il commit locale: si risolve a mano, il loop continua.
            try {
                # proposal vuota = solo churn di state.yaml: niente commit
                if (-not ($task.type -eq "proposal" -and -not $fileWasCreated)) {
                & git -C $ProjectRoot add -A 2>&1 | Out-Null
                & git -C $ProjectRoot diff --cached --quiet
                if ($LASTEXITCODE -ne 0) {
                    $commitMsg = "kb: $($task.type) $($task.path) (auto #$($task.id))"
                    & git -C $ProjectRoot commit -q -m $commitMsg -m "Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>" 2>&1 | Out-Null
                    & git -C $ProjectRoot pull -q --rebase 2>&1 | Out-Null
                    if ($LASTEXITCODE -ne 0) {
                        & git -C $ProjectRoot rebase --abort 2>&1 | Out-Null
                        Write-Host "  [GIT] rebase in conflitto - annullato, commit solo locale" -ForegroundColor Yellow
                        Add-Content -Path $LogFile -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [WRN] GIT_REBASE_CONFLICT task=$($task.id)" -Encoding UTF8
                    } else {
                        & git -C $ProjectRoot push -q origin HEAD:master 2>&1 | Out-Null
                        if ($LASTEXITCODE -eq 0) {
                            Write-Host "  [GIT] commit + push ok" -ForegroundColor DarkGreen
                        } else {
                            Write-Host "  [GIT] push fallito - commit resta locale" -ForegroundColor Yellow
                            Add-Content -Path $LogFile -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [WRN] GIT_PUSH_FAIL task=$($task.id)" -Encoding UTF8
                        }
                    }
                }
                }
            } catch {
                Write-Host "  [GIT] errore: $($_.Exception.Message)" -ForegroundColor Yellow
            }

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
