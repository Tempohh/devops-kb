---
title: "Database Patterns da Codice — ORM e Accesso ai Dati nei Microservizi"
slug: database-patterns
category: dev
tags: [database, orm, jpa, hibernate, entity-framework, gorm, mongodb, connection-pool, microservizi, java, dotnet, go]
search_keywords: [database patterns, orm patterns, jpa hibernate, spring data jpa, n+1 query, n+1 problem, lazy loading, eager loading, entitygraph, join fetch, transactional boundaries, @transactional, spring transaction, second-level cache, hibernate cache, entity framework core, efcore, dbcontext, dbcontext lifetime, adddbcontext, adddbcontextfactory, ef migrations kubernetes, owned entities efcore, compiled queries efcore, gorm go, gorm hooks, gorm transactions, gorm soft delete, gorm batch, mongodb spring data, spring data mongodb, mongotemplate, motor python async, motor asyncmotorclient, hikaricp, hikari connection pool, java connection pool, sqlclient dotnet, microsoft.data.sqlclient, pgxpool go, postgresql go, database per microservice, shared schema, schema condiviso, repository pattern, unit of work, query optimization orm, orm performance, lazy loading pitfall, proxy hibernate, fetch strategy, database access pattern, microservice database, aggregate root, bounded context database, outbox pattern database, optimistic locking, pessimistic locking, versioning jpa, concurrency orm]
parent: dev/integrazioni/_index
related: [databases/postgresql/connection-pooling, databases/nosql/mongodb, databases/fondamentali/transazioni-concorrenza, dev/linguaggi/java-spring-boot, dev/linguaggi/dotnet, dev/linguaggi/go]
official_docs: https://docs.spring.io/spring-data/jpa/docs/current/reference/html/
status: complete
difficulty: advanced
last_updated: 2026-03-28
---

# Database Patterns da Codice — ORM e Accesso ai Dati nei Microservizi

## Panoramica

Ogni microservizio che persiste dati deve risolvere gli stessi problemi fondamentali: come mappare oggetti di dominio a righe di database, come gestire le transazioni, come evitare query inefficienti, e come dimensionare correttamente il pool di connessioni. Gli ORM semplificano il mapping ma introducono **pitfall non ovvie** — un campo `@ManyToOne` con lazy loading innocuo in sviluppo può generare centinaia di query in produzione.

Questo documento copre la prospettiva del developer: le scelte ORM concrete per i tre stack enterprise principali (Java/Spring, .NET, Go), l'accesso a MongoDB, la configurazione del connection pooling lato applicazione, e le decisioni architetturali su database-per-servizio vs schema condiviso.

!!! warning "Separazione responsabilità"
    Questo documento si concentra sul codice applicativo. La configurazione dell'infrastruttura database (PgBouncer, replica, failover) è separata — vedi [Connection Pooling — PgBouncer](../../databases/postgresql/connection-pooling.md).

---

## Concetti Chiave

### Il Problema N+1

Il problema N+1 è la causa più comune di degradazione delle performance negli ORM. Si manifesta quando il codice carica una collection e poi accede a un'associazione per ogni elemento:

```java
// SBAGLIATO — genera 1 query per gli ordini + N query per ogni cliente
List<Order> orders = orderRepository.findAll(); // SELECT * FROM orders → N righe
for (Order o : orders) {
    System.out.println(o.getCustomer().getName()); // SELECT * FROM customers WHERE id=? × N
}
```

Il fix dipende dal contesto:
- **JOIN FETCH / EntityGraph**: carica tutto in una query (attenzione ai prodotti cartesiani su collection multiple)
- **Batch size**: raggruppa i SELECT secondari in batch (`IN (id1, id2, ..., idN)`)
- **DTO projection**: selezione diretta dei campi necessari senza entità JPA

### Lazy vs Eager Loading

| Strategia | Comportamento | Quando usarla |
|---|---|---|
| `LAZY` (default per `@*ToMany`) | L'associazione viene caricata on-demand alla prima lettura | La maggior parte dei casi — evita caricamenti inutili |
| `EAGER` (default per `@*ToOne`) | L'associazione viene sempre caricata con l'entità | Solo per associazioni sempre necessarie e di dimensione costante |

