---
title: "Java Quarkus — Cloud-Native Framework"
slug: java-quarkus
category: dev
tags: [java, quarkus, graalvm, native-image, microservizi, serverless, microprofile, cdi, panache, resteasy]
search_keywords: [quarkus, quarkus framework, quarkus native, quarkus graalvm, native image java, supersonic subatomic java, fast startup java, low memory java, quarkus vs spring boot, quarkus kubernetes, quarkus serverless, quarkus lambda, quarkus openshift, quarkus dev mode, quarkus live reload, quarkus hot reload, microprofile, microprofile health, microprofile metrics, microprofile openapi, microprofile fault tolerance, cdi quarkus, dependency injection quarkus, resteasy reactive, resteasy, jax-rs, panache, active record, panache repository, quarkus orm, quarkus jpa, quarkus hibernate, quarkus kafka, smallrye, smallrye fault tolerance, circuit breaker quarkus, quarkus estensioni, quarkus extensions, quarkus build, quarkus container image, graalvm limitazioni, native image limitazioni, reflection graalvm, aot quarkus, ahead of time, scala verticale, scale to zero, cold start, faas java, aws lambda java, quarkus metrics prometheus, opentelemetry quarkus]
parent: dev/linguaggi/_index
related: [dev/linguaggi/java-spring-boot, messaging/kafka/sviluppo/quarkus-kafka]
official_docs: https://quarkus.io/guides/
status: reviewed
difficulty: intermediate
last_updated: 2026-10-04
last_verified: 2026-10-04
---

# Java Quarkus — Cloud-Native Framework

## Panoramica

Quarkus è un framework Java cloud-native ottimizzato per GraalVM e OpenJDK HotSpot, progettato esplicitamente per ambienti Kubernetes, serverless e FaaS (Function as a Service). Il suo slogan "Supersonic Subatomic Java" riflette i due obiettivi primari: startup in pochi millisecondi (spesso <50ms in modalità native) e footprint di memoria minimale (<100MB RSS in molti scenari). Questi risultati si ottengono spostando gran parte del lavoro di configurazione, reflection e scanning al momento del build (Ahead-of-Time compilation) invece che a runtime — l'inverso dell'approccio Spring Boot.

Quarkus abbraccia gli standard MicroProfile e Jakarta EE, quindi sviluppatori con esperienza CDI, JAX-RS e JPA trovano un ambiente familiare. Il framework supporta sia la modalità JVM tradizionale (con startup ~300-500ms e warm-up JIT) sia la modalità Native Image tramite GraalVM. La modalità dev con live reload continuo è tra le più reattive del panorama Java. Quando usare Quarkus: workload serverless con scale-to-zero, AWS Lambda, edge computing, sidecar con risorse limitate, microservizi con vincoli stringenti su memoria e startup. Quando preferire Spring Boot: team con expertise Spring consolidata, applicazioni enterprise con dipendenze Spring (Spring Security, Spring Data specifico), ecosistema Spring Cloud.

---

## Concetti Chiave

### Quarkus vs Spring Boot — Confronto Architetturale

| Aspetto | Spring Boot | Quarkus (JVM) | Quarkus (Native) |
|---|---|---|---|
| Startup time | ~2–5s | ~300–500ms | ~20–50ms |
| Memory RSS (idle) | ~200–500 MB | ~150–250 MB | ~30–80 MB |
| Throughput (peak) | Eccellente (JIT warm) | Eccellente (JIT warm) | Ottimo (no JIT overhead) |
| Peak performance | Dopo warm-up JIT | Dopo warm-up JIT | Immediato ma limitato |
| Build time | ~30–60s | ~60–90s | ~3–10 minuti |
| Debug experience | Eccellente | Eccellente | Limitato |
| Reflection arbitraria | Sì | Sì | Limitata (registrazione esplicita) |
| Standard | Spring proprietario | CDI + MicroProfile + Jakarta EE | CDI + MicroProfile + Jakarta EE |
| Ideal scenario | CRUD enterprise | Microservizi k8s | Serverless, Lambda, edge |

### Modalità di Esecuzione

**JVM Mode** — l'applicazione viene compilata in bytecode e gira su HotSpot o GraalVM CE. Startup più veloce rispetto a Spring Boot perché il work di startup (scanning, proxy generation, config parsing) viene eseguito a build time. Compatibilità piena con tutte le librerie Java.

**Native Mode** — tramite GraalVM `native-image`, l'applicazione viene compilata in un binario nativo per la piattaforma target. Non richiede JVM a runtime. Startup in decine di millisecondi, footprint minimo. Limitazioni: reflection, serializzazione dinamica, classpath scanning a runtime non supportati senza configurazione esplicita.

### AOT — Ahead-of-Time Processing

