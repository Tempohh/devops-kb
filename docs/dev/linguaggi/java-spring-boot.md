---
title: "Java Spring Boot 3.x per Kubernetes"
slug: java-spring-boot
category: dev
tags: [java, spring-boot, kubernetes, microservizi, actuator, testcontainers, buildpacks]
search_keywords: [spring boot, spring boot 3, spring boot kubernetes, spring boot microservizi, spring boot k8s, application.yml, spring profiles, spring cloud kubernetes, configurationproperties, actuator, health check, readiness probe, liveness probe, metriche prometheus, micrometer, testcontainers, integration test, layered jar, buildpacks, cloud native buildpacks, spring initializr, spring boot docker, spring boot container, spring boot native, graalvm native, resilience4j, spring kafka, java microservizi, jvm microservizi, spring framework, spring mvc, spring webflux, reactive spring, spring data jpa, spring security, spring cloud, kubernetes config, configmap spring, secret spring, java 21, virtual threads, loom]
parent: dev/linguaggi/_index
related: [messaging/kafka/sviluppo/spring-kafka, dev/linguaggi/java-quarkus]
official_docs: https://docs.spring.io/spring-boot/docs/current/reference/html/
status: complete
difficulty: intermediate
last_updated: 2026-03-28
---

# Java Spring Boot 3.x per Kubernetes

## Panoramica

Spring Boot 3.x è il framework Java standard-de-facto per costruire microservizi pronti per il deployment su Kubernetes. Con Spring Boot 3.0+ (richiede Java 17+) l'ecosistema ha fatto un salto generazionale: supporto nativo a Jakarta EE 9+, GraalVM Native Image out-of-the-box, Virtual Threads (Java 21+) tramite Project Loom, e un'integrazione profonda con l'osservabilità tramite Micrometer e OpenTelemetry. Per il contesto Kubernetes, Spring Boot 3.x offre: gestione della configurazione tramite ConfigMap e Secret via `spring-cloud-kubernetes`, health endpoint separati per readiness/liveness probe, esposizione metriche Prometheus senza configurazioni extra, e immagini container ottimizzate tramite Layered Jar o Cloud Native Buildpacks.

Quando usare Spring Boot: team Java esistente, necessità di un ecosistema maturo (Spring Data, Spring Security, Spring Kafka, Spring Cloud), applicazioni CRUD/enterprise con logica di business complessa, integrazione con sistemi legacy. Quando NON usarlo: sidecar o proxy leggeri (preferire Go), workload ML/AI Python-first, applicazioni serverless con cold start critici sotto 100ms (preferire Quarkus Native o Go).

---

## Concetti Chiave

### Spring Boot 3.x — Novità Rilevanti per Microservizi

| Feature | Versione | Impatto |
|---|---|---|
| Jakarta EE 9+ (namespace `jakarta.*`) | 3.0 | Breaking change da Spring Boot 2.x |
| GraalVM Native Image | 3.0 | Startup <100ms, footprint <100MB |
| Micrometer Tracing (OTel) | 3.0 | Sostituisce Spring Cloud Sleuth |
| Virtual Threads (Loom) | 3.2 | Throughput HTTP senza pool tuning |
| `@HttpExchange` declarative client | 3.0 | Alternativa a Feign Client |
| `RestClient` (blocante, fluent) | 3.2 | Sostituisce `RestTemplate` |
| `ProblemDetail` (RFC 9457) | 3.0 | Error responses standardizzate |
| AOT (Ahead-of-Time) compilation | 3.0 | Riduce startup anche senza Native |

### Struttura Progetto Standard

```
my-service/
├── src/
│   ├── main/
│   │   ├── java/com/example/myservice/
│   │   │   ├── MyServiceApplication.java     # Entry point
│   │   │   ├── config/
│   │   │   │   └── AppConfig.java            # @ConfigurationProperties
│   │   │   ├── controller/
│   │   │   │   └── OrderController.java
│   │   │   ├── service/
│   │   │   │   └── OrderService.java
│   │   │   └── repository/
│   │   │       └── OrderRepository.java
│   │   └── resources/
│   │       ├── application.yml               # Config base
│   │       ├── application-dev.yml           # Profile dev
│   │       └── application-prod.yml          # Profile prod
│   └── test/
│       └── java/com/example/myservice/
│           ├── OrderControllerIT.java         # Integration test
│           └── OrderServiceTest.java          # Unit test
├── Dockerfile                                 # Multi-stage (alternativa a Buildpacks)
└── pom.xml
```

