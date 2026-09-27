# KB Saturation Report — 2026-09-28 (sessione #691)

## Gate meccanico

```
file_count: 314, target: 330, over_target: false, headroom: 16, category_saturated_pct: 85
```

Invariato dalle sessioni precedenti (#649...#689). Sotto target: proposte di
espansione ammesse se superano il test di utilità.

## Nota di cadenza

Il report #689 raccomandava di non ripetere una sessione proposal prima del
2026-10-01. Questo task (id 691, P2) è arrivato il 2026-09-28, 3 giorni prima —
eseguito comunque perché già in coda, ma senza forzare nuove proposte di
contenuto: il focus di questa sessione è stato interamente connettività
(`related`), coerente con quanto il report precedente indicava come prossimo
passo ("continuare la verifica di connettività sui file `related`-ricchi
ancora non campionati").

## Focus usato in questa sessione

Continuazione del focus **`docs/iac/terraform/`** (sessione precedente aveva
già identificato e chiuso con prop-118 un gap di contenuto su `terraform
test`). Nessuna nuova proposta `new-file`/`extend-section`: i file terraform
sono ora tutti di qualità alta. Il gap residuo trovato è di connettività, non
di contenuto.

File letti per intero in questa sessione (5): `iac/terraform/testing.md`
(verifica post-espansione #690), `iac/terraform/moduli.md`,
`iac/terraform/state-management.md`, `iac/terraform/opentofu.md`,
`iac/terraform/ci-cd.md`. Verifica mirata frontmatter/related (5):
`iac/terraform/fondamentali.md`, `monitoring/tools/loki.md`,
`ci-cd/jenkins/shared-libraries.md`, `ai/training/valutazione.md` — nessuna
asimmetria trovata in questo secondo gruppo (conferma quanto già osservato
in #689).

## Risultato

`testing.md` post-espansione è di qualità alta e ben integrato (ha
admonition dedicate a fondamentali, moduli, ci-cd/pipeline). Confrontando
`related` frontmatter e admonition body tra i 5 file terraform letti per
intero, emergono due asimmetrie reali (non simmetria formale):

- **moduli.md → testing.md**: `testing.md` ha un blocco "Terraform Moduli —
  Test dei Moduli Condivisi" che rimanda a `moduli.md`, ma `moduli.md` non
  ricambia il link verso `testing.md`, nonostante il contenuto di `moduli.md`
  parli esplicitamente di testing dei moduli condivisi. → prop-119
  (fix-relation, medium).
- **state-management.md ← ci-cd.md, testing.md**: sia `ci-cd.md` che
  `testing.md` includono `iac/terraform/state-management` in `related` (e
  `ci-cd.md` ha un'admonition dedicata al backend/locking), ma
  `state-management.md` non ricambia verso nessuno dei due. → prop-120
  (fix-relation, medium).

Nessun gap di contenuto (new-file/extend-section) confermato in questa
sessione: la categoria iac/terraform, dopo prop-118, non presenta lacune
operative non banali. Non generate proposte per crossplane/pulumi/ansible
(invariato da #689).

## Categorie vicine alla saturazione

Invariato rispetto a #689.

## Categorie con gap reali

- Nessun gap di *contenuto* residuo in `iac/terraform/` dopo prop-118.
  I due gap trovati in questa sessione sono di *connettività* (related
  asimmetrico), non di copertura.

## Prossima sessione consigliata

Non prima di 2026-10-04 (rispettare il cooldown, questa sessione è arrivata
in anticipo rispetto a quanto raccomandato in #689). Se prop-119/prop-120
vengono approvate e applicate, verificare che le admonition aggiunte non
creino a loro volta nuove asimmetrie (es. `ci-cd.md` dovrebbe già avere il
link a `testing.md` — verificato presente in questa sessione, nessuna azione
necessaria lì). Focus successivo: spostarsi da `iac/` (ormai ripulito) a
`docs/monitoring/` o `docs/databases/`, seguendo la rotazione di default
indicata a suo tempo in #683, dato che iac/terraform non presenta più gap
evidenti.
