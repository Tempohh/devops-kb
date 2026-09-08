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
- [ ] F1 `mkdocs build --strict` pulito
- [ ] F2 `py_compile` su `_automation/*.py`
- [ ] F3 YAML valido su workflow + config
- [ ] F4 scansione broken-link

## Fase G — Deploy + verifica
- [ ] G1 push unico
- [ ] G2 `gh workflow run deploy.yml`
- [ ] G3 `gh run watch`
- [ ] G4 WebFetch homepage + pagine profonde
- [ ] G5 diagnosi/fix se necessario

## Fase H — Analisi finale + memoria
- [ ] H1 riepilogo
- [ ] H2 memorie
- [ ] H3 checklist Chrome per l'utente
