---
title: "Data Layer"
slug: data
category: dev
tags: [database, migrations, connection-pooling, cache, redis, orm, microservizi, data-layer, postgresql, nosql]
search_keywords: [data layer, database per servizio, database per microservice, schema migrations, migrazioni schema, connection pooling, pool di connessioni, cache patterns, cache-aside, write-through, read-through, redis cache, orm, object relational mapping, hibernate, jpa, sqlalchemy, gorm, pgbouncer, hikaricp, pgx, flyway, liquibase, golang-migrate, alembic, read replica, replica lettura, ottimistic locking, optimistic locking, pessimistic locking, soft delete, n+1 problem, n+1 query, transaction, transazione, outbox pattern, saga data, cqrs data side, event sourcing storage, database isolation, database microservizi, data access layer, repository pattern, unit of work]
parent: dev/_index
related: [databases/_index, databases/postgresql/connection-pooling, databases/nosql/redis, databases/fondamentali/transazioni-concorrenza, messaging/kafka/pattern-microservizi/outbox-pattern, messaging/kafka/pattern-microservizi/cqrs, dev/integrazioni/_index, dev/resilienza/_index]
official_docs: https://microservices.io/patterns/data/
status: complete
difficulty: intermediate
last_updated: 2026-03-28
---

# Data Layer

## Panoramica

Il data layer di un microservizio comprende tutto ciò che riguarda come il servizio **persiste, legge e gestisce i propri dati**: dalla scelta del database, alla gestione delle connessioni, alle migrazioni dello schema, fino ai pattern di caching. In un'architettura a microservizi ogni servizio possiede il suo database — nessun altro servizio può accedervi direttamente.

Questa sezione si concentra sulla **prospettiva del developer**: come si scrive codice che interagisce con il database in modo corretto, efficiente e manutenibile. La configurazione infrastrutturale (replica, backup, managed services) è nella sezione [Databases](../../databases/_index.md).

Quando NON ignorare il data layer: un data layer mal progettato è spesso la causa primaria di problemi in produzione — connection exhaustion, deadlock, migrazioni fallite, N+1 silenzioso che distrugge le performance sotto carico.

---

## Concetti Chiave

### Database per Servizio

Il principio fondamentale: ogni microservizio ha il suo database (o almeno il suo schema isolato). Questo garantisce il **loose coupling** — un servizio può evolvere il suo schema senza impattare altri.

```
✅ Architettura corretta:
  OrderService    → orders_db     (PostgreSQL 16)
  UserService     → users_db      (PostgreSQL 16)
  ProductService  → products_db   (MongoDB 7)
  SessionService  → sessions_db   (Redis 7)

❌ Anti-pattern (shared database):
  OrderService  ──┐
  UserService   ──┼──→ monolith_db   ← coupling nascosto, impossibile scalare
  ProductService──┘                     indipendentemente
```

!!! warning "Shared database = distributed monolith"
    Se due servizi leggono la stessa tabella, sono accoppiati a livello di schema. Una migrazione che rinomina una colonna rompe entrambi. Questo vanifica i benefici dei microservizi.

### Repository Pattern

Isola la logica di accesso ai dati dal business layer. Il servizio interagisce con un'interfaccia `Repository`, non direttamente con ORM/driver.

```go
// Go — interfaccia repository
type OrderRepository interface {
    FindByID(ctx context.Context, id uuid.UUID) (*Order, error)
    FindByUserID(ctx context.Context, userID uuid.UUID, opts PaginationOpts) ([]*Order, error)
    Save(ctx context.Context, order *Order) error
    Delete(ctx context.Context, id uuid.UUID) error
}

// Implementazione PostgreSQL
type postgresOrderRepository struct {
    pool *pgxpool.Pool
}

func (r *postgresOrderRepository) FindByID(ctx context.Context, id uuid.UUID) (*Order, error) {
    var o Order
    err := r.pool.QueryRow(ctx,
        `SELECT id, user_id, status, total_price, created_at
         FROM orders WHERE id = $1 AND deleted_at IS NULL`,
        id,
    ).Scan(&o.ID, &o.UserID, &o.Status, &o.TotalPrice, &o.CreatedAt)
    if errors.Is(err, pgx.ErrNoRows) {
        return nil, ErrOrderNotFound
    }
    return &o, err
}
```