Quarkus introduce il concetto di **Augmentation**: durante la build, un processo separato (Quarkus Augmentation) esegue deployment processors che analizzano il codice, risolvono le dipendenze CDI, generano proxy e gestori, e scrivono metadati ottimizzati. Il risultato è un'applicazione con un'impronta di startup minima perché non deve fare discovery a runtime.

```
Build Time (Augmentation)                Runtime
─────────────────────────────────────── ─────────────────────
CDI scanning & proxy generation    →    Proxy già generati
Config parsing & validation        →    Config già validata
Extension processing               →    Extension già elaborate
REST route registration            →    Route già registrate
Hibernate mapping validation       →    Schema già validato
                                        ─────────────────────
                                        Solo: inizializzazione
                                        connessioni + avvio server
                                        (~20-50ms native)
```

### MicroProfile — Standard per Microservizi Java

Quarkus implementa le specifiche MicroProfile tramite SmallRye:

| Specifica | Implementazione | Scopo |
|---|---|---|
| Health (MP Health) | SmallRye Health | Liveness/Readiness/Startup probe |
| Metrics | Micrometer (`quarkus-micrometer`; SmallRye Metrics legacy) | Esposizione metriche Prometheus |
| Telemetry | OpenTelemetry (`quarkus-opentelemetry`) | Tracing/metrics/logs distribuiti OTLP |
| OpenAPI | SmallRye OpenAPI | Documentazione API automatica |
| Fault Tolerance | SmallRye Fault Tolerance | Circuit breaker, retry, timeout, bulkhead |
| Rest Client | SmallRye REST Client | Client HTTP dichiarativo |
| Config | SmallRye Config | Configurazione multi-source |
| JWT | SmallRye JWT | Autenticazione JWT/Bearer |

---

## Architettura / Come Funziona

### Struttura Progetto Standard

```
my-quarkus-service/
├── src/
│   ├── main/
│   │   ├── java/com/example/
│   │   │   ├── resource/
│   │   │   │   └── OrderResource.java       # JAX-RS endpoint
│   │   │   ├── service/
│   │   │   │   └── OrderService.java        # Business logic CDI bean
│   │   │   ├── entity/
│   │   │   │   └── Order.java               # Panache entity (Active Record)
│   │   │   ├── repository/
│   │   │   │   └── OrderRepository.java     # Panache repository (opzionale)
│   │   │   └── health/
│   │   │       └── DatabaseHealthCheck.java # Custom health check
│   │   └── resources/
│   │       ├── application.properties       # Config principale
│   │       └── META-INF/resources/          # Static assets
│   └── test/
│       └── java/com/example/
│           ├── OrderResourceNativeIT.java   # @QuarkusIntegrationTest
│           └── OrderResourceTest.java       # @QuarkusTest
├── src/native-test/                         # Test specifici per native build
├── .mvn/
├── Dockerfile.jvm                           # Generato da Quarkus
├── Dockerfile.native                        # Generato da Quarkus
└── pom.xml
```

### Ciclo di Build e Deploy

```
Developer                    Build                        Kubernetes
──────────                   ────────────────────────     ──────────────────────
mvn quarkus:dev          →   Augmentation (AOT)
                             ├─ CDI proxy gen
                             ├─ Config validation
                             └─ Extension processing
                                      │
mvn package              →   JAR/Native binary
  [-Pnative]                          │
                             Docker image build
                             (Dockerfile.jvm o .native)
                                      │
docker push              →                               Pod startup
                                                         ├─ JVM: ~300ms
                                                         └─ Native: ~20-50ms
                                                                  │
                                                         Traffic routed
```

### Dev Mode — Live Reload

La killer feature di Quarkus è la **dev mode**: `mvn quarkus:dev` avvia il processo e monitora le modifiche ai sorgenti. Al successivo HTTP request, Quarkus compila e ricarica le classi modificate in pochi millisecondi — senza riavviare la JVM. Questo include modifiche a endpoint, service, entità, template.

```
┌─────────────────────────────────────────────────────────┐
│                    Quarkus Dev Mode                      │
│                                                          │
│  HTTP Request                                            │
│      │                                                   │
│      ▼                                                   │
│  File changed?                                           │
│  ├─ NO  → Serve direttamente                            │
│  └─ YES → Recompile (incrementale, ~100-300ms)          │
│           Reload classi modificate                       │
│           Serve la request con codice aggiornato         │
│                                                          │
│  Dev UI: http://localhost:8080/q/dev-ui                  │
│  ├─ Lista estensioni attive                             │
│  ├─ Dev Services (DB/Kafka in container automatici)     │
│  ├─ Config attuale                                      │
│  ├─ Swagger UI (OpenAPI)                                │
│  └─ Continuous Testing panel                            │
└─────────────────────────────────────────────────────────┘
```

---

## Configurazione & Pratica

### Setup Progetto — pom.xml

