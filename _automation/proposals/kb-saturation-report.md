# KB Saturation Report — 2026-09-27 (sessione #610)

## Gate meccanico

```
file_count: 314, target: 330, over_target: false, headroom: 16
category_saturated_pct: 85, allow_zero_proposals: true
```

Sotto target. Focus ruotato su `docs/dev/` (raccomandazione del report #609:
"mai stato in focus esplicito, categoria ampia e potenzialmente eterogenea").

## Copertura stimata per categoria

| Categoria | Files | Coverage % | Depth | Note |
|-----------|-------|------------|-------|------|
| dev/ | 27 | ~85% | Alta: la maggior parte delle sottocategorie usa il pattern "1 file `_index.md` = trattazione completa del tema" (testing, data, resilienza, sicurezza, integrazioni, api) invece di molti file piccoli — verificato NON un problema, sono file lunghi e completi (500-950 righe) | 2 gap reali trovati: GraphQL promesso ma assente, Node.js citato ma senza file |
| databases/ | 31 | ~90% | Alta: fondamentali, postgresql, mysql, nosql, sql-avanzato, replicazione-ha, kubernetes-cloud tutti con più file coerenti | Nessun gap reale trovato (mysql confrontato con postgresql: profondità paragonabile, 2 file densi vs 4 più mirati) |

## Analisi di questa sessione

File analizzati (9): `dev/testing/_index.md`, `dev/data/_index.md`, `dev/_index.md`,
`dev/api/_index.md`, `dev/integrazioni/_index.md`, `dev/resilienza/_index.md`,
`dev/sicurezza/_index.md`, `dev/linguaggi/_index.md`, `databases/_index.md` (+
`databases/mysql/_index.md` come decimo).

**Verificato NON un gap — Testing e Data Layer come "subcat da 1 file"**:
ipotesi iniziale (dal report #609) che `dev/testing/` e `dev/data/` fossero
sottodimensionati (contengono solo un `_index.md` ciascuno). Lettura integrale
mostra che sono file completi di 500-950 righe con Panoramica, Concetti Chiave,
Architettura, Configurazione & Pratica multi-linguaggio (Java/Python/Go),
Best Practices, Troubleshooting con 4+ problemi documentati — non stub.
Pattern coerente con `messaging/rabbitmq` (già validato in sessione #609).

**Gap reale #1 — GraphQL promesso ma assente in `dev/api/_index.md`**: il
frontmatter (`tags: [..., graphql, ...]`) e la Panoramica di `dev/_index.md`
("REST, gRPC, GraphQL, AsyncAPI") annunciano GraphQL come uno dei paradigmi
trattati, ma il corpo del file ha sezioni solo per REST, gRPC e AsyncAPI.
→ prop-063 (extend-section).

**Gap reale #2 — Node.js citato ma senza file dedicato**: `dev/linguaggi/_index.md`
include Node.js nella tabella comparativa con metriche complete (startup,
footprint, throughput, "Ideal per: I/O bound, BFF") e nei `tags`/
`search_keywords`, ma la lista "Argomenti in questa sezione" ha file solo per
Java Spring Boot, Java Quarkus, .NET, Go, Python. Asimmetria non di design —
gli altri 4 linguaggi della stessa tabella hanno tutti un file dedicato.
→ prop-064 (new-file).

**Verificato NON un gap — MySQL vs PostgreSQL**: MySQL ha 2 file (Architettura
e Replicazione, Performance Tuning) contro i 4 di PostgreSQL, ma la
profondità per file è comparabile (replicazione binlog/GTID, Group
Replication, Galera, InnoDB internals coperti in un solo file denso). Non un
gap — solo organizzazione diversa.

## Categorie vicine alla saturazione

- **dev/testing, dev/data, dev/resilienza, dev/sicurezza, dev/integrazioni**:
  confermati saturi in questa sessione — file singoli ma completi, nessuna
  sezione mancante rispetto alla loro Panoramica dichiarata.
- **databases/**: nessun gap reale trovato, coverage alta e coerente.
- **security/**, **messaging/rabbitmq**, **networking**, **cloud/aws**,
  **ci-cd/testing**: confermati saturi nelle sessioni precedenti (#591-596,
  #607, #609).

## Categorie con gap reali

- **dev/api/**: GraphQL promesso nel frontmatter/file padre, mai trattato nel
  corpo (prop-063).
- **dev/linguaggi/**: Node.js citato in tabella comparativa senza file
  dedicato, a differenza di tutti gli altri linguaggi elencati (prop-064).

## Focus usato in questa sessione

`docs/dev/` (rotazione da report #609: "mai stato in focus esplicito").
Trovati 2 gap reali circoscritti (non strutturali — la categoria nel
complesso è matura), a differenza delle 2 sessioni precedenti (#607, #609)
che avevano chiuso a zero proposte.

## Prossima sessione consigliata

2026-09-28 o successiva, focus `docs/databases/` (verificato in questa
sessione solo su `_index` + `mysql/_index`, non ancora letti in profondità i
file di dettaglio: `postgresql/extensions.md`, `nosql/cassandra.md`,
`kubernetes-cloud/db-su-kubernetes.md`) e/o completamento di `docs/dev/`
(sottocategorie non ancora verificate in questa sessione: `runtime`,
`processi`, e i file di dettaglio di `linguaggi` — `go.md`, `python.md`,
`java-spring-boot.md`, `java-quarkus.md`, `dotnet.md` — per verificare se
contengono gap interni oltre all'assenza di Node.js già segnalata).