### ORM vs Query Builder vs SQL Raw

| Approccio | Vantaggi | Svantaggi | Quando usare |
|---|---|---|---|
| ORM (Hibernate, GORM, SQLAlchemy) | Produttività, mapping automatico | Magic nascosto, N+1 facile, query non ottimali | CRUD semplice, prototipi |
| Query Builder (jOOQ, sqlc, Knex) | Type-safe, SQL visibile | Più verboso | Applicazioni medio-complesse |
| SQL Raw + mapper manuale | Controllo totale, performance ottimale | Boilerplate, manutenzione schema manuale | Query complesse, performance critiche |

!!! tip "Raccomandazione per microservizi"
    Preferire un query builder o SQL raw con un thin mapper. Gli ORM nascondono troppa complessità in sistemi dove il controllo delle query è critico per le performance. `sqlc` (Go) e `jOOQ` (Java) offrono type-safety senza sacrificare trasparenza.

---

## Schema Migrations

Le migrazioni gestiscono l'evoluzione del database nel tempo in modo controllato e riproducibile. Sono **parte del codebase**, non operazioni manuali.

### Principi

```
Regole d'oro per le migrazioni:
  1. Mai modificare una migration già applicata in produzione
  2. Ogni migration è irreversibile per design (il rollback è una nuova migration)
  3. Le migration backward-compatible permettono deploy senza downtime
  4. Le migration breaking richiedono un deployment in più fasi (expand-contract)
```

### Flyway (Java/JVM)

```java
// Struttura file migrations (Maven/Gradle)
// src/main/resources/db/migration/
//   V1__create_orders_table.sql
//   V2__add_shipping_address.sql
//   V3__add_status_index.sql
```

```sql
-- V1__create_orders_table.sql
CREATE TABLE orders (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID        NOT NULL,
    status      VARCHAR(20) NOT NULL DEFAULT 'pending',
    total_price NUMERIC(12,2) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at  TIMESTAMPTZ           -- soft delete
);

CREATE INDEX idx_orders_user_id ON orders(user_id);
CREATE INDEX idx_orders_status  ON orders(status) WHERE deleted_at IS NULL;
```

```java
// Configurazione Spring Boot — Flyway applicato automaticamente all'avvio
// application.yaml
spring:
  flyway:
    enabled: true
    locations: classpath:db/migration
    baseline-on-migrate: false
    out-of-order: false   # strict ordering
    validate-on-migrate: true
```

### golang-migrate

```bash
# Installazione
go install -tags 'postgres' github.com/golang-migrate/migrate/v4/cmd/migrate@latest

# Creazione migration
migrate create -ext sql -dir ./migrations -seq add_payment_method

# Esecuzione
migrate -path ./migrations -database "postgres://user:pass@localhost/orders_db?sslmode=disable" up

# Rollback 1 step
migrate -path ./migrations -database "..." down 1
```

```sql
-- 000002_add_payment_method.up.sql
ALTER TABLE orders ADD COLUMN payment_method VARCHAR(30);
ALTER TABLE orders ADD COLUMN payment_ref    VARCHAR(100);

-- 000002_add_payment_method.down.sql
ALTER TABLE orders DROP COLUMN payment_method;
ALTER TABLE orders DROP COLUMN payment_ref;
```

### Expand-Contract Pattern (Zero-downtime)

Per migrazioni breaking (rename colonna, cambio tipo), usare il pattern in 3 fasi:

```
Fase 1 — EXPAND: aggiungere la nuova colonna (backward-compatible)
  ALTER TABLE orders ADD COLUMN customer_id UUID;

  → Deploying v2: scrive su ENTRAMBE le colonne (user_id e customer_id)
    Legge ancora da user_id

Fase 2 — MIGRATE: backfill dei dati
  UPDATE orders SET customer_id = user_id WHERE customer_id IS NULL;
  ALTER TABLE orders ALTER COLUMN customer_id SET NOT NULL;

  → Deploying v3: legge da customer_id, scrive solo su customer_id

Fase 3 — CONTRACT: rimozione colonna vecchia
  ALTER TABLE orders DROP COLUMN user_id;

  → Deploying v4: solo customer_id esiste
```

