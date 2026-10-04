---
title: "Debezium e Change Data Capture"
slug: debezium-cdc
category: messaging
tags: [kafka, debezium, cdc, change-data-capture, postgresql, mysql]
search_keywords: [debezium cdc, change data capture kafka, debezium postgresql, debezium mysql, wal binlog kafka, outbox debezium, data replication kafka, cdc connector, kafka connect cdc, logical replication slot, pgoutput, binlog replication, event sourcing cdc, debezium snapshot, database change events, wal2json, debezium offset]
parent: messaging/kafka/kafka-connect
related: [messaging/kafka/pattern-microservizi/outbox-pattern, messaging/kafka/kafka-connect/source-connectors]
official_docs: https://debezium.io/documentation/
status: reviewed
difficulty: advanced
last_updated: 2026-10-04
last_verified: 2026-10-04
---

# Debezium e Change Data Capture

## Panoramica

**Debezium** è una piattaforma open source per il **Change Data Capture (CDC)**: legge il log delle transazioni del database (WAL per PostgreSQL, binlog per MySQL) e pubblica ogni insert, update e delete come evento su Kafka in tempo reale. A differenza del polling JDBC, CDC è event-driven: le modifiche vengono catturate immediatamente e il carico sul database è minimo.

**Quando usarlo:** Data replication cross-sistema, implementazione del pattern Outbox, event sourcing da sistemi legacy, sincronizzazione near-real-time tra database.

**Quando NON usarlo:** Database che non espongono il log delle transazioni (es. alcune versioni di cloud database con log access limitato), sistemi dove il volume di modifiche è estremo e il parsing del WAL diventa collo di bottiglia.

## Concetti Chiave

**WAL (Write-Ahead Log)** — PostgreSQL scrive ogni modifica nel WAL prima di applicarla al database. Debezium legge il WAL tramite il protocollo di **logical replication** di PostgreSQL.

**Binlog** — MySQL/MariaDB usa il binary log per la replicazione. Debezium si connette come uno slave di replicazione.

**Snapshot iniziale** — Alla prima connessione, Debezium effettua uno snapshot dell'intero database (o delle tabelle configurate) per inizializzare lo stato. Poi passa al CDC in streaming.

**Evento CDC** — Ogni record Kafka prodotto da Debezium contiene:
- `before`: stato della riga prima della modifica (null per INSERT)
- `after`: stato della riga dopo la modifica (null per DELETE)
- `op`: tipo operazione (`c`=create/insert, `u`=update, `d`=delete, `r`=read/snapshot)
- `source`: metadati (database, tabella, timestamp, LSN/binlog position)

**Offset Debezium** — La posizione nel WAL/binlog viene salvata da Kafka Connect nel topic degli offset (`OFFSET_STORAGE_TOPIC`, negli esempi `debezium-offsets`). Garantisce la ripresa dal punto giusto dopo un restart. Delivery **at-least-once**: dopo un crash alcuni eventi possono essere riemessi, i consumer devono essere idempotenti.

**REPLICA IDENTITY (PostgreSQL)** — Determina cosa finisce nel WAL come "vecchia" riga per UPDATE/DELETE. Col default (`DEFAULT`) `before` contiene solo la chiave primaria (e `null` se la chiave non cambia in un UPDATE sulle altre colonne). Per avere `before` completo: `ALTER TABLE orders REPLICA IDENTITY FULL;` (più WAL scritto, quindi usarlo solo dove serve).

## Architettura / Come Funziona

```mermaid
flowchart LR
    subgraph DB["PostgreSQL"]
        T1[(orders)]
        T2[(payments)]
        WAL["WAL\nLogical Replication Slot"]
    end

    subgraph Connect["Kafka Connect"]
        DEB["Debezium\nPostgreSQL Connector"]
    end

    subgraph Kafka
        K1[db.public.orders]
        K2[db.public.payments]
        OFFS[debezium-offsets]
    end

    subgraph Consumers
        SVC1[Microservizio A]
        SVC2[Elasticsearch Sync]
        SVC3[Analytics Pipeline]
    end

    WAL -->|Logical replication| DEB
    DEB --> K1
    DEB --> K2
    DEB <--> OFFS
    K1 --> SVC1
    K1 --> SVC2
    K2 --> SVC3
```