!!! warning "EAGER è quasi sempre sbagliato"
    `FetchType.EAGER` viene applicato a **ogni** query sull'entità, anche JPQL che non accede all'associazione. Con più relazioni EAGER si ottengono join impliciti e prodotti cartesiani inattesi. Preferire LAZY e specificare il fetch esplicitamente quando serve.

### Transazioni — Boundaries e Propagation

Una transazione deve abbracciare una unità di lavoro logicamente atomica. Le trappole più comuni:

- **Transazione aperta troppo lunga**: include chiamate HTTP o operazioni lente → blocca connessioni del pool
- **Transazione aperta troppo corta**: split tra repository → inconsistenze se il secondo fallisce
- **LazyInitializationException**: accesso a un'associazione lazy fuori dalla transazione

```
@Service → @Transactional (confine corretto: l'intera operazione di business)
  ├── repositoryA.save(...)
  ├── repositoryB.findById(...)   ← stesso contesto transazionale
  └── evento pubblicato (outbox)  ← scritto nel DB nella stessa TX
```

---

## JPA / Hibernate — Java (Spring Boot)

### Spring Data JPA Repository

```java
// Approccio base: Repository con query derivate e JPQL
@Repository
public interface OrderRepository extends JpaRepository<Order, UUID> {

    // Query derivata — Spring genera la JPQL automaticamente
    List<Order> findByStatusAndCreatedAtAfter(OrderStatus status, Instant cutoff);

    // JPQL con JOIN FETCH — risolve N+1 per un'associazione singola
    @Query("SELECT o FROM Order o JOIN FETCH o.customer WHERE o.status = :status")
    List<Order> findWithCustomer(@Param("status") OrderStatus status);

    // DTO Projection — carica solo i campi necessari, nessuna entità JPA in memoria
    @Query("SELECT new com.example.dto.OrderSummary(o.id, o.total, c.name) " +
           "FROM Order o JOIN o.customer c WHERE o.status = :status")
    List<OrderSummary> findSummaries(@Param("status") OrderStatus status);
}
```

### EntityGraph — Fix N+1 Dichiarativo

`@EntityGraph` permette di specificare le associazioni da caricare in JOIN senza modificare la query:

```java
@Entity
@NamedEntityGraph(
    name = "Order.withItems",
    attributeNodes = {
        @NamedAttributeNode("customer"),
        @NamedAttributeNode(value = "items", subgraph = "items.product"),
    },
    subgraphs = @NamedSubgraph(
        name = "items.product",
        attributeNodes = @NamedAttributeNode("product")
    )
)
public class Order { /* ... */ }

// Nel repository
@EntityGraph("Order.withItems")
List<Order> findByStatus(OrderStatus status);
// Genera: SELECT ... FROM orders o
//         JOIN customers c ON ...
//         JOIN order_items i ON ...
//         JOIN products p ON ...
// Una sola query.
```

!!! warning "EntityGraph e collection multiple"
    Caricare due `@OneToMany` con JOIN FETCH/EntityGraph nella stessa query genera un prodotto cartesiano (M×N righe). Per più collection usare query separate o `@BatchSize`.

### Batch Size — Alternativa al JOIN

```java
// Configurazione globale in application.properties
spring.jpa.properties.hibernate.default_batch_fetch_size=30

// Oppure per-entità
@OneToMany(mappedBy = "order", fetch = FetchType.LAZY)
@BatchSize(size = 30)
private List<OrderItem> items;

// Con batch size=30, per 100 ordini:
// Senza batch:  100 SELECT item WHERE order_id=?
// Con batch:    4 SELECT item WHERE order_id IN (?, ?, ..., ?) — ~4 query
```

### @Transactional — Boundaries e Propagation

```java
@Service
@Transactional(readOnly = true)  // default: tutte le operazioni read-only (ottimizzazione Hibernate)
public class OrderService {

    // Override per operazioni di scrittura
    @Transactional  // REQUIRED (default): partecipa alla TX esistente o ne apre una nuova
    public Order createOrder(CreateOrderCommand cmd) {
        Order order = new Order(cmd);
        orderRepository.save(order);
        // Outbox: evento scritto nella stessa TX — garantisce atomicità
        outboxRepository.save(new OutboxEvent("OrderCreated", order.getId()));
        return order;
    }

    // REQUIRES_NEW: nuova TX indipendente — utile per audit log che non deve rollback
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void saveAuditLog(AuditEntry entry) {
        auditRepository.save(entry);
    }

    // readOnly = true: Hibernate salta dirty checking al flush — risparmio CPU su query
    public List<OrderSummary> listOrders(OrderFilter filter) {
        return orderRepository.findSummaries(filter);
    }
}
```