!!! warning "Non droppare mai colonne nel deploy iniziale"
    Un `DROP COLUMN` immediato rompe qualsiasi istanza del servizio ancora in esecuzione con il codice vecchio. L'expand-contract garantisce che il vecchio codice continui a funzionare durante il rolling update.

---

## Connection Pooling

Ogni connessione a PostgreSQL costa ~5-10 MB di RAM sul server e ha overhead di setup significativo. Il connection pooling riusa le connessioni esistenti.

### PgBouncer (livello infrastrutturale)

PgBouncer è un proxy che si mette davanti a PostgreSQL e gestisce un pool condiviso tra tutti i processi dell'applicazione.

```ini
# pgbouncer.ini
[databases]
orders_db = host=postgres-primary port=5432 dbname=orders_db

[pgbouncer]
pool_mode = transaction          # una connessione per transazione (consigliato)
max_client_conn = 1000           # massimo client che si connettono a PgBouncer
default_pool_size = 25           # connessioni reali verso PostgreSQL
reserve_pool_size = 5            # connessioni di riserva per picchi
reserve_pool_timeout = 3         # secondi prima di usare le riserve
server_idle_timeout = 600        # chiudi connessioni idle dopo 10 minuti
```

!!! warning "Pool mode e prepared statements"
    In modalità `transaction`, i prepared statements server-side NON funzionano — ogni transazione potrebbe usare una connessione diversa. Usare `session` mode se necessario, oppure gestire prepared statements lato client.

### HikariCP (Java)

```yaml
# application.yaml
spring:
  datasource:
    url: jdbc:postgresql://pgbouncer:5432/orders_db
    hikari:
      maximum-pool-size: 10         # regola in base a: (CPU cores * 2) + spindle disks
      minimum-idle: 5
      connection-timeout: 30000     # 30s — fail fast se il pool è esaurito
      idle-timeout: 600000          # 10 minuti
      max-lifetime: 1800000         # 30 minuti — rinnova connessioni periodicamente
      keepalive-time: 30000         # ping ogni 30s per non far chiudere la connessione
      connection-test-query: SELECT 1
```

### pgx Pool (Go)

```go
// Configurazione pgxpool
config, err := pgxpool.ParseConfig(os.Getenv("DATABASE_URL"))
if err != nil {
    return nil, fmt.Errorf("parse db config: %w", err)
}

config.MaxConns = 10
config.MinConns = 2
config.MaxConnLifetime = 30 * time.Minute
config.MaxConnIdleTime = 10 * time.Minute
config.HealthCheckPeriod = 1 * time.Minute
config.ConnConfig.ConnectTimeout = 5 * time.Second

pool, err := pgxpool.NewWithConfig(ctx, config)
if err != nil {
    return nil, fmt.Errorf("create pool: %w", err)
}

// Verifica connettività all'avvio
if err := pool.Ping(ctx); err != nil {
    return nil, fmt.Errorf("ping database: %w", err)
}
```

### Formula per la dimensione del pool

```
Formula empirica (PostgreSQL):
  pool_size = (numero_core_cpu_db * 2) + numero_spindle_disk

Esempio: DB con 4 core, SSD (=1 spindle):
  pool_size = (4 * 2) + 1 = 9  → arrotondare a 10

Regola aggiuntiva: per ogni istanza dell'applicazione
  pool_per_istanza = pool_size_totale / numero_istanze

Es. 10 istanze app, pool totale 20:
  pool_per_istanza = 2
```

---

## Cache Patterns

Il caching riduce la latenza e il carico sul database. Redis è lo strumento di riferimento per il caching distribuito in architetture a microservizi.

### Cache-Aside (Lazy Loading)

Il pattern più comune: l'applicazione gestisce esplicitamente cache e database.

