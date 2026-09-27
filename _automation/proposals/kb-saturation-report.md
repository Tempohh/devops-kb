# KB Saturation Report — 2026-09-27 (sessione #600)

## Gate meccanico

```
file_count: 309, target: 330, over_target: false, headroom: 21
category_saturated_pct: 85, allow_zero_proposals: true
```

Sotto target. Focus ruotato su `docs/databases/` come raccomandato dal report
della sessione #597 (gap mai esplorato in profondità, coverage ~70%).

## Copertura stimata per categoria

| Categoria | Files | Coverage % | Depth | Note |
|-----------|-------|------------|-------|------|
| databases | 27 (+7 `_index`) | ~75% | Alta su PostgreSQL/NoSQL, assente MySQL | Vedi analisi sotto |
| networking | 44 | ~90% | Alta | Confermato saturo (sessioni #591-596) |
| cloud/aws | 45 | ~90% | Alta | Confermato saturo (sessioni #594-596) |
| iac | 14 | ~75% | Alta | Gap Pulumi Policy-as-Code chiuso (prop-056, auto #598) |
| monitoring | 21 | ~70% | Alta sui 3 pilastri classici | Gap continuous profiling chiuso (prop-057, auto #599) |

## Analisi di questa sessione

File analizzati: censimento strutturale completo di `docs/databases/**`
(27 file di contenuto + 7 `_index`, tutti `status: complete`, nessun
`needs-review`/`draft`) più lettura mirata di `postgresql/extensions.md`,
`ai/sviluppo/rag.md` e `dev/integrazioni/database-patterns.md` per verificare
due ipotesi di gap prima di proporre.

**Verificato NON un gap**: vector database. `postgresql/extensions.md` copre
pgvector (HNSW/IVFFlat, troubleshooting, dimensionamento) e `ai/sviluppo/rag.md`
copre il confronto Qdrant/Pinecone/Weaviate/pgvector/ChromaDB dal lato
applicativo. Copertura già solida e cross-linkata — nessuna proposta.

**Gap reali confermati**:
1. **MySQL/MariaDB assente al 100%**: la categoria `databases` è profondamente
   PostgreSQL-centrica (replicazione, MVCC/vacuum, extension, connection
   pooling) e NoSQL (Cassandra/MongoDB/Redis/Elasticsearch), ma zero contenuto
   su MySQL/MariaDB — uno degli RDBMS più diffusi in produzione, con
   meccanismi interni non sovrapponibili a Postgres (binlog vs WAL, InnoDB
   clustered index, Group Replication/Galera vs streaming replication). Non è
   simmetria formale: i concetti sono diversi, non solo i nomi dei comandi.
2. **Migrazioni di schema — nessun confronto tool**: esiste il pattern di
   deployment ("init container" Kubernetes) in
   `dev/integrazioni/database-patterns.md`, ma nessun confronto operativo tra
   Flyway/Liquibase/Atlas (versioned vs declarative, rollback automatico vs
   manuale, drift detection). Gap più piccolo del precedente — score medium.

## Categorie vicine alla saturazione

- **networking**, **cloud/aws**: confermato saturo, nessuna nuova analisi in
  questa sessione (fuori focus).

## Categorie con gap reali

- **databases/mysql**: sottocategoria interamente mancante — proposta
  generata (prop-058, priority high).
- **databases/fondamentali**: manca confronto schema-migration tool —
  proposta generata (prop-059, priority medium).

## Focus usato in questa sessione

`docs/databases/`, per rotazione esplicita raccomandata dal report della
sessione #597 ("prossima sessione consigliata: focus databases, coverage ~70%
mai esplorato in profondità"). Il focus ha prodotto un gap `high` (MySQL,
sottocategoria intera assente) e uno `medium` (schema migrations),
confermando che databases meritava il turno.

## Decisione: 2 proposte

- `prop-058`: MySQL/MariaDB — Architettura InnoDB e Replicazione,
  `databases/mysql`, priority high.
- `prop-059`: Migrazioni di Schema — Flyway/Liquibase/Atlas,
  `databases/fondamentali`, priority medium.

Zero proposte aggiuntive su NoSQL/replicazione-ha/sql-avanzato: tutti i file
letti/censiti sono `status: complete`, con `related` ricchi, nessuna isola
individuata, nessun gap che superi il test di utilità (info reperibile in 2
click nella doc ufficiale di un singolo prodotto per i sotto-argomenti già
coperti).

## Prossima sessione consigliata

2026-09-28 o successiva. Se `prop-058` viene eseguita, valutare un secondo
file MySQL (`performance-tuning.md` con query optimizer/indici InnoDB,
speculare a `sql-avanzato/query-optimizer.md`) solo se emerge gap reale.
Altrimenti ruotare focus su `ci-cd/` (non riletto in profondità da diverse
sessioni) o completare il giro `monitoring/tools`/`monitoring/alerting`.