```xml
<!-- pom.xml — Quarkus BOM e dipendenze core -->
<properties>
    <!-- 3.40 = LTS corrente (30/09/2026); 3.33 e 3.27 LTS in manutenzione/fine vita. 4.0 è in beta -->
    <quarkus.platform.version>3.40.0</quarkus.platform.version>
    <compiler-plugin.version>3.13.0</compiler-plugin.version>
    <maven.compiler.release>21</maven.compiler.release>
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    <skipITs>true</skipITs>
    <quarkus.native.container-build>true</quarkus.native.container-build>
</properties>

<dependencyManagement>
    <dependencies>
        <dependency>
            <groupId>io.quarkus.platform</groupId>
            <artifactId>quarkus-bom</artifactId>
            <version>${quarkus.platform.version}</version>
            <type>pom</type>
            <scope>import</scope>
        </dependency>
    </dependencies>
</dependencyManagement>

<dependencies>
    <!-- REST layer — Quarkus REST (ex RESTEasy Reactive, rinominato dalla 3.9) con Jackson -->
    <dependency>
        <groupId>io.quarkus</groupId>
        <artifactId>quarkus-rest-jackson</artifactId>
    </dependency>

    <!-- ORM — Hibernate ORM con Panache (Active Record / Repository) -->
    <dependency>
        <groupId>io.quarkus</groupId>
        <artifactId>quarkus-hibernate-orm-panache</artifactId>
    </dependency>
    <dependency>
        <groupId>io.quarkus</groupId>
        <artifactId>quarkus-jdbc-postgresql</artifactId>
    </dependency>

    <!-- Health — MicroProfile Health -->
    <dependency>
        <groupId>io.quarkus</groupId>
        <artifactId>quarkus-smallrye-health</artifactId>
    </dependency>

    <!-- Metrics — Micrometer + Prometheus -->
    <dependency>
        <groupId>io.quarkus</groupId>
        <artifactId>quarkus-micrometer-registry-prometheus</artifactId>
    </dependency>

    <!-- OpenAPI / Swagger UI -->
    <dependency>
        <groupId>io.quarkus</groupId>
        <artifactId>quarkus-smallrye-openapi</artifactId>
    </dependency>

    <!-- Fault Tolerance — circuit breaker, retry, timeout -->
    <dependency>
        <groupId>io.quarkus</groupId>
        <artifactId>quarkus-smallrye-fault-tolerance</artifactId>
    </dependency>

    <!-- REST Client (ex rest-client-reactive) -->
    <dependency>
        <groupId>io.quarkus</groupId>
        <artifactId>quarkus-rest-client-jackson</artifactId>
    </dependency>

    <!-- Kubernetes integration -->
    <dependency>
        <groupId>io.quarkus</groupId>
        <artifactId>quarkus-kubernetes</artifactId>
    </dependency>
    <dependency>
        <groupId>io.quarkus</groupId>
        <artifactId>quarkus-kubernetes-config</artifactId>
    </dependency>

    <!-- Container image build (Jib) -->
    <dependency>
        <groupId>io.quarkus</groupId>
        <artifactId>quarkus-container-image-jib</artifactId>
    </dependency>

    <!-- Testing -->
    <dependency>
        <groupId>io.quarkus</groupId>
        <artifactId>quarkus-junit5</artifactId>
        <scope>test</scope>
    </dependency>
    <dependency>
        <groupId>io.rest-assured</groupId>
        <artifactId>rest-assured</artifactId>
        <scope>test</scope>
    </dependency>
</dependencies>

<build>
    <plugins>
        <plugin>
            <groupId>io.quarkus.platform</groupId>
            <artifactId>quarkus-maven-plugin</artifactId>
            <version>${quarkus.platform.version}</version>
            <extensions>true</extensions>
            <executions>
                <execution>
                    <goals>
                        <goal>build</goal>
                        <goal>generate-code</goal>
                        <goal>generate-code-tests</goal>
                    </goals>
                </execution>
            </executions>
        </plugin>
    </plugins>
</build>

<!-- Profile per build nativa -->
<profiles>
    <profile>
        <id>native</id>
        <activation>
            <property>
                <name>native</name>
            </property>
        </activation>
        <properties>
            <skipITs>false</skipITs>
            <quarkus.native.enabled>true</quarkus.native.enabled>
        </properties>
    </profile>
</profiles>
```

### application.properties — Configurazione

