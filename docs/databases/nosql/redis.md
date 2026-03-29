---
title: "Redis"
slug: redis
category: databases
tags: [redis, cache, nosql, in-memory, pub-sub, streams, sentinel, cluster]
search_keywords: [redis cache, redis data structures, redis strings, redis hashes, redis lists, redis sets, redis sorted sets, redis streams, redis pub sub, redis persistence rdb aof, redis sentinel, redis cluster, redis eviction lru lfu, redis ttl, redis pipelining, redis lua scripting, redis transactions multi exec, redis geospatial, redis bloom filter, redis timeseries, keydb dragonfly, redis replication, redis failover, redis memory optimization, redis slowlog]
parent: databases/nosql/_index
related: [databases/fondamentali/modelli-dati, networking/api-gateway/rate-limiting, databases/nosql/mongodb]
official_docs: https://redis.io/docs/
status: complete
difficulty: intermediate
last_updated: 2026-03-29
---

# Redis

## Panoramica

Redis (Remote Dictionary Server) è un data store in-memory che opera su strutture dati native: stringhe, hash, liste, set, sorted set, stream e altri tipi specializzati. La latenza tipica è 0.1-1ms — ordini di grandezza inferiore a qualsiasi database disco-based.

Redis non è solo un cache: è un building block per pattern architetturali comuni — rate limiting, session store, leaderboard, queue, Pub/Sub, stream processing — con semantica atomica e operazioni composte native.

!!! warning "Single-threaded per il core"
    Il loop di comando principale di Redis è single-threaded (I/O è multithread da Redis 6). Questo garantisce atomicità di ogni operazione senza lock, ma significa che operazioni lente (es. `KEYS *`, `LRANGE` su liste enormi) bloccano tutti i client. Evitare operazioni O(n) su dataset grandi in produzione.

## Strutture Dati

### Strings

Il tipo base — può contenere testo, numeri interi, float, o dati binari (JPEG, protobuf, ecc.):

```bash
SET utente:1001:nome "Andrea"
GET utente:1001:nome                   # "Andrea"

# Con TTL (expire)
SET sessione:abc123 '{"user":1001}' EX 3600   # scade in 1 ora
TTL sessione:abc123                    # 3598 (secondi rimanenti)

# Atomic counter
INCR visite:homepage                   # 1
INCRBY visite:homepage 10              # 11
INCR visite:homepage                   # 12

# SET only if not exists (pattern mutex/idempotency key)
SET lock:risorsa "owner-id" NX EX 30  # OK se non esiste, nil se esiste
```

### Hashes

Mappa di campi → valori. Ideale per oggetti (utenti, prodotti) senza dover serializzare JSON:

```bash
HSET utente:1001 nome "Andrea" email "andrea@example.com" età 30
HGET utente:1001 nome              # "Andrea"
HGETALL utente:1001                # tutti i campi
HINCRBY utente:1001 età 1          # incremento atomico di un campo

# Più efficiente di GET/SET JSON: aggiorna un singolo campo senza (de)serializzare
```

### Lists

Lista doppiamente linkata — operazioni O(1) sulle code (LPUSH/RPUSH/LPOP/RPOP):

```bash
RPUSH coda:email "msg1" "msg2" "msg3"   # Aggiunge in fondo
LPOP coda:email                          # Rimuove e ritorna dalla testa: "msg1"
LLEN coda:email                          # 2

# BRPOP — blocking pop (task queue pattern)
BRPOP coda:email 30   # Attendi fino a 30s per un elemento
```

### Sets

Insieme di stringhe uniche — operazioni insiemistiche (union, intersection, difference):

```bash
SADD tag:articolo:1 "redis" "nosql" "cache"
SMEMBERS tag:articolo:1
SISMEMBER tag:articolo:1 "redis"   # 1 (true)

# Intersezione: utenti che hanno messo like sia all'articolo 1 che al 2
SINTERSTORE risultato like:articolo:1 like:articolo:2
```

### Sorted Sets (ZSets)

