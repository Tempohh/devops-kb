# KB Overhaul — Piano di esecuzione

> Sessione autonoma avviata 2026-09-08. Obiettivo: automazione senza PC, governance/coerenza,
> policy modelli, sweep di attualità, deploy verificato su GitHub Pages.

Stato: `[ ]` da fare · `[~]` in corso · `[x]` fatto

## Fase A — CI/CD & hosting
- [x] A1 `mkdocs.yml`: fix plugin tags (rimuovi `tags_file`), aggiungi `site_url`/`repo_url`/`repo_name`/`edit_uri`
- [x] A2 `docs/tags.md`: `[TAGS]` → `<!-- material/tags -->`
- [x] A3 `.github/workflows/deploy.yml`: build + `mkdocs gh-deploy --force` su push a master + dispatch
- [x] A4 `.github/workflows/kb-maintenance.yml`: cron 6h + dispatch, guardato da secret, esegue run_once.py
- [x] A5 `requirements.txt`: pin versioni

## Fase B — Core automazione + policy modelli
- [x] B1 `_automation/config.yaml`: model/effort per task type, target, cadenze
- [x] B2 `_automation/run_once.py`: iterazione bounded cross-platform
- [x] B3 fix `kb-safe.ps1` python probe; `.ps1` leggono config.yaml
- [x] B4 `manage-state.py`: `stats-doc`, `review-candidates`, `resolve-interrupted`, freno saturazione, task currency

## Fase C — Governance & coerenza
- [x] C1 `CLAUDE.md`: automazione, ciclo di stato, policy modelli, gerarchia 11 cat, registro criticità
- [x] C2 `docs/_metadata/taxonomy.yml`: 11 categorie
- [x] C3 nuovi prompt: review / consolidate / currency
- [x] C4 `proposal-prompt.md`: zero proposte ammesse + legge saturation report
- [x] C5 `_automation/AUTOMATION.md`
- [x] C6 `docs/index.md`: tabella rigenerata
- [x] C7 risolvi task 467 in state.yaml

## Fase D — Sweep attualità AI
- [x] D1 `docs/ai/modelli/claude.md` → Claude 5
- [x] D2 `docs/ai/modelli/scelta-modello.md`
- [x] D3 `docs/ai/modelli/modelli-open-source.md`
- [x] D4 grep-sweep stale model strings
- [x] D5 `last_verified` sui file toccati

## Fase E — Housekeeping
- [x] E1 sposta `Certificazione.html` + `KNOWLEDGE-BASE-BLUEPRINT.txt` → `_meta/`
- [x] E2 sfoltisci `.claude/settings.local.json`

## Fase F — Test
- [x] F1 `mkdocs build --strict` pulito
- [x] F2 `py_compile` su `_automation/*.py`
- [x] F3 YAML valido su workflow + config
- [x] F4 scansione broken-link

## Fase G — Deploy + verifica
- [x] G1 push unico
- [x] G2 `gh workflow run deploy.yml`
- [x] G3 `gh run watch`
- [x] G4 WebFetch homepage + pagine profonde
- [x] G5 diagnosi/fix se necessario

## Fase H — Analisi finale + memoria
- [x] H1 riepilogo
- [x] H2 memorie
- [x] H3 checklist Chrome per l'utente


---

## Esito (2026-09-08)

Commit `331844b`..`187d133` su `master`, pushati. 5 commit.

- `deploy.yml`: run #34220794169 **success** (1m3s) → gh-pages → Pages `built`.
- `pages-build-deployment`: **success**. Live: https://tempohh.github.io/devops-kb/ → 200.
- `kb-maintenance.yml`: dispatch #34221099582 **success** — clean-skip (secret assente), notice informativo.
- Verifica contenuto (WebFetch): `/ai/modelli/claude/` mostra famiglia Claude 5 + adaptive thinking + pricing corretti; homepage stats generate (295 file / 171.851 righe / 11 cat); `/tags/` rende l'indice (no `[TAGS]`).

### Da fare (utente)
1. Repo Settings → Secrets → Actions → `CLAUDE_CODE_OAUTH_TOKEN` (da `claude setup-token`) per attivare la manutenzione schedulata.
2. Verifica visiva Chrome (checklist in chat).
3. D3 `modelli-open-source.md`: non editato a mano, è fra i 12 task `currency` in coda.