**Flusso di un UPDATE:**
1. L'applicazione esegue `UPDATE orders SET status='shipped' WHERE id=123`
2. PostgreSQL scrive la modifica nel WAL
3. Debezium legge il record dal WAL tramite la logical replication slot
4. Pubblica su `db.public.orders` un record con `op=u`, `before={...old state...}`, `after={...new state...}`
5. I consumer ricevono l'evento e reagiscono (es. sincronizzano Elasticsearch)

## Configurazione & Pratica

### Configurare PostgreSQL per logical replication

```sql
-- postgresql.conf
-- wal_level = logical  (richiede restart)
-- max_replication_slots = 10
-- max_wal_senders = 10

-- Creare un utente dedicato per Debezium
CREATE USER debezium WITH REPLICATION LOGIN PASSWORD 'debezium_secret';

-- Concedere accesso alle tabelle
GRANT SELECT ON ALL TABLES IN SCHEMA public TO debezium;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO debezium;

-- Creare una publication (FOR ALL TABLES richiede superuser).
-- In produzione preferire un elenco esplicito di tabelle, creato da un admin:
-- CREATE PUBLICATION debezium_pub FOR TABLE public.orders, public.payments;
CREATE PUBLICATION debezium_pub FOR ALL TABLES;
```

### Docker Compose: PostgreSQL + Kafka + Debezium

!!! note "Versioni immagini"
    L'esempio usa Debezium 3.7.0.Final (ottobre 2026; connector Java 17+, Kafka Connect 3.1+). Le immagini sono pubblicate su `quay.io/debezium/connect`, non più su Docker Hub. Preferire tag completi (`3.7.0.Final`) a `latest`/`3.7`, che sono mobili.

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: mydb
    command:
      - "postgres"
      - "-c"
      - "wal_level=logical"
      - "-c"
      - "max_replication_slots=10"
    ports:
      - "5432:5432"

  kafka:
    image: apache/kafka:3.9.0
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: 'broker,controller'
      KAFKA_CONTROLLER_QUORUM_VOTERS: '1@kafka:9093'
      KAFKA_LISTENERS: 'PLAINTEXT://kafka:29092,CONTROLLER://kafka:9093,PLAINTEXT_HOST://0.0.0.0:9092'
      KAFKA_ADVERTISED_LISTENERS: 'PLAINTEXT://kafka:29092,PLAINTEXT_HOST://localhost:9092'
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: 'CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT'
      KAFKA_CONTROLLER_LISTENER_NAMES: 'CONTROLLER'
      CLUSTER_ID: '5L6g3nShT-eMCtK--X86sw'  # UUID base64 di 22 caratteri (kafka-storage random-uuid)
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1
    ports:
      - "9092:9092"

  kafka-connect:
    image: quay.io/debezium/connect:3.7.0.Final
    depends_on:
      - kafka
      - postgres
    environment:
      BOOTSTRAP_SERVERS: kafka:29092
      GROUP_ID: debezium-cluster
      CONFIG_STORAGE_TOPIC: debezium-configs
      OFFSET_STORAGE_TOPIC: debezium-offsets
      STATUS_STORAGE_TOPIC: debezium-status
    ports:
      - "8083:8083"
```

### Registrare il connector PostgreSQL

```bash
curl -X POST http://localhost:8083/connectors \
  -H "Content-Type: application/json" \
  -d '{
    "name": "postgres-cdc-connector",
    "config": {
      "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
      "database.hostname": "postgres",
      "database.port": "5432",
      "database.user": "debezium",
      "database.password": "debezium_secret",
      "database.dbname": "mydb",
      "topic.prefix": "db",
      "table.include.list": "public.orders,public.payments",

      "plugin.name": "pgoutput",
      "publication.name": "debezium_pub",
      "slot.name": "debezium_slot",

      "snapshot.mode": "initial",
      "snapshot.isolation.mode": "repeatable_read",

      "heartbeat.interval.ms": "10000",

      "transforms": "unwrap",
      "transforms.unwrap.type": "io.debezium.transforms.ExtractNewRecordState",
      "transforms.unwrap.drop.tombstones": "false",
      "transforms.unwrap.delete.handling.mode": "rewrite",
      "transforms.unwrap.add.fields": "op,source.ts_ms"
    }
  }'