Come Set ma ogni elemento ha uno score numerico — ordinato per score. Ideale per leaderboard, priority queue, geospatial index:

```bash
ZADD leaderboard 10500 "alice" 9800 "bob" 12000 "carol"
ZREVRANGE leaderboard 0 2 WITHSCORES   # Top 3: carol, alice, bob
ZRANK leaderboard "alice"               # 1 (0-indexed, dal più basso)
ZINCRBY leaderboard 500 "alice"         # alice ora ha 11000
```

### Streams

Log di eventi append-only con consumer groups — Kafka-like ma embedded in Redis:

```bash
# Produce un evento
XADD sensori:temperatura * host web-01 valore 73.2

# Consume con consumer group (distribuzione tra worker)
XGROUP CREATE sensori:temperatura worker-group $ MKSTREAM

XREADGROUP GROUP worker-group consumer-1 COUNT 10 BLOCK 2000 STREAMS sensori:temperatura >
# > = leggi solo messaggi non ancora consegnati

# Acknowledge dopo processing
XACK sensori:temperatura worker-group <message-id>
```

---

## Persistenza

Redis offre due meccanismi di persistenza (possono coesistere):

| Meccanismo | Descrizione | Pro | Contro |
|------------|-------------|-----|--------|
| **RDB (snapshot)** | Dump binario del dataset a intervalli | File compatto, restore veloce | Perde dati dall'ultimo snapshot |
| **AOF (Append-Only File)** | Log di ogni operazione di scrittura | Durabilità max con `fsync always` | File più grande, replay più lento |

```bash
# redis.conf

# RDB — snapshot ogni 60s se >= 1000 chiavi cambiate
save 60 1000
save 300 100
save 900 1
dbfilename dump.rdb

# AOF — più durabile
appendonly yes
appendfilename "appendonly.aof"
# fsync ogni secondo (default): perde max 1s di dati in caso di crash
appendfsync everysec
# fsync ad ogni scrittura: massima durabilità, throughput ridotto
# appendfsync always
# no fsync: massimo throughput, perde dati in caso di crash OS
# appendfsync no

# AOF rewrite: compatta il file eliminando operazioni ridondanti
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb
```

---

## Eviction — Gestione Memoria

Quando Redis raggiunge `maxmemory`, la policy di eviction determina cosa eliminare:

```bash
# redis.conf
maxmemory 4gb
maxmemory-policy allkeys-lru   # Policy più comune per cache

# Policy disponibili:
# noeviction         — restituisce errore quando pieno (non-cache use case)
# allkeys-lru        — elimina la chiave meno recentemente usata (cache generale)
# allkeys-lfu        — elimina la chiave meno frequentemente usata (PG 4+)
# volatile-lru       — LRU solo su chiavi con TTL (misto cache+persistent)
# volatile-ttl       — elimina la chiave con TTL più basso (prossima a scadere)
# allkeys-random     — elimina casuale (per lo più inutile)
```

---

## Redis Sentinel — Alta Disponibilità

Sentinel monitora i nodi Redis e orchestra il failover automatico:

```
+----------+        +----------+
| Primary  |<──────>| Replica 1|
+----------+        +----------+
     ^                   ^
     |                   |
+----------+        +----------+
| Sentinel |        | Sentinel |
|   (1)    |        |   (2)    |
+----------+        +----------+
      \               /
       +----------+
       | Sentinel |
       |   (3)    |
       +----------+
Quorum = 2 (maggioranza di 3)
```

```bash
# sentinel.conf
sentinel monitor mymaster redis-primary 6379 2   # quorum=2
sentinel down-after-milliseconds mymaster 5000    # 5s → SDOWN
sentinel failover-timeout mymaster 60000
sentinel parallel-syncs mymaster 1               # quante replica si sincronizzano in parallelo
```

