# KB Saturation Report — 2026-10-02 (sessione #702)

## Gate meccanico

```
file_count: 316, target: 330, over_target: false, headroom: 14, category_saturated_pct: 85, allow_zero_proposals: true
```

Sotto target (headroom 14): proposte di espansione ammesse se superano il
test di utilità. Nota di cadenza: task #702 (P2) arrivato lo stesso giorno
della sessione #701 — quinto caso consecutivo di arrivo anticipato rispetto
alla finestra raccomandata (#694→#696→#698→#701→#702). Vedi raccomandazione
finale per verifica lato sorgente del task.

## Focus usato in questa sessione

Rotazione indicata dal report #701: ritorno su `docs/iac/`, `docs/monitoring/`,
`docs/databases/` (default, non esplorate da due sessioni `proposal` di fila
dopo `dev/` e `ci-cd/testing/` risultate sature).

File letti (10): `iac/crossplane/_index.md`, `iac/crossplane/fondamentali.md`,
`iac/ansible/roles-collections.md`, `iac/pulumi/_index.md`,
`monitoring/tools/_index.md`, `monitoring/_index.md`, `databases/mysql/_index.md`,
`databases/kubernetes-cloud/_index.md`, `iac/_index.md`, `iac/ansible/_index.md`.

## Risultato

**docs/iac/**: Terraform e Ansible hanno copertura "enterprise" completa
(roles-collections.md è un file di 980+ righe con Molecule, Vault multi-env,
dynamic inventory). Gap reale trovato: **Crossplane è l'unico strumento IaC
senza guidance di testing** — il file fondamentali.md segnala esplicitamente
il bisogno ("trattare la Composition come un'API pubblica, test automatici
prima del merge") ma non spiega come farlo. Pulumi ha testing solo accennato
nell'indice della sezione fondamentali, non approfondito a parte — gap minore,
non proposto in questa sessione (score insufficiente rispetto a Crossplane).

**docs/monitoring/**: tre pilastri + quarto segnale (continuous profiling)
ben coperti, scalabilità storage (Thanos/Mimir/VictoriaMetrics) documentata.
Due gap trasversali reali: (1) **gestione cardinalità/costo metriche** —
problema operativo che emerge solo a scala, mai affrontato nonostante
prometheus-scalabilita.md tratti lo storage ma non il controllo a monte della
cardinalità; (2) **synthetic/blackbox monitoring** — i tre pilastri sono
tutti white-box, manca il segnale di disponibilità percepita dall'esterno
che alimenterebbe gli SLO già documentati in `sre/slo-sla-sli.md`.

**docs/databases/**: mysql/ (sessione precedente) e kubernetes-cloud/
risultano completi e ben connessi (`related` ricchi, troubleshooting
presente). Nessun gap operativo individuato in questa sessione — categoria
matura, non ha generato proposte.

## Proposte generate

- **prop-125** (high, new-file) — `monitoring/tools/cardinality-cost-management.md`
- **prop-126** (medium, new-file) — `monitoring/tools/synthetic-monitoring.md`
- **prop-127** (medium, extend-section) — `iac/crossplane/fondamentali.md` (testing Composition)

## Categorie vicine alla saturazione

`docs/dev/` e `docs/ci-cd/testing/` confermate sature (sessione #701).
`docs/databases/` risulta densa ma non ancora formalmente satura (nessun
segnale `category_saturated_pct` superato nel report meccanico).

## Categorie con gap reali

`docs/monitoring/tools/` (cardinalità, synthetic monitoring) e
`docs/iac/crossplane/` (testing) — vedi proposte sopra.

## Prossima sessione consigliata

Non prima di 2026-10-09. Se arriva comunque prima (pattern ricorrente da 5
sessioni), focus successivo: `docs/security/` o `docs/cloud/` (non ancora
esplorate in sessioni `proposal` recenti), oppure verificare l'implementazione
di prop-125/126/127 prima di generarne di nuove nella stessa area.
