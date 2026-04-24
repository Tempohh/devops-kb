---
title: "Test Strategy per Microservizi"
slug: test-strategy
category: ci-cd
tags: [testing, test-pyramid, unit-tests, integration-tests, e2e-tests, testcontainers, mutation-testing, microservices]
search_keywords: [test pyramid, test strategy, test strategia, unit test, integration test, e2e test, end to end test, testcontainers, contract testing, mutation testing, PIT, mutmut, go-mutesting, test coverage, code coverage, test automation, microservices testing, testing microservizi, test isolation, mock, stub, double, awaitility, test splitting, shard, parallel tests, fail fast, test quality, brittle tests, flaky tests, non deterministic tests, spring boot test, pytest, jest, junit, test suite, smoke test, regression test, component test]
parent: ci-cd/testing/_index
related: [ci-cd/testing/contract-testing, ci-cd/github-actions/workflow-avanzati, ci-cd/gitlab-ci/pipeline-avanzato, ci-cd/strategie/pipeline-security]
official_docs: https://testcontainers.com/
status: complete
difficulty: intermediate
last_updated: 2026-04-04
---

# Test Strategy per Microservizi

## Panoramica

Una test strategy definisce **quali test scrivere, quanti, quando eseguirli e come distribuirli nella pipeline CI/CD**. In un'architettura a microservizi questo è particolarmente critico: senza una strategia deliberata si finisce con test lenti, fragili, e che non trovano i bug reali.

Il modello di riferimento è la **test pyramid**, proposta da Mike Cohn: molti unit test veloci alla base, meno integration test nel mezzo, pochissimi E2E test in cima. L'intuizione è che salire la piramide aumenta il costo di esecuzione e manutenzione. I test lenti bloccano la pipeline; i test fragili generano falsi negativi che erodono la fiducia.

Per i microservizi la piramide ha quattro livelli distinti: unit test, integration test (con infrastruttura reale tramite Testcontainers), contract test (interfacce tra servizi), ed E2E test limitati ai happy path critici. Ogni livello risponde a domande diverse e va eseguito con timing diversi nel CI.

**Quando questa guida è utile:**
- Stai strutturando la strategia di test per un nuovo servizio
- La pipeline è lenta e vuoi capire dove tagliare
- I test passano in CI ma falliscono in produzione
- Il team spende più tempo a mantenere i test che a scrivere codice

**Quando non è sufficiente:**
- Performance testing e load testing — richiedono strumenti dedicati (Gatling, k6)
- Security testing — SAST/DAST hanno protocolli separati
- Chaos engineering — disciplina distinta (Chaos Monkey, Litmus)

---

## Concetti Chiave

!!! note "La Test Pyramid"
    La piramide identifica quattro livelli di test, ordinati per velocità, costo e quantità:

    ```
                    ┌───────────┐
                    │  E2E (4)  │   ← pochi, solo happy path, solo su main
                  ┌─┴───────────┴─┐
                  │ Contract (3)  │   ← interfacce tra servizi, Pact
                ┌─┴───────────────┴─┐
                │  Integration (2)  │   ← DB reale, broker reale, Testcontainers
              ┌─┴───────────────────┴─┐
              │      Unit (1)         │   ← logica business, fast, >80% coverage
              └───────────────────────┘
    ```

    Un progetto sano ha molti più unit test che E2E. Se la distribuzione è invertita (più E2E che unit), la pipeline sarà lenta e il feedback loop degradato.

!!! note "Test Coverage ≠ Test Quality"
    Il coverage percentuale misura le righe eseguite, non le asserzioni utili. Un test che esegue codice senza asserire nulla aumenta il coverage senza trovare bug. Il **mutation testing** è la tecnica corretta per misurare la qualità effettiva dei test.

!!! warning "I test fragili (flaky) sono un debito tecnico"
    Un test che passa e fallisce in modo non deterministico è peggio di nessun test: genera rumore, erode la fiducia nel CI, e porta i team a ignorare i rossi. Le cause più comuni sono: stato condiviso tra test, sleep/wait fissi, dipendenze da ordine di esecuzione, e race condition nei test asincroni.

---

## Architettura / Come Funziona

### Layer 1 — Unit Test

I unit test verificano la **logica di business in isolamento** da qualsiasi dipendenza esterna. Una funzione che calcola il prezzo scontato, un validatore di input, un algoritmo di routing: questi sono i candidati ideali.

**Cosa mockare:** tutto ciò che non è logica di business pura — DB, servizi HTTP, message broker, file system, clock di sistema.