```properties
# application.properties — Quarkus usa properties invece di YAML (YAML supportato con estensione)

# Datasource
quarkus.datasource.db-kind=postgresql
quarkus.datasource.username=${DB_USER:orders}
quarkus.datasource.password=${DB_PASSWORD:changeme}
quarkus.datasource.jdbc.url=${DB_URL:jdbc:postgresql://localhost:5432/orders}
quarkus.datasource.jdbc.max-size=16
quarkus.datasource.jdbc.min-size=2

# Hibernate ORM
quarkus.hibernate-orm.database.generation=validate
quarkus.hibernate-orm.log.sql=false

# HTTP
quarkus.http.port=8080
quarkus.http.ssl-port=8443

# Health endpoint (MicroProfile Health)
quarkus.smallrye-health.root-path=/q/health
# Kubernetes probe paths standard:
# GET /q/health/live   → liveness
# GET /q/health/ready  → readiness
# GET /q/health/started → startup

# Metrics Prometheus
quarkus.micrometer.export.prometheus.path=/q/metrics

# OpenAPI
quarkus.smallrye-openapi.path=/q/openapi
# Swagger UI solo in dev mode (default); i commenti inline NON sono supportati nei .properties
quarkus.swagger-ui.always-include=false
quarkus.swagger-ui.path=/q/swagger-ui

# Kubernetes config — legge ConfigMap
quarkus.kubernetes-config.enabled=true
quarkus.kubernetes-config.config-maps=order-service-config
quarkus.kubernetes-config.namespace=production

# Logging
quarkus.log.level=INFO
quarkus.log.category."com.example".level=DEBUG
quarkus.log.console.format=%d{HH:mm:ss} %-5p [%c{2.}] (%t) %s%e%n

# Container image (Jib)
quarkus.container-image.registry=my-registry
quarkus.container-image.group=myteam
quarkus.container-image.name=order-service
quarkus.container-image.tag=${quarkus.application.version:latest}
quarkus.container-image.push=false

# Kubernetes manifests generati automaticamente
quarkus.kubernetes.service-type=ClusterIP
quarkus.kubernetes.resources.requests.memory=128Mi
quarkus.kubernetes.resources.requests.cpu=100m
quarkus.kubernetes.resources.limits.memory=256Mi
quarkus.kubernetes.resources.limits.cpu=500m
```

```properties
# application.properties — override per dev (profilo %dev)
%dev.quarkus.hibernate-orm.database.generation=drop-and-create
%dev.quarkus.hibernate-orm.log.sql=true
%dev.quarkus.log.category."com.example".level=DEBUG
%dev.quarkus.datasource.username=dev
%dev.quarkus.datasource.password=dev
%dev.quarkus.kubernetes-config.enabled=false

# Test: senza url configurato, Dev Services avvia un PostgreSQL in container (Testcontainers)
%test.quarkus.hibernate-orm.database.generation=drop-and-create
```

### RESTEasy Reactive — Endpoint JAX-RS

RESTEasy Reactive è l'implementazione JAX-RS non-bloccante di Quarkus, costruita su Vert.x. Supporta sia chiamate bloccanti che reattive (Uni/Multi da Mutiny).

```java
// OrderResource.java — endpoint RESTEasy Reactive
@Path("/orders")
@Produces(MediaType.APPLICATION_JSON)
@Consumes(MediaType.APPLICATION_JSON)
@ApplicationScoped
public class OrderResource {

    @Inject
    OrderService orderService;

    // Endpoint bloccante: con tipo di ritorno non reattivo gira su worker thread
    // (@NonBlocking forza l'event loop, @Blocking forza il worker)
    @GET
    @Path("/{id}")
    public Order getOrder(@PathParam("id") Long id) {
        return orderService.findById(id);
    }

    // Endpoint reattivo con Uni (Mutiny)
    // Con hibernate-orm (bloccante) NON restituire Uni da metodi @Transactional:
    // per DB reattivo servono hibernate-reactive-panache e @WithTransaction
    @POST
    public Response createOrder(CreateOrderRequest request) {
        Order order = orderService.createOrder(request);
        return Response.status(Response.Status.CREATED).entity(order).build();
    }

    // Stream di eventi (SSE)
    @GET
    @Path("/stream")
    @Produces(MediaType.SERVER_SENT_EVENTS)
    public Multi<Order> streamOrders() {
        return orderService.streamAll();
    }

    // Query parametri e paginazione
    @GET
    public List<Order> listOrders(
        @QueryParam("page") @DefaultValue("0") int page,
        @QueryParam("size") @DefaultValue("20") int size,
        @QueryParam("status") OrderStatus status
    ) {
        return orderService.list(page, size, status);
    }
}
```

```java
// ExceptionMapper — gestione errori uniforme
@Provider
public class ValidationExceptionMapper
        implements ExceptionMapper<ConstraintViolationException> {

    @Override
    public Response toResponse(ConstraintViolationException e) {
        Map<String, String> errors = e.getConstraintViolations()
            .stream()
            .collect(Collectors.toMap(
                cv -> cv.getPropertyPath().toString(),
                ConstraintViolation::getMessage
            ));
        return Response.status(Response.Status.BAD_REQUEST)
            .entity(Map.of("errors", errors))
            .build();
    }
}
```

### Panache ORM — Active Record e Repository

Panache è il layer ORM di Quarkus sopra Hibernate. Offre due pattern: **Active Record** (metodi sulle entità) e **Repository** (repository separato).

**Pattern Active Record** (più conciso, ideale per entità semplici):