```python
# Python — cache-aside con Redis
import redis
import json

redis_client = redis.Redis(host="redis", port=6379, decode_responses=True)

def get_product(product_id: str) -> dict:
    cache_key = f"product:{product_id}"

    # 1. Cerca in cache
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    # 2. Cache miss → leggi dal DB
    product = db.query("SELECT * FROM products WHERE id = %s", product_id)
    if not product:
        return None

    # 3. Salva in cache con TTL
    redis_client.setex(cache_key, 300, json.dumps(product))  # TTL: 5 minuti
    return product

def update_product(product_id: str, data: dict) -> None:
    db.execute("UPDATE products SET ... WHERE id = %s", product_id)
    # Cache invalidation esplicita
    redis_client.delete(f"product:{product_id}")
```

### Write-Through

Scrittura simultanea su cache e database. Garantisce coerenza ma aumenta la latenza di scrittura.

```go
// Go — write-through
func (r *productRepo) Update(ctx context.Context, product *Product) error {
    // 1. Scrivi sul database
    if err := r.db.UpdateProduct(ctx, product); err != nil {
        return fmt.Errorf("db update: %w", err)
    }

    // 2. Aggiorna cache immediatamente (write-through)
    data, _ := json.Marshal(product)
    cacheKey := fmt.Sprintf("product:%s", product.ID)
    if err := r.cache.Set(ctx, cacheKey, data, 5*time.Minute).Err(); err != nil {
        // Log ma non fallire — la cache è supplementare
        r.logger.Warn("cache write-through failed", "key", cacheKey, "err", err)
    }

    return nil
}
```

### Confronto Pattern Cache

| Pattern | Lettura | Scrittura | Coerenza | Uso tipico |
|---|---|---|---|---|
| Cache-aside | App gestisce | Invalida cache | Eventuale | Default per read-heavy |
| Write-through | Sempre da cache | DB + cache insieme | Forte | Dati letti frequentemente dopo scrittura |
| Write-behind | Da cache | Cache → DB async | Eventuale | Write-heavy, ok con perdita dati minima |
| Read-through | Cache gestisce | Solo DB | Eventuale | Abstraction layer completa |

!!! tip "Cache key naming"
    Usare sempre prefissi strutturati: `{service}:{entity}:{id}`. Esempio: `orders:product:uuid-123`. Permette namespace isolation e flush selettivo con `SCAN` per pattern.

---

## Gestione delle Transazioni

### Transazioni Locali

```java
// Java/Spring — transazione dichiarativa
@Service
@Transactional
public class OrderService {

    @Transactional(isolation = Isolation.READ_COMMITTED,
                   propagation = Propagation.REQUIRED,
                   timeout = 30)
    public Order createOrder(CreateOrderRequest req) {
        Order order = new Order(req);
        orderRepository.save(order);
        inventoryRepository.decrementStock(req.getItems());
        // Se decrementStock lancia eccezione → rollback automatico
        return order;
    }

    // Solo lettura — ottimizza: no lock, usa read replica se disponibile
    @Transactional(readOnly = true)
    public List<Order> findOrdersByUser(UUID userId) {
        return orderRepository.findByUserId(userId);
    }
}
```

### Optimistic Locking

Evita lock pessimistici costosi per operazioni con bassa probabilità di conflitto.

```sql
-- Aggiunta colonna version alla tabella
ALTER TABLE orders ADD COLUMN version INTEGER NOT NULL DEFAULT 1;
```

```go
// Go — optimistic locking con version check
func (r *orderRepo) UpdateStatus(ctx context.Context, orderID uuid.UUID,
                                  currentVersion int, newStatus string) error {
    result, err := r.pool.Exec(ctx,
        `UPDATE orders
         SET status = $1, version = version + 1
         WHERE id = $2 AND version = $3 AND deleted_at IS NULL`,
        newStatus, orderID, currentVersion,
    )
    if err != nil {
        return fmt.Errorf("update: %w", err)
    }

    if result.RowsAffected() == 0 {
        return ErrOptimisticLockConflict  // un'altra istanza ha modificato il record
    }
    return nil
}

// Chiamante: retry su conflitto
for attempt := 0; attempt < 3; attempt++ {
    order, _ := repo.FindByID(ctx, orderID)
    err := repo.UpdateStatus(ctx, orderID, order.Version, "confirmed")
    if !errors.Is(err, ErrOptimisticLockConflict) {
        break
    }
    time.Sleep(50 * time.Millisecond)
}
```