**Cosa NON mockare:** le collaborazioni interne alla stessa unità, le value objects, i domain objects. Mock eccessivi producono test che verificano l'implementazione invece del comportamento.

**Target:** coverage >80% sulle classi di dominio, esecuzione <1 minuto totale.

### Layer 2 — Integration Test

I test di integrazione verificano che il codice funzioni correttamente **con l'infrastruttura reale**: database reale, message broker reale, servizi HTTP reali (mockati a livello di rete, non di codice).

Lo strumento di riferimento è **Testcontainers**: avvia container Docker durante i test e li ferma al termine. Questo elimina la dipendenza da ambienti esterni condivisi e garantisce riproducibilità.

**Cosa testare:** repository layer (query SQL, transazioni), Kafka consumer/producer, cache Redis, chiamate HTTP verso servizi esterni (con WireMock).

**Target:** esecuzione <15 minuti, eseguiti su ogni PR insieme agli unit test.

### Layer 3 — Contract Test

I contract test verificano le **interfacce tra servizi** senza richiedere che entrambi siano attivi simultaneamente. Il framework Pact implementa il pattern Consumer-Driven Contracts.

Questo layer è descritto in dettaglio in [Contract Testing](contract-testing.md). In questa guida si assume che i contract test esistano e si integrano nella pipeline dopo gli integration test.

### Layer 4 — E2E Test

I test end-to-end verificano i **happy path critici** dell'intero sistema deployato. Sono i più costosi da eseguire e mantenere: richiedono tutti i servizi attivi, dati realistici, e sono sensibili a latenze e ordering.

**Regola pratica:** massimo 10-20 scenari E2E, solo i flussi che portano valore di business diretto (checkout, registrazione, pagamento). Non usare E2E per validare logica di business — i unit test lo fanno meglio e 100× più veloce.

**Quando eseguirli:** solo su `main` dopo il merge, non su ogni PR. Il feedback su una PR deve arrivare in <10 minuti; gli E2E possono prendere 20-30 minuti.

---

## Configurazione & Pratica

### Testcontainers — Java / Spring Boot

```java
// OrderRepositoryTest.java
@SpringBootTest
@Testcontainers
@Transactional
class OrderRepositoryTest {

    @Container
    static PostgreSQLContainer<?> postgres =
        new PostgreSQLContainer<>("postgres:16-alpine")
            .withDatabaseName("testdb")
            .withUsername("test")
            .withPassword("test")
            .withReuse(true); // riusa il container tra test della stessa JVM

    @DynamicPropertySource
    static void overrideProperties(DynamicPropertyRegistry registry) {
        // Inietta l'URL del container nel contesto Spring
        registry.add("spring.datasource.url", postgres::getJdbcUrl);
        registry.add("spring.datasource.username", postgres::getUsername);
        registry.add("spring.datasource.password", postgres::getPassword);
    }

    @Autowired
    private OrderRepository orderRepository;

    @Test
    void shouldPersistOrderWithItems() {
        Order order = Order.create(CustomerId.of("cust-123"));
        order.addItem(ProductId.of("prod-456"), Quantity.of(2), Money.of(29.99));

        Order saved = orderRepository.save(order);

        assertThat(saved.getId()).isNotNull();
        assertThat(saved.getItems()).hasSize(1);
        assertThat(saved.getTotalAmount()).isEqualByComparingTo("59.98");
    }

    @Test
    void shouldFindOrdersByCustomer() {
        // Prepara dati
        orderRepository.save(Order.create(CustomerId.of("cust-999")));
        orderRepository.save(Order.create(CustomerId.of("cust-999")));

        List<Order> orders = orderRepository.findByCustomerId(CustomerId.of("cust-999"));

        assertThat(orders).hasSize(2);
    }
}
```

### Testcontainers — Kafka Integration Test (Java)

```java
// KafkaOrderConsumerTest.java
@SpringBootTest
@Testcontainers
class KafkaOrderConsumerTest {

    @Container
    static KafkaContainer kafka =
        new KafkaContainer(DockerImageName.parse("confluentinc/cp-kafka:7.6.0"))
            .withReuse(true);

    @DynamicPropertySource
    static void overrideKafkaProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.kafka.bootstrap-servers", kafka::getBootstrapServers);
    }

    @Autowired
    private KafkaTemplate<String, OrderCreatedEvent> kafkaTemplate;

    @Autowired
    private InventoryUpdateService inventoryUpdateService; // il consumer sotto test

    @Test
    void shouldProcessOrderCreatedEvent() throws Exception {
        OrderCreatedEvent event = new OrderCreatedEvent("order-123", List.of(
            new OrderItem("prod-456", 2)
        ));

        kafkaTemplate.send("order-created", event).get(5, TimeUnit.SECONDS);

        // Awaitility: polling con timeout invece di sleep fisso
        await()
            .atMost(Duration.ofSeconds(10))
            .pollInterval(Duration.ofMillis(200))
            .untilAsserted(() ->
                assertThat(inventoryUpdateService.getProcessedOrders())
                    .contains("order-123")
            );
    }
}
```