```java
// Order.java — Panache Active Record
@Entity
@Table(name = "orders")
public class Order extends PanacheEntity {
    // PanacheEntity aggiunge automaticamente il campo `id` (Long, generato)

    @Column(nullable = false)
    public String userId;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    public OrderStatus status = OrderStatus.PENDING;

    @Column(nullable = false)
    public Instant createdAt = Instant.now();

    @OneToMany(mappedBy = "order", cascade = CascadeType.ALL, fetch = FetchType.LAZY)
    public List<OrderItem> items = new ArrayList<>();

    // Query methods statici — definiti direttamente sull'entità
    public static PanacheQuery<Order> findByUserId(String userId) {
        return find("userId", userId);   // PanacheQuery: consente .page(...).list()
    }

    public static List<Order> findByStatus(OrderStatus status) {
        return list("status", status);
    }

    public static PanacheQuery<Order> findPendingOlderThan(Instant threshold) {
        return find("status = ?1 AND createdAt < ?2", OrderStatus.PENDING, threshold);
    }

    // Count con filtro
    public static long countByUserAndStatus(String userId, OrderStatus status) {
        return count("userId = ?1 AND status = ?2", userId, status);
    }
}
```

```java
// OrderService.java — usa Panache Active Record
@ApplicationScoped
public class OrderService {

    @Transactional
    public Order createOrder(CreateOrderRequest req) {
        Order order = new Order();
        order.userId = req.userId();
        order.items = req.items().stream()
            .map(item -> {
                OrderItem oi = new OrderItem();
                oi.productId = item.productId();
                oi.quantity = item.quantity();
                oi.order = order;
                return oi;
            }).collect(Collectors.toCollection(ArrayList::new));  // lista mutabile per Hibernate
        order.persist();        // Salva — equivale a entityManager.persist(order)
        return order;
    }

    public Order findById(Long id) {
        return Order.findById(id);  // Metodo statico da PanacheEntity
    }

    public List<Order> listByUser(String userId, int page, int size) {
        return Order.findByUserId(userId)
            .page(page, size)   // Paginazione built-in
            .list();
    }

    @Transactional
    public Order updateStatus(Long id, OrderStatus newStatus) {
        Order order = Order.findByIdOptional(id)
            .orElseThrow(() -> new NotFoundException("Order " + id + " not found"));
        order.status = newStatus;
        // Nessuna chiamata esplicita a save() — Hibernate dirty checking
        return order;
    }
}
```

**Pattern Repository** (più testabile, ideale per logica complessa):

```java
// OrderRepository.java — Panache Repository
@ApplicationScoped
public class OrderRepository implements PanacheRepository<Order> {

    public List<Order> findRecentByUser(String userId, int limit) {
        return find("userId = ?1 ORDER BY createdAt DESC", userId)
            .page(0, limit)
            .list();
    }

    public Optional<Order> findActiveOrder(String userId) {
        return find("userId = ?1 AND status IN (?2, ?3)",
                userId, OrderStatus.PENDING, OrderStatus.PROCESSING)
            .firstResultOptional();
    }
}
```

### MicroProfile Health

```java
// DatabaseHealthCheck.java — custom liveness check
@Liveness                     // Contribuisce a /q/health/live
@ApplicationScoped
public class DatabaseHealthCheck implements HealthCheck {

    @Inject
    AgroalDataSource dataSource;

    @Override
    public HealthCheckResponse call() {
        try (var conn = dataSource.getConnection();
             var stmt = conn.prepareStatement("SELECT 1")) {
            stmt.execute();
            return HealthCheckResponse.up("database");
        } catch (Exception e) {
            return HealthCheckResponse.named("database")
                .down()
                .withData("error", e.getMessage())
                .build();
        }
    }
}
```

```java
// ExternalServiceHealthCheck.java — readiness check
@Readiness                    // Contribuisce a /q/health/ready
@ApplicationScoped
public class ExternalServiceHealthCheck implements HealthCheck {

    @Inject
    PaymentServiceClient paymentClient;

    @Override
    public HealthCheckResponse call() {
        try {
            paymentClient.ping();
            return HealthCheckResponse.up("payment-service");
        } catch (Exception e) {
            return HealthCheckResponse.named("payment-service")
                .down()
                .withData("url", paymentClient.getBaseUrl())
                .build();
        }
    }
}
```

### MicroProfile Fault Tolerance

