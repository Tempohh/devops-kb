# KB Saturation Report — 2026-09-27 (sessione #651)

## Gate meccanico

```
file_count: 314, target: 330, over_target: false, headroom: 16, category_saturated_pct: 85
```

Invariato dal gate della sessione precedente (#649). Sotto target, espansione ammessa
ma solo con gap reali (vedi PASSO 0/3 del prompt).

## Focus usato in questa sessione

Come raccomandato dal report di #649: primo giro di lettura di **contenuto**
(non solo connettività) su `cloud/aws/` e `databases/` — mai state oggetto di
un giro mirato a currency/refusi (solo controlli hub→figli nelle sessioni
precedenti). 10 file letti in profondità, scelti tra i più densi/centrali
delle due sezioni:

- `cloud/aws/compute/lambda.md`, `cloud/aws/containers/eks.md`,
  `cloud/aws/database/rds-aurora.md`, `cloud/aws/database/dynamodb.md`,
  `cloud/aws/iam/policies-avanzate.md`
- `databases/postgresql/replicazione.md`, `databases/mysql/performance-tuning.md`,
  `databases/nosql/mongodb.md`, `databases/sql-avanzato/query-optimizer.md`,
  `databases/kubernetes-cloud/managed-databases.md`

## Risultato

Tutti e 10 i file sono risultati **solidi dal punto di vista di currency**:
nessun comando/flag deprecato, nessun limite di servizio palesemente
obsoleto (es. limiti Lambda, RCU/WCU DynamoDB, versioni engine RDS/Aurora
tutti plausibili e coerenti tra loro), nessun conflitto tra pagine correlate.
Diversi file (`mysql/performance-tuning.md`, `sql-avanzato/query-optimizer.md`)
hanno `last_updated: 2026-09-27` — già toccati di recente in sessioni
`currency`/`review` precedenti — a conferma che il lavoro di manutenzione
pregresso su queste aree ha già avuto effetto.

Un solo gap reale trovato, di tipo **connettività** (non contenuto):

- **`databases/kubernetes-cloud/managed-databases.md`** (hub cross-cloud
  RDS/Aurora/DynamoDB/Cloud SQL/Azure DB) non collega i file di
  approfondimento AWS che riassume nel testo — `cloud/aws/database/rds-aurora.md`
  e `cloud/aws/database/dynamodb.md` — né riceve il link inverso da questi.
  → prop-089 (low, fix-relation).

Nessun gap di tipo `new-file` o `extend-section` proposto: entrambe le
sezioni esaminate sono mature e ben mantenute.

## Categorie vicine alla saturazione

Invariato dalle sessioni precedenti: **databases/**, **dev/linguaggi/**,
**messaging/rabbitmq**, **cloud/aws**, **networking/**, **dev/testing,
dev/data, dev/resilienza, dev/sicurezza, dev/integrazioni**, **monitoring/**,
**iac/**, **cloud/azure/**, **ai/**, **security/**, **containers/**,
**messaging/kafka/**. Con questa sessione si confermano di alta qualità
(content-read, non solo connettività) anche i file più densi di
`cloud/aws/{compute,containers,database,iam}` e `databases/{postgresql,
mysql,nosql,sql-avanzato,kubernetes-cloud}`.

## Categorie con gap reali

Un solo gap concreto trovato in questa sessione: connettività mancante tra
`databases/kubernetes-cloud/managed-databases.md` e i due file AWS che
riassume (vedi sopra, prop-089).

## Prossima sessione consigliata

Non prima di 2026-10-03. Il giro di lettura content-focused su `cloud/aws/`
e `databases/` copre solo una parte dei file di queste sezioni (10 su ~75
totali tra le due): prossimo focus suggerito continuare lo stesso tipo di
lettura (non connettività) su `cloud/aws/{networking,security,storage,
messaging,monitoring}` e `databases/{fondamentali,replicazione-ha,nosql
rimanenti}` — file mai stati oggetto di un giro currency mirato finora.
