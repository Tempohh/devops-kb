---
title: "Connection Pooling e Proxy — ProxySQL"
slug: connection-pooling-proxysql
category: databases
tags: [mysql, mariadb, proxysql, connection-pooling, high-availability, performance]
search_keywords: [proxysql, connection pooling mysql, mysql proxy, query routing, read write split, maxscale, rds proxy, mysql_servers, mysql_query_rules, mysql_replication_hostgroups, thread_cache_size, max_connections mysql, connection multiplexing, query cache proxysql, query rewrite, proxysql cluster, failover mysql proxy, orchestrator, group replication, admin interface 6032]
parent: databases/mysql/_index
related: [databases/postgresql/connection-pooling, databases/mysql/architettura-replicazione, databases/kubernetes-cloud/managed-databases]
official_docs: https://proxysql.com/documentation/
status: complete
difficulty: advanced
last_updated: 2026-10-02
---

# Connection Pooling e Proxy — ProxySQL

## Panoramica

MySQL usa un modello **thread-per-connection**: ogni connessione client ottiene un thread OS dedicato (o uno dal `thread_cache`), non un processo come PostgreSQL. Questo è più leggero di un `fork()`, ma non gratis — ogni thread tiene allocati buffer di sort (`sort_buffer_size`), join (`join_buffer_size`) e di rete finché la connessione resta aperta, e questi buffer **non** sono condivisi con il buffer pool InnoDB. Con migliaia di connessioni applicative simultanee (tipico con pod Kubernetes, funzioni serverless o pool applicativi configurati troppo larghi), la memoria per-thread può superare il buffer pool stesso, e il context switching tra migliaia di thread degrada il throughput prima ancora che la query diventi il collo di bottiglia.

**ProxySQL** è un livello di proxy/pooling che si inserisce tra applicazione e MySQL: espone un endpoint MySQL-compatibile, multiplexa le connessioni client su un pool ridotto di connessioni server, instrada le query (read/write split, sharding logico) e assorbe il failover del primary. A differenza di PgBouncer — che fa solo pooling — ProxySQL è anche un router L7 con query cache e rewrite integrati, pagando in cambio una configurazione più complessa (tabelle SQL invece di un file `.ini`).

!!! warning "ProxySQL non sostituisce da solo l'alta disponibilità"
    ProxySQL instrada il traffico verso il primary corretto, ma **non decide** chi è il primary: serve un meccanismo esterno di failover (Orchestrator, MySQL Group Replication, Galera) che aggiorna gli hostgroup di ProxySQL. Senza questa integrazione, un failover manuale lascia ProxySQL a instradare scritture verso un nodo ormai read-only.

## Concetti Chiave

- **Hostgroup**: raggruppamento logico di server MySQL con lo stesso ruolo (es. writer hostgroup `10`, reader hostgroup `20`). Le query rule instradano verso un hostgroup, non verso un singolo host.
- **Connection multiplexing**: come PgBouncer in transaction mode, ProxySQL può riassegnare una connessione server a un client diverso tra una query e l'altra, riducendo drasticamente il numero di connessioni reali verso MySQL.
- **Query routing basato su regex**: le `mysql_query_rules` instradano in base a pattern SQL (es. tutte le `SELECT` → reader hostgroup, tutto il resto → writer hostgroup), non sulla sintassi esplicita dell'applicazione.
- **Fast-forward vs multiplexing**: alcune sessioni (uso di `LOCK TABLES`, variabili di sessione non standard, transazioni esplicite lunghe) forzano ProxySQL in modalità "fast-forward", che disabilita temporaneamente il multiplexing per quella connessione — va monitorato perché riduce l'efficienza del pool.
- **Query cache integrata**: ProxySQL può cachare risultati di `SELECT` in memoria con TTL configurabile per query rule, riducendo il carico sul backend per query identiche e frequenti (dashboard, lookup di configurazione).
- **Admin interface**: ProxySQL si configura via SQL su una porta separata (6032 di default) — le modifiche restano in staging (`_runtime` vs tabelle persistite) finché non vengono promosse con `LOAD ... TO RUNTIME` e salvate con `SAVE ... TO DISK`.

### Perché Serve un Pooler — Memoria per Thread vs Buffer Pool

