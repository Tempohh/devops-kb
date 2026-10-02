# KB Saturation Report — 2026-10-02 (sessione #698)

## Gate meccanico

```
file_count: 315, target: 330, over_target: false, headroom: 15, category_saturated_pct: 85, allow_zero_proposals: true
```

## Nota di cadenza

Il report #696 raccomandava di non ripetere una sessione `proposal` prima del
2026-10-04 e suggeriva, come alternativa, una sessione `currency` mirata su
`databases/kubernetes-cloud/managed-databases.md`. Il task #698 (P2) è arrivato
comunque il 2026-10-02 — due giorni prima della finestra consigliata, terzo
caso consecutivo di questo pattern (#694→#696→#698 a cadenza più stretta del
raccomandato). Eseguito comunque perché già in coda; la proposta di currency
suggerita dal report precedente è stata incorporata come prop-124 invece di
essere scartata.

## Focus usato in questa sessione

Default (nessuna indicazione di rotazione esplicita nel report precedente,
che riguardava cadenza non focus): `docs/iac/`, `docs/monitoring/`,
`docs/databases/` — le tre categorie di default per coverage più bassa, mai
in focus esplicito finora.

File letti (10): `iac/terraform/testing.md` (needs-review), `monitoring/_index.md`
(needs-review), `iac/_index.md`, `iac/crossplane/fondamentali.md`,
`databases/kubernetes-cloud/managed-databases.md`, `databases/mysql/_index.md`,
`iac/pulumi/stacks-ambienti.md`, `monitoring/tools/_index.md`,
`databases/nosql/_index.md`. Verifica mirata via grep: nessuna menzione di
ProxySQL/MaxScale in `docs/databases/`.

## Risultato

**iac/**: terraform, ansible, pulumi, crossplane tutti a `status: complete`
(eccetto `terraform/testing.md`, `needs-review` — modifica recente, non un gap
di contenuto), `related` ricchi. Crossplane ha solo 2 file contro i 6 di
terraform, ma la profondità esistente (fondamentali) già copre quando/quando-non
usarlo in modo completo; una terza voce (es. Composition Functions avanzate)
sarebbe approfondimento per un tool di nicchia, non un gap operativo diffuso
— scartato.

**monitoring/**: tools/alerting/sre tutti `complete`, struttura matura
(incluso continuous profiling come "quarto segnale"). `monitoring/_index.md`
è `needs-review` ma per modifica recente, non gap di contenuto. Nessuna
proposta generata.

**databases/**: trovato gap reale — `databases/mysql/` copre architettura/
replicazione e performance tuning ma non ha equivalente di
`postgresql/connection-pooling.md` (PgBouncer): nessun file menziona ProxySQL
o MaxScale in tutta la sezione databases. MySQL usa un modello
thread-per-connection con costo per-connessione significativo, rendendo il
pooling/proxy layer un argomento operativo concreto e mancante. → prop-123
(new-file, medium, score medium).

`databases/kubernetes-cloud/managed-databases.md` confermato come file più
vecchio (`last_updated: 2026-03-29`) tra tutti quelli letti in questa e nella
sessione precedente — segmento ad alto tasso di cambiamento (nuove offerte
serverless/distribuite dei cloud provider). → prop-124 (currency, medium).

## Categorie vicine alla saturazione

Invariato rispetto a #696 — nessun cambiamento strutturale significativo da
allora (315 vs 314 file, +1 da sessioni `new_topic` intermedie non-`proposal`).

## Categorie con gap reali

- `databases/mysql/`: manca connection pooling/proxy layer (ProxySQL/MaxScale),
  gap rispetto al livello di dettaglio già raggiunto da `postgresql/`.
  → prop-123.
- `databases/kubernetes-cloud/managed-databases.md`: contenuto più vecchio
  della KB in quest'area, a rischio currency. → prop-124.

## Prossima sessione consigliata

Non prima di 2026-10-09 (una settimana da oggi, non +2 giorni come nei cicli
precedenti — il pattern di arrivo anticipato di task `proposal` P2 andrebbe
verificato lato sorgente del task, visto che la criticità #5 in CLAUDE.md
aveva già rimosso l'iniezione automatica standalone da `run_once.py`: se il
pattern persiste, la causa è probabilmente manuale/`state.yaml` diretto, non
`run_once.py`). Focus successivo: se prop-123/prop-124 vengono approvate e
implementate, verificare `related` reciproci tra il nuovo file MySQL e
`postgresql/connection-pooling.md`; altrimenti ruotare il focus verso
`docs/dev/` o `docs/ci-cd/testing/` (non ancora esplorate in sessioni
`proposal` recenti).
