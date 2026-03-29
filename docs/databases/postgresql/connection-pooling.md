---
title: "Connection Pooling — PgBouncer"
slug: connection-pooling
category: databases
tags: [postgresql, pgbouncer, connection-pooling, performance, scalabilità]
search_keywords: [pgbouncer, connection pool, connection pooling postgresql, transaction mode, session mode, statement mode, max_client_conn, default_pool_size, server_pool_mode, pgpool-ii, pg_bouncer, connection overhead, fork per connection, prepared statements pooling, server_idle_timeout, client_idle_timeout, pgbouncer admin, pgbouncer stats, pooler exporter, connection saturation]
parent: databases/postgresql/_index
related: [databases/postgresql/replicazione, databases/postgresql/mvcc-vacuum, databases/kubernetes-cloud/db-su-kubernetes]
official_docs: https://www.pgbouncer.org/config.html
status: complete
difficulty: intermediate
last_updated: 2026-03-29
---

# Connection Pooling — PgBouncer

## Panoramica

PostgreSQL usa un processo separato per ogni connessione client (architettura process-per-connection). Ogni `fork()` costa circa 5-10MB di RAM e qualche millisecondo di CPU. Con applicazioni che aprono centinaia o migliaia di connessioni — soprattutto con deployment su Kubernetes dove ogni pod ha il suo pool — PostgreSQL si degrada prima per esaurimento di risorse di sistema che per carico SQL.

**PgBouncer** è un connection pooler leggero (scritto in C, ~1MB RAM idle) che si posiziona tra l'applicazione e PostgreSQL, riutilizzando le connessioni al server. L'applicazione vede un PostgreSQL normale sulla porta 5432 (o 6432); PgBouncer mantiene un pool ridotto di connessioni reali al server.

!!! warning "PgBouncer non è opzionale in produzione"
    Su istanze con >100 connessioni simultanee, PgBouncer (o equivalent) è praticamente obbligatorio. AWS RDS, Aurora e la maggior parte dei managed service lo raccomandano esplicitamente. RDS Proxy è essenzialmente PgBouncer as-a-service.

## Concetti Chiave

### I Tre Pool Mode

| Modalità | Quando rilascia la connessione al pool | Compatibilità | Performance |
|----------|----------------------------------------|---------------|-------------|
| **Session** | Quando il client si disconnette | Totale | Bassa (nessun risparmio) |
| **Transaction** | Dopo ogni COMMIT/ROLLBACK | Alta (con limitazioni) | Alta |
| **Statement** | Dopo ogni singola statement | Bassa (no transazioni multi-statement) | Massima |

**Transaction mode** è la scelta standard per la quasi totalità delle applicazioni web.

**Limitazioni di Transaction Mode:**
- `SET` e variabili di sessione (es. `SET search_path = myschema`) non sopravvivono tra transazioni — la connessione potrebbe andare a un client diverso
- `LISTEN/NOTIFY` richiede session mode
- Prepared statements: richiedono configurazione specifica (`max_prepared_statements`)
- `DECLARE CURSOR` senza `HOLD` non funziona cross-transaction

### Anatomia del Pool

```
App Pod 1 (20 connessioni) ─┐
App Pod 2 (20 connessioni) ─┤──> PgBouncer ──> PostgreSQL (10 connessioni server)
App Pod 3 (20 connessioni) ─┘
App Pod 4 (20 connessioni) ─┘
                              60 client conn      10 server conn
                              max_client_conn=200  default_pool_size=10
```

Se tutte le 10 connessioni server sono occupate, i client vengono messi in coda (fino a `server_connect_timeout`). PgBouncer non rifiuta richieste — le serializza.

### Pool Size — Formula

```
# Regola empirica:
pool_size = num_cores * 2  (per workload CPU-bound)
pool_size = num_cores * 4  (per workload I/O-bound)

# Esempio: RDS db.r6g.4xlarge (16 vCPU), I/O-bound
pool_size = 16 * 4 = 64 connessioni al server

# Con 10 pod applicativi che usano PgBouncer:
max_client_conn = 10 * 50 = 500 connessioni client
```