!!! warning "@Transactional e proxy Spring"
    `@Transactional` funziona tramite proxy AOP. Una chiamata **interna** allo stesso bean (es. `this.metodoTransazionale()`) bypassa il proxy e non apre nessuna transazione. Spostare il metodo in un bean separato o usare `ApplicationContext.getBean()`.

### Second-Level Cache (Hibernate L2)

```yaml
# application.yml — Hibernate second-level cache con Caffeine (in-process)
spring:
  jpa:
    properties:
      hibernate:
        cache:
          use_second_level_cache: true
          use_query_cache: true
          region.factory_class: org.hibernate.cache.jcache.JCacheRegionFactory
        javax:
          cache:
            provider: com.github.benmanes.caffeine.jcache.spi.CaffeineCachingProvider
```

```java
@Entity
@Cache(usage = CacheConcurrencyStrategy.READ_WRITE)  // aggiornato a ogni write
public class Product {
    @Id private UUID id;
    private String name;
    private BigDecimal price;
    // entità raramente modificata — candidata ideale per L2 cache
}

// Query cache — cachea i risultati di query specifiche
@QueryHints(@QueryHint(name = "org.hibernate.cacheable", value = "true"))
List<Product> findByCategory(String category);
```

!!! tip "Quando usare L2 cache"
    Ideale per: lookup table, entità di configurazione, dati raramente modificati con alta frequenza di lettura. **Non usare** su entità con alta frequenza di write o in cluster senza invalidazione distribuita (rischio dati stale).

### HikariCP — Connection Pool Java

```yaml
# application.yml — configurazione HikariCP (default in Spring Boot 2+)
spring:
  datasource:
    url: jdbc:postgresql://db:5432/mydb
    username: app
    password: ${DB_PASSWORD}
    hikari:
      maximum-pool-size: 10          # regola base: (num_core * 2) + num_disk
      minimum-idle: 5                # connessioni mantenute anche a basso carico
      connection-timeout: 30000      # ms — attesa per connessione dal pool
      idle-timeout: 600000           # ms — connessione idle rimossa dopo 10 min
      max-lifetime: 1800000          # ms — max vita connessione (< server timeout)
      pool-name: HikariPool-Orders
      leak-detection-threshold: 5000 # ms — logga connessioni non rilasciate
```

```java
// Verifica pool a runtime tramite MBean o metriche Micrometer
// In Actuator: GET /actuator/metrics/hikaricp.connections.active
// Prometheus: hikaricp_connections_active{pool="HikariPool-Orders"}
```

!!! tip "Formula pool size"
    Per PostgreSQL: `(num_cpu_core × 2) + num_disk`. Con 4 core e SSD: 9-10 connessioni per pod. Se usi PgBouncer davanti, il pool Hikari può essere più piccolo (es. 5-8) perché PgBouncer gestisce il multiplexing.

---

## Entity Framework Core — .NET

### DbContext Lifetime in Dependency Injection

Il `DbContext` in EF Core non è thread-safe e mantiene un change tracker in memoria. La scelta del lifetime nella DI ha impatti significativi:

```csharp
// Corretto per applicazioni web (default raccomandato)
// DbContext creato per ogni HTTP request, disposed automaticamente
builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseNpgsql(connectionString));

// Corretto per worker/background services e Blazor Server
// DbContextFactory crea istanze on-demand — evita conflitti su thread multipli
builder.Services.AddDbContextFactory<AppDbContext>(options =>
    options.UseNpgsql(connectionString));

// Nel worker:
public class OrderProcessor(IDbContextFactory<AppDbContext> factory)
{
    public async Task ProcessAsync(Guid orderId)
    {
        await using var ctx = await factory.CreateDbContextAsync();
        var order = await ctx.Orders.FindAsync(orderId);
        // ...
        await ctx.SaveChangesAsync();
    } // ctx disposed qui — connessione rilasciata al pool
}
```

