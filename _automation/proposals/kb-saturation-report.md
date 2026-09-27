# KB Saturation Report — 2026-09-27 (sessione #656)

## Gate meccanico

```
file_count: 314, target: 330, over_target: false, headroom: 16, category_saturated_pct: 85
```

Invariato dalle sessioni precedenti (#649, #651, #653). Sotto target, espansione
ammessa ma solo con gap reali (vedi PASSO 0/3 del prompt).

## Focus usato in questa sessione

Come raccomandato dal report di #653: prosecuzione del giro content-focused su
`cloud/azure/` (mai stato oggetto di lettura mirata prima d'ora), sulle
sottocategorie principali: networking, security, storage, database,
monitoring, messaging. 10 file letti in profondità:

- `cloud/azure/networking/vnet.md`, `cloud/azure/networking/load-balancing.md`,
  `cloud/azure/networking/connettivita.md`
- `cloud/azure/security/key-vault.md`, `cloud/azure/security/defender-sentinel.md`
- `cloud/azure/storage/storage-avanzato.md`
- `cloud/azure/database/cosmos-db.md`, `cloud/azure/database/azure-sql.md`
- `cloud/azure/monitoring/monitor-log-analytics.md`
- `cloud/azure/messaging/event-hubs.md`

Nota: `databases/postgresql/{connection-pooling,extensions,mvcc-vacuum}.md`,
indicati come "mancanti" nel report #653, in realtà **esistono già** (verificato
con Glob) — quella nota andava letta come "non ancora sottoposti a lettura di
contenuto", non come file da creare. Corretto qui per evitare che una sessione
futura proponga `new-file` per file già presenti.

## Risultato

Tutti e 10 i file sono risultati **maturi e solidi**: contenuto denso, esempi
CLI (`az`) realistici, snippet Python/PowerShell dove pertinente, sezioni
Troubleshooting con scenari multipli concreti, nessun comando/flag palesemente
deprecato. Nessun gap di contenuto (`new-file` / `extend-section`) trovato.

Due gap di **connettività** individuati, stesso pattern già visto in #651/#653
(file hub molto referenziati ma con `related` proprio non aggiornato in modo
reciproco):

- **`cloud/azure/security/key-vault.md`** — referenziato in dettaglio da
  `storage-avanzato.md` (sezione CMK) e `cosmos-db.md`, ma il proprio `related`
  (3 voci: app-service-functions, aks-containers, azure-sql) non li include.
  → prop-092 (low, fix-relation).
- **`cloud/azure/monitoring/monitor-log-analytics.md`** — referenziato con
  esempi concreti di diagnostic settings da `azure-sql.md` e `event-hubs.md`,
  ma il proprio `related` (3 voci: virtual-machines, aks-containers,
  defender-sentinel) non li include. → prop-093 (low, fix-relation).

Nessuna proposta `new-file` in questa sessione: le sottocategorie esaminate di
`cloud/azure/` sono coperte in modo completo e maturo quanto le equivalenti
già validate su `cloud/aws/` in #653.

## Categorie vicine alla saturazione

Invariato: **databases/**, **dev/linguaggi/**, **messaging/rabbitmq**,
**cloud/aws**, **networking/**, **dev/testing, dev/data, dev/resilienza,
dev/sicurezza, dev/integrazioni**, **monitoring/**, **iac/**, **cloud/azure/**,
**ai/**, **security/**, **containers/**, **messaging/kafka/**. Con questa
sessione si confermano di alta qualità (content-read) anche
`cloud/azure/{networking,security,storage,database,monitoring,messaging}`
(campione di 10 file).

## Categorie con gap reali

Due gap di connettività isolati (vedi sopra, prop-092/093). Nessun gap di
contenuto in questa sessione.

## Prossima sessione consigliata

Non prima di 2026-10-04. Il giro content-focused ha ora coperto un campione
denso sia di `cloud/aws/` (#653) sia di `cloud/azure/` (questa sessione). Per
`cloud/azure/`, restano non ancora letti in profondità: `compute/` (aks-containers,
virtual-machines, app-service-functions), `identita/` (entra-id, governance,
rbac-managed-identity), `ci-cd/` (arm-bicep, azure-devops). In alternativa,
applicare prop-092/093 (fix-relation, se approvate) e passare a un primo giro
content-focused su `databases/postgresql/` (file esistenti ma non ancora
letti per contenuto: `connection-pooling.md`, `extensions.md`,
`mvcc-vacuum.md`) o su `iac/` (mai stato in focus finora).