---

## Architettura / Come Funziona

### Ciclo di Vita su Kubernetes

```
Developer                Kubernetes
─────────               ──────────────────────────────────────────
mvn package         →   Layered JAR / OCI image via Buildpacks
                         │
                         ▼
                     Pod startup
                     ┌──────────────────────────────────────────┐
                     │  JVM starts → Spring Context init         │
                     │  ├─ @Bean registration                    │
                     │  ├─ DataSource connection pool init       │
                     │  ├─ Kafka consumer/producer init          │
                     │  └─ Health indicators setup               │
                     │                                           │
                     │  Actuator /actuator/health/readiness      │
                     │  └─ ApplicationAvailability: ACCEPTING    │
                     └──────────────────────────────────────────┘
                              │ readinessProbe OK
                              ▼
                     Traffic routed to Pod
                              │
                     ┌────────┴────────────────────────────────┐
                     │ Request processing                       │
                     │  Spring MVC (thread-per-request)         │
                     │    o Spring WebFlux (reactive)           │
                     │    o Virtual Threads (Loom, Java 21+)    │
                     └─────────────────────────────────────────┘
```

### Configurazione: dal ConfigMap all'Applicazione

```
Kubernetes ConfigMap/Secret
        │
        │  spring-cloud-kubernetes
        ▼
Spring Environment (PropertySource)
        │
        │  @ConfigurationProperties
        ▼
Java POJO type-safe
        │
        │  @Autowired / constructor injection
        ▼
Business Logic
```

---

## Configurazione & Pratica

### Bootstrap con Spring Initializr

Dipendenze raccomandate per un microservizio Kubernetes standard:

```xml
<!-- pom.xml — dipendenze core per microservizio Kubernetes -->
<dependencies>
    <!-- Web layer -->
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-web</artifactId>
        <!-- Oppure spring-boot-starter-webflux per reactive -->
    </dependency>

    <!-- Actuator — health + metrics -->
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-actuator</artifactId>
    </dependency>

    <!-- Micrometer Prometheus registry -->
    <dependency>
        <groupId>io.micrometer</groupId>
        <artifactId>micrometer-registry-prometheus</artifactId>
    </dependency>

    <!-- Spring Cloud Kubernetes — ConfigMap/Secret integration -->
    <dependency>
        <groupId>org.springframework.cloud</groupId>
        <artifactId>spring-cloud-starter-kubernetes-client-config</artifactId>
    </dependency>

    <!-- Resilience4j — circuit breaker, retry, rate limiter -->
    <dependency>
        <groupId>org.springframework.cloud</groupId>
        <artifactId>spring-cloud-starter-circuitbreaker-resilience4j</artifactId>
    </dependency>

    <!-- Database (esempio PostgreSQL) -->
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-data-jpa</artifactId>
    </dependency>
    <dependency>
        <groupId>org.postgresql</groupId>
        <artifactId>postgresql</artifactId>
    </dependency>

    <!-- Testcontainers per integration test -->
    <dependency>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-testcontainers</artifactId>
        <scope>test</scope>
    </dependency>
    <dependency>
        <groupId>org.testcontainers</groupId>
        <artifactId>postgresql</artifactId>
        <scope>test</scope>
    </dependency>

    <!-- Spring Kafka (se necessario) -->
    <dependency>
        <groupId>org.springframework.kafka</groupId>
        <artifactId>spring-kafka</artifactId>
    </dependency>
</dependencies>

<!-- Spring Cloud BOM — allinea le versioni -->
<dependencyManagement>
    <dependencies>
        <dependency>
            <groupId>org.springframework.cloud</groupId>
            <artifactId>spring-cloud-dependencies</artifactId>
            <version>2023.0.3</version>
            <type>pom</type>
            <scope>import</scope>
        </dependency>
    </dependencies>
</dependencyManagement>
```

