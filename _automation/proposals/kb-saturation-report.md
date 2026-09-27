# KB Saturation Report — 2026-09-28 (sessione #689)

## Gate meccanico

```
file_count: 314, target: 330, over_target: false, headroom: 16, category_saturated_pct: 85
```

Invariato dalle sessioni precedenti (#649...#683). Sotto target: proposte di
espansione ammesse se superano il test di utilità.

## Focus usato in questa sessione

Focus di default da PASSO 3 (nessuna raccomandazione di rotazione urgente nel
report #683, che indicava semmai di continuare il giro connettività su file
non ancora campionati): **`docs/iac/`** — categoria a coverage più bassa
(17 file contro i 20+ di monitoring/databases), mai stata target diretto di
un new-file/extend-section in questo giro di sessioni.

File letti per intero in questa sessione (4): `iac/crossplane/fondamentali.md`,
`iac/pulumi/fondamentali.md`, `iac/ansible/roles-collections.md`,
`iac/terraform/testing.md`. Più verifica mirata frontmatter/related (5):
`monitoring/tools/prometheus.md`, `monitoring/tools/grafana.md`,
`ci-cd/jenkins/pipeline-fundamentals.md`, `ai/training/fine-tuning.md`,
`databases/postgresql/extensions.md` — nessuna asimmetria di relazione
trovata in questo secondo gruppo (tutti reciproci o hub/consumer normali).

## Risultato

I quattro file IaC letti per intero sono di qualità alta (Troubleshooting
concreto, anti-pattern, esempi runnabili, `related` ricco e reciproco). Un
gap reale individuato: **`iac/terraform/testing.md`** documenta la piramide
di testing IaC (static/policy/integration) ma copre solo strumenti esterni
(Terratest, checkov, conftest) — manca **`terraform test`**, il framework
nativo HCL di HashiCorp (v1.6+, file `.tftest.hcl`), che è oggi l'opzione
consigliata per test di modulo senza introdurre una dipendenza Go. Verificato
via grep che non è documentato altrove in `docs/iac/`. → prop-118
(extend-section, high, target `iac/terraform/testing.md`).

Nessun altro gap di contenuto o di connettività confermato in questa
sessione. Non generate proposte per crossplane/pulumi/ansible: categorie
sottili in termini di conteggio file ma i file esistenti sono completi e non
mostrano gap operativi non banali (niente "riempimento" per simmetria).

## Categorie vicine alla saturazione

Invariato rispetto a #683.

## Categorie con gap reali

- `iac/terraform/` — gap puntuale di contenuto (vedi sopra), non di
  copertura strutturale.

## Prossima sessione consigliata

Non prima di 2026-10-01. Continuare la verifica di connettività sui file
`related`-ricchi ancora non campionati (`monitoring/tools/loki.md`,
`ci-cd/jenkins/shared-libraries.md`, `ai/training/valutazione.md`) e, se
prop-118 viene approvata e applicata, verificarne la reciprocità con
`iac/terraform/moduli.md` una volta aggiornata.