### Outbox Pattern (Transazioni + Messaggi)

Il problema del dual-write: salvare sul DB e pubblicare un evento su Kafka in modo atomico.

```sql
-- Tabella outbox nella stessa transazione del business write
CREATE TABLE outbox_events (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_id UUID        NOT NULL,
    event_type   VARCHAR(100) NOT NULL,
    payload      JSONB        NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);
```

```go
// Go — save order + outbox in una singola transazione
func (s *orderService) CreateOrder(ctx context.Context, req CreateOrderRequest) (*Order, error) {
    return s.db.WithTransaction(ctx, func(tx pgx.Tx) (*Order, error) {
        order := &Order{ID: uuid.New(), Status: "pending", ...}

        // 1. Salva l'ordine
        if _, err := tx.Exec(ctx, insertOrderSQL, order.ID, ...); err != nil {
            return nil, err
        }

        // 2. Salva l'evento nella tabella outbox — STESSA transazione
        event, _ := json.Marshal(OrderCreatedEvent{OrderID: order.ID, ...})
        if _, err := tx.Exec(ctx,
            `INSERT INTO outbox_events (aggregate_id, event_type, payload)
             VALUES ($1, $2, $3)`,
            order.ID, "order.created", event,
        ); err != nil {
            return nil, err
        }

        return order, nil
        // Commit atomico: se fallisce, né l'ordine né l'evento vengono salvati
    })
}
// Un worker separato legge outbox_events e pubblica su Kafka
```

Per approfondimento → [Outbox Pattern](../../messaging/kafka/pattern-microservizi/outbox-pattern.md)

---

## Soft Delete e Auditing

### Soft Delete

```sql
-- Schema con soft delete
ALTER TABLE orders ADD COLUMN deleted_at TIMESTAMPTZ;
ALTER TABLE orders ADD COLUMN deleted_by UUID;

-- Indici parziali per escludere i deleted automaticamente
CREATE INDEX idx_orders_user_active ON orders(user_id)
    WHERE deleted_at IS NULL;
```

```go
// Go — FindByID esclude automaticamente i deleted
func (r *repo) FindByID(ctx context.Context, id uuid.UUID) (*Order, error) {
    err := r.pool.QueryRow(ctx,
        `SELECT id, status, total_price, created_at
         FROM orders
         WHERE id = $1 AND deleted_at IS NULL`,  // ← sempre questo WHERE
        id,
    ).Scan(...)
}

// SoftDelete invece di DELETE fisico
func (r *repo) Delete(ctx context.Context, id uuid.UUID, deletedBy uuid.UUID) error {
    _, err := r.pool.Exec(ctx,
        `UPDATE orders SET deleted_at = NOW(), deleted_by = $2 WHERE id = $1`,
        id, deletedBy,
    )
    return err
}
```

!!! warning "Indici parziali obbligatori"
    Senza `WHERE deleted_at IS NULL` negli indici, le query su record attivi fanno full-scan della tabella inclusi i deleted. Su dataset con molti deleted, le performance degradano drasticamente.

---

## Best Practices

### Evitare il Problema N+1

```python
# ❌ N+1: 1 query per ordini + 1 query per utente per ogni ordine
orders = db.query("SELECT * FROM orders WHERE status = 'pending'")
for order in orders:
    user = db.query("SELECT * FROM users WHERE id = %s", order.user_id)
    # → 1 + N query se ci sono N ordini

# ✅ JOIN o eager loading: sempre 1 query
orders_with_users = db.query("""
    SELECT o.*, u.name, u.email
    FROM orders o
    JOIN users u ON u.id = o.user_id
    WHERE o.status = 'pending'
""")

# ✅ Alternativa: batch load (IN clause)
order_ids = [o.id for o in orders]
users = db.query("SELECT * FROM users WHERE id = ANY(%s)", order_ids)
users_map = {u.id: u for u in users}
```