```
# Esempio: istanza con 16GB RAM, innodb_buffer_pool_size=10G
# sort_buffer_size=2M, join_buffer_size=2M, read_buffer_size=128K (per connessione)

max_connections = 2000   # valore comune ma pericoloso senza pooler

# Caso peggiore teorico (tutte le connessioni attive con sort+join allocati):
2000 * (2M + 2M + 0.128M) ≈ 8.25 GB

# Sommato al buffer pool (10G): 18.25 GB > 16 GB RAM disponibile
# → OOM killer, swapping, o MySQL che rifiuta nuove connessioni
```

Con ProxySQL davanti, l'applicazione può aprire quante connessioni vuole verso il proxy (leggere, ~pochi KB l'una); solo un pool ridotto e dimensionato (es. 50-100) raggiunge davvero MySQL.

## Architettura / Come Funziona

### Topologia Tipica

```
App Pod 1 (30 conn) ─┐
App Pod 2 (30 conn) ─┤──> ProxySQL (6033) ──┬──> MySQL Primary   (hostgroup 10, writer)
App Pod 3 (30 conn) ─┤                       ├──> MySQL Replica 1 (hostgroup 20, reader)
App Pod 4 (30 conn) ─┘                       └──> MySQL Replica 2 (hostgroup 20, reader)
                        120 client conn            ~40 connessioni server totali
                        (pooling + multiplexing)    (dimensionate su CPU backend)
```

Le `SELECT` vengono instradate di default sull'hostgroup reader (20); `INSERT`/`UPDATE`/`DELETE`/DDL e le `SELECT ... FOR UPDATE` vanno sul writer (10). Il routing è governato da `mysql_query_rules`, valutate in ordine di `rule_id`.

### Failover-Aware Routing

ProxySQL non elegge un primary da solo. Si integra con:

- **Orchestrator**: monitora la topologia di replicazione, promuove un nuovo primary in caso di failure, e tramite hook (`post-failover`) aggiorna la tabella `mysql_servers` di ProxySQL spostando l'hostgroup writer sul nuovo nodo.
- **MySQL Group Replication / InnoDB Cluster**: ProxySQL ha supporto nativo per leggere lo stato del gruppo da `performance_schema.replication_group_members` e aggiornare automaticamente quale nodo è `ONLINE`/primary, senza script esterni.
- **Galera Cluster**: ProxySQL può fare galera-aware health check nativo (`mysql-galera_hostgroups`), instradando scritture verso un solo nodo alla volta per evitare conflitti di certificazione multi-master.

!!! tip "Group Replication è l'integrazione più semplice da operare"
    Se si parte da zero su un nuovo stack MySQL in alta disponibilità, l'integrazione nativa ProxySQL + Group Replication richiede meno componenti esterni (nessun Orchestrator separato) rispetto a replica asincrona classica + Orchestrator.

## Configurazione & Pratica

### Setup Base — mysql_servers e Hostgroup

```sql
-- Connettersi all'admin interface (porta 6032, credenziali separate da quelle applicative)
-- mysql -u admin -padmin -h 127.0.0.1 -P 6032

-- Definire i server backend con il relativo hostgroup
INSERT INTO mysql_servers (hostgroup_id, hostname, port, weight, max_connections)
VALUES
  (10, 'mysql-primary.internal', 3306, 1000, 200),   -- writer
  (20, 'mysql-replica1.internal', 3306, 1000, 200),  -- reader
  (20, 'mysql-replica2.internal', 3306, 800, 200);    -- reader, peso minore (hardware più debole)

LOAD MYSQL SERVERS TO RUNTIME;
SAVE MYSQL SERVERS TO DISK;
```

```sql
-- Credenziali applicative — ProxySQL autentica i client e poi
-- usa le proprie credenziali verso il backend (non devono coincidere)
INSERT INTO mysql_users (username, password, default_hostgroup, transaction_persistent)
VALUES ('app_user', 'StrongPasswordHash', 10, 1);
-- transaction_persistent=1: mantieni la connessione sullo stesso hostgroup
-- per tutta la transazione, anche se contiene SELECT

LOAD MYSQL USERS TO RUNTIME;
SAVE MYSQL USERS TO DISK;
```

### Query Rules — Read/Write Split