### Testcontainers — Python / pytest

```python
# test_order_repository.py
import pytest
from testcontainers.postgres import PostgresContainer
from sqlalchemy import create_engine
from myapp.repositories import OrderRepository
from myapp.models import Order, OrderItem

@pytest.fixture(scope="session")
def postgres_container():
    """Container riusato per tutta la sessione di test."""
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg

@pytest.fixture(scope="session")
def db_engine(postgres_container):
    engine = create_engine(postgres_container.get_connection_url())
    # Crea schema
    from myapp.models import Base
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()

@pytest.fixture
def order_repo(db_engine):
    """Ogni test riceve una sessione pulita con rollback automatico."""
    with db_engine.connect() as conn:
        with conn.begin() as tx:
            repo = OrderRepository(conn)
            yield repo
            tx.rollback()  # rollback: il test non inquina gli altri

def test_save_and_retrieve_order(order_repo):
    order = Order(customer_id="cust-123", items=[
        OrderItem(product_id="prod-456", quantity=2, unit_price=29.99)
    ])
    saved = order_repo.save(order)

    retrieved = order_repo.find_by_id(saved.id)

    assert retrieved is not None
    assert retrieved.customer_id == "cust-123"
    assert len(retrieved.items) == 1
    assert retrieved.total_amount == pytest.approx(59.98)
```

### Testcontainers — WireMock per HTTP esterno

```java
// PaymentServiceClientTest.java — testa la chiamata HTTP verso un provider esterno
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
@Testcontainers
class PaymentServiceClientTest {

    @Container
    static WireMockContainer wireMock =
        new WireMockContainer("wiremock/wiremock:3.3.1")
            .withMapping("payment-success", PaymentServiceClientTest.class,
                         "wiremock/payment-success.json");

    @DynamicPropertySource
    static void overridePaymentServiceUrl(DynamicPropertyRegistry registry) {
        registry.add("payment.service.base-url", wireMock::getBaseUrl);
    }

    @Autowired
    private PaymentServiceClient paymentClient;

    @Test
    void shouldReturnSuccessOnValidPayment() {
        PaymentRequest request = new PaymentRequest("order-123", Money.of(59.98));

        PaymentResult result = paymentClient.processPayment(request);

        assertThat(result.isSuccessful()).isTrue();
        assertThat(result.getTransactionId()).isNotBlank();
    }
}
```

```json
// src/test/resources/wiremock/payment-success.json
{
  "request": {
    "method": "POST",
    "urlPattern": "/payments"
  },
  "response": {
    "status": 200,
    "headers": { "Content-Type": "application/json" },
    "jsonBody": {
      "transactionId": "txn-abc-123",
      "status": "SUCCESS",
      "amount": 59.98
    }
  }
}
```

### Struttura Pipeline CI — GitHub Actions