La formula di PostgreSQL per il massimo teorico: `max_connections = (RAM - shared_buffers) / (work_mem * average_concurrent_queries)`. In pratica, `max_connections = 100-400` è il range comune.

---

## Configurazione

### pgbouncer.ini

```ini
[databases]
# Format: db_alias = host=... port=... dbname=...
myapp = host=postgres-primary port=5432 dbname=myapp_db

# Read replica (opzionale, per read splitting manuale)
myapp_ro = host=postgres-replica port=5432 dbname=myapp_db

# Wildcard: tutte le connessioni a qualsiasi db vengono accettate
# * = host=postgres-primary

[pgbouncer]
# ─── Connessioni ──────────────────────────────────────────────────────────
listen_addr = 0.0.0.0
listen_port = 5432                # PgBouncer ascolta su 5432 (stessa porta di PostgreSQL)

# ─── Pool mode ────────────────────────────────────────────────────────────
pool_mode = transaction            # transaction è lo standard per app web

# ─── Limiti pool ──────────────────────────────────────────────────────────
max_client_conn = 1000             # Max connessioni client totali
default_pool_size = 25             # Connessioni server per (database, user) pair
min_pool_size = 5                  # Mantieni almeno N connessioni server attive
reserve_pool_size = 5              # Connessioni extra se pool è saturo
reserve_pool_timeout = 3           # Usa reserve se pool pieno per >3s

# ─── Timeout ──────────────────────────────────────────────────────────────
server_idle_timeout = 600          # Chiudi connessione server idle da >10min
client_idle_timeout = 0            # 0 = mai disconnettere client idle (l'app gestisce)
server_connect_timeout = 15        # Timeout per connessione a PostgreSQL
query_timeout = 0                  # 0 = nessun timeout query (gestisce l'app)
query_wait_timeout = 120           # Dopo 120s in coda → errore al client

# ─── Autenticazione ───────────────────────────────────────────────────────
auth_type = scram-sha-256          # scram-sha-256 o md5 (evitare plain)
auth_file = /etc/pgbouncer/userlist.txt

# ─── Admin ────────────────────────────────────────────────────────────────
admin_users = pgbouncer_admin      # Utenti che possono fare SHOW STATS
stats_users = monitoring           # Utenti read-only per monitoring
stats_period = 60                  # Aggiorna stats ogni 60s

# ─── Log ──────────────────────────────────────────────────────────────────
log_connections = 0                # 1 = loga ogni connessione (verbose)
log_disconnections = 0
log_pooler_errors = 1
```

```
# /etc/pgbouncer/userlist.txt
# Format: "username" "hashed_password"
# Genera con: psql -c "SELECT rolname, rolpassword FROM pg_authid WHERE rolname='myapp';"
"myapp_user" "SCRAM-SHA-256$4096:..."
"pgbouncer_admin" "SCRAM-SHA-256$4096:..."
```

### Prepared Statements in Transaction Mode

```ini
# pgbouncer.ini — abilita prepared statement caching
max_prepared_statements = 100      # 0 = disabilita, >0 = PgBouncer fa il tracking

# Con max_prepared_statements > 0, PgBouncer trasla i named prepared statement
# (es. "stmt_1") in statement anonimi server-side, rendendoli compatibili con
# il pool mode transaction. Richiede PostgreSQL 14+.
```

```python
# Python psycopg3 — prepared statements funzionano con PgBouncer
# (psycopg3 gestisce il lato client, non usa named server-side prepared statements)
conn = psycopg3.connect(dsn, prepare_threshold=5)
# Dopo 5 esecuzioni, la query viene preparata automaticamente
```

### Docker Compose / Kubernetes