```sql
-- Regola 1: tutte le SELECT (tranne FOR UPDATE) vanno al reader hostgroup
INSERT INTO mysql_query_rules (rule_id, active, match_pattern, destination_hostgroup, apply)
VALUES (100, 1, '^SELECT.*(?<!FOR UPDATE)$', 20, 1);

-- Regola 2: SELECT ... FOR UPDATE deve andare al writer (coerenza transazionale)
INSERT INTO mysql_query_rules (rule_id, active, match_pattern, destination_hostgroup, apply)
VALUES (90, 1, '^SELECT.*FOR UPDATE$', 10, 1);

-- Regola 3 (opzionale): query cache per una lookup table a bassa variazione
INSERT INTO mysql_query_rules (rule_id, active, match_pattern, cache_ttl, apply)
VALUES (80, 1, '^SELECT \\* FROM configurazioni', 30000, 1);  -- TTL 30s in ms

LOAD MYSQL QUERY RULES TO RUNTIME;
SAVE MYSQL QUERY RULES TO DISK;
```

```sql
-- Verifica quali regole stanno effettivamente matchando (contatori live)
SELECT rule_id, hits, match_pattern, destination_hostgroup
FROM stats_mysql_query_rules
ORDER BY hits DESC;
```

### Integrazione con Group Replication (failover-aware)

```sql
-- ProxySQL interroga periodicamente performance_schema.replication_group_members
-- sui nodi del gruppo per determinare automaticamente writer/reader
INSERT INTO mysql_group_replication_hostgroups
  (writer_hostgroup, backup_writer_hostgroup, reader_hostgroup, offline_hostgroup,
   active, max_writers, writer_is_also_reader, max_transactions_behind)
VALUES (10, 15, 20, 9999, 1, 1, 0, 100);
-- max_transactions_behind=100: un reader troppo indietro in replica (lag)
-- viene temporaneamente escluso dal routing

LOAD MYSQL SERVERS TO RUNTIME;
SAVE MYSQL SERVERS TO DISK;
```

### Docker Compose

```yaml
proxysql:
  image: proxysql/proxysql:2.6.0
  volumes:
    - ./proxysql.cnf:/etc/proxysql.cnf:ro
  ports:
    - "6033:6033"   # porta dati (traffico applicativo)
    - "6032:6032"   # porta admin
  environment:
    PROXYSQL_ADMIN_PASSWORD: ${PROXYSQL_ADMIN_PASSWORD}
```

### Deployment su Kubernetes — HA del Proxy

```yaml
# ProxySQL stesso deve essere ridondante — non un singolo point of failure
apiVersion: apps/v1
kind: Deployment
metadata:
  name: proxysql
spec:
  replicas: 3                     # ProxySQL Cluster nativo (da v2) sincronizza la config tra repliche
  selector:
    matchLabels:
      app: proxysql
  template:
    metadata:
      labels:
        app: proxysql
    spec:
      containers:
      - name: proxysql
        image: proxysql/proxysql:2.6.0
        ports:
        - containerPort: 6033
        - containerPort: 6032
        resources:
          requests:
            memory: "256Mi"
            cpu: "200m"
          limits:
            memory: "512Mi"
            cpu: "1"
        readinessProbe:
          tcpSocket:
            port: 6033
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: proxysql
spec:
  selector:
    app: proxysql
  ports:
  - name: data
    port: 6033
    targetPort: 6033
```

```sql
-- ProxySQL Cluster — le repliche si sincronizzano tra loro via protocollo nativo,
-- eliminando la necessità di un meccanismo esterno (es. keepalived + VIP)
INSERT INTO proxysql_servers (hostname, port, comment)
VALUES ('proxysql-1.internal', 6032, 'nodo 1'),
       ('proxysql-2.internal', 6032, 'nodo 2'),
       ('proxysql-3.internal', 6032, 'nodo 3');

LOAD PROXYSQL SERVERS TO RUNTIME;
SAVE PROXYSQL SERVERS TO DISK;
```

!!! warning "Deployment sidecar vs centralizzato cambia il blast radius"
    ProxySQL come sidecar in ogni pod applicativo isola i problemi (un proxy down impatta un solo pod) ma moltiplica i pool verso il backend — più difficile dimensionare `max_connections` lato MySQL. Un deployment centralizzato (3+ repliche, come sopra) concentra il pooling ma è un singolo dominio di failure da proteggere con ProxySQL Cluster o un load balancer davanti alle repliche.

## Best Practices