```yaml
# .github/workflows/ci.yml
name: CI Pipeline

on:
  push:
    branches: ["**"]
  pull_request:

jobs:
  # Layer 1 + 2: unit e integration in parallelo se il progetto li separa
  # In molti progetti si eseguono insieme per semplicità
  unit-tests:
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with:
          java-version: "21"
          distribution: "temurin"
          cache: "maven"
      - name: Run unit tests
        run: mvn test -Dgroups="unit" -T 4 # 4 thread paralleli

  integration-tests:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    # Docker è disponibile di default su ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with:
          java-version: "21"
          distribution: "temurin"
          cache: "maven"
      - name: Run integration tests
        run: mvn test -Dgroups="integration"
        env:
          TESTCONTAINERS_RYUK_DISABLED: "false"
          DOCKER_HOST: unix:///var/run/docker.sock

  contract-tests:
    runs-on: ubuntu-latest
    needs: [unit-tests, integration-tests]
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-java@v4
        with:
          java-version: "21"
          distribution: "temurin"
          cache: "maven"
      - name: Run Pact consumer tests
        run: mvn test -Dgroups="contract"
      - name: Publish pacts to broker
        run: |
          mvn pact:publish \
            -Dpact.broker.url=${{ vars.PACT_BROKER_URL }} \
            -Dpact.broker.username=${{ secrets.PACT_BROKER_USER }} \
            -Dpact.broker.password=${{ secrets.PACT_BROKER_PASSWORD }} \
            -Dpact.consumer.version=${{ github.sha }} \
            -Dpact.tag=${{ github.ref_name }}
      - name: Can I deploy?
        run: |
          pact-broker can-i-deploy \
            --pacticipant OrderService \
            --version ${{ github.sha }} \
            --to-environment production \
            --broker-base-url ${{ vars.PACT_BROKER_URL }}

  e2e-tests:
    runs-on: ubuntu-latest
    needs: [contract-tests]
    # E2E solo su main, non su ogni PR
    if: github.ref == 'refs/heads/main'
    timeout-minutes: 30
    environment: staging
    steps:
      - uses: actions/checkout@v4
      - name: Run E2E smoke tests
        run: mvn test -Dgroups="e2e" -Dbase.url=${{ vars.STAGING_URL }}
      - name: Upload E2E report
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: e2e-report
          path: target/surefire-reports/
```

### Tagging dei test (JUnit 5 / Spring)

```java
// Annotazione custom per categorizzare i test
@Target({ ElementType.TYPE, ElementType.METHOD })
@Retention(RetentionPolicy.RUNTIME)
@Tag("unit")
public @interface UnitTest {}

@Target({ ElementType.TYPE, ElementType.METHOD })
@Retention(RetentionPolicy.RUNTIME)
@Tag("integration")
@Testcontainers  // Testcontainers implicito per tutti gli integration test
public @interface IntegrationTest {}

// Uso nei test
@UnitTest
class PricingEngineTest {
    @Test void shouldApplySeasonalDiscount() { ... }
}

@IntegrationTest
class OrderRepositoryTest {
    @Container
    static PostgreSQLContainer<?> postgres = ...;
}
```

```xml
<!-- maven-surefire-plugin in pom.xml: esegui solo il gruppo specificato -->
<plugin>
    <groupId>org.apache.maven.plugins</groupId>
    <artifactId>maven-surefire-plugin</artifactId>
    <version>3.2.5</version>
    <configuration>
        <groups>${groups}</groups> <!-- -Dgroups=unit oppure -Dgroups=integration -->
    </configuration>
</plugin>
```

---

## Mutation Testing

Il mutation testing introduce **piccole mutazioni nel codice sorgente** (cambia `>` in `>=`, elimina una riga, inverte una condizione) e verifica che i test esistenti rilevino la mutazione. Se un test non fallisce quando il codice è mutato, probabilmente non sta testando quel comportamento in modo efficace.

### PIT — Java

```xml
<!-- pom.xml: plugin PIT per mutation testing -->
<plugin>
    <groupId>org.pitest</groupId>
    <artifactId>pitest-maven</artifactId>
    <version>1.15.3</version>
    <dependencies>
        <!-- Supporto JUnit 5 -->
        <dependency>
            <groupId>org.pitest</groupId>
            <artifactId>pitest-junit5-plugin</artifactId>
            <version>1.2.1</version>
        </dependency>
    </dependencies>
    <configuration>
        <targetClasses>
            <param>com.example.domain.*</param>   <!-- solo classi di dominio -->
        </targetClasses>
        <targetTests>
            <param>com.example.*Test</param>
        </targetTests>
        <mutationThreshold>60</mutationThreshold>  <!-- fallisce sotto il 60% -->
        <coverageThreshold>80</coverageThreshold>
        <outputFormats>
            <outputFormat>HTML</outputFormat>
            <outputFormat>XML</outputFormat>
        </outputFormats>
        <!-- Mutatori: scegli quelli pertinenti al dominio -->
        <mutators>
            <mutator>STRONGER</mutator>
        </mutators>
    </configuration>
</plugin>
```

```bash
# Esegui mutation testing
mvn org.pitest:pitest-maven:mutationCoverage

# Output esempio nel report HTML:
# Mutation score: 73% (219/300 mutations killed)
# Line coverage: 87%
# Classes below threshold: PricingEngine (54%) → richiede più test
```

### mutmut — Python