```yaml
# docker-compose.yml
pgbouncer:
  image: pgbouncer/pgbouncer:1.22
  environment:
    POSTGRESQL_HOST: postgres
    POSTGRESQL_PORT: 5432
    POSTGRESQL_DATABASE: myapp_db
    POSTGRESQL_USERNAME: myapp_user
    POSTGRESQL_PASSWORD: ${DB_PASSWORD}
    PGBOUNCER_POOL_MODE: transaction
    PGBOUNCER_MAX_CLIENT_CONN: 500
    PGBOUNCER_DEFAULT_POOL_SIZE: 25
  ports:
    - "5432:5432"
  depends_on:
    - postgres
```

```yaml
# Kubernetes — PgBouncer come sidecar nel Deployment dell'app
# oppure come deployment separato (più comune)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: pgbouncer
spec:
  replicas: 2                      # HA: 2 repliche PgBouncer davanti allo stesso PostgreSQL
  selector:
    matchLabels:
      app: pgbouncer
  template:
    metadata:
      labels:
        app: pgbouncer
    spec:
      containers:
      - name: pgbouncer
        image: pgbouncer/pgbouncer:1.22
        ports:
        - containerPort: 5432
        envFrom:
        - secretRef:
            name: pgbouncer-config
        resources:
          requests:
            memory: "64Mi"
            cpu: "50m"
          limits:
            memory: "128Mi"
            cpu: "500m"
        livenessProbe:
          tcpSocket:
            port: 5432
          periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: pgbouncer
spec:
  selector:
    app: pgbouncer
  ports:
  - port: 5432
    targetPort: 5432
```

---

## Monitoraggio e Diagnostica

### Admin Console

PgBouncer espone una console SQL virtuale (database `pgbouncer`):

```bash
# Connettiti alla console admin
psql -h localhost -p 5432 -U pgbouncer_admin pgbouncer
```

```sql
-- Statistiche pool in tempo reale
SHOW POOLS;
-- database | user       | cl_active | cl_waiting | sv_active | sv_idle | sv_used | maxwait
-- myapp    | myapp_user |        45 |          3 |        25 |       0 |       5 |       2

-- cl_active   = client connessi e con server assegnato
-- cl_waiting  = client in coda (pool saturo) ← monitorare questo!
-- sv_active   = server connection in uso
-- sv_idle     = server connection disponibili nel pool
-- maxwait     = secondi di attesa del client più vecchio in coda

-- Stats aggregate per database (req/s, byte/s, latenza)
SHOW STATS;
-- database | total_xact_count | total_query_count | total_received | avg_xact_time_us

-- Connessioni client attive
SHOW CLIENTS;

-- Connessioni server attive
SHOW SERVERS;

-- Configurazione live
SHOW CONFIG;

-- Ricarica config senza restart
RELOAD;

-- Pausa (drain) — per manutenzione. Le query si sospendono, non falliscono
PAUSE;
RESUME;
```

### Metriche Prometheus

```yaml
# pgbouncer_exporter — espone metriche PgBouncer per Prometheus
# https://github.com/prometheus-community/pgbouncer_exporter

# docker-compose
pgbouncer_exporter:
  image: prometheuscommunity/pgbouncer-exporter:latest
  environment:
    DATA_SOURCE_URI: "localhost:5432/pgbouncer?sslmode=disable"
    DATA_SOURCE_USER: monitoring
    DATA_SOURCE_PASS: ${MONITORING_PASSWORD}
  ports:
    - "9127:9127"
```

```yaml
# Alerting rules critiche
groups:
- name: pgbouncer
  rules:
  - alert: PgBouncerClientWaiting
    expr: pgbouncer_pools_client_waiting_connections > 5
    for: 30s
    annotations:
      summary: "PgBouncer: {{ $value }} client in attesa — pool saturo"

  - alert: PgBouncerMaxWaitHigh
    expr: pgbouncer_pools_client_maxwait_seconds > 10
    for: 1m
    annotations:
      summary: "PgBouncer: client aspetta {{ $value }}s — aumentare pool size o debug query lente"

  - alert: PgBouncerNoServerConnections
    expr: pgbouncer_pools_server_active_connections + pgbouncer_pools_server_idle_connections == 0
    for: 1m
    annotations:
      summary: "PgBouncer: nessuna connessione server — PostgreSQL irraggiungibile?"
```