!!! warning "DbContext Scoped vs Singleton"
    Non registrare mai `DbContext` come Singleton — il change tracker accumula entità indefinitamente causando memory leak e risultati inconsistenti. Non iniettare un `DbContext` Scoped in un Singleton (rischio "captive dependency").

### Migrations in Kubernetes — Init Container Pattern

```yaml
# Kubernetes — init container esegue le migration prima che il pod principale si avvii
spec:
  initContainers:
    - name: db-migration
      image: myapp:latest
      command: ["dotnet", "MyApp.dll", "--migrate-only"]
      env:
        - name: ConnectionStrings__Default
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: connection-string
  containers:
    - name: app
      image: myapp:latest
```

```csharp
// Program.cs — supporto flag --migrate-only
if (args.Contains("--migrate-only"))
{
    using var scope = app.Services.CreateScope();
    var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
    await db.Database.MigrateAsync();
    Console.WriteLine("Migration completata.");
    return;
}

app.Run();
```

### Owned Entities — Value Objects senza tabella separata

```csharp
// Modellare indirizzi o oggetti di valore come Owned — no JOIN richiesto
public class Customer
{
    public Guid Id { get; private set; }
    public string Name { get; private set; } = null!;
    public Address ShippingAddress { get; private set; } = null!;
}

[Owned]
public record Address(string Street, string City, string PostalCode, string Country);

// In OnModelCreating — le colonne finiscono nella stessa tabella Customer
modelBuilder.Entity<Customer>().OwnsOne(c => c.ShippingAddress, addr =>
{
    addr.Property(a => a.Street).HasColumnName("shipping_street");
    addr.Property(a => a.City).HasColumnName("shipping_city");
    addr.Property(a => a.PostalCode).HasColumnName("shipping_postal_code");
    addr.Property(a => a.Country).HasColumnName("shipping_country");
});
```

### Compiled Queries — Performance per Query Ripetitive

```csharp
// Compiled query — la traduzione LINQ→SQL avviene una sola volta (cached a livello app)
private static readonly Func<AppDbContext, OrderStatus, IAsyncEnumerable<Order>>
    GetOrdersByStatus = EF.CompileAsyncQuery(
        (AppDbContext ctx, OrderStatus status) =>
            ctx.Orders
               .Include(o => o.Customer)
               .Where(o => o.Status == status)
               .OrderByDescending(o => o.CreatedAt)
    );

// Utilizzo
public async Task<List<Order>> GetPendingOrdersAsync()
{
    var results = new List<Order>();
    await foreach (var order in GetOrdersByStatus(_ctx, OrderStatus.Pending))
        results.Add(order);
    return results;
}
```

### SqlClient — Connection Pool .NET

```csharp
// Il pool è gestito automaticamente da Microsoft.Data.SqlClient / Npgsql
// Configurazione tramite connection string
var connectionString = "Host=db;Database=mydb;Username=app;Password=...;" +
                       "Maximum Pool Size=20;" +     // default: 100
                       "Minimum Pool Size=5;" +
                       "Connection Idle Lifetime=300;" + // secondi
                       "Connection Pruning Interval=10;";

// Per PostgreSQL con Npgsql
builder.Services.AddDbContext<AppDbContext>(options =>
    options.UseNpgsql(connectionString, npgsql =>
    {
        npgsql.EnableRetryOnFailure(maxRetryCount: 3,
                                    maxRetryDelay: TimeSpan.FromSeconds(5),
                                    errorCodesToAdd: null);
    }));
```

---

## GORM — Go

### Configurazione Base e Connection Pool

```go
import (
    "gorm.io/driver/postgres"
    "gorm.io/gorm"
    "gorm.io/gorm/logger"
)

func NewDB(dsn string) (*gorm.DB, error) {
    db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{
        Logger: logger.Default.LogMode(logger.Warn), // logga solo query lente e errori
    })
    if err != nil {
        return nil, err
    }

    sqlDB, _ := db.DB()
    sqlDB.SetMaxOpenConns(10)              // pool massimo
    sqlDB.SetMaxIdleConns(5)              // connessioni idle mantenute
    sqlDB.SetConnMaxLifetime(time.Hour)   // rotazione connessioni
    sqlDB.SetConnMaxIdleTime(10 * time.Minute)

    return db, nil
}
```

### Transazioni in GORM