```python
# Connessione con Sentinel (Python redis-py)
from redis.sentinel import Sentinel

sentinel = Sentinel([
    ('sentinel-1', 26379),
    ('sentinel-2', 26379),
    ('sentinel-3', 26379),
], socket_timeout=0.1)

# Scopre automaticamente primary e replica
primary = sentinel.master_for('mymaster', socket_timeout=0.1)
replica = sentinel.slave_for('mymaster', socket_timeout=0.1)

primary.set('chiave', 'valore')
replica.get('chiave')   # read dalla replica
```

---

## Redis Cluster — Sharding Nativo

Redis Cluster distribui il keyspace su più nodi usando 16384 hash slot. Ogni nodo gestisce un sottoinsieme di slot e ha almeno una replica:

```
Nodo A (primary): slot 0-5460
Nodo B (primary): slot 5461-10922
Nodo C (primary): slot 10923-16383
  + replica per A, B, C
```

```bash
# Crea cluster con redis-cli (3 primary + 3 replica)
redis-cli --cluster create \
  node1:6379 node2:6379 node3:6379 \
  node4:6379 node5:6379 node6:6379 \
  --cluster-replicas 1

# Stato del cluster
redis-cli -c cluster nodes
redis-cli -c cluster info

# Le key correlate devono essere sullo stesso slot (per MGET/transazioni)
# Usa hash tag: {user:1001}:profilo e {user:1001}:sessione vanno sullo stesso slot
```

```python
# Client Cluster (redis-py)
from redis.cluster import RedisCluster

r = RedisCluster(
    startup_nodes=[{"host": "node1", "port": 6379}],
    decode_responses=True
)
r.set("chiave", "valore")
```

---

## Pattern Comuni

### Rate Limiting con Sliding Window

```lua
-- Script Lua (atomico)
local key = KEYS[1]
local limit = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local now = tonumber(ARGV[3])

-- Rimuovi eventi fuori dalla finestra
redis.call('ZREMRANGEBYSCORE', key, '-inf', now - window)
local count = redis.call('ZCARD', key)

if count < limit then
    redis.call('ZADD', key, now, now)  -- aggiungi evento corrente
    redis.call('EXPIRE', key, window)
    return 1  -- allowed
else
    return 0  -- rate limited
end
```

### Distributed Lock (Redlock)

```python
# Con redlock-py
import redlock

dlm = redlock.Redlock([
    {"host": "redis-1", "port": 6379},
    {"host": "redis-2", "port": 6379},
    {"host": "redis-3", "port": 6379},
])

lock = dlm.lock("resource-name", 10000)  # TTL 10s
if lock:
    try:
        # sezione critica
        pass
    finally:
        dlm.unlock(lock)
```

### Cache-Aside

```python
def get_utente(user_id: int):
    key = f"utente:{user_id}"
    cached = redis.get(key)
    if cached:
        return json.loads(cached)   # cache hit

    # cache miss
    utente = db.query("SELECT * FROM utenti WHERE id = %s", user_id)
    redis.setex(key, 3600, json.dumps(utente))   # cache per 1 ora
    return utente
```

---

## Monitoraggio

```bash
# Statistiche live
redis-cli INFO stats
redis-cli INFO memory
redis-cli INFO replication

# Monitoraggio in tempo reale (attenzione: impatto in produzione)
redis-cli MONITOR   # logga ogni comando — usare solo per debug brevi

# Slow log: comandi che hanno superato slowlog-log-slower-than (default 10ms)
redis-cli SLOWLOG GET 10

# Analisi memoria per tipo di chiave
redis-cli --bigkeys    # trova le chiavi più grandi
redis-cli --memkeys    # analisi memoria per prefisso (Redis 7+)

# Metriche Prometheus: redis_exporter
# https://github.com/oliver006/redis_exporter
```

## Best Practices

- **Usare TTL su quasi tutto**: chiavi senza TTL in un cache sono un memory leak — il dataset cresce senza limite
- **Evitare chiavi KEYS * in produzione**: è O(n) su tutto il keyspace — blocca il server. Usare `SCAN` con cursor
- **Pipelining per batch**: raggruppa N comandi in una singola round-trip riducendo la latenza di N-1 RTT
- **Naming convention**: `oggetto:id:campo` (es. `utente:1001:profilo`) — rende la gestione e il monitoraggio prevedibile
- **Sentinel per HA, Cluster per scale**: Sentinel (failover automatico, singolo dataset) vs Cluster (sharding, dataset > RAM di un nodo). Non usare Cluster se non strettamente necessario — aggiunge complessità operativa e vincoli sulle operazioni multi-key