---

## Best Practices

- **Transaction mode per default**: per ogni applicazione web stateless (HTTP API). Evitare session mode tranne casi specifici (LISTEN/NOTIFY, sessione utente persistente)
- **pool_size = num_CPU * 2-4**: non aumentare pool_size oltre questo range — più connessioni = più context switch = peggioramento. Il bottleneck è PostgreSQL, non PgBouncer
- **2 istanze PgBouncer per HA (High Availability)**: PgBouncer è stateless — 2 repliche davanti allo stesso PostgreSQL garantiscono HA senza complessità. In Kubernetes usare un Service con 2 pod
- **Sidecar vs deployment dedicato**: sidecar (PgBouncer nel pod dell'app) massimizza il controllo per pod; deployment dedicato riduce i processi. In Kubernetes il deployment dedicato è più comune
- **Non usare PgBouncer per PostgreSQL gestito (RDS, Cloud SQL)**: AWS RDS Proxy, Cloud SQL Auth Proxy e simili integrano già il connection pooling — aggiungere PgBouncer davanti crea doppio pooling senza benefici

## Troubleshooting

### Scenario 1 — Prepared statement già esistente

**Sintomo:** L'applicazione riceve `ERROR: prepared statement "stmt_X" already exists` in transaction mode.

**Causa:** L'app usa named server-side prepared statements (es. via JDBC, libpq o driver ORM) che non vengono deallocati tra transazioni — in transaction mode la connessione server viene riassegnata a un altro client senza `DEALLOCATE`.

**Soluzione:** Abilitare il tracking PgBouncer oppure usare statement anonimi lato driver.

```ini
# pgbouncer.ini — abilita il remapping dei prepared statement
max_prepared_statements = 100   # PgBouncer traccia e traduce i named PS

# Oppure, a livello driver (JDBC), disabilitare i server-side prepared statement:
# jdbc:postgresql://host:5432/db?prepareThreshold=0
```

```sql
-- Verifica prepared statement attivi sul server
SELECT name, statement, prepare_time
FROM pg_prepared_statements;

-- Pulizia manuale se necessario
DEALLOCATE ALL;
```

---

### Scenario 2 — Pool saturo: `cl_waiting` alto

**Sintomo:** `SHOW POOLS` riporta `cl_waiting > 0` in modo persistente; le query subiscono latenza insolita o timeout con `ERROR: query_wait_timeout`.

**Causa:** `default_pool_size` è troppo basso rispetto al carico, oppure esistono query lente che tengono occupate le connessioni server.

**Soluzione:** Diagnosticare prima se il problema è il pool size o le query lente.

```sql
-- 1. Controlla pool in tempo reale
psql -h localhost -p 5432 -U pgbouncer_admin pgbouncer -c "SHOW POOLS;"

-- 2. Identifica query lente su PostgreSQL
SELECT pid, now() - pg_stat_activity.query_start AS duration, query, state
FROM pg_stat_activity
WHERE state != 'idle' AND query_start < now() - interval '5 seconds'
ORDER BY duration DESC;

-- 3. Top query per tempo totale (richiede pg_stat_statements)
SELECT query, calls, total_exec_time/calls AS avg_ms, rows
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 20;
```

```ini
# pgbouncer.ini — aumentare pool solo dopo aver escluso query lente
default_pool_size = 40      # era 25
reserve_pool_size = 10
```

---

### Scenario 3 — Connessioni esaurite: `no more connections allowed`

**Sintomo:** `ERROR: no more connections allowed (max_client_conn)` — nuovi client vengono rifiutati.

**Causa:** Il totale di connessioni client ha raggiunto `max_client_conn`. Tipico con scaling orizzontale dell'app (molti pod Kubernetes) o connection leak.

**Soluzione:** Verificare chi occupa le connessioni, poi agire su `max_client_conn` o ridurre i leak.

```sql
-- Verifica connessioni client correnti
psql -h localhost -p 5432 -U pgbouncer_admin pgbouncer -c "SHOW CLIENTS;"

-- Quante connessioni apre ogni pod applicativo?
psql -h localhost -p 5432 -U pgbouncer_admin pgbouncer -c "SHOW STATS;"
```

```ini
# pgbouncer.ini — aumentare il limite (verificare prima i limiti OS: ulimit -n)
max_client_conn = 2000

# Impostare anche un idle timeout per forzare la chiusura di connessioni abbandonate
client_idle_timeout = 300   # 5 minuti
```

---

### Scenario 4 — PostgreSQL irraggiungibile: `server_connect_timeout` ricorrente

**Sintomo:** Log PgBouncer pieno di `server_connect_timeout`; `SHOW POOLS` mostra `sv_active=0, sv_idle=0`; l'app riceve errori di connessione.

**Causa:** PostgreSQL ha raggiunto `max_connections`, è sovraccarico, o non è raggiungibile per problemi di rete/crash.

**Soluzione:** Diagnosticare su PostgreSQL direttamente.

```bash
# Test connettività diretta (esclude PgBouncer dalla diagnosi)
psql -h postgres-primary -p 5432 -U myapp_user myapp_db -c "SELECT 1;"

# Verifica connessioni attive su PostgreSQL
psql -h postgres-primary -U postgres -c "
SELECT count(*), state, wait_event_type, wait_event
FROM pg_stat_activity
GROUP BY state, wait_event_type, wait_event
ORDER BY count DESC;"

# Verifica max_connections e uso corrente
psql -h postgres-primary -U postgres -c "
SELECT current_setting('max_connections')::int AS max_conn,
       count(*) AS current_conn,
       current_setting('max_connections')::int - count(*) AS available
FROM pg_stat_activity;"
```

---

### Scenario 5 — Pool mai in warm-up: `sv_idle=0` costante

**Sintomo:** `SHOW POOLS` riporta sempre `sv_idle=0` anche a basso carico; ogni richiesta paga il costo di apertura connessione.

**Causa:** `server_idle_timeout` troppo basso chiude le connessioni prima che vengano riutilizzate, oppure `min_pool_size=0` e il pool viene svuotato tra i burst.

**Soluzione:** Aumentare `min_pool_size` e rivedere i timeout.

```ini
# pgbouncer.ini — mantieni connessioni pre-aperte
min_pool_size = 5           # Connessioni server sempre attive nel pool
server_idle_timeout = 600   # Non chiudere connessioni idle per almeno 10min (default)

# Verifica la configurazione live senza restart
# psql -h localhost -p 5432 -U pgbouncer_admin pgbouncer -c "SHOW CONFIG;"
```

```bash
# Reload config senza restart (applica min_pool_size e timeout immediatamente)
psql -h localhost -p 5432 -U pgbouncer_admin pgbouncer -c "RELOAD;"

# Monitora il warm-up
watch -n 2 'psql -h localhost -p 5432 -U pgbouncer_admin pgbouncer -c "SHOW POOLS;"'
```

## Relazioni

??? info "MVCC e Vacuum — PostgreSQL internals"
    Le transazioni corte beneficiano maggiormente di transaction mode poiché MVCC accumula dead tuple proporzionalmente alla durata delle transazioni.

    **Approfondimento →** [MVCC e Vacuum](mvcc-vacuum.md)

??? info "PostgreSQL su Kubernetes — Deployment pattern"
    PgBouncer viene tipicamente deployato come Deployment separato o come sidecar nei pod applicativi.

    **Approfondimento →** [Database su Kubernetes](../kubernetes-cloud/db-su-kubernetes.md)

## Riferimenti

- [PgBouncer Documentation](https://www.pgbouncer.org/config.html)
- [PgBouncer FAQ — Transaction Mode Limitations](https://www.pgbouncer.org/faq.html)
- [Citus — Choosing the Right Pool Size](https://docs.citusdata.com/en/stable/performance/performance_tuning.html)
- [AWS RDS Proxy vs PgBouncer](https://aws.amazon.com/blogs/database/using-amazon-rds-proxy-with-amazon-rds-for-postgresql/)