### Timeout Obbligatori su Ogni Query

```go
// Ogni query deve avere un context con timeout
ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
defer cancel()

rows, err := pool.Query(ctx, "SELECT * FROM orders WHERE user_id = $1", userID)
```

### Separazione Read/Write (CQRS Data Side)

```yaml
# Datasource separati per lettura e scrittura
spring:
  datasource:
    write:
      url: jdbc:postgresql://postgres-primary:5432/orders_db
      hikari:
        maximum-pool-size: 5
    read:
      url: jdbc:postgresql://postgres-replica:5432/orders_db
      hikari:
        maximum-pool-size: 15   # più connessioni per read-heavy
```

```java
@Repository
public class OrderRepositoryImpl {

    @Qualifier("writeDataSource")
    private final DataSource writeDs;

    @Qualifier("readDataSource")
    private final DataSource readDs;

    @Transactional("writeTransactionManager")
    public void save(Order order) { /* usa writeDs */ }

    @Transactional(value = "readTransactionManager", readOnly = true)
    public List<Order> findByStatus(String status) { /* usa readDs */ }
}
```

---

## Troubleshooting

### Problema: Connection pool esaurito sotto carico

**Sintomo:** Errori `connection pool exhausted` o timeout acquisendo connessione. Le request si accumulano nel backlog.

**Causa:** Il pool è troppo piccolo per il carico, oppure le query sono lente e tengono le connessioni occupate troppo a lungo.

**Soluzione:**
```bash
# 1. Verifica connessioni attive su PostgreSQL
SELECT state, count(*)
FROM pg_stat_activity
WHERE datname = 'orders_db'
GROUP BY state;

# 2. Identifica query lente che tengono connessioni aperte
SELECT pid, query, query_start, state, wait_event_type
FROM pg_stat_activity
WHERE datname = 'orders_db' AND state != 'idle'
ORDER BY query_start;

# 3. Aumenta il pool (con cautela — vedi formula CPU)
# 4. Aggiungi PgBouncer davanti al DB se non presente
# 5. Aggiungi connection-timeout basso per fail fast
```

---

### Problema: Migration fallita a metà su produzione

**Sintomo:** La migration si blocca o fallisce con errore. Lo schema è in stato inconsistente.

**Causa:** Query DDL lunga su tabella grossa (es. `ADD COLUMN NOT NULL` fa table rewrite), lock contention, o errore nel SQL.

**Soluzione:**
```sql
-- 1. Verifica stato migrations (Flyway)
SELECT * FROM flyway_schema_history ORDER BY installed_rank DESC LIMIT 5;

-- 2. Per Flyway: repair per marcare migration fallita come risolta dopo fix manuale
-- flyway repair (da CLI o @FlywayDataSource)

-- 3. Per ADD COLUMN su tabella grande: usare pg_repack o ADD COLUMN con DEFAULT NULL
-- ❌ ALTER TABLE large_table ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active';
--    (table rewrite completo, lock lungo)
-- ✅ Step 1: ADD COLUMN nullable
ALTER TABLE large_table ADD COLUMN status VARCHAR(20);
-- ✅ Step 2: backfill in batch
UPDATE large_table SET status = 'active' WHERE id BETWEEN x AND y;
-- ✅ Step 3: SET NOT NULL con check constraint NOT VALID
ALTER TABLE large_table ADD CONSTRAINT chk_status_not_null
    CHECK (status IS NOT NULL) NOT VALID;
ALTER TABLE large_table VALIDATE CONSTRAINT chk_status_not_null;
```

---

### Problema: Cache stale dopo aggiornamento

**Sintomo:** Gli utenti vedono dati vecchi dopo un aggiornamento. Il problema scompare dopo il TTL.

**Causa:** Cache invalidation non gestita correttamente, o race condition tra invalidazione e ri-lettura.

