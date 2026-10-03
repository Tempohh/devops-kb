# Sistema di automazione KB

Documento autoritativo sul layer di automazione. `CLAUDE.md` (root) descrive i
protocolli *di contenuto*; questo file descrive *come la KB si mantiene da sola*.

---

## 1. Modelli di esecuzione

| Modo | Come si avvia | Quando usarlo |
|---|---|---|
| **CI su dispatch** (raccomandato) | `.github/workflows/kb-maintenance.yml` — trigger **solo `workflow_dispatch`**; lo scheduling **00/06/12/18 ora di Roma** e' delegato a uno scheduler ESTERNO (cron-job.org) che chiama l'endpoint REST `dispatches`. Anche *Actions → Run workflow* a mano. | Manutenzione continua "a PC spento". Nessuna dipendenza dalla macchina locale. |
| **Locale — 1 task** | doppio click su `KB_Aggiorna_Sicuro.bat` (→ `kb-safe.ps1` → `run_once.py --max-tasks 1`) | Eseguire un singolo task al volo su Windows, con la stessa logica della CI. |
| **Locale — loop infinito** | `KB_Aggiorna_Infinito.bat` (→ `kb-infinite.ps1`) | Sessioni intensive locali. **Non** applica la policy modello di `config.yaml`. Legacy. |