### application.yml — Struttura con Spring Profiles

```yaml
# application.yml — configurazione base (tutti i profili)
spring:
  application:
    name: order-service
  profiles:
    active: ${SPRING_PROFILES_ACTIVE:dev}  # fallback a dev se non impostato

  # DataSource — valori default, override per profilo
  datasource:
    url: ${DB_URL:jdbc:postgresql://localhost:5432/orders}
    username: ${DB_USER:orders}
    password: ${DB_PASSWORD:changeme}
    hikari:
      maximum-pool-size: 10
      minimum-idle: 2
      connection-timeout: 30000

  jpa:
    hibernate:
      ddl-auto: validate           # NEVER create/update in prod — usa Flyway/Liquibase
    open-in-view: false            # Disabilita OSIV per microservizi (evita lazy loading nei controller)

# Actuator — configurazione base
management:
  endpoints:
    web:
      exposure:
        include: health,info,prometheus,metrics  # non esporre 'env' o 'configprops' in prod
  endpoint:
    health:
      probes:
        enabled: true              # Abilita /actuator/health/readiness e /actuator/health/liveness
      show-details: when-authorized
  health:
    livenessstate:
      enabled: true
    readinessstate:
      enabled: true

# Logging
logging:
  level:
    root: INFO
    com.example.myservice: DEBUG
  pattern:
    console: "%d{ISO8601} [%thread] %-5level %logger{36} - %msg%n"
```

```yaml
# application-prod.yml — override per produzione
spring:
  datasource:
    hikari:
      maximum-pool-size: 20     # Scala in base alle repliche e ai connection limit del DB
      minimum-idle: 5

  jpa:
    show-sql: false

logging:
  level:
    root: WARN
    com.example.myservice: INFO

management:
  endpoint:
    health:
      show-details: never       # Non esporre dettagli health in prod
```

### Spring Cloud Kubernetes — ConfigMap come PropertySource

Con `spring-cloud-starter-kubernetes-client-config`, i ConfigMap Kubernetes vengono automaticamente mappati come `PropertySource` nell'ambiente Spring.

```yaml
# bootstrap.yml (o application.yml con spring.config.import)
spring:
  cloud:
    kubernetes:
      config:
        enabled: true
        name: order-service-config    # Nome del ConfigMap
        namespace: production         # Namespace Kubernetes
        sources:
          - name: order-service-config
          - name: shared-config        # ConfigMap condivisi
      secrets:
        enabled: true
        name: order-service-secrets
        namespace: production

      # Reload automatico al cambio del ConfigMap (opzionale, attenzione in prod)
      reload:
        enabled: true
        strategy: refresh             # 'refresh' (solo @RefreshScope) o 'restart_context'
        period: 30000
```

```yaml
# ConfigMap Kubernetes corrispondente
apiVersion: v1
kind: ConfigMap
metadata:
  name: order-service-config
  namespace: production
data:
  # Spring Boot legge queste chiavi come property
  application.properties: |
    app.order.max-items=100
    app.order.timeout-seconds=30
    app.payment.service-url=http://payment-service:8080
```

### @ConfigurationProperties — Type-Safe Config

Preferire sempre `@ConfigurationProperties` ai singoli `@Value` per configurazioni strutturate:

```java
// config/AppProperties.java
@ConfigurationProperties(prefix = "app")
@Validated  // Abilita validazione JSR-303
public record AppProperties(
    @NotNull OrderProperties order,
    @NotNull PaymentProperties payment
) {
    public record OrderProperties(
        @Min(1) @Max(1000) int maxItems,
        @Positive int timeoutSeconds
    ) {}

    public record PaymentProperties(
        @NotBlank String serviceUrl,
        @Positive int retryAttempts
    ) {}
}
```

```java
// MyServiceApplication.java
@SpringBootApplication
@EnableConfigurationProperties(AppProperties.class)
public class MyServiceApplication {
    public static void main(String[] args) {
        SpringApplication.run(MyServiceApplication.class, args);
    }
}
```