```

**Topic generati:** `db.public.orders`, `db.public.payments` (`<topic.prefix>.<schema>.<tabella>`). `database.server.name` è stato rimosso in Debezium 2.0: oggi si usa solo `topic.prefix`.

Con l'`unwrap` configurato qui il valore dei record è già "piatto" (vedi SMT sotto); l'envelope completo seguente è ciò che si ottiene **senza** la trasformazione.

### Struttura di un evento CDC (senza unwrap)

```json
{
  "schema": { "..." },
  "payload": {
    "before": null,
    "after": {
      "id": 123,
      "customer_id": 456,
      "status": "created",
      "amount": 99.99,
      "created_at": "2026-02-23T14:30:00Z"
    },
    "source": {
      "version": "3.7.0.Final",
      "connector": "postgresql",
      "name": "db",
      "ts_ms": 1740321000000,
      "db": "mydb",
      "schema": "public",
      "table": "orders",
      "lsn": 33058752
    },
    "op": "c",
    "ts_ms": 1740321001234
  }
}
```

### SMT ExtractNewRecordState (unwrap)

La trasformazione `ExtractNewRecordState` semplifica la struttura dell'evento estraendo solo il campo `after` (lo stato corrente della riga):

```json
{
  "id": 123,
  "customer_id": 456,
  "status": "created",
  "amount": 99.99,
  "__op": "c",
  "__deleted": "false",
  "__source_ts_ms": 1740321000000
}
```

## Best Practices

!!! tip "Usare pgoutput su PostgreSQL"
    `plugin.name=pgoutput` è il plugin di replication nativo di PostgreSQL 10+ e non richiede estensioni aggiuntive. Preferirlo a `wal2json` o `decoderbufs`.

!!! warning "Gestire la replication slot con cura"
    Una replication slot in PostgreSQL trattiene il WAL finché Debezium non lo ha letto. Se Debezium è fermo a lungo, il WAL cresce indefinitamente fino a riempire il disco. Monitorare `pg_replication_slots` (WAL trattenuto) con alert e impostare `max_slot_wal_keep_size` (PostgreSQL 13+) come rete di sicurezza: oltre il limite lo slot viene invalidato (`wal_status=lost`) e serve un nuovo snapshot, ma il database sorgente non si ferma. Droppare gli slot di connector dismessi.

!!! tip "Heartbeat per evitare WAL retention su tabelle non attive"
    Con `heartbeat.interval.ms` Debezium emette heartbeat e conferma l'LSN letto anche quando le tabelle monitorate sono ferme ma il database genera WAL per altre tabelle, così PostgreSQL può liberarlo. Se il database è del tutto inattivo l'LSN non avanza comunque: in quel caso aggiungere `heartbeat.action.query` (es. un `UPDATE` su una tabella di heartbeat inclusa nella publication) per generare una modifica.

!!! warning "Snapshot iniziale su tabelle grandi"
    Lo snapshot legge l'intera tabella in una singola transazione. Su tabelle da milioni di righe, può richiedere ore. Pianificare la prima connessione con attenzione. Usare `snapshot.mode=no_data` (storico `schema_only`) se non serve lo stato iniziale, oppure i **signal ad-hoc / incremental snapshot** per ricaricare singole tabelle senza fermare lo streaming.

## Troubleshooting

### Scenario 1 — Replication slot già esistente

**Sintomo:** Il connector non si avvia e nei log compare `ERROR: replication slot "debezium_slot" is active for PID <n>` (oppure `already exists` se si crea lo slot a mano con lo stesso nome).

**Causa:** Debezium normalmente **riusa** uno slot esistente. L'errore "is active" compare quando la vecchia connessione di replica è ancora aperta (crash, task zombie, due connector con lo stesso `slot.name`). Ogni connector deve avere uno `slot.name` univoco.

**Soluzione:** Verificare lo stato dello slot; se la sessione è orfana terminarla, e rimuovere lo slot solo se il connector è dismesso (si perde la posizione e serve un nuovo snapshot).

```sql
-- Controllare slot esistenti e il loro stato
SELECT slot_name, active, active_pid, restart_lsn, wal_status
FROM pg_replication_slots;

-- Sessione orfana: terminare il backend che tiene lo slot
SELECT pg_terminate_backend(active_pid) FROM pg_replication_slots
WHERE slot_name = 'debezium_slot' AND active;

