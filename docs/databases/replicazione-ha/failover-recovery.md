---
title: "Failover e Recovery"
slug: failover-recovery
category: databases
tags: [failover, recovery, alta-disponibilità, patroni, promozione, failback]
search_keywords: [database failover, automatic failover, patroni failover, postgresql failover, promote standby, failback procedure, switchover vs failover, split brain prevention, distributed lock etcd consul, health check database, connection draining, vip virtual ip failover, keepalived postgresql, pg_promote, recovery target, read-write split after failover, connection pooler failover, pgbouncer failover]
parent: databases/replicazione-ha/_index
related: [databases/replicazione-ha/strategie-replica, databases/postgresql/replicazione, databases/replicazione-ha/backup-pitr]
official_docs: https://patroni.readthedocs.io/en/latest/
status: complete
difficulty: advanced
last_updated: 2026-03-29
---

# Failover e Recovery

## Panoramica

Il **failover** è il processo di promozione di una standby a primary quando il primary originale diventa irraggiungibile. Il **switchover** è la stessa operazione eseguita in modo pianificato (manutenzione, upgrade). La differenza fondamentale: in un failover non sai con certezza se il primary è davvero morto o solo temporaneamente irraggiungibile (split-brain risk).

Senza un sistema di failover automatico, il DBA deve:
1. Rilevare manualmente il problema (minuti)
2. Verificare che il primary sia davvero down (minuti)
3. Scegliere la standby più avanzata
4. Promuoverla manualmente
5. Riconfigurare le altre standby per seguire la nuova primary
6. Aggiornare le connessioni delle applicazioni

**Tempo totale: 15-60 minuti** — inaccettabile per la maggior parte delle applicazioni.

## Patroni — Failover Automatico