```go
// Transazione esplicita — pattern raccomandato per operazioni multi-step
func (r *OrderRepository) CreateWithItems(ctx context.Context, order *Order) error {
    return r.db.WithContext(ctx).Transaction(func(tx *gorm.DB) error {
        if err := tx.Create(order).Error; err != nil {
            return err // rollback automatico
        }
        for _, item := range order.Items {
            item.OrderID = order.ID
            if err := tx.Create(&item).Error; err != nil {
                return err // rollback
            }
        }
        // SavePoint — checkpoint parziale nella transazione
        tx.SavePoint("after_items")
        if err := tx.Create(&OutboxEvent{OrderID: order.ID}).Error; err != nil {
            tx.RollbackTo("after_items") // rollback solo all'outbox, non all'ordine
            return err
        }
        return nil // commit
    })
}

// Transazione manuale per controllo esplicito
func (r *OrderRepository) Transfer(ctx context.Context, fromID, toID UUID, amount float64) error {
    tx := r.db.WithContext(ctx).Begin()
    if tx.Error != nil {
        return tx.Error
    }
    defer func() {
        if r := recover(); r != nil {
            tx.Rollback()
        }
    }()

    if err := tx.Model(&Account{}).Where("id = ?", fromID).
        Update("balance", gorm.Expr("balance - ?", amount)).Error; err != nil {
        tx.Rollback()
        return err
    }
    if err := tx.Model(&Account{}).Where("id = ?", toID).
        Update("balance", gorm.Expr("balance + ?", amount)).Error; err != nil {
        tx.Rollback()
        return err
    }
    return tx.Commit().Error
}
```

### Hooks — Logica Pre/Post Operazione

```go
type Order struct {
    gorm.Model
    Status    string
    Total     float64
    UpdatedBy string
}

// Hook BeforeCreate — validazione o enrichment prima dell'INSERT
func (o *Order) BeforeCreate(tx *gorm.DB) error {
    if o.Total <= 0 {
        return errors.New("total deve essere positivo")
    }
    o.Status = "pending" // forza stato iniziale
    return nil
}

// Hook AfterCreate — side effect post-INSERT (stessa transazione)
func (o *Order) AfterCreate(tx *gorm.DB) error {
    return tx.Create(&AuditLog{
        EntityID: o.ID,
        Action:   "created",
        At:       time.Now(),
    }).Error
}
```

### Soft Delete e Batch Operations

```go
// Soft delete — gorm.Model include DeletedAt *gorm.DeletedAt
// Delete non rimuove la riga ma imposta deleted_at
type Product struct {
    gorm.Model       // ID, CreatedAt, UpdatedAt, DeletedAt
    Name  string
    Price float64
}

db.Delete(&product) // UPDATE products SET deleted_at=NOW() WHERE id=?

// Query automaticamente esclude soft-deleted
db.Find(&products) // WHERE deleted_at IS NULL

// Includere soft-deleted esplicitamente
db.Unscoped().Find(&products) // nessun filtro deleted_at

// Batch insert — molto più efficiente di loop di Create
orders := []Order{order1, order2, order3, /* ... */}
db.CreateInBatches(orders, 100) // INSERT in gruppi da 100

// Batch update con clausola WHERE
db.Model(&Order{}).Where("status = ?", "draft").
    Updates(map[string]interface{}{"status": "cancelled", "updated_by": "system"})
```

### pgxpool — Pool Nativo PostgreSQL in Go

```go
// Alternativa a GORM per query SQL native con pgxpool (github.com/jackc/pgx/v5)
import "github.com/jackc/pgx/v5/pgxpool"

func NewPool(ctx context.Context, dsn string) (*pgxpool.Pool, error) {
    cfg, err := pgxpool.ParseConfig(dsn)
    if err != nil {
        return nil, err
    }
    cfg.MaxConns = 10
    cfg.MinConns = 2
    cfg.MaxConnLifetime = time.Hour
    cfg.MaxConnIdleTime = 30 * time.Minute
    cfg.HealthCheckPeriod = time.Minute

    return pgxpool.NewWithConfig(ctx, cfg)
}

// Query con pool — connessione acquisita e rilasciata automaticamente
func (r *ProductRepo) FindByID(ctx context.Context, id uuid.UUID) (*Product, error) {
    row := r.pool.QueryRow(ctx,
        "SELECT id, name, price FROM products WHERE id = $1", id)
    var p Product
    if err := row.Scan(&p.ID, &p.Name, &p.Price); err != nil {
        return nil, err
    }
    return &p, nil
}
```