```java
// OrderService.java — fault tolerance con SmallRye
@ApplicationScoped
public class OrderService {

    @Inject
    PaymentServiceClient paymentClient;

    // Circuit breaker + Retry + Timeout combinati
    @CircuitBreaker(
        requestVolumeThreshold = 10,   // Valuta dopo 10 richieste
        failureRatio = 0.5,            // Apri se >50% fallisce
        delay = 5000,                  // Attendi 5s prima di half-open
        successThreshold = 2           // 2 successi in half-open per chiudere
    )
    @Retry(
        maxRetries = 3,
        delay = 500,
        jitter = 200,
        retryOn = {ConnectException.class, TimeoutException.class}
    )
    @Timeout(2000)                     // Fail dopo 2 secondi
    @Fallback(fallbackMethod = "processPaymentFallback")
    public PaymentResult processPayment(String orderId, BigDecimal amount) {
        return paymentClient.charge(orderId, amount);
    }

    // Fallback eseguito quando il circuit breaker è aperto o tutti i retry falliscono
    private PaymentResult processPaymentFallback(String orderId, BigDecimal amount) {
        // Logica alternativa: accoda per processing asincrono
        paymentQueue.enqueue(orderId, amount);
        return PaymentResult.queued(orderId);
    }

    // Bulkhead — limita le chiamate concorrenti a un servizio esterno
    @Bulkhead(
        value = 10,             // Max 10 richieste concorrenti
        waitingTaskQueue = 20   // Max 20 in coda (solo per @Asynchronous)
    )
    public InventoryResult checkInventory(String productId) {
        return inventoryClient.check(productId);
    }
}
```

### Native Build con GraalVM

```bash
# Build native — richiede GraalVM installato o container build
# Opzione 1: GraalVM locale (più veloce)
mvn package -Pnative

# Opzione 2: Container build (nessuna dipendenza locale su GraalVM — raccomandato in CI)
mvn package -Pnative -Dquarkus.native.container-build=true \
    -Dquarkus.native.builder-image=quay.io/quarkus/ubi-quarkus-mandrel-builder-image:jdk-21

# Build immagine Docker per native
docker build -f src/main/docker/Dockerfile.native -t my-registry/order-service:1.0.0-native .

# Verifica startup time
docker run --rm my-registry/order-service:1.0.0-native
# Output: Quarkus 3.x.x started in 0.023s. Listening on http://0.0.0.0:8080
```

**Gestione reflection per Native Image** — classi usate via reflection devono essere dichiarate esplicitamente:

```java
// RegisterForReflection — annotazione Quarkus per registrare classi a GraalVM
@RegisterForReflection
public class ExternalApiResponse {
    // Questa classe viene deserializzata via Jackson reflection
    // Senza @RegisterForReflection il native build fallisce a runtime
    public String status;
    public Map<String, Object> data;
}
```

```json
// src/main/resources/META-INF/native-image/com.example/order-service/reflect-config.json
// alternativa per librerie esterne (raccolto automaticamente da native-image)
[
  {
    "name": "com.external.library.SomeClass",
    "allDeclaredConstructors": true,
    "allPublicMethods": true,
    "allDeclaredFields": true
  }
]
```

### REST Client Dichiarativo

```java
// PaymentServiceClient.java — client HTTP dichiarativo (MicroProfile REST Client)
@RegisterRestClient(configKey = "payment-service")
@Path("/api/v1")
public interface PaymentServiceClient {

    @POST
    @Path("/charges")
    @Produces(MediaType.APPLICATION_JSON)
    @Consumes(MediaType.APPLICATION_JSON)
    PaymentResult charge(ChargeRequest request);

    @GET
    @Path("/health")
    void ping();
}
```

```properties
# Configurazione del REST Client in application.properties
quarkus.rest-client.payment-service.url=${PAYMENT_SERVICE_URL:http://payment-service:8080}
quarkus.rest-client.payment-service.connect-timeout=2000
quarkus.rest-client.payment-service.read-timeout=5000
```

```java
// Uso nel service tramite @RestClient qualifier
@ApplicationScoped
public class OrderService {

    @Inject
    @RestClient
    PaymentServiceClient paymentClient;

    // ...
}
```

### Test con @QuarkusTest

```java
// OrderResourceTest.java — test con Dev Services (PostgreSQL in container)
@QuarkusTest
class OrderResourceTest {

    // Quarkus avvia l'applicazione una volta per l'intera suite di test
    // Database reale: Dev Services avvia automaticamente il container (nessuna config)

    @Test
    void createOrder_validRequest_returns201() {
        given()
            .contentType(ContentType.JSON)
            .body("""
                {
                  "userId": "user-123",
                  "items": [{"productId": "PROD-001", "quantity": 2}]
                }
                """)
        .when()
            .post("/orders")
        .then()
            .statusCode(201)
            .body("status", equalTo("PENDING"))
            .body("id", notNullValue());
    }

    @Test
    void getOrder_notFound_returns404() {
        given()
            .pathParam("id", 99999)
        .when()
            .get("/orders/{id}")
        .then()
            .statusCode(404);
    }

    @Test
    void health_liveness_returnsUp() {
        given()
        .when()
            .get("/q/health/live")
        .then()
            .statusCode(200)
            .body("status", equalTo("UP"));
    }
}
```