```java
// OrderService.java — uso delle properties
@Service
public class OrderService {

    private final AppProperties props;
    private final OrderRepository repository;

    public OrderService(AppProperties props, OrderRepository repository) {
        this.props = props;
        this.repository = repository;
    }

    public Order createOrder(CreateOrderRequest req) {
        if (req.items().size() > props.order().maxItems()) {
            throw new IllegalArgumentException(
                "Ordine supera il limite di " + props.order().maxItems() + " items"
            );
        }
        // ...
    }
}
```

### Actuator — Readiness e Liveness Probe

Con `management.health.probes.enabled: true`, Spring Boot espone due endpoint distinti:

```
GET /actuator/health/liveness
  → HTTP 200: {"status":"UP"}     Pod è vivo, JVM funziona
  → HTTP 503: {"status":"DOWN"}   K8s riavvia il Pod

GET /actuator/health/readiness
  → HTTP 200: {"status":"UP"}     Pod può ricevere traffico
  → HTTP 503: {"status":"OUT_OF_SERVICE"}  K8s rimuove dal routing
```

```yaml
# Kubernetes Deployment — probe configuration
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
spec:
  template:
    spec:
      containers:
        - name: order-service
          image: my-registry/order-service:1.0.0
          ports:
            - containerPort: 8080
            - containerPort: 8081  # Porta management separata (raccomandato)
          env:
            - name: SPRING_PROFILES_ACTIVE
              value: prod
            - name: DB_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: order-service-secrets
                  key: db-password
          livenessProbe:
            httpGet:
              path: /actuator/health/liveness
              port: 8081
            initialDelaySeconds: 30   # Attendi warm-up JVM
            periodSeconds: 10
            failureThreshold: 3
          readinessProbe:
            httpGet:
              path: /actuator/health/readiness
              port: 8081
            initialDelaySeconds: 15
            periodSeconds: 5
            failureThreshold: 3
          resources:
            requests:
              memory: "256Mi"
              cpu: "250m"
            limits:
              memory: "512Mi"
              cpu: "1000m"
```

```yaml
# application.yml — porta management separata
server:
  port: 8080

management:
  server:
    port: 8081     # Actuator su porta dedicata — non esposta all'Ingress pubblico
```

### Metriche Prometheus con Micrometer

Con la dipendenza `micrometer-registry-prometheus`, l'endpoint `/actuator/prometheus` è automaticamente disponibile.

```java
// Metriche custom nel service
@Service
public class OrderService {

    private final MeterRegistry registry;
    private final Counter ordersCreated;
    private final Timer orderProcessingTime;

    public OrderService(MeterRegistry registry) {
        this.registry = registry;
        this.ordersCreated = Counter.builder("orders.created")
            .description("Numero di ordini creati")
            .tag("status", "success")
            .register(registry);
        this.orderProcessingTime = Timer.builder("order.processing.time")
            .description("Tempo di elaborazione ordine")
            .register(registry);
    }

    public Order createOrder(CreateOrderRequest req) {
        return orderProcessingTime.record(() -> {
            Order order = doCreateOrder(req);
            ordersCreated.increment();
            return order;
        });
    }
}
```

```yaml
# ServiceMonitor per Prometheus Operator (se presente)
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: order-service-monitor
  labels:
    release: prometheus
spec:
  selector:
    matchLabels:
      app: order-service
  endpoints:
    - port: management        # Porta 8081
      path: /actuator/prometheus
      interval: 15s
```

### Testcontainers — Integration Test

Spring Boot 3.1+ ha integrazione nativa con Testcontainers tramite `@ServiceConnection`:

```java
// OrderControllerIT.java — integration test con database reale
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@Testcontainers
class OrderControllerIT {

    // Spring Boot 3.1+: @ServiceConnection configura automaticamente la DataSource
    @Container
    @ServiceConnection
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16-alpine")
            .withDatabaseName("orders_test")
            .withUsername("test")
            .withPassword("test");

    @Autowired
    private TestRestTemplate restTemplate;

    @Autowired
    private OrderRepository orderRepository;

    @BeforeEach
    void setUp() {
        orderRepository.deleteAll();
    }

    @Test
    void createOrder_validRequest_returns201() {
        var request = new CreateOrderRequest(
            List.of(new OrderItem("PROD-001", 2)),
            "user-123"
        );

        var response = restTemplate.postForEntity("/orders", request, Order.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        assertThat(response.getBody()).isNotNull();
        assertThat(response.getBody().status()).isEqualTo(OrderStatus.PENDING);
        assertThat(orderRepository.count()).isEqualTo(1);
    }

    @Test
    void createOrder_tooManyItems_returns400() {
        // Supera il limite configurato in application.yml (max-items: 5 in test)
        var items = IntStream.range(0, 10)
            .mapToObj(i -> new OrderItem("PROD-" + i, 1))
            .toList();

        var response = restTemplate.postForEntity(
            "/orders",
            new CreateOrderRequest(items, "user-123"),
            ProblemDetail.class
        );

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
    }
}
```

```java
// Per test con Kafka (Testcontainers + Spring Kafka)
@SpringBootTest
@Testcontainers
class OrderEventIT {

    @Container
    @ServiceConnection
    static KafkaContainer kafka = new KafkaContainer(
        DockerImageName.parse("confluentinc/cp-kafka:7.6.0")
    );

    @Autowired
    private KafkaTemplate<String, OrderEvent> kafkaTemplate;

    @Test
    void orderCreated_publishesEvent() throws InterruptedException {
        var latch = new CountDownLatch(1);
        // ... verifica ricezione evento
    }
}
```

### Layered JAR e Buildpacks

**Opzione 1: Layered JAR** — immagine Docker manuale ottimizzata

```dockerfile
# Dockerfile — multi-stage con layered JAR
FROM eclipse-temurin:21-jdk-alpine AS builder
WORKDIR /app
COPY pom.xml .
COPY src ./src
# Separare il download delle dipendenze per cache layer
RUN mvn dependency:go-offline -q
RUN mvn package -DskipTests -q

# Estrai i layer del JAR
FROM eclipse-temurin:21-jre-alpine AS layers
WORKDIR /app
COPY --from=builder /app/target/*.jar app.jar
RUN java -Djarmode=layertools -jar app.jar extract

# Immagine finale — layer ordinati per cache efficienza
FROM eclipse-temurin:21-jre-alpine
WORKDIR /app

# Layer che cambiano meno frequentemente → prima (meglio cachati)
COPY --from=layers /app/dependencies/ ./
COPY --from=layers /app/spring-boot-loader/ ./
COPY --from=layers /app/snapshot-dependencies/ ./
# Layer che cambia più spesso → ultimo
COPY --from=layers /app/application/ ./

EXPOSE 8080 8081
ENTRYPOINT ["java", \
  "-XX:+UseContainerSupport", \
  "-XX:MaxRAMPercentage=75.0", \
  "-Djava.security.egd=file:/dev/./urandom", \
  "org.springframework.boot.loader.launch.JarLauncher"]
```

**Opzione 2: Cloud Native Buildpacks** — zero Dockerfile

```xml
<!-- pom.xml — spring-boot-maven-plugin con Buildpacks -->
<plugin>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-maven-plugin</artifactId>
    <configuration>
        <image>
            <name>my-registry/order-service:${project.version}</name>
            <!-- Builder Paketo — default Spring Boot -->
            <builder>paketobuildpacks/builder-jammy-base</builder>
            <env>
                <!-- JVM flags via Buildpack env var -->
                <JAVA_TOOL_OPTIONS>-XX:MaxRAMPercentage=75</JAVA_TOOL_OPTIONS>
                <!-- Forza Java 21 -->
                <BP_JVM_VERSION>21</BP_JVM_VERSION>
            </env>
        </image>
    </configuration>
</plugin>
```

```bash
# Build e push immagine con Buildpacks
mvn spring-boot:build-image -Dspring-boot.build-image.imageName=my-registry/order-service:1.0.0

# Pubblica l'immagine
docker push my-registry/order-service:1.0.0
```

!!! tip "Buildpacks vs Dockerfile"
    Buildpacks gestiscono automaticamente: layering ottimale, security patches (rebasing senza rebuild), SBOM (Software Bill of Materials), e configurazione JVM container-aware. Preferire Buildpacks quando il team non ha esigenze specifiche di Dockerfile personalizzati.

---

## Best Practices