## Troubleshooting

### Scenario 1 — Latenza alta su singoli comandi

**Sintomo:** Alcuni comandi impiegano decine o centinaia di ms; gli altri client si bloccano durante quel periodo.

**Causa:** Il loop di comando Redis è single-threaded: un'operazione O(n) su un dataset grande (es. `KEYS *`, `SMEMBERS` su un set con milioni di elementi, `LRANGE 0 -1`) blocca tutti gli altri client per tutta la sua durata.

**Soluzione:** Identificare i comandi lenti con SLOWLOG, sostituirli con alternative O(1)/O(log n) o con iterazione via cursor.

```bash
# Soglia slowlog (default 10000 µs = 10ms)
redis-cli CONFIG SET slowlog-log-slower-than 5000   # abbassa a 5ms

# Visualizza gli ultimi 10 comandi lenti
redis-cli SLOWLOG GET 10
# output: id, timestamp, durata (µs), comando, client

# Sostituzione: invece di KEYS * usa SCAN con cursor
redis-cli SCAN 0 MATCH "utente:*" COUNT 100
# cursor=0 inizia; continua con il cursor restituito finché ritorna 0

# Verifica istantanea dei comandi in corso
redis-cli CLIENT LIST
```

---

### Scenario 2 — Memoria che cresce senza limite

**Sintomo:** `redis-cli INFO memory` mostra `used_memory` in crescita costante; OOM killer o eviction error (`OOM command not allowed when used memory > maxmemory`).

**Causa:** Chiavi senza TTL accumulate nel tempo (tipico di session store o cache senza scadenza), oppure `maxmemory` non configurato e policy `noeviction` (default).

**Soluzione:** Impostare TTL sui nuovi oggetti, configurare `maxmemory` e policy di eviction, analizzare le chiavi più pesanti.

```bash
# Analisi memoria corrente
redis-cli INFO memory | grep -E "used_memory_human|maxmemory_human|mem_fragmentation_ratio"

# Trova le chiavi più grandi (sampling — non blocca)
redis-cli --bigkeys

# Quante chiavi NON hanno TTL?
redis-cli INFO keyspace
# db0:keys=150000,expires=80000,avg_ttl=3600000
# → 70000 chiavi senza TTL

# Configura maxmemory e eviction
redis-cli CONFIG SET maxmemory 4gb
redis-cli CONFIG SET maxmemory-policy allkeys-lru

# Imposta TTL su chiavi esistenti senza scadenza (operazione batch con SCAN)
# Esempio: aggiunge TTL di 7 giorni a tutte le chiavi "sessione:*" senza TTL
redis-cli SCAN 0 MATCH "sessione:*" COUNT 500 | while read cursor keys; do
  for key in $keys; do
    redis-cli TTL "$key" | grep -q "^-1$" && redis-cli EXPIRE "$key" 604800
  done
  [ "$cursor" = "0" ] && break
done
```

---

### Scenario 3 — Errore MOVED in Redis Cluster

**Sintomo:** Il client riceve `MOVED 5432 node2:6379` e non riesce a eseguire il comando.

**Causa:** Il client non è cluster-aware: invia il comando al nodo sbagliato invece di seguire il redirect verso il nodo che gestisce l'hash slot della chiave.

**Soluzione:** Usare un client con supporto cluster nativo; per operazioni multi-key usare hash tag per forare le chiavi sullo stesso slot.