```java
// OrderResourceNativeIT.java — test eseguiti sul binario native compilato
@QuarkusIntegrationTest     // Usa il package prodotto da mvn package -Pnative
class OrderResourceNativeIT extends OrderResourceTest {
    // Eredita i test — eseguiti contro il binario (black-box: niente @Inject)
    // Eseguiti solo con: mvn verify -Pnative
}
```

---

## Best Practices

### Scegliere Tra JVM Mode e Native Mode

!!! tip "Quando usare Native"
    Native Image conviene quando: (1) scale-to-zero con cold start critico (serverless, Lambda), (2) sidecar container con memory budget <100MB, (3) CLI tools in Java, (4) edge computing con risorse limitate. In altri casi (microservizi Kubernetes long-running), **JVM mode con container-aware JVM** ha throughput peak superiore grazie al JIT compiler.

!!! warning "Limitazioni Native Image"
    Alcune librerie Java non sono compatibili con GraalVM native-image senza configurazione: (1) librerie che usano reflection dinamica non registrata, (2) classpath scanning a runtime (Classgraph, Reflections), (3) code generation a runtime (CGLIB proxy non Quarkus), (4) alcune funzionalità di serializzazione Java. Sempre verificare la compatibilità native delle librerie di terze parti prima di adottarle.

### Configurazione per Produzione

```properties
# application.properties — hardening per produzione

# Swagger UI in produzione: escluso di default (solo dev mode)
quarkus.swagger-ui.always-include=false

# Metadati OpenAPI
quarkus.smallrye-openapi.info-title=Order Service
quarkus.smallrye-openapi.info-version=1.0.0

# Graceful shutdown
quarkus.shutdown.timeout=30S

# Logging strutturato JSON: richiede l'estensione quarkus-logging-json
%prod.quarkus.log.console.json.enabled=true

# Connection pool sizing
quarkus.datasource.jdbc.max-size=20
quarkus.datasource.jdbc.min-size=5
quarkus.datasource.jdbc.acquisition-timeout=PT5S
```

### Panache — Evitare N+1 Query

```java
// SBAGLIATO — genera N query per ogni Order.items caricato lazy
List<Order> orders = Order.listAll();
orders.forEach(o -> o.items.forEach(item -> process(item)));  // N+1!

// CORRETTO — fetch join esplicito
List<Order> orders = Order.find(
    "SELECT DISTINCT o FROM Order o LEFT JOIN FETCH o.items WHERE o.status = ?1",
    OrderStatus.PENDING
).list();

// CORRETTO — usa @BatchSize per lazy loading efficiente
@OneToMany(mappedBy = "order", fetch = FetchType.LAZY)
@BatchSize(size = 20)   // Carica items in batch di 20 invece che uno alla volta
public List<OrderItem> items;
```

### Transazioni e CDI

```java
// @Transactional a livello di service — mai nei resource/controller
@ApplicationScoped
public class OrderService {

    @Transactional                        // Apre/chiude transazione qui
    public Order createOrder(...) { }

    @Transactional(Transactional.TxType.REQUIRES_NEW)  // Nuova transazione sempre
    public void auditLog(String event) { }

    // Senza @Transactional — solo lettura, nessun overhead transazionale
    public Order findById(Long id) {
        return Order.findById(id);
    }
}
```

---

## Troubleshooting

### Native Build fallisce — ClassNotFoundException a runtime

**Sintomo:** L'applicazione compila in native ma a runtime lancia `ClassNotFoundException` o `NoSuchMethodException`.

**Causa:** Una classe viene acceduta via reflection senza essere registrata per GraalVM.

**Soluzione:**
```java
// Aggiungi @RegisterForReflection alla classe in questione
@RegisterForReflection
public class ProblematicClass { ... }

// Per più classi in un package esterno (es. libreria di terze parti):
@RegisterForReflection(targets = {ExternalDto.class, AnotherDto.class})
public class ReflectionConfiguration { }
```

```bash
# Usa l'agent GraalVM per generare automaticamente la configurazione
# (eseguilo durante i test di integrazione per catturare tutti i casi)
java -agentlib:native-image-agent=config-output-dir=src/main/resources/META-INF/native-image \
     -jar target/order-service-runner.jar
# Poi esegui i test/carichi e termina l'applicazione — genera i file di config
```

### Dev Mode non rileva le modifiche

**Sintomo:** `mvn quarkus:dev` è avviato ma le modifiche ai file `.java` non vengono ricaricate.

**Causa:** Il reload è lazy: parte alla prima richiesta HTTP successiva alla modifica, non al salvataggio. Altre cause: file fuori dal source path del modulo, errore di compilazione precedente non risolto, filesystem watching inaffidabile (WSL2, cartelle di rete).

**Soluzione:**
```bash
# 1. Invia una richiesta (curl localhost:8080/...) per innescare il reload
# 2. Nel terminale di dev mode: premi 's' per forzare restart, 'r' per rieseguire i test
# 3. Multi-modulo: avvia mvn quarkus:dev dal modulo applicativo con gli altri moduli nel reactor
# 4. WSL2: tieni il progetto nel filesystem Linux, non in /mnt/c
```