---

## MongoDB — Spring Data e Motor (Python)

### Spring Data MongoDB

```java
@Document(collection = "orders")
public class Order {
    @Id
    private String id;
    private String customerId;
    private List<OrderItem> items;          // embedded — no JOIN
    private Address shippingAddress;        // embedded value object
    private Instant createdAt;

    @DBRef                                  // riferimento a documento Customer
    private Customer customer;              // caricato con query separata (lazy by default)
}

@Repository
public interface OrderRepository extends MongoRepository<Order, String> {

    // Query derivata — Spring genera il query document
    List<Order> findByCustomerIdAndCreatedAtAfter(String customerId, Instant cutoff);

    // Aggregation pipeline — necessaria per operazioni complesse
    @Aggregation(pipeline = {
        "{ $match: { status: ?0 } }",
        "{ $group: { _id: '$customerId', total: { $sum: '$totalAmount' } } }",
        "{ $sort: { total: -1 } }",
        "{ $limit: 10 }"
    })
    List<CustomerTotal> findTopCustomersByStatus(String status);
}
```

```java
// MongoTemplate per operazioni più complesse o bulk
@Service
public class OrderService {

    private final MongoTemplate mongoTemplate;

    public void bulkStatusUpdate(List<String> orderIds, String newStatus) {
        Query query = Query.query(Criteria.where("_id").in(orderIds));
        Update update = Update.update("status", newStatus)
                              .currentDate("updatedAt");
        mongoTemplate.updateMulti(query, update, Order.class);
    }

    // Upsert — insert se non esiste, update se esiste
    public void upsertProduct(Product p) {
        Query query = Query.query(Criteria.where("sku").is(p.getSku()));
        Update update = new Update()
            .set("name", p.getName())
            .set("price", p.getPrice())
            .setOnInsert("createdAt", Instant.now());
        mongoTemplate.upsert(query, update, Product.class);
    }
}
```

!!! tip "Document design: embed vs reference"
    **Embed** quando i dati vengono sempre letti insieme all'aggregato (es. `OrderItem` nell'ordine). **Reference** (`@DBRef`) quando l'entità ha ciclo di vita indipendente e dimensione variabile (es. `Customer`). In MongoDB, la denormalizzazione è normale e preferita ai join.

### Motor — MongoDB Async in Python

```python
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import asyncio

# Configurazione client async (un client per applicazione — thread-safe)
client = AsyncIOMotorClient(
    "mongodb://user:pass@host:27017/mydb",
    maxPoolSize=10,
    minPoolSize=2,
    serverSelectionTimeoutMS=5000,
)
db = client["mydb"]
orders_collection = db["orders"]

# CRUD asincrono con Motor
async def find_order(order_id: str) -> dict | None:
    return await orders_collection.find_one({"_id": ObjectId(order_id)})

async def create_order(order: dict) -> str:
    result = await orders_collection.insert_one(order)
    return str(result.inserted_id)

async def update_order_status(order_id: str, status: str) -> bool:
    result = await orders_collection.update_one(
        {"_id": ObjectId(order_id)},
        {"$set": {"status": status, "updatedAt": datetime.utcnow()}}
    )
    return result.modified_count > 0

# Aggregation async
async def get_revenue_by_day(from_date: datetime) -> list[dict]:
    pipeline = [
        {"$match": {"createdAt": {"$gte": from_date}}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$createdAt"}},
            "revenue": {"$sum": "$total"}
        }},
        {"$sort": {"_id": 1}}
    ]
    return await orders_collection.aggregate(pipeline).to_list(length=None)
```

---

## Database per Microservizio vs Schema Condiviso

### Trade-off Principali

| Dimensione | Database per Microservizio | Schema Condiviso |
|---|---|---|
| **Autonomia del team** | Alta — deploy indipendente, schema evolutivo | Bassa — migration coordinate tra team |
| **Join tra entità** | Impossibile via SQL — richiedono API call o replica | Naturali e performanti |
| **Consistenza** | Eventual consistency — richiede pattern Saga o Outbox | ACID native tra tabelle |
| **Coupling** | Basso — nessuna dipendenza a livello DB | Alto — schema condiviso crea implicit coupling |
| **Operational overhead** | Alto — N database da gestire, backup, monitoring | Basso — un solo database |
| **Isolamento failure** | Alto — DB down impatta solo il servizio | Basso — DB down impatta tutti i servizi |

