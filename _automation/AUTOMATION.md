# Sistema di automazione KB

Documento autoritativo sul layer di automazione. `CLAUDE.md` (root) descrive i
protocolli *di contenuto*; questo file descrive *come la KB si mantiene da sola*.

---

## 1. Modelli di esecuzione

| Modo | Come si avvia | Quando usarlo |
|---|---|---|
| **CI schedulata** (raccomandato) | `.github/workflows/kb-maintenance.yml` — cron ogni 6h + *Run workflow* | Manutenzione continua "a PC spento". Nessuna dipendenza dalla macchina locale. |
| **Locale — 1 task** | doppio click su `KB_Aggiorna_Sicuro.bat` (→ `kb-safe.ps1` → `run_once.py --max-tasks 1`) | Eseguire un singolo task al volo su Windows, con la stessa logica della CI. |
| **Locale — loop infinito** | `KB_Aggiorna_Infinito.bat` (→ `kb-infinite.ps1`) | Sessioni intensive locali. **Non** applica la policy modello di `config.yaml`. Legacy. |

Deploy del sito: `.github/workflows/deploy.yml` (build + `mkdocs gh-deploy`) parte
a ogni push su `master` che tocca `docs/`, `mkdocs.yml`, `requirements.txt`.
`kb-maintenance.yml` ripubblica anche da solo dopo aver committato contenuto.

---

## 2. Attivare la CI di manutenzione (una tantum)

`kb-maintenance.yml` si **salta in modo pulito** finché non esiste il secret.

1. In locale: `claude setup-token` → copia il token OAuth.
2. GitHub → repo **Settings → Secrets and variables → Actions → New repository secret**
   - Name: `CLAUDE_CODE_OAUTH_TOKEN`
   - Value: il token
3. (Opzionale) *Actions → KB maintenance → Run workflow* per un giro immediato.

Il token resta sui limiti del piano Claude esistente: su rate limit il run
termina "soft" (exit 0, task ancora `pending`) e il cron successivo riprende.
`state.yaml` rende ogni run ripartibile.

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
  ├─ analisi > 7g?  ─► init-analysis                     errore?     ─► force-complete, stop
  ├─ proposte pending? ─► auto-approve (CI) / lascia      ok?         ─► force-complete
  └─ altrimenti ─► inject-proposal-task                                  ├─ validate-all
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
| `proposal` | `proposal-prompt.md` | opus-5 / high | analisi strategica → proposte in `proposals/pending/` |

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

`review-candidates` / `inject-review-tasks` selezionano i file con `last_verified`
più vecchio. `init-analysis` inietta `review_sample_size` review per ciclo.

---

## 6. Freno di saturazione

`python _automation/manage-state.py saturation-gate` → JSON con `file_count`,
`target` (`config.yaml` → `saturation.target_file_count`), `over_target`.

`proposal-prompt.md` lo consulta al PASSO 0:
- oltre il target o categoria satura (≥ `category_saturated_pct` nel
  `kb-saturation-report.md`) → niente `new-file` salvo `score: high` con gap esplicito;
- **è ammesso restituire zero proposte** con motivazione.

---

## 7. File di stato e retention

| File | Ruolo | Retention |
|---|---|---|
| `state.yaml` | coda + storico task + contatori + `analysis` | `queue` completa (storico serve a non ricreare task); `completed` summary limitata a 15 (`prune`) |
| `runs.log` | log diagnostico locale | **non versionato**; rotazione a 512 KB × 2 (`maintain`) |
| `current-task.json` | task passato all'agente nel run corrente | **non versionato** |
| `proposals/pending|approved|rejected/` | proposte | `approved`/`rejected` limitate a 50 file (`maintain`) |
| `config.yaml` | policy modello, target, cadenze | versionato |

---

## 8. Comandi `manage-state.py` (riferimento)

```
next-task | mark-started <id> | force-complete <id>
check-mkdocs | validate-all <json> | audit-preflight <path>
estimate-tokens <path> <in> <out> | update-run | prune | maintain | stats
analysis-status | init-analysis
list-proposals | approve-proposal <id> | reject-proposal <id>
auto-approve-proposals | inject-proposal-task
resolve-interrupted            # pulisce un interrupted_task stale
saturation-gate                # stato saturazione vs target
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