[Patroni](https://patroni.readthedocs.io/) è il tool standard per gestire cluster PostgreSQL con failover automatico. Usa un **distributed lock** (etcd, Consul, ZooKeeper) per prevenire lo split-brain: solo il nodo che detiene il lock può essere primary.

### Architettura

```
┌─────────────────────────────────────────────────────┐
│                    etcd cluster                      │
│  (distributed consensus — garantisce un solo leader) │
└───────────────┬──────────────────────────────────────┘
                │ heartbeat ogni loop_wait (10s default)
        ┌───────┼───────┐
        ▼       ▼       ▼
   Patroni   Patroni  Patroni
   Node 1    Node 2   Node 3
   (Primary) (Standby)(Standby)
      │
   PostgreSQL PostgreSQL PostgreSQL

Flusso failover:
1. Node 1 (Primary) non rinnova il lock su etcd → TTL scade (30s default)
2. Node 2 e 3 rilevono il lock libero
3. Elezione: vince il nodo con replica più avanzata (pg_wal_lsn_diff)
4. Il vincitore prende il lock e promuove il proprio PostgreSQL
5. Gli altri nodi si riconnettono al nuovo primary (pg_basebackup se necessario)
```

### Configurazione

```yaml
# patroni.yml (esempio completo per un nodo)
scope: postgres-cluster     # nome del cluster — uguale su tutti i nodi
namespace: /db/             # prefisso in etcd
name: pg-node-1             # nome univoco di questo nodo

restapi:
  listen: 0.0.0.0:8008
  connect_address: 10.0.1.10:8008

etcd:
  hosts: etcd1:2379,etcd2:2379,etcd3:2379

bootstrap:
  dcs:
    ttl: 30                         # TTL del lock — se il primary non rinnova entro 30s → failover
    loop_wait: 10                   # Frequenza controllo (ogni 10s)
    retry_timeout: 30
    maximum_lag_on_failover: 1048576  # 1MB — non eleggere standby con lag > 1MB

  initdb:
    - encoding: UTF8
    - data-checksums             # abilita checksum per rilevare corruzione

postgresql:
  listen: 0.0.0.0:5432
  connect_address: 10.0.1.10:5432
  data_dir: /var/lib/postgresql/17/main
  bin_dir: /usr/lib/postgresql/17/bin

  authentication:
    replication:
      username: replicator
      password: "strongpassword"
    superuser:
      username: postgres
      password: "superpassword"

  parameters:
    # WAL
    wal_level: replica
    max_wal_senders: 10
    wal_keep_size: 1GB
    # Sync commit — 'on' per RPO=0, 'off' per massima performance
    synchronous_commit: "on"
    synchronous_standby_names: "ANY 1 (*)"   # sincrono con qualsiasi 1 standby
    # Performance
    shared_buffers: 4GB
    max_connections: 200

tags:
  nofailover: false     # questo nodo può essere promosso
  noloadbalance: false  # questo nodo può ricevere read
  clonefrom: false
```

### Operazioni Patroni

```bash
# Stato del cluster
patronictl -c /etc/patroni.yml list
# + Cluster: postgres-cluster --+----+-----------+
# | Member    | Host      | Role   | State | TL |
# +-----------+-----------+--------+-------+----+
# | pg-node-1 | 10.0.1.10 | Leader | running | 1 |
# | pg-node-2 | 10.0.1.11 | Replica| running | 1 |
# | pg-node-3 | 10.0.1.12 | Replica| running | 1 |

# Switchover pianificato (graceful, senza perdita dati)
patronictl -c /etc/patroni.yml switchover postgres-cluster \
    --master pg-node-1 \
    --candidate pg-node-2 \
    --scheduled now

# Failover manuale forzato (quando il primary è irraggiungibile)
patronictl -c /etc/patroni.yml failover postgres-cluster \
    --master pg-node-1 \
    --candidate pg-node-2 \
    --force

# Reinizializza una standby che ha troppo lag (dopo failover e promozione)
patronictl -c /etc/patroni.yml reinit postgres-cluster pg-node-1

# Pause automatismo Patroni (per operazioni manuali)
patronictl -c /etc/patroni.yml pause postgres-cluster
patronictl -c /etc/patroni.yml resume postgres-cluster

# API REST di Patroni
curl http://pg-node-1:8008/patroni          # stato nodo
curl http://pg-node-1:8008/cluster          # stato cluster
curl http://pg-node-1:8008/primary          # 200 se primary, 503 se no
curl http://pg-node-1:8008/replica          # 200 se replica, 503 se no
# → usato per health check dal load balancer (HAProxy, AWS Target Group)
```

### HAProxy + Patroni (Connection Routing)

```
App ──> HAProxy ──> Primary (per write)
              │──> Replica (per read-only)

HAProxy usa le API REST di Patroni per health check:
GET /primary → 200 = questo nodo è il primary
GET /replica → 200 = questo nodo è una replica
```

```
# haproxy.cfg
frontend postgres_write
    bind *:5432
    default_backend pg_primary

frontend postgres_read
    bind *:5433
    default_backend pg_replicas

backend pg_primary
    option httpchk GET /primary
    server pg-node-1 10.0.1.10:5432 check port 8008
    server pg-node-2 10.0.1.11:5432 check port 8008
    server pg-node-3 10.0.1.12:5432 check port 8008

backend pg_replicas
    option httpchk GET /replica
    balance roundrobin
    server pg-node-1 10.0.1.10:5432 check port 8008
    server pg-node-2 10.0.1.11:5432 check port 8008
    server pg-node-3 10.0.1.12:5432 check port 8008
```

---

## Failover su Managed Services

### AWS RDS Multi-AZ

```
Primary (AZ-A) ──── sincrona ──── Standby (AZ-B)

Failover automatico in 60-120s:
1. RDS rileva primary irraggiungibile
2. Promuove la standby (stessa AZ-B)
3. Aggiorna il DNS del CNAME endpoint → punta alla nuova primary
4. Le connessioni esistenti vengono droppate → l'app deve riconnettersi

RTO: 1-2 minuti (DNS TTL + promozione)
RPO: 0 (replica sincrona)
```

```python
# Gestire il reconnect automatico nell'app
import psycopg2
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=30)
)
def execute_with_retry(query, params=None):
    with psycopg2.connect(RDS_ENDPOINT) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()
```

### Aurora Global Database

```
Primary Region (us-east-1)        Secondary Region (eu-west-1)
        │                                    │
Aurora Primary Cluster ──── replication ──> Aurora Secondary Cluster
  (read + write)               <1s lag         (read-only)

Failover cross-region (promozione secondario a primary):
  1. Distacca il cluster secondario dal primary
  2. Promuove il cluster secondario a standalone writer
  3. L'app aggiorna il connection string
  RTO: ~1 minuto, RPO: < 1 secondo (lag tipico)
```

---

## Failback — Ripristino del Nodo Originale

Dopo un failover, il nodo originale (ex-primary) deve essere reintegrato come standby. Non assumere mai che torni automaticamente come primary — il nuovo primary ha continuato a ricevere write.

```bash
# Con Patroni — reinizializza l'ex-primary come standby del nuovo primary
patronictl -c /etc/patroni.yml reinit postgres-cluster pg-node-1

# Patroni esegue pg_basebackup dal nuovo primary e riconfigura come standby
# Poi verifica che la replica sia in sync e lo aggiunge al cluster

# ATTENZIONE: il reinit cancella tutti i dati locali del nodo!
# pg_basebackup ricopierà tutto dal nuovo primary
```

**Failback ≠ Ripristino dell'ex-primary come leader**: in produzione, dopo un failover automatico, il nuovo primary rimane primary. L'ex-primary diventa standby. Per tornare al layout originale, eseguire un switchover esplicito — solo se c'è una ragione tecnica (es. il nodo originale è su hardware più potente).

---

## Split-Brain — Il Rischio Principale

Il **split-brain** avviene quando due nodi credono entrambi di essere il primary e accettano write indipendentemente. Il risultato è una divergenza dei dati difficile o impossibile da risolvere.

```
Scenario split-brain:
  Primary A ─── (rete partizionata) ─── Standby B
     │                                      │
     │ A continua a ricevere write          │ B non riceve heartbeat
     │                                      │ B si auto-promuove
     │ Entrambi accettano write diverse!    │
     │◄──── dati divergono ────────────────►│

Prevenzione con Patroni + distributed lock:
  - Solo chi detiene il lock su etcd può essere primary
  - Se A perde la connessione a etcd → rilascia il lock → smette di accettare write
  - B prende il lock → si promuove
  - A, se ripristinato, non può ridiventare primary senza lock
```

---

## Test del Failover

Testare il failover in produzione (o staging) è **obbligatorio** — non scoprire i problemi durante un'emergenza reale:

```bash
# Test 1: Simulazione crash del primary (SIGKILL — no graceful shutdown)
kill -9 $(pidof postgres)   # sul nodo primary

# Test 2: Partizione di rete (iptables)
iptables -A INPUT -s <etcd-ip> -j DROP    # nodo non può comunicare con etcd
iptables -A OUTPUT -d <etcd-ip> -j DROP   # → dopo TTL, Patroni rilascia il lock

# Verificare:
# - Quando il nuovo primary è operativo (patronictl list)
# - Se l'app ha ricevuto errori e per quanto tempo
# - Se l'app si è riconnessa automaticamente
# - RPO: nessun dato perso (o quanti secondi persi con async)

# Ripristino test
iptables -D INPUT -s <etcd-ip> -j DROP
iptables -D OUTPUT -d <etcd-ip> -j DROP
patronictl reinit postgres-cluster <ex-primary-node>
```

**Metriche da misurare in ogni test:**
- Tempo di detection (da crash a inizio elezione)
- Tempo di promozione (da elezione a nuovo primary operativo)
- Tempo di recovery dell'applicazione (da errori a write di successo)
- Dati persi (RPO effettivo)

## Troubleshooting

### Scenario 1 — Patroni non esegue il failover dopo il crash del primary

**Sintomo:** Il primary è down, `patronictl list` mostra il nodo come `stopped` o `unknown`, ma nessuna standby viene promossa.

**Causa:** Il TTL del lock etcd non è ancora scaduto, oppure i nodi etcd sono irraggiungibili e Patroni non può acquisire il lock. In entrambi i casi nessun nodo può diventare leader.

**Soluzione:** Verificare lo stato di etcd e ridurre il TTL se troppo conservativo.

```bash
# Verifica health etcd
etcdctl --endpoints=etcd1:2379,etcd2:2379,etcd3:2379 endpoint health
etcdctl --endpoints=etcd1:2379 endpoint status

# Controlla il lock corrente nel DCS
etcdctl --endpoints=etcd1:2379 get /db/postgres-cluster/leader

# Forza il failover manualmente (se etcd è raggiungibile)
patronictl -c /etc/patroni.yml failover postgres-cluster \
    --master pg-node-1 \
    --candidate pg-node-2 \
    --force

# Ridurre TTL nella configurazione DCS (richiede restart Patroni)
# bootstrap.dcs.ttl: 20   (default 30 — abbassare con cautela)
```

---

### Scenario 2 — Ex-primary non si unisce al cluster dopo il failover

**Sintomo:** Dopo un failover, il nodo che era primary rimane in stato `stopped` o `start failed` in `patronictl list`. I log mostrano errori tipo `could not connect to the primary server` o `timeline diverged`.

**Causa:** Il nodo ex-primary ha WAL divergenti rispetto al nuovo primary (ha continuato a ricevere write localmente o ha una timeline più vecchia). Patroni non può applicare pg_rewind o il nodo ha troppo lag.

**Soluzione:** Reinizializzare il nodo da zero tramite basebackup del nuovo primary.

```bash
# Verifica lo stato del nodo e l'errore specifico
patronictl -c /etc/patroni.yml list
journalctl -u patroni -n 100 --no-pager

# Controlla divergenza timeline
psql -U postgres -c "SELECT timeline_id, redo_lsn FROM pg_control_checkpoint();"
# Sul nuovo primary:
psql -U postgres -c "SELECT pg_current_wal_lsn();"

# Reinizializza il nodo (cancella dati locali e riparte da basebackup)
patronictl -c /etc/patroni.yml reinit postgres-cluster pg-node-1

# Verifica che il nodo si sia unito correttamente
patronictl -c /etc/patroni.yml list
# Attendi stato "running" con replication_state "streaming"
```

---

### Scenario 3 — L'applicazione non si riconnette dopo il failover

**Sintomo:** Il cluster ha un nuovo primary funzionante, ma l'applicazione continua a ricevere errori `connection refused` o `FATAL: the database system is starting up`. Il traffico non riprende automaticamente.

**Causa:** Le connessioni aperte sono cached sul vecchio IP/socket. HAProxy non ha ancora rilevato il cambio tramite health check, oppure l'applicazione non implementa retry con backoff.

**Soluzione:** Verificare la configurazione del load balancer e aggiungere retry logic lato applicazione.

```bash
# Verifica che HAProxy veda il nuovo primary
echo "show servers state" | socat stdio /run/haproxy/admin.sock
# Il server con il nuovo IP del primary deve essere "UP"

# Controlla che le API REST di Patroni rispondano correttamente
curl -s http://pg-node-2:8008/primary   # deve rispondere 200
curl -s http://pg-node-1:8008/primary   # deve rispondere 503 (ex-primary)

# Se usi PgBouncer: verifica che abbia applicato il nuovo primary
psql -p 6432 -U pgbouncer pgbouncer -c "SHOW POOLS;"

# Ricarica configurazione PgBouncer senza downtime
psql -p 6432 -U pgbouncer pgbouncer -c "RELOAD;"

# Test connessione diretta al nuovo primary
psql -h pg-node-2 -U postgres -c "SELECT pg_is_in_recovery();"  # deve restituire 'f'
```

---

### Scenario 4 — Failover in loop: nodi si promuovono e falliscono ripetutamente

**Sintomo:** `patronictl list` mostra alternanza continua del leader. I log riportano `promoted` e poi `demoted` in rapida successione. Il cluster non raggiunge uno stato stabile.

**Causa:** Il nodo promosso ha un lag superiore a `maximum_lag_on_failover` oppure `pg_rewind` non è abilitato e le timeline divergono ad ogni promozione. Può anche essere causato da clock drift tra i nodi che invalida il TTL del lock.

**Soluzione:** Mettere in pausa Patroni, diagnosticare il nodo problematico, correggere la configurazione e riprendere.

```bash
# Ferma l'automazione Patroni per analisi sicura
patronictl -c /etc/patroni.yml pause postgres-cluster

# Controlla il lag di ogni replica
psql -U postgres -c "
SELECT client_addr, state, sent_lsn, write_lsn, flush_lsn, replay_lsn,
       (sent_lsn - replay_lsn) AS replication_lag_bytes
FROM pg_stat_replication;"

# Verifica sincronizzazione NTP su tutti i nodi
timedatectl show --property=NTPSynchronized
chronyc tracking

# Abilita pg_rewind nella configurazione Patroni (necessario per reintegrazione rapida)
# In patroni.yml aggiungere:
#   postgresql:
#     use_pg_rewind: true

# Reinizializza il nodo con lag elevato
patronictl -c /etc/patroni.yml reinit postgres-cluster <nodo-con-lag>

# Riprendi l'automazione solo dopo che tutti i nodi sono "running"
patronictl -c /etc/patroni.yml list
patronictl -c /etc/patroni.yml resume postgres-cluster
```

## Riferimenti

- [Patroni Documentation](https://patroni.readthedocs.io/)
- [Zalando — Patroni on Kubernetes](https://github.com/zalando/patroni)
- [AWS RDS Failover](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Concepts.MultiAZ.html)
- [PostgreSQL — pg_promote()](https://www.postgresql.org/docs/current/functions-admin.html#FUNCTIONS-RECOVERY-CONTROL)