### Quando Usare Schema Condiviso (con guardrail)

```sql
-- Schema separato per servizio, stesso cluster PostgreSQL
-- Ogni servizio accede SOLO al proprio schema tramite search_path

-- Schema migration del servizio Orders
CREATE SCHEMA IF NOT EXISTS orders;
SET search_path = orders;

CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL,  -- NO foreign key verso schema customers
    status VARCHAR(50) NOT NULL,
    total NUMERIC(10,2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

```yaml
# application.yml — servizio Orders usa solo il proprio schema
spring:
  datasource:
    url: jdbc:postgresql://db:5432/platform?currentSchema=orders
  jpa:
    properties:
      hibernate:
        default_schema: orders
```

!!! warning "Cross-schema join = hard coupling"
    Anche su stesso cluster PostgreSQL, un JOIN tra `orders.orders` e `customers.customers` crea un vincolo che rende impossibile separare i servizi in futuro. Preferire API call o event-driven replication per dati cross-dominio.

---

## Best Practices

- **Evitare `findAll()` senza paginazione**: su tabelle crescenti causa OOM. Usare sempre `Pageable` (JPA), `Skip/Take` (EF Core), o cursori (GORM, pgx).
- **Proiezioni sulle query di lettura**: non caricare entità complete quando servono solo 2-3 campi. Le DTO projection riducono I/O, memoria, e parsing.
- **Transazioni read-only esplicite**: `@Transactional(readOnly = true)` (JPA), `.AsNoTracking()` (EF Core), abilitano ottimizzazioni del runtime.
- **Pool size < server max_connections**: la somma dei pool di tutti i pod non deve superare `max_connections` di PostgreSQL. Con PgBouncer in mezzo, i limiti cambiano.
- **Circuit breaker per operazioni DB lente**: se la query supera il timeout, non bloccare il thread. Usare connection timeout + circuit breaker (vedi [Circuit Breaker](../resilienza/circuit-breaker.md)).
- **Migration idempotenti**: ogni migration deve poter essere eseguita più volte senza errori — critico in ambienti Kubernetes dove init container può ripartire.

!!! tip "Regola generale sul fetch"
    Inizia sempre con `LAZY` su tutto. Quando identifichi (tramite slow query log o APM) un N+1, aggiungilo come `JOIN FETCH` / `EntityGraph` / `Include` solo per quella query specifica — non a livello globale dell'entità.

---

## Troubleshooting

### Sintomo: Query molto lente in produzione, veloci in dev

**Causa**: In dev il database ha pochi record — il piano query usa Sequential Scan invece di Index Scan. In produzione con milioni di righe le stesse query diventano lente.

**Soluzione**:
```sql
-- Verifica il piano query su dati reali
EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM orders WHERE customer_id = 'uuid-123';
-- Cerca: "Seq Scan" su tabelle grandi → manca un indice
-- Crea l'indice
CREATE INDEX CONCURRENTLY idx_orders_customer_id ON orders(customer_id);
```

### Sintomo: `LazyInitializationException` (JPA) / `ObjectDisposedException` (EF Core)

**Causa**: Accesso a un'associazione lazy dopo la chiusura della sessione/contesto. Tipicamente in un DTO transformer fuori dalla transazione, o in un controller che tenta di serializzare l'entità.

**Soluzione**:
```java
// Opzione 1: caricare esplicitamente ciò che serve dentro la transazione
@Transactional(readOnly = true)
public OrderDTO getOrder(UUID id) {
    Order order = repo.findWithItems(id); // JOIN FETCH items
    return OrderDTO.from(order);          // serializzazione dentro TX
}

// Opzione 2: usare DTO projection — nessuna entità, nessun problema lazy
@Query("SELECT new OrderDTO(o.id, o.total, c.name) FROM Order o JOIN o.customer c WHERE o.id = :id")
Optional<OrderDTO> findDtoById(@Param("id") UUID id);
```

### Sintomo: Pool esaurito — timeout su acquisizione connessione

**Causa**: Il pool è dimensionato troppo piccolo, oppure ci sono leak (connessioni non rilasciate), oppure le query sono troppo lente e tengono le connessioni occupate.

**Soluzione**:
```yaml
# 1. Abilita leak detection (HikariCP)
spring.datasource.hikari.leak-detection-threshold: 2000  # ms