```bash
# Installa
pip install mutmut

# Esegui su un modulo specifico
mutmut run --paths-to-mutate src/domain/pricing.py

# Visualizza risultati
mutmut results
# Survived mutations (da correggere con nuovi test):
# --- src/domain/pricing.py (line 34) ---
# - if discount_rate > 0.5:
# + if discount_rate >= 0.5:
# ^^^^^^^^ questo mutante è sopravvissuto → manca un test per il boundary

# Applica un mutante per ispezionarlo
mutmut apply 5
# ... scrivi un test che lo uccida ...
mutmut unapply

# HTML report
mutmut html
```

### go-mutesting — Go

```bash
# Installa
go install github.com/zimmski/go-mutesting/cmd/go-mutesting@latest

# Esegui su un package
go-mutesting ./internal/domain/...

# Output:
# PASS: mutation at "pricing.go:34:5" was detected by tests
# FAIL: mutation at "pricing.go:67:12" was NOT detected by tests
# Mutation score: 68.0% (17/25)
```

### Integrazione nel CI (mutation testing opzionale)

```yaml
# GitHub Actions: mutation testing su PR che toccano il dominio
mutation-testing:
  runs-on: ubuntu-latest
  needs: [unit-tests]
  # Solo se ci sono modifiche nelle classi di dominio
  if: contains(github.event.pull_request.changed_files, 'src/main/java/com/example/domain')
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-java@v4
      with:
        java-version: "21"
        distribution: "temurin"
        cache: "maven"
    - name: Run mutation testing
      run: mvn org.pitest:pitest-maven:mutationCoverage
    - name: Upload mutation report
      uses: actions/upload-artifact@v4
      with:
        name: mutation-report
        path: target/pit-reports/
```

---

## Best Practices

**Scrivi test che verificano il comportamento, non l'implementazione.** Un test che verifica che un metodo specifico sia stato chiamato è fragile: si rompe a ogni refactoring. Un test che verifica il risultato osservabile (output, effetto su DB, messaggio pubblicato) è stabile.

**Un test, un'asserzione logica.** Non confondere con "una sola riga `assert`": una verifica logica può includere più asserzioni correlate. Confondere due scenari distinti in un test rende il failure message ambiguo.

**Isola lo stato tra test.** Ogni test deve partire da uno stato pulito e non dipendere dall'ordine di esecuzione. Per i test con DB: usa rollback (@Transactional in Spring, `tx.rollback()` in pytest) o reset esplicito tra i test. Non condividere oggetti mutable statici tra test.

**Usa Awaitility/polling invece di sleep fissi.** Un `Thread.sleep(3000)` è sia lento che fragile. Awaitility (Java), `tenacity` (Python), o un semplice loop con timeout verificano la condizione non appena è vera.

!!! tip "Testcontainers con `withReuse(true)`"
    In sviluppo locale, `withReuse(true)` mantiene i container attivi tra diverse run di test, riducendo il tempo di startup da 5-10 secondi a 0. In CI, la riusabilità è gestita dai layer di cache Docker. Da abilitare per container pesanti come Kafka e database.

!!! tip "Test splitting per parallelizzare"
    Per suite di integration test molto grandi, usa `--shard` (Jest) o `--split-by=timing` (GitHub Actions matrix) per distribuire i test su più runner in parallelo. Dimezza i tempi con 2 runner, riduce di 2/3 con 3.

!!! warning "Non mockare il database per gli integration test"
    Database embedded come H2 o SQLite usati al posto di PostgreSQL/MySQL hanno comportamenti diversi: SQL dialetti, constraint di integrità, JSON columns, generated columns. I bug trovati in produzione che passano sui mock sono bug che i test dovevano trovare ma non hanno trovato. Usa Testcontainers con il DB reale.

!!! warning "E2E su ogni PR è un anti-pattern"
    Gli E2E rallentano il feedback loop e sono i test più fragili (network latency, data race, servizi instabili). Limitarli a `main` o a un gate post-merge mantiene le PR veloci e gli E2E informativi sullo stato stabile del sistema.

---

## Troubleshooting

**I Testcontainers falliscono in CI con "Cannot connect to the Docker daemon"**

: Causa: il runner CI non ha il Docker daemon disponibile o il socket è in una posizione non standard.
Soluzione: su GitHub Actions, usare `ubuntu-latest` (Docker incluso). Aggiungere `DOCKER_HOST: unix:///var/run/docker.sock` come env variable. Se si usa Kubernetes runner, abilitare Docker-in-Docker o Testcontainers Cloud.

```bash
# Verifica che Docker sia disponibile nel runner
docker info
# Se fallisce: il runner non ha Docker abilitato
```