-- Solo se il connector è dismesso (active = false): eliminare lo slot
SELECT pg_drop_replication_slot('debezium_slot');
```

---

### Scenario 2 — Alto lag del connector (Debezium indietro rispetto al DB)

**Sintomo:** Gli eventi Kafka arrivano con ritardo crescente rispetto alle scritture sul database; il WAL trattenuto dallo slot cresce.

**Causa:** Un source connector non è un consumer: non ha consumer lag. Il ritardo sta nella lettura del WAL → Kafka: batch/queue troppo piccoli, produce lento verso il broker, SMT costose, o snapshot in corso su tabelle grandi.

**Soluzione:** Misurare il lag lato sorgente (JMX `MilliSecondsBehindSource`, o `retained_wal` su `pg_replication_slots`, vedi Scenario 4), poi aumentare i buffer. `max.batch.size` e `max.queue.size` sono proprietà **del connector** (non di `connect-distributed.properties`); `PUT .../config` sostituisce l'intera configurazione, quindi va inviata completa.

```bash
# Config corrente del connector (da modificare e rimandare per intero)
curl -s http://localhost:8083/connectors/postgres-cdc-connector/config | jq . > cfg.json
# aggiungere in cfg.json: "max.batch.size": "8192", "max.queue.size": "16384"
curl -X PUT http://localhost:8083/connectors/postgres-cdc-connector/config \
  -H "Content-Type: application/json" -d @cfg.json
```

---

### Scenario 3 — Record con `op=r` invece di `op=c`

**Sintomo:** I consumer ricevono eventi con `"op": "r"` che non corrispondono a inserimenti reali.

**Causa:** `op=r` (read) indica record provenienti dallo snapshot iniziale, non da modifiche live. È il comportamento atteso alla prima connessione con `snapshot.mode=initial`.

**Soluzione:** Trattare `r` come upsert nei consumer (stesso effetto di `c`), filtrarlo se lo snapshot non serve, oppure saltarlo con `snapshot.mode=no_data` (in Debezium < 2.6 chiamato `schema_only`). Lo snapshot viene eseguito solo se non esiste già un offset: cambiare il mode su un connector già avviato non lo riesegue.

```bash
# Impostare snapshot.mode (config completa, vedi Scenario 2: PUT sostituisce tutto)
curl -s http://localhost:8083/connectors/postgres-cdc-connector/config \
  | jq '."snapshot.mode"="no_data"' \
  | curl -X PUT http://localhost:8083/connectors/postgres-cdc-connector/config \
      -H "Content-Type: application/json" -d @-

# Verificare lo stato corrente del connector
curl http://localhost:8083/connectors/postgres-cdc-connector/status | jq .
```

---

### Scenario 4 — Disco pieno su PostgreSQL per WAL retention

**Sintomo:** Il disco del server PostgreSQL si riempie; `pg_replication_slots` mostra `wal_status=lost` o `retained_wal` molto elevato.

**Causa:** La replication slot trattiene tutto il WAL generato finché Debezium non lo legge. Se Debezium è fermo (crash, manutenzione), il WAL si accumula.

**Soluzione:** Monitorare proattivamente il WAL trattenuto e configurare un limite.

```sql
-- Monitorare WAL trattenuto da ogni slot
SELECT slot_name, active,
       pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)) AS retained_wal,
       wal_status
FROM pg_replication_slots;

-- In emergenza (Debezium fermo, disco in esaurimento): eliminare il slot
-- ATTENZIONE: il prossimo avvio ripartirà dallo snapshot iniziale
SELECT pg_drop_replication_slot('debezium_slot');
```

```ini
# postgresql.conf — impostare un limite di WAL per slot (PostgreSQL 13+)
max_slot_wal_keep_size = 10GB
```

## Riferimenti

- [Debezium Documentation](https://debezium.io/documentation/)
- [Debezium PostgreSQL Connector](https://debezium.io/documentation/reference/stable/connectors/postgresql.html)
- [Debezium MySQL Connector](https://debezium.io/documentation/reference/stable/connectors/mysql.html)
- [ExtractNewRecordState SMT](https://debezium.io/documentation/reference/stable/transformations/event-flattening.html)