### Circuit Breaker aperto in modo inatteso

**Sintomo:** Le chiamate al servizio esterno falliscono con `CircuitBreakerOpenException` anche quando il servizio è tornato disponibile.

**Causa:** Il `delay` del circuit breaker (stato half-open) non è trascorso, o il `successThreshold` non è stato raggiunto.

**Soluzione:**
```java
// Aggiungi logging per diagnosticare lo stato del circuit breaker
@CircuitBreaker(
    requestVolumeThreshold = 10,
    failureRatio = 0.5,
    delay = 5000,
    successThreshold = 2
)
public Result callExternalService() {
    // ...
}

// Inietta il CircuitBreakerMaintenance per monitoraggio
@Inject
CircuitBreakerMaintenance circuitBreakerMaintenance;

// Forza reset in testing o operazioni manuali
public void resetCircuitBreaker() {
    circuitBreakerMaintenance.resetAll();
}
```

```properties
# Override a runtime dei parametri delle annotazioni (formato MicroProfile FT):
# <classe>/<metodo>/<Annotazione>/<parametro>
com.example.service.OrderService/processPayment/CircuitBreaker/delay=10000
# Oppure globale: mp.fault.tolerance.global.CircuitBreaker.delay=10000
```

### Panache — LazyInitializationException

**Sintomo:** `LazyInitializationException: could not initialize proxy` quando si accede a un'associazione lazy fuori da una transazione.

**Causa:** Un'associazione `@OneToMany(fetch = FetchType.LAZY)` viene acceduta dopo la chiusura della sessione Hibernate (fuori dal metodo `@Transactional`).

**Soluzione:**
```java
// SBAGLIATO — accesso lazy fuori da transazione
public Order getOrderWithItems(Long id) {
    Order order = Order.findById(id);
    return order;  // items non caricati, sessione chiusa dopo findById
}
// Nel resource: order.items → LazyInitializationException

// CORRETTO — fetch eager nella query quando serve
public Order getOrderWithItems(Long id) {
    return Order.find(
        "SELECT o FROM Order o LEFT JOIN FETCH o.items WHERE o.id = ?1", id
    ).firstResult();
}

// CORRETTO — proiezione DTO (evita il problema a monte)
public OrderDto getOrderDto(Long id) {
    Order order = Order.find(
        "SELECT o FROM Order o LEFT JOIN FETCH o.items WHERE o.id = ?1", id
    ).firstResult();
    return OrderDto.from(order);  // Mappa prima di uscire dalla transazione
}
```

---

## Relazioni

Quarkus condivide il contesto JVM con Spring Boot e si integra con l'ecosistema di messaggistica:

??? info "Java Spring Boot — Confronto e Migrazione"
    Spring Boot 3.x e Quarkus risolvono problemi simili con approcci diversi. Spring Boot offre un ecosistema più maturo e una curva di apprendimento più bassa per team Java esistenti. Quarkus eccelle in ambienti resource-constrained. La scelta dipende principalmente dal contesto di deploy (long-running vs serverless) e dall'expertise del team.

    **Confronto completo →** [Java Spring Boot](java-spring-boot.md)

??? info "Quarkus Kafka — Integrazione con Kafka"
    Quarkus integra Kafka tramite l'estensione SmallRye Reactive Messaging, che offre un'API dichiarativa con annotazioni `@Incoming` e `@Outgoing`. Supporta sia l'API Kafka nativa che l'astrazione reattiva MicroProfile Reactive Messaging. Compatibile con native build (a differenza di alcuni connettori Spring Kafka).

    **Approfondimento completo →** [Quarkus Kafka](../../messaging/kafka/sviluppo/quarkus-kafka.md)

---

## Riferimenti

- [Quarkus Guides — documentazione ufficiale](https://quarkus.io/guides/)
- [Quarkus Getting Started](https://quarkus.io/get-started/)
- [GraalVM Native Image — limitazioni](https://www.graalvm.org/latest/reference-manual/native-image/metadata/Compatibility/)
- [MicroProfile Fault Tolerance spec](https://download.eclipse.org/microprofile/microprofile-fault-tolerance-4.0/microprofile-fault-tolerance-spec-4.0.html)
- [Panache ORM Guide](https://quarkus.io/guides/hibernate-orm-panache)
- [RESTEasy Reactive Guide](https://quarkus.io/guides/resteasy-reactive)
- [Quarkus Kubernetes Extension](https://quarkus.io/guides/deploying-to-kubernetes)
- [Quarkus Native Build Guide](https://quarkus.io/guides/building-native-image)
- [SmallRye Health](https://smallrye.io/smallrye-health/)
- [Quarkus vs Spring Boot — comparazione tecnica](https://quarkus.io/quarkus-vs-spring-for-microservices/)