### Gestione della Configurazione

- **Mai hardcodare** credenziali o URL: usare sempre variabili d'ambiente o ConfigMap
- **Usare `@ConfigurationProperties`** invece di `@Value` per configurazioni strutturate — permettono validazione e sono refactorable
- **Separare config applicativa da config infrastrutturale**: `application.yml` per defaults, ConfigMap per override per-ambiente
- **Non usare `spring.config.location`** in Kubernetes — usare `spring-cloud-kubernetes` che integra nativamente

### Actuator in Produzione

```yaml
# Sicurezza Actuator — non esporre tutto in produzione
management:
  endpoints:
    web:
      exposure:
        # SOLO questi endpoint — mai 'env' (espone secrets), 'heapdump', 'threaddump' senza auth
        include: health,prometheus,info
  endpoint:
    health:
      show-details: never        # Details solo in dev
  # Separa sempre porta management dalla porta applicativa
  server:
    port: 8081
```

!!! warning "Attenzione: Actuator e segreti"
    L'endpoint `/actuator/env` espone TUTTE le property, incluse password e token. Non includerlo mai nell'`exposure.include` in produzione senza autenticazione Spring Security.

### Graceful Shutdown

```yaml
# application.yml — graceful shutdown per rolling updates K8s
server:
  shutdown: graceful            # Completa le richieste in corso prima di terminare

spring:
  lifecycle:
    timeout-per-shutdown-phase: 30s  # Tempo massimo per lo shutdown
```

Il `preStop` hook Kubernetes dovrebbe aspettare qualche secondo prima di SIGTERM per permettere a kube-proxy di aggiornare le regole iptables:

```yaml
# Deployment — lifecycle hook
lifecycle:
  preStop:
    exec:
      command: ["/bin/sh", "-c", "sleep 5"]
```

### JVM Tuning per Container

```bash
# JVM flags raccomandate per container Kubernetes
JAVA_TOOL_OPTIONS="\
  -XX:+UseContainerSupport \
  -XX:MaxRAMPercentage=75.0 \
  -XX:InitialRAMPercentage=50.0 \
  -XX:+UseG1GC \
  -XX:MaxGCPauseMillis=200 \
  -Djava.security.egd=file:/dev/./urandom \
  -Dfile.encoding=UTF-8"
```

!!! tip "Virtual Threads (Java 21 + Spring Boot 3.2)"
    Abilitare Virtual Threads elimina la necessità di tuning del thread pool per applicazioni I/O-bound:
    ```yaml
    spring:
      threads:
        virtual:
          enabled: true   # Abilita Loom Virtual Threads per Tomcat e task scheduler
    ```
    Con Virtual Threads, ogni richiesta HTTP usa un virtual thread (leggero) invece di un OS thread — il pool Tomcat non è più un collo di bottiglia.

---

## Troubleshooting

### Il Pod non diventa Ready — readinessProbe fallisce

**Sintomo:** Pod in stato `Running` ma non riceve traffico; `kubectl describe pod` mostra readiness probe failures.

**Causa comune:** Spring Context impiega più tempo del previsto (connessione DB, warm-up cache).

**Soluzione:**
```yaml
# Aumentare initialDelaySeconds o usare startupProbe
startupProbe:
  httpGet:
    path: /actuator/health/readiness
    port: 8081
  failureThreshold: 30          # 30 * 10s = 5 minuti massimo per startup
  periodSeconds: 10
livenessProbe:
  # Inizia solo dopo startupProbe OK
  httpGet:
    path: /actuator/health/liveness
    port: 8081
  periodSeconds: 10
  failureThreshold: 3
```

### OOMKilled — Il Container viene terminato per memoria

**Sintomo:** `kubectl describe pod` mostra `OOMKilled`; `kubectl top pod` mostra memoria vicina al limit.

**Causa:** `MaxRAMPercentage` troppo alto o limite container troppo basso. La JVM usa memoria extra per metaspace, code cache, direct buffers.