- **Dimensionare `max_connections` per hostgroup, non globalmente**: ogni server in `mysql_servers` ha il proprio `max_connections` — un reader più debole deve avere un limite più basso del writer, non lo stesso valore copiato per tutti.
- **`transaction_persistent=1` per utenti che mischiano SELECT e scritture nella stessa transazione**: senza questo flag, ProxySQL può instradare una `SELECT` dentro una transazione aperta verso il reader hostgroup, rompendo la coerenza read-your-writes.
- **Non abilitare la query cache su tabelle con scritture frequenti**: il TTL fisso di ProxySQL non invalida automaticamente alla scrittura (a differenza della vecchia MySQL query cache, rimossa in 8.0) — va usata solo su dati quasi statici.
- **ProxySQL Cluster nativo da v2 invece di keepalived+VIP**: riduce i componenti esterni da mantenere e sincronizza automaticamente `mysql_servers`/`mysql_query_rules` tra le repliche del proxy.
- **Promuovere sempre `RUNTIME` poi `DISK`**: una modifica solo `LOAD ... TO RUNTIME` senza `SAVE ... TO DISK` si perde al riavvio del processo ProxySQL — comune causa di configurazioni "sparite" dopo un redeploy.
- **Monitorare `Questions`/`Com_*` su `stats_mysql_global` per capire il mix di query reale**, non solo i log applicativi — spesso la query mix reale differisce da quanto assunto nelle regole di routing.

## Troubleshooting

### Scenario 1 — Connection storm al riavvio del pool

**Sintomo:** Al riavvio di ProxySQL (o di un deployment Kubernetes con rolling restart), MySQL riceve un picco improvviso di migliaia di tentativi di connessione simultanei, con errori `Too many connections` lato backend.

**Causa:** Tutte le connessioni client riconnettono contemporaneamente a un ProxySQL "freddo" senza pool pre-aperto, e ProxySQL a sua volta apre nuove connessioni server tutte insieme invece di gradualmente.

**Soluzione:**
```sql
-- Limitare quante nuove connessioni server ProxySQL puo' aprire al secondo per hostgroup
UPDATE mysql_servers SET max_connections = 150 WHERE hostgroup_id = 10;

-- Verificare il throttling di connessione lato globale variables
SELECT * FROM global_variables WHERE variable_name LIKE 'mysql-max_connections%';

-- Aumentare temporaneamente max_connections lato MySQL durante i rolling restart
-- pianificati, poi riportarlo al valore normale
SET GLOBAL max_connections = 1000;  -- solo come buffer temporaneo, non soluzione strutturale
```

---

### Scenario 2 — Query instradata sull'hostgroup sbagliato

**Sintomo:** Scritture che falliscono con `--read-only` error, oppure letture che vanno inaspettatamente al writer sovraccaricandolo.

**Causa:** Una `mysql_query_rules` con regex troppo permissiva o `rule_id` in conflitto intercetta la query prima della regola attesa — le regole sono valutate in ordine di `rule_id` crescente e la prima che matcha con `apply=1` vince.

**Soluzione:**
```sql
-- Debug: verificare quale regola ha effettivamente matchato per una query specifica
SELECT rule_id, hits, match_pattern
FROM stats_mysql_query_rules
WHERE hits > 0
ORDER BY rule_id;

-- Tracciare in tempo reale le query e il loro hostgroup di destinazione
SET mysql-eventslog_filename='queries.log';
SET mysql-eventslog_format=2;
LOAD MYSQL VARIABLES TO RUNTIME;
-- poi ispezionare il log eventi per vedere hostgroup assegnato per query

-- Correggere l'ordine o la specificità della regex, poi ricaricare
UPDATE mysql_query_rules SET rule_id = 85 WHERE rule_id = 100;  -- es. riordino priorità
LOAD MYSQL QUERY RULES TO RUNTIME;
```

---

### Scenario 3 — Split-brain tra ProxySQL e topologia reale

**Sintomo:** ProxySQL continua a instradare scritture verso un nodo che non è più il primary reale (es. dopo un failover manuale non propagato), causando errori `--read-only` o, peggio, scritture silenziosamente accettate su un nodo in stato inconsistente.

**Causa:** Il meccanismo di aggiornamento della topologia (Orchestrator hook, oppure polling Group Replication) non ha aggiornato `mysql_servers`/`mysql_group_replication_hostgroups` dopo il failover, oppure il failover è stato eseguito manualmente senza notificare ProxySQL.