```bash
# Verifica quale slot appartiene a una chiave
redis-cli CLUSTER KEYSLOT "utente:1001"
# → 13645

# Verifica quale nodo gestisce quel slot
redis-cli -c CLUSTER NODES | grep "13645"

# Con redis-cli -c il redirect è automatico
redis-cli -c -h node1 -p 6379 GET "utente:1001"
# Internally: MOVED → segue redirect

# Hash tag per co-locare chiavi correlate sullo stesso slot
# {user:1001}:profilo  e  {user:1001}:sessione → stesso slot (basato su "user:1001")
redis-cli CLUSTER KEYSLOT "{user:1001}:profilo"
redis-cli CLUSTER KEYSLOT "{user:1001}:sessione"
# → devono restituire lo stesso numero

# Stato del cluster
redis-cli -c CLUSTER INFO | grep cluster_state
redis-cli -c CLUSTER NODES
```

---

### Scenario 4 — Failover Sentinel troppo lento o non avviene

**Sintomo:** Il primary è down ma Sentinel impiega più di 30 secondi per promuovere la replica; oppure il failover non parte mai.

**Causa 1:** `down-after-milliseconds` troppo alto (default 30000ms = 30s).
**Causa 2:** Quorum non raggiunto (meno di `quorum` Sentinel concordano che il primary è down).
**Causa 3:** Il Sentinel non riesce a connettersi alla replica da promuovere.

**Soluzione:** Ridurre il timeout di rilevamento, verificare il quorum e la connettività tra Sentinel e nodi.

```bash
# Stato corrente visto dai Sentinel
redis-cli -p 26379 SENTINEL masters
redis-cli -p 26379 SENTINEL replicas mymaster
redis-cli -p 26379 SENTINEL sentinels mymaster

# Numero di Sentinel che vedono il primary DOWN
redis-cli -p 26379 SENTINEL ckquorum mymaster
# Output: OK X usable Sentinels. Quorum and failover authorization can be reached

# Abbassa il timeout di rilevamento (aggiornamento a caldo)
redis-cli -p 26379 SENTINEL SET mymaster down-after-milliseconds 5000
redis-cli -p 26379 SENTINEL SET mymaster failover-timeout 30000

# Log Sentinel per debug
tail -f /var/log/redis/sentinel.log | grep -E "ODOWN|SDOWN|failover|promote"

# Forza failover manuale (per test)
redis-cli -p 26379 SENTINEL FAILOVER mymaster
```

---

### Scenario 5 — Replica lag alto o replica disconnessa

**Sintomo:** `redis-cli INFO replication` mostra `master_link_status:down` o `lag` in crescita sulla replica; i dati sulla replica sono stale.

**Causa:** Replication backlog troppo piccolo (la replica non riesce a fare partial resync dopo una disconnessione breve); rete lenta; primary sovraccarico con molte scritture.

**Soluzione:** Aumentare `repl-backlog-size`, verificare la rete, monitorare il replication offset.

```bash
# Stato replication sul primary
redis-cli INFO replication
# master_replid: ...
# master_repl_offset: 1234567
# repl_backlog_size: 1048576    # default 1MB — spesso troppo piccolo
# connected_slaves: 1
# slave0: ip=...,port=6379,state=online,offset=1234500,lag=0

# Aumenta backlog per tollerare disconnessioni brevi senza full resync
redis-cli CONFIG SET repl-backlog-size 64mb

# Sulle repliche: verifica lag e stato
redis-cli -h replica-host INFO replication | grep -E "master_link_status|master_last_io|slave_repl_offset"

# Confronta offset primary vs replica
PRIMARY_OFFSET=$(redis-cli -h primary INFO replication | grep master_repl_offset | cut -d: -f2)
REPLICA_OFFSET=$(redis-cli -h replica INFO replication | grep slave_repl_offset | cut -d: -f2)
echo "Lag in bytes: $((PRIMARY_OFFSET - REPLICA_OFFSET))"

# Verifica latenza di rete tra nodi
redis-cli -h replica --latency-history -i 1
```

## Riferimenti

- [Redis Documentation](https://redis.io/docs/)
- [Redis University — Free Courses](https://university.redis.com/)
- [Antirez — Redis internals blog](http://antirez.com/)
- [The Little Redis Book](https://www.openmymind.net/redis.pdf)