**Soluzione:**
```go
// Pattern cache invalidation sicuro: delete + reload
func (s *service) UpdateOrder(ctx context.Context, order *Order) error {
    // 1. Aggiorna DB
    if err := s.repo.Update(ctx, order); err != nil {
        return err
    }
    // 2. Invalida cache DOPO il commit DB
    // Non aggiornare la cache qui — la prossima read la ricaricherà fresca
    cacheKey := fmt.Sprintf("order:%s", order.ID)
    if err := s.cache.Del(ctx, cacheKey).Err(); err != nil {
        s.logger.Warn("cache invalidation failed", "key", cacheKey)
        // Non è un errore fatale — il TTL coprirà la finestra
    }
    return nil
}
```

---

### Problema: Deadlock su transazioni concorrenti

**Sintomo:** Errori `deadlock detected` intermittenti, più frequenti sotto carico.

**Causa:** Due transazioni acquisiscono lock in ordine opposto sulle stesse righe.

**Soluzione:**
```sql
-- 1. Identifica i deadlock nel log PostgreSQL
-- LOG: deadlock detected
-- DETAIL: Process X waits for ShareLock on transaction Y; blocked by process Z

-- 2. Soluzione: ordinare sempre gli accessi nello stesso ordine
-- ❌ TX1: lock order 1, poi lock order 2
-- ❌ TX2: lock order 2, poi lock order 1

-- ✅ Entrambe le TX lockano in ordine crescente per ID
SELECT * FROM orders WHERE id IN (1, 2) ORDER BY id FOR UPDATE;

-- 3. Ridurre la durata delle transazioni — meno tempo locked = meno deadlock
-- 4. Usare SELECT ... FOR UPDATE SKIP LOCKED per job worker
SELECT id FROM tasks WHERE status = 'pending' LIMIT 1 FOR UPDATE SKIP LOCKED;
```

---

## Relazioni

??? info "Databases — Configurazione infrastrutturale del DB"
    Connection pooling a livello di infrastruttura (PgBouncer su Kubernetes), replica setup, backup e PITR → [Databases](../../databases/_index.md). Questa sezione si concentra sul codice applicativo, quella sull'infrastruttura.

??? info "Dev / Integrazioni — Saga Pattern e consistenza distribuita"
    Quando un'operazione coinvolge più servizi con database separati, le transazioni locali non bastano. Il Saga pattern coordina sequenze di transazioni locali → [Integrazioni](../integrazioni/_index.md).

??? info "Messaging / Outbox Pattern — Dual-write atomico"
    Per pubblicare eventi Kafka in modo atomico con il salvataggio sul database → [Outbox Pattern](../../messaging/kafka/pattern-microservizi/outbox-pattern.md).

??? info "Messaging / CQRS — Separazione read/write model"
    Il CQRS spinto all'estremo usa database distinti per read model e write model, sincronizzati via eventi → [CQRS](../../messaging/kafka/pattern-microservizi/cqrs.md).

??? info "Databases / Connection Pooling — PgBouncer nel dettaglio"
    Configurazione avanzata di PgBouncer, modalità transaction vs session, monitoring → [Connection Pooling](../../databases/postgresql/connection-pooling.md).

??? info "Databases / NoSQL — Redis come cache"
    Strutture dati Redis, Redis Cluster, Redis Sentinel, TTL strategies, eviction policies → [Redis](../../databases/nosql/redis.md).

---

## Riferimenti

- [Database per Microservice Pattern — microservices.io](https://microservices.io/patterns/data/database-per-service.html)
- [Outbox Pattern — microservices.io](https://microservices.io/patterns/data/transactional-outbox.html)
- [Flyway Documentation](https://documentation.red-gate.com/flyway)
- [golang-migrate](https://github.com/golang-migrate/migrate)
- [pgx — PostgreSQL Driver & Toolkit for Go](https://github.com/jackc/pgx)
- [HikariCP — Connection Pool](https://github.com/brettwooldridge/HikariCP)
- [PgBouncer Documentation](https://www.pgbouncer.org/config.html)
- [Use The Index, Luke — SQL Performance](https://use-the-index-luke.com/)
- [Martin Fowler — Patterns of Enterprise Application Architecture](https://martinfowler.com/books/eaa.html)