**I test con Testcontainers sono lenti anche in CI**

: Causa: il container viene avviato e fermato per ogni test class invece di essere riusato.
Soluzione: dichiarare il container come `static` in Java (lifecycle legato alla classe, non al singolo test). Usare `scope="session"` per le fixture pytest. Abilitare `withReuse(true)` in sviluppo locale.

```java
// SBAGLIATO: un container per test
@Container
PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16");

// CORRETTO: un container per classe (static)
@Container
static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16");
```

**I test falliscono in modo non deterministico (flaky)**

: Causa più comune: stato condiviso tra test, ordine di esecuzione non garantito, o attese temporali fisse.
Diagnosi: eseguire i test in ordine casuale (`mvn test -Dsurefire.runOrder=random`). Identificare quale test "inquina" lo stato per il successivo.

```bash
# JUnit 5: esegui in ordine casuale per trovare dipendenze implicite
mvn test -Dsurefire.runOrder=random -Dsurefire.rerunFailingTestsCount=3

# pytest: esegui in ordine casuale
pip install pytest-randomly
pytest --randomly-seed=12345
```

**Mutation score basso nonostante coverage alta**

: Causa: i test non contengono asserzioni significative, o testano casi che non stressano i boundary.
Diagnosi: esaminare il report HTML di PIT e trovare i mutanti sopravvissuti. Di solito si concentrano nei branch (`if/else`), boundary conditions (`>` vs `>=`), e loop.
Soluzione: aggiungere test che verificano esplicitamente i casi limite: valori zero, negativi, valori al boundary esatto.

**Awaitility timeout scaduto nonostante l'evento sia arrivato**

: Causa: l'offset Kafka del consumer è impostato su `latest` invece di `earliest` nei test, quindi non vede i messaggi prodotti prima della sottoscrizione.
Soluzione: impostare `auto.offset.reset=earliest` nelle properties del consumer di test.

```yaml
# application-test.properties / Spring
spring.kafka.consumer.auto-offset-reset: earliest
spring.kafka.consumer.group-id: test-group-${random.uuid} # gruppo unico per evitare conflitti
```

---

## Relazioni

??? info "Contract Testing — Layer 3 della piramide"
    Il contract testing (Pact) è il livello 3 della test pyramid e si integra nella pipeline dopo gli integration test. Questa guida copre la struttura generale; Pact è trattato in dettaglio nel file dedicato.

    **Approfondimento →** [Contract Testing](contract-testing.md)

??? info "GitHub Actions — Pipeline strutturata"
    La struttura a job sequenziali descritta in questa guida (unit → integration → contract → e2e) si implementa direttamente con `needs:` nei workflow GitHub Actions.

    **Approfondimento →** [GitHub Actions Workflow Avanzati](../github-actions/workflow-avanzati.md)

??? info "GitLab CI — Stage di test"
    In GitLab CI la stessa struttura si mappa su stage separati con `needs:` e artifacts tra stage. Il parallelismo si implementa con `parallel:` e matrix.

    **Approfondimento →** [GitLab CI Pipeline Avanzato](../gitlab-ci/pipeline-avanzato.md)

??? info "Pipeline Security — Quality gates"
    I test sono un layer di sicurezza della supply chain. Il mutation score e il coverage sono gate di qualità che si integrano nei job CI accanto ai controlli SAST.

    **Approfondimento →** [Pipeline Security](../strategie/pipeline-security.md)

---

## Riferimenti

- [Testcontainers — documentazione ufficiale](https://testcontainers.com/) — guida per Java, Go, Python, Node.js
- [PIT Mutation Testing](https://pitest.org/) — mutation testing per Java
- [mutmut](https://mutmut.readthedocs.io/) — mutation testing per Python
- [Awaitility](https://github.com/awaitility/awaitility) — libreria Java per asserzioni asincrone
- [Martin Fowler — Test Pyramid](https://martinfowler.com/bliki/TestPyramid.html) — articolo originale di Mike Cohn rielaborato da Fowler
- [Martin Fowler — Practical Test Pyramid](https://martinfowler.com/articles/practical-test-pyramid.html) — guida pratica con esempi
- [Google Testing Blog — Just Say No to More End-to-End Tests](https://testing.googleblog.com/2015/04/just-say-no-to-more-end-to-end-tests.html) — motivazioni per ridurre gli E2E
- [Testcontainers Cloud](https://testcontainers.com/cloud/) — Testcontainers senza Docker-in-Docker in CI