Deploy del sito: **solo** `.github/workflows/deploy.yml` (build + `mkdocs gh-deploy`),
che parte a ogni push su `master` che tocca `docs/`, `mkdocs.yml`, `requirements.txt`.
`kb-maintenance.yml` si limita a `git push`: non chiama piu' `mkdocs gh-deploy` da solo
(faceva doppio deploy per ogni task che toccava `docs/`, uno manuale e uno via trigger —
criticita' registrata in CLAUDE.md). `deploy-pages` ha `cancel-in-progress: true`: push
ravvicinati (es. `kb-infinite.ps1`, che pusha dopo ogni task) cancellano le build
intermedie in coda e restano solo l'ultima.

> **Perche' uno scheduler esterno e non `schedule:` nel workflow?** Il cron di
> GitHub Actions sui runner condivisi parte con 30 min – 4 h di ritardo (o viene
> droppato) nelle fasce di carico. Con il vecchio gate a finestra di 1 h **ogni
> run schedulato finiva scartato** (`ora di Roma fuori da 00/06/12/18`): da quando
> lo schedule fu ancorato, zero iterazioni reali. cron-job.org (timezone
> `Europe/Rome`, gestisce da se' CEST/CET) chiama l'API al minuto giusto.

---

## 2. Attivare la CI di manutenzione (una tantum)

`kb-maintenance.yml` si **salta in modo pulito** finché non esiste il secret.

1. In locale: `claude setup-token` → copia il token OAuth.
2. GitHub → repo **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `CLAUDE_CODE_OAUTH_TOKEN`
   - Value: il token
3. (Opzionale) *Actions → KB maintenance → Run workflow* per un giro immediato.

Il token resta sui limiti del piano Claude esistente: su rate limit il run
termina "soft" (exit 0, task ancora `pending`) e il dispatch successivo riprende.
`state.yaml` rende ogni run ripartibile.

### Scheduler esterno (cron-job.org) — setup una tantum

Serve un servizio puntuale che chiami l'endpoint `dispatches` di GitHub alle
00/06/12/18 ora di Roma. Passi (repo `Tempohh/devops-kb`):

1. **Fine-grained PAT** — GitHub → *Settings → Developer settings → Personal
   access tokens → Fine-grained tokens → Generate new token*
   - *Resource owner*: `Tempohh` · *Repository access*: **Only select repositories → `devops-kb`**
   - *Permissions → Repository → Actions*: **Read and write** (unico permesso necessario)
   - *Expiration*: max consentito; **promemoria in calendario per la rotazione**
2. **Verifica il token** (una riga, sostituisci `$PAT`):
   ```bash
   curl -sS -X POST \
     -H "Authorization: Bearer $PAT" \
     -H "Accept: application/vnd.github+json" \
     -H "X-GitHub-Api-Version: 2022-11-28" \
     https://api.github.com/repos/Tempohh/devops-kb/actions/workflows/kb-maintenance.yml/dispatches \
     -d '{"ref":"master","inputs":{"max_tasks":"1"}}' -w '%{http_code}\n'
   ```
   Atteso: **`204`** e un nuovo run *workflow_dispatch* in *Actions*.
3. **cron-job.org** (account gratuito) → *Create cronjob*:
   - *URL*: `https://api.github.com/repos/Tempohh/devops-kb/actions/workflows/kb-maintenance.yml/dispatches`
   - *Request method*: **POST**
   - *Headers*:
     - `Authorization: Bearer <PAT>`
     - `Accept: application/vnd.github+json`
     - `X-GitHub-Api-Version: 2022-11-28`
   - *Request body*: `{"ref":"master","inputs":{"max_tasks":"1"}}`
   - *Schedule*: minuto `0`, ore `0,6,12,18`, ogni giorno · **timezone `Europe/Rome`**
     (cron-job.org applica da se' il passaggio CEST/CET)
   - *Notifications*: attiva "on failure" — se il dispatch smette di partire,
     l'automazione si ferma **in silenzio** (nessun run = nessuna notice).
4. **Salvaguardia**: se cron-job.org o il PAT muoiono, la KB smette di aggiornarsi
   senza errori. Controllo veloce: `gh run list --workflow=kb-maintenance.yml -L 5`
   deve mostrare run `workflow_dispatch` recenti. In alternativa si puo' aggiungere
   al workflow un `schedule:` giornaliero *senza* gate orario come rete di sicurezza.

### Pausa / ripresa

Interruttore: la **Actions variable** `KB_MAINTENANCE_ENABLED` (repo → *Settings →
Secrets and variables → Actions → Variables*). Modificabile **solo dall'owner**
del repo — non esistono altri collaboratori.

| Vuoi | Comando | Effetto |
|---|---|---|
| Mettere in pausa | `gh variable set KB_MAINTENANCE_ENABLED --body false` | lo step *Gate* di `kb-maintenance.yml` esce con `enabled=false`: dispatch esterno e *Run workflow* fanno il no-op pulito |
| Riprendere | `gh variable set KB_MAINTENANCE_ENABLED --body true` (o `gh variable delete`) | default: se assente o diversa da `false/0/off/no` l'automazione gira |
| Giro singolo in pausa | *Actions → KB maintenance → Run workflow* con `force: true` | esegue un'iterazione ignorando la pausa (il token resta comunque richiesto) |

In locale la stessa variabile come **env var** ferma `run_once.py` /
`KB_Aggiorna_Sicuro.bat`: `setx KB_MAINTENANCE_ENABLED false` (persistente) o
`set KB_MAINTENANCE_ENABLED=false` per la sola shell corrente.

---

## 3. Anatomia di un run (`run_once.py`)

```
next-task ─► pre-flight (0 token) ─► modello per tipo ─► claude -p --model M
   │             │                                            │
   │             ├─ new_topic: skip se il file esiste          ▼
   │             ├─ audit/expand/review/currency: skip se assente     update-run
   │             └─ audit: skip se audit-preflight passa         │
   ▼                                                             ▼
coda vuota?                                              rate limit? ─► stop soft (task pending)
  └─ next-work (cascata, §6) ─► injected ─► next-task    errore?     ─► force-complete, stop
                              ─► idle ─► stop pulito      ok?         ─► force-complete
                                                                        ├─ validate-all
                                                                        ├─ prune
fine giro: check-mkdocs (broken link ─► P0) + maintain                  └─ git commit
```

`--dry-run` non chiama `claude` e non muta stato/commit. `--push` fa `git push`
(la CI gestisce il push da sé, quindi non lo passa).

---

## 4. Tipi di task

| type | prompt | modello (config.yaml) | scopo |
|---|---|---|---|
| `new_topic` | `run-prompt.md` | sonnet-5 / high | nuovo argomento dal template |
| `expand` | `expand-prompt.md` | sonnet-5 / medium | espansione additiva |
| `audit` | `audit-prompt.md` | haiku-4-5 / low | fix meccanico (sezione mancante, keyword) |
| `review` | `review-prompt.md` | opus-5 / high | **giudizio** su correttezza / attualità / valore |
| `currency` | `currency-prompt.md` | sonnet-5 / high | ricontrollo dei soli fatti datati vs `official_docs` |
| `consolidate` | `consolidate-prompt.md` | sonnet-5 / high | merge di file ridondanti / retire con fix dei link |
| `proposal` | `proposal-prompt.md` | opus-5 / high | esplorazione di **una** sottocategoria (`scope`) → 0–4 proposte in `proposals/pending/` |

Cambia la policy modificando `_automation/config.yaml` → `models:`.

---

## 5. Ciclo di vita dello `status` (frontmatter)

```
draft ──► (audit meccanico) ──► complete ──► (review critica) ──► reviewed ──► (currency) ──► verified*
              │                                    │
              └────────────► needs-review ◄────────┘   (lavoro non banale rimasto)
```

- `complete`  = supera il gate meccanico (righe, code-block, troubleshooting).
- `reviewed`  = un modello ad alto ragionamento ha giudicato il file corretto/attuale/utile. Aggiunge `last_verified`.
- `needs-review` = modifica significativa o review non conclusa; ha priorità nei giri di review.
- `last_verified` è il segnale di freschezza affidabile. `last_updated` cambia **solo** su modifica sostanziale del contenuto.

Le review le inietta la cascata (§6, fonti `lifecycle` e `review`) a batch di
`cascade.batch_review`. `review-candidates` / `inject-review-tasks` / `init-analysis`
restano come comandi manuali.

---

## 6. Cascata `next-work` e criterio di completezza

A coda vuota **entrambi i loop** (`kb-infinite.ps1`, `run_once.py`) chiamano
`manage-state.py next-work`, che scorre fonti di lavoro in ordine fisso e inietta
un batch dalla **prima non vuota**. Ogni fonte è misurata in Python (0 token) ed è
finita: il modello lavora solo su lavoro già identificato.

| # | Fonte | Rilevazione | Task | Batch |
|---|---|---|---|---|
| 1 | `proposals` | `proposals/pending/` non vuota | auto-approve (ps1: dopo la finestra utente) | — |
| 2 | `lifecycle` | `status: draft` / `needs-review` | `audit` / `review` | `batch_review` |
| 3 | `gate` | `complete` che fallisce `audit-preflight` o ha `related` rotti | `audit` | `batch_audit` |
| 4 | `review` | `complete` che passa il gate, mai revisionato | `review` | `batch_review` |
| 5 | `currency` | `reviewed` con `last_verified` più vecchio di `currency_interval_days` | `currency` | `batch_currency` |
| 6 | `exploration` | sottocategoria non esaurita (`coverage.yaml`) | `proposal` con `scope` | 1 |

**Anti-loop**: stesso (tipo, file) non ritentato prima di `retry_cooldown_days`;
oltre `max_attempts` tentativi il file è saltato (serve un umano). I task iniettati
portano `created_at` e `source`.

**Esplorazione per sottocategoria** (sostituisce la vecchia proposal globale e il
tetto fisso `target_file_count`): ogni sottocategoria (cartelle reali +
`taxonomy.yml`) viene esplorata da una proposal limitata al suo `scope`.
`force-complete` registra l'esito in `coverage.yaml`: 0 proposte ⇒ `exhausted`,
con l'impronta dell'insieme dei suoi file. Ordine: mai esplorate (prima le più
piccole) → aperte (più vecchie prima) → esaurite da riaprire. Un'esaurita si riapre
solo se cambia l'insieme dei suoi file o dopo `exhausted_reopen_days` (90).

**Stato terminale**: tutte le fonti vuote ⇒ `idle` con `next_check_at` (prossima
scadenza currency o riapertura). `kb-infinite.ps1` dorme senza chiamare il modello
né committare, rivalutando ogni ≤10 min (~1 s di Python). È l'unico stop oltre al
rate limit, e significa: tutte le sottocategorie implementate sono esaurite e ogni
file è revisionato e fresco.

`saturation.max_file_count` (default `null`) è solo un tetto di budget opzionale:
se raggiunto sospende la fonte `exploration`.

```bash
python _automation/manage-state.py cascade-status          # candidati per fonte (sola lettura)
python _automation/manage-state.py next-work --dry-run     # cosa verrebbe iniettato
```

---

## 7. File di stato e retention

| File | Ruolo | Retention |
|---|---|---|
| `state.yaml` | coda + storico task + contatori + `analysis` | `queue` completa (storico serve a non ricreare task); `completed` summary limitata a 15 (`prune`) |
| `runs.log` | log diagnostico locale | **non versionato**; rotazione a 512 KB × 2 (`maintain`) |
| `current-task.json` | task passato all'agente nel run corrente | **non versionato** |
| `proposals/pending|approved|rejected/` | proposte | `approved`/`rejected` limitate a 50 file (`maintain`) |
| `coverage.yaml` | esito esplorazione per sottocategoria (`exhausted`, impronta) | versionato; scritto solo da `force-complete` |
| `config.yaml` | policy modello, cascata, cadenze | versionato |

---

## 8. Comandi `manage-state.py` (riferimento)

```
next-task | mark-started <id> | force-complete <id>
check-mkdocs | validate-all <json> | audit-preflight <path>
estimate-tokens <path> <in> <out> | update-run | prune | maintain | stats
analysis-status | init-analysis
list-proposals | approve-proposal <id> | reject-proposal <id>
auto-approve-proposals | inject-proposal-task (manuale)
next-work [--dry-run] [--no-approve]   # cascata a coda vuota (§6)
cascade-status                 # candidati per fonte, sola lettura
resolve-interrupted            # pulisce un interrupted_task stale
saturation-gate                # file vs max_file_count (tetto opzionale)
review-candidates [n]          # n file verificati meno di recente
inject-review-tasks [n]        # crea n task review
stats-doc [write]              # (ri)genera la tabella in docs/index.md
```

---

## 9. Upgrade path

- **Deploy nativo Actions**: passare da `mkdocs gh-deploy` a
  `actions/upload-pages-artifact` + `actions/deploy-pages` richiede
  `gh api --method PUT repos/OWNER/REPO/pages -f build_type=workflow`.
  Attualmente si usa `gh-deploy` (modalità Pages "legacy" da branch `gh-pages`)
  perché non tocca la configurazione Pages e non ha rischi sul sito live.
- **`--effort` nel CLI**: se la versione di Claude Code lo supporta, mettere
  `pass_effort_flag: true` in `config.yaml`.