**Soluzione:**
```sql
-- Verificare lo stato percepito da ProxySQL
SELECT hostgroup_id, hostname, status FROM mysql_servers;
-- status deve essere ONLINE per i nodi attivi; SHUNNED/OFFLINE_SOFT per nodi esclusi

-- Con Group Replication, forzare un refresh immediato dello stato del gruppo
-- (ProxySQL lo fa a intervalli regolari, ma può essere forzato riconfigurando)
LOAD MYSQL SERVERS TO RUNTIME;

-- Se il failover è stato manuale, aggiornare manualmente l'hostgroup writer
UPDATE mysql_servers SET hostgroup_id = 10 WHERE hostname = 'mysql-nuovo-primary.internal';
UPDATE mysql_servers SET hostgroup_id = 20 WHERE hostname = 'mysql-vecchio-primary.internal';
LOAD MYSQL SERVERS TO RUNTIME;
SAVE MYSQL SERVERS TO DISK;
```

!!! warning "Il polling di Group Replication ha una finestra di stale read"
    Tra il failover reale e il prossimo ciclo di polling di ProxySQL (default pochi secondi, configurabile con `mysql-monitor_groupreplication_healthcheck_interval`) esiste una finestra in cui il routing può essere stale. Per workload critici, ridurre l'intervallo di polling o integrare un hook attivo lato Orchestrator invece di affidarsi solo al polling passivo.

---

### Scenario 4 — `stats_mysql_query_rules` mostra 0 hit su tutte le regole

**Sintomo:** Tutto il traffico sembra passare, ma nessuna query rule mostra `hits > 0`; le query finiscono tutte sull'hostgroup di default indipendentemente dalle regole configurate.

**Causa:** Le regole sono state inserite nella tabella di configurazione ma mai promosse a runtime (`LOAD MYSQL QUERY RULES TO RUNTIME` mancante), oppure l'utente applicativo ha un `default_hostgroup` che bypassa le regole perché `apply=0` su tutte.

**Soluzione:**
```sql
-- Verificare se le regole sono effettivamente in RUNTIME (non solo nella tabella di config)
SELECT rule_id, active, apply FROM mysql_query_rules;

-- Confrontare con la tabella runtime effettiva
SELECT rule_id, active, apply FROM runtime_mysql_query_rules;
-- Se differiscono, le modifiche non sono state promosse

LOAD MYSQL QUERY RULES TO RUNTIME;
SAVE MYSQL QUERY RULES TO DISK;

-- Verificare anche che l'utente non abbia un default_hostgroup che
-- scavalchi il routing previsto per via di regole con apply=0 troppo in alto in ordine
SELECT username, default_hostgroup FROM mysql_users;
```

## Relazioni

??? info "PgBouncer — stesso problema su PostgreSQL"
    Il problema di fondo (troppe connessioni effimere, degrado prima per risorse di sistema che per carico SQL reale) è identico su PostgreSQL, risolto con PgBouncer. Le differenze principali: PgBouncer fa solo pooling (nessun query routing nativo), configurazione via file `.ini` invece che tabelle SQL.

    **Approfondimento →** [Connection Pooling — PgBouncer](../postgresql/connection-pooling.md)

??? info "Architettura MySQL — thread-per-connection e replicazione"
    Il modello thread-per-connection e la replicazione binlog/GTID su cui si basa il read/write split di ProxySQL sono trattati in dettaglio qui.

    **Approfondimento →** [Architettura e Replicazione](architettura-replicazione.md)

??? info "Managed Database e Proxy as-a-Service"
    RDS Proxy (per RDS/Aurora MySQL) offre un equivalente managed di pooling e failover-awareness, senza gestione diretta dell'infrastruttura ProxySQL.

    **Approfondimento →** [Managed Databases](../kubernetes-cloud/managed-databases.md)

## Riferimenti

- [ProxySQL Documentation](https://proxysql.com/documentation/)
- [ProxySQL — Group Replication Integration](https://proxysql.com/documentation/group-replication-configuration/)
- [ProxySQL Cluster](https://proxysql.com/documentation/proxysql-cluster/)
- [MariaDB MaxScale Documentation](https://mariadb.com/docs/server/products/mariadb-maxscale)
- [AWS RDS Proxy for MySQL](https://aws.amazon.com/rds/proxy/)