# 2. Verifica metriche
# hikaricp_connections_active — quante sono in uso
# hikaricp_connections_pending — quante stanno aspettando
# hikaricp_connections_timeout_total — quante hanno superato il timeout

# 3. Riduci la durata delle transazioni — la connessione è tenuta per tutta la TX
# 4. Aggiungi statement_timeout a PostgreSQL come safety net
```

```sql
-- statement_timeout: interrompe query che durano più di N ms
-- Impostato a livello di role o di connessione
ALTER ROLE app_user SET statement_timeout = '30s';
```

### Sintomo: Stale data dopo update — EF Core non vede le modifiche

**Causa**: Il `DbContext` ha in memoria una versione cachata dell'entità. `SaveChanges` non fa una re-fetch automatica dal DB.

**Soluzione**:
```csharp
// Opzione 1: reload esplicito dopo update
ctx.Entry(order).Reload();

// Opzione 2: con optimistic concurrency — EF Core rileva conflitti automaticamente
public class Order
{
    public Guid Id { get; set; }
    [Timestamp]
    public byte[] RowVersion { get; set; } = null!; // SQL Server
    // Per PostgreSQL usare xmin:
    // public uint xmin { get; set; }
}
// Se due processi aggiornano lo stesso ordine, il secondo riceve DbUpdateConcurrencyException
```

### Sintomo: GORM non aggiorna campi con valore zero (0, false, "")

**Causa**: GORM usa `Updates()` con struct — i campi zero-value vengono ignorati (considerati "non specificati").

**Soluzione**:
```go
// SBAGLIATO — amount=0 e active=false non vengono aggiornati
db.Model(&product).Updates(Product{Price: 0, Active: false})

// CORRETTO — usare map per aggiornare zero-values
db.Model(&product).Updates(map[string]interface{}{
    "price":  0,
    "active": false,
})

// OPPURE — usare Select per specificare esattamente i campi
db.Model(&product).Select("price", "active").Updates(Product{Price: 0, Active: false})
```

---

## Relazioni

??? info "Connection Pooling lato infrastruttura — PgBouncer"
    PgBouncer è il pooler lato server: riceve connessioni da tutti i pod e mantiene un pool ridotto verso PostgreSQL. HikariCP / Npgsql / pgxpool sono i pool **lato applicazione**. In produzione si usano entrambi a livelli diversi dello stack.

    **Approfondimento completo →** [Connection Pooling — PgBouncer](../../databases/postgresql/connection-pooling.md)

??? info "Transazioni distribuite e Saga Pattern"
    Quando una operazione di business attraversa più microservizi con database separati, le transazioni ACID non bastano. Il Saga pattern coordina le operazioni con compensazioni esplicite.

    **Approfondimento completo →** [Transazioni e Concorrenza](../../databases/fondamentali/transazioni-concorrenza.md)

??? info "MongoDB — Architettura e Replicazione"
    Spring Data MongoDB e Motor coprono l'accesso da codice. Per replica sets, sharding, e configurazione operativa di MongoDB, vedi la documentazione di database.

    **Approfondimento completo →** [MongoDB](../../databases/nosql/mongodb.md)

---

## Riferimenti

- [Spring Data JPA Reference Documentation](https://docs.spring.io/spring-data/jpa/docs/current/reference/html/)
- [Hibernate ORM User Guide — Fetching](https://docs.jboss.org/hibernate/orm/current/userguide/html_single/Hibernate_User_Guide.html#fetching)
- [Entity Framework Core Documentation](https://learn.microsoft.com/en-us/ef/core/)
- [GORM Documentation](https://gorm.io/docs/)
- [pgx / pgxpool Documentation](https://pkg.go.dev/github.com/jackc/pgx/v5/pgxpool)
- [Motor (async MongoDB driver for Python)](https://motor.readthedocs.io/)
- [HikariCP Configuration](https://github.com/brettwooldridge/HikariCP#configuration-knobs-baby)
- [Database per Service Pattern — microservices.io](https://microservices.io/patterns/data/database-per-service.html)