**Soluzione:**
```bash
# Regola empirica: limit container = heap JVM * 1.5
# Se MaxRAMPercentage=75 e memory limit=512Mi:
#   Heap = 512 * 0.75 = 384Mi
#   Extra JVM overhead ~150Mi
#   Container limit dovrebbe essere 512Mi+

# Verifica consumo reale
kubectl exec -it <pod> -- java -XX:+PrintFlagsFinal -version 2>&1 | grep MaxHeapSize

# Aggiusta il limit
resources:
  limits:
    memory: "768Mi"   # Aumenta se OOMKilled
```

### Hikari Connection Pool — connessioni esaurite

**Sintomo:** `HikariPool-1 - Connection is not available, request timed out after 30000ms`

**Causa:** Troppi thread concorrenti rispetto al pool size, o connection leak.

**Soluzione:**
```yaml
spring:
  datasource:
    hikari:
      maximum-pool-size: 20      # Aumenta (attenzione: max_connections PostgreSQL)
      connection-timeout: 5000   # Fallisci veloce invece di aspettare 30s
      leak-detection-threshold: 10000  # Log se una connessione è aperta >10s
      # Formula empirica: pool_size = (core_count * 2) + effective_spindle_count
```

### Spring Cloud Kubernetes — ConfigMap non letto

**Sintomo:** Le property del ConfigMap non vengono iniettate; log: `Unable to load config maps`

**Causa 1:** ServiceAccount senza permessi RBAC.

**Soluzione:**
```yaml
# RBAC per spring-cloud-kubernetes
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: order-service-config-reader
  namespace: production
rules:
  - apiGroups: [""]
    resources: ["configmaps", "secrets"]
    verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: order-service-config-reader-binding
  namespace: production
subjects:
  - kind: ServiceAccount
    name: order-service
    namespace: production
roleRef:
  kind: Role
  name: order-service-config-reader
  apiGroup: rbac.authorization.k8s.io
```

**Causa 2:** Applicazione in esecuzione fuori dal cluster (locale) senza configurazione fallback.

**Soluzione:**
```yaml
# application-dev.yml — disabilita spring-cloud-kubernetes in locale
spring:
  cloud:
    kubernetes:
      enabled: false
      config:
        enabled: false
      secrets:
        enabled: false
```

---

## Relazioni

Spring Boot 3.x è il punto di integrazione con molti altri argomenti della KB:

??? info "Spring Kafka — Integrazione Kafka"
    Spring Kafka fornisce `KafkaTemplate` e `@KafkaListener` per produrre/consumare messaggi. Si configura tramite `application.yml` (`spring.kafka.*`) e beneficia di tutti i pattern descritti in questo documento (profiles, Actuator health indicator per Kafka, Testcontainers per test).

    **Approfondimento completo →** [Spring Kafka](../../messaging/kafka/sviluppo/spring-kafka.md)

??? info "Resilience4j — Circuit Breaker & Retry"
    `spring-cloud-starter-circuitbreaker-resilience4j` integra Resilience4j con Spring Boot: annotazioni `@CircuitBreaker`, `@Retry`, `@RateLimiter` sulle chiamate HTTP, configurazione in `application.yml` con profili, e metriche automatiche su Micrometer/Prometheus.

??? info "JVM Tuning — Ottimizzazione Runtime"
    I parametri JVM descritti in questa sezione (MaxRAMPercentage, G1GC, Virtual Threads) sono approfonditi nel documento dedicato al tuning JVM per container Kubernetes.

---

## Riferimenti

- [Spring Boot Reference Documentation](https://docs.spring.io/spring-boot/docs/current/reference/html/)
- [Spring Cloud Kubernetes](https://spring.io/projects/spring-cloud-kubernetes)
- [Spring Boot Actuator](https://docs.spring.io/spring-boot/docs/current/reference/html/actuator.html)
- [Testcontainers Spring Boot](https://testcontainers.com/guides/testing-spring-boot-rest-api-using-testcontainers/)
- [Cloud Native Buildpacks — Spring Boot](https://docs.spring.io/spring-boot/docs/current/maven-plugin/reference/htmlsingle/#build-image)
- [Micrometer Documentation](https://micrometer.io/docs)
- [Resilience4j Spring Boot 3](https://resilience4j.readme.io/docs/getting-started-3)
- [Paketo Buildpacks](https://paketo.io/docs/)
