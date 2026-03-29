---
title: "Testing Microservizi"
slug: testing
category: dev
tags: [testing, unit-testing, integration-testing, contract-testing, testcontainers, chaos-engineering, test-doubles, microservizi]
search_keywords: [testing microservizi, microservices testing, unit test, integration test, contract testing, consumer driven contracts, pact, test doubles, mock, stub, fake, spy, testcontainers, chaos engineering, chaos monkey, end to end testing, e2e test, api testing, component testing, service testing, test pyramid, test piramide, pyramid of tests, quality assurance, qa, tdd, test driven development, bdd, behavior driven development, junit, pytest, go test, jest, mocha, mockito, wiremock, httpretty, nock, hoverfly, localstack, test isolation, test containers, docker test, in-memory database, hsqldb, h2 database, mutation testing, property based testing, fault injection, resilience testing, smoke test, canary test, contract broker, pact broker, provider verification]
parent: dev/_index
related: [dev/resilienza/_index, dev/api/_index, dev/integrazioni/_index, ci-cd/testing/_index]
official_docs: https://testcontainers.com/
status: complete
difficulty: intermediate
last_updated: 2026-03-28
---

# Testing Microservizi

## Panoramica

Il testing di microservizi è strutturalmente diverso dal testing di un monolite: la boundary tra i servizi è un sistema distribuito, non una chiamata di funzione in-process. Le dipendenze possono essere temporaneamente non disponibili, i contratti delle API evolvono indipendentemente, e la fiducia nel comportamento complessivo del sistema richiede una strategia multi-livello.

Il modello di riferimento è la **Test Pyramid** di Mike Cohn, adattata ai microservizi:

```
        /\
       /E2E\         ← pochi, lenti, costosi — solo i percorsi critici
      /______\
     /Contract \     ← verificano i contratti tra servizi (Pact)
    /____________\
   / Integration  \  ← testano un servizio con dipendenze reali (Testcontainers)
  /________________\
 /    Unit Tests    \ ← molti, veloci, isolati — logica di business
/____________________\
```

Un servizio ben testato ha la base larga (unit) e l'apice stretto (E2E). Invertire la piramide è un anti-pattern: una suite di test lenta, fragile, e costosa da mantenere.

Quando NON testare tutto a livello E2E: se stai testando l'integrazione di 5 servizi per verificare la logica di un singolo servizio, stai testando nel posto sbagliato. Scendi nella piramide fino al livello più basso che copre la proprietà che ti interessa.

!!! tip "Filosofia del test di microservizi"
    Ogni servizio deve essere testabile in isolamento. Se non riesci a testare un servizio senza avviare 3 altri servizi, questo è un segnale che il design del servizio ha problemi di coupling, non che la suite di test è incompleta.

---

## Concetti Chiave

### La Test Pyramid per Microservizi

```
Livello        | Velocità | Costo   | Copertura                       | Scope
───────────────|──────────|---------|---------------------------------|──────────────────────
Unit           | <1ms     | Basso   | Logica interna, algoritmi, calcoli | Singola classe/funzione
Integration    | 1-30s    | Medio   | DB reale, broker reale, HTTP call | Servizio + dipendenze reali
Contract       | 5-60s    | Medio   | Compatibilità API tra consumatore e provider | 2 servizi (in isolamento)
Component      | 10-120s  | Medio   | Comportamento end-to-end di un servizio | 1 servizio (dipendenze simulate)
E2E            | 30s-10m  | Alto    | Percorsi critici nel sistema live  | N servizi in ambiente reale
```

### Test Doubles

I test doubles sostituiscono le dipendenze reali durante i test. Esistono cinque varianti con semantica diversa:

| Tipo | Descrizione | Quando usarlo |
|---|---|---|
| **Dummy** | Oggetto passato ma mai usato | Quando il parametro è richiesto ma irrilevante al test |
| **Stub** | Restituisce risposte predeterminate | Quando vuoi controllare l'input al SUT |
| **Fake** | Implementazione funzionante ma semplificata | DB in memoria, file system in memoria |
| **Mock** | Verifica le interazioni avvenute | Quando il comportamento osservabile è la chiamata stessa |
| **Spy** | Wrapper su oggetto reale che registra le chiamate | Quando vuoi verificare che una chiamata sia avvenuta senza sostituire il comportamento |

!!! warning "Mock vs Stub: l'errore comune"
    Un mock verifica le **interazioni** (che una chiamata sia avvenuta con certi parametri). Uno stub fornisce **dati di input** al sistema under test. Abusare dei mock porta a test che verificano i dettagli implementativi invece del comportamento — si rompono al refactoring anche quando il comportamento non è cambiato.

### Test Isolation

Ogni test deve essere completamente indipendente dagli altri: stesso ordine di esecuzione, stesso risultato. Le violazioni più comuni dell'isolation:

- **Stato condiviso nel database** → usa transaction rollback o ricrea il DB per ogni test
- **Stato condiviso in variabili statiche/globali** → resetta esplicitamente prima di ogni test
- **Side effects sull'esterno** → intercetta le chiamate HTTP, non fare chiamate reali
- **Dipendenze dall'ordine di esecuzione** → ogni test deve creare il proprio stato iniziale

---

## Architettura / Come Funziona

### Component Test: il Servizio in Isolamento

Il component test è il livello più importante per i microservizi: testa un singolo servizio sostituendo TUTTE le dipendenze esterne con test doubles controllati (WireMock per HTTP, embedded broker per Kafka, Testcontainers per DB).

```
Component Test — Architettura
─────────────────────────────────────────────────────
         ┌──────────────────────────────────────────┐
         │           Test Runner                    │
         └──────────────┬───────────────────────────┘
                        │ HTTP request / gRPC call
                        ▼
         ┌──────────────────────────────────────────┐
         │         Servizio Under Test              │
         │  ┌────────────────────────────────────┐  │
         │  │  API Layer (Controller/Handler)    │  │
         │  └────────────────┬───────────────────┘  │
         │                   │                      │
         │  ┌────────────────▼───────────────────┐  │
         │  │  Business Logic                    │  │
         │  └────────────────┬───────────────────┘  │
         │                   │                      │
         │  ┌────────────────▼───────────────────┐  │
         │  │  Repository / Client Layer         │  │
         │  └──────┬─────────────────┬───────────┘  │
         └─────────│─────────────────│──────────────┘
                   │                 │
                   ▼                 ▼
          ┌─────────────┐   ┌─────────────────┐
          │ Testcontainer│   │   WireMock       │
          │ (PostgreSQL) │   │ (HTTP upstream)  │
          └─────────────┘   └─────────────────┘
```

### Contract Testing: il Confine tra Servizi

Il contract testing risolve il problema del "chi rompe chi" quando due servizi evolvono indipendentemente. Con **Pact** (consumer-driven contracts):

1. **Il Consumer** scrive un test che definisce cosa si aspetta dall'API del Provider
2. Il test genera automaticamente un **Pact file** (contratto in JSON)
3. Il Pact file viene pubblicato su un **Pact Broker**
4. **Il Provider** esegue una verifica: rispetta il contratto?

```
Flow Contract Testing con Pact
──────────────────────────────────────────────────────────────
Consumer Service                    Provider Service
     │                                     │
     │ 1. Scrive consumer test             │
     │    (definisce interazione attesa)   │
     │                                     │
     │ 2. Test genera Pact file JSON       │
     │                                     │
     │ 3. Pubblica Pact su Pact Broker     │
     │         ↓                           │
     │    ┌─────────────┐                  │
     │    │  Pact Broker│ ←──────────── 4. Provider fetcha il contratto
     │    └─────────────┘                  │
     │                                     │ 5. Provider esegue la verifica
     │                                     │    (risponde alle interazioni
     │                                     │     definite nel contratto?)
     │                                     │
     │                                  6. Risultato pubblicato su Pact Broker
     │
7. "Can I Deploy?" — il Broker verifica compatibilità
   prima di ogni deploy
```

---

## Configurazione & Pratica

### Unit Test — Java (JUnit 5 + Mockito)

```java
// OrderService.java
@Service
public class OrderService {
    private final OrderRepository orderRepository;
    private final PaymentClient paymentClient;
    private final InventoryClient inventoryClient;

    public Order createOrder(CreateOrderRequest request) {
        // Verifica disponibilità inventario
        if (!inventoryClient.isAvailable(request.getProductId(), request.getQuantity())) {
            throw new InsufficientStockException(request.getProductId());
        }

        Order order = Order.create(request);
        Order saved = orderRepository.save(order);

        // Inizializza il pagamento
        paymentClient.initiate(new PaymentRequest(saved.getId(), saved.getTotalAmount()));
        return saved;
    }
}
```

```java
// OrderServiceTest.java
@ExtendWith(MockitoExtension.class)
class OrderServiceTest {

    @Mock
    private OrderRepository orderRepository;

    @Mock
    private PaymentClient paymentClient;

    @Mock
    private InventoryClient inventoryClient;

    @InjectMocks
    private OrderService orderService;

    @Test
    void createOrder_whenStockAvailable_shouldSaveAndInitiatePayment() {
        // Arrange
        var request = new CreateOrderRequest("product-123", 2, BigDecimal.valueOf(50.00));
        var savedOrder = Order.builder().id("order-456").totalAmount(BigDecimal.valueOf(100.00)).build();

        when(inventoryClient.isAvailable("product-123", 2)).thenReturn(true);
        when(orderRepository.save(any(Order.class))).thenReturn(savedOrder);

        // Act
        Order result = orderService.createOrder(request);

        // Assert
        assertThat(result.getId()).isEqualTo("order-456");

        // Verifica che il pagamento sia stato iniziato con i parametri corretti
        verify(paymentClient).initiate(argThat(req ->
            req.getOrderId().equals("order-456") &&
            req.getAmount().compareTo(BigDecimal.valueOf(100.00)) == 0
        ));
    }

    @Test
    void createOrder_whenInsufficientStock_shouldThrowAndNotSave() {
        // Arrange
        var request = new CreateOrderRequest("product-123", 100, BigDecimal.valueOf(50.00));
        when(inventoryClient.isAvailable("product-123", 100)).thenReturn(false);

        // Act & Assert
        assertThatThrownBy(() -> orderService.createOrder(request))
            .isInstanceOf(InsufficientStockException.class);

        // Verifica che il repository NON sia stato chiamato
        verifyNoInteractions(orderRepository, paymentClient);
    }
}
```

### Integration Test — Testcontainers (Java)

Testcontainers avvia container Docker reali durante i test — nessun mock per le dipendenze infrastrutturali.

```xml
<!-- pom.xml -->
<dependency>
    <groupId>org.testcontainers</groupId>
    <artifactId>junit-jupiter</artifactId>
    <version>1.19.7</version>
    <scope>test</scope>
</dependency>
<dependency>
    <groupId>org.testcontainers</groupId>
    <artifactId>postgresql</artifactId>
    <version>1.19.7</version>
    <scope>test</scope>
</dependency>
<dependency>
    <groupId>org.testcontainers</groupId>
    <artifactId>kafka</artifactId>
    <version>1.19.7</version>
    <scope>test</scope>
</dependency>
```

```java
// OrderIntegrationTest.java
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@Testcontainers
@ActiveProfiles("test")
class OrderIntegrationTest {

    // Il container viene condiviso tra tutti i test della classe (performance)
    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16-alpine")
        .withDatabaseName("orders_test")
        .withUsername("test")
        .withPassword("test");

    @Container
    static KafkaContainer kafka = new KafkaContainer(DockerImageName.parse("confluentinc/cp-kafka:7.6.0"));

    // Configura Spring per usare i container dinamici
    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", postgres::getJdbcUrl);
        registry.add("spring.datasource.username", postgres::getUsername);
        registry.add("spring.datasource.password", postgres::getPassword);
        registry.add("spring.kafka.bootstrap-servers", kafka::getBootstrapServers);
    }

    @Autowired
    private TestRestTemplate restTemplate;

    @Autowired
    private OrderRepository orderRepository;

    @BeforeEach
    void setUp() {
        orderRepository.deleteAll(); // stato pulito per ogni test
    }

    @Test
    void createOrder_shouldPersistToDatabase() {
        var request = new CreateOrderRequest("product-123", 2, BigDecimal.valueOf(50.00));

        ResponseEntity<Order> response = restTemplate.postForEntity(
            "/api/orders",
            request,
            Order.class
        );

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        assertThat(response.getBody()).isNotNull();
        assertThat(orderRepository.findById(response.getBody().getId())).isPresent();
    }
}
```

### Component Test con WireMock (Java)

```java
// OrderComponentTest.java — testa il servizio completo con dipendenze HTTP simulate
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@Testcontainers
class OrderComponentTest {

    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16-alpine");

    // WireMock simula i servizi upstream (Inventory e Payment)
    @RegisterExtension
    static WireMockExtension wireMock = WireMockExtension.newInstance()
        .options(wireMockConfig().dynamicPort())
        .build();

    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", postgres::getJdbcUrl);
        registry.add("spring.datasource.username", postgres::getUsername);
        registry.add("spring.datasource.password", postgres::getPassword);
        registry.add("app.inventory-service.url", wireMock::baseUrl);
        registry.add("app.payment-service.url", wireMock::baseUrl);
    }

    @Autowired
    private TestRestTemplate restTemplate;

    @Test
    void createOrder_whenInventoryAndPaymentOk_shouldReturn201() {
        // Simula risposta dell'inventory service
        wireMock.stubFor(get(urlPathMatching("/inventory/product-123"))
            .willReturn(aResponse()
                .withStatus(200)
                .withHeader("Content-Type", "application/json")
                .withBody("""
                    {"productId": "product-123", "available": true, "quantity": 100}
                    """)));

        // Simula risposta del payment service
        wireMock.stubFor(post(urlPathEqualTo("/payments"))
            .willReturn(aResponse()
                .withStatus(201)
                .withHeader("Content-Type", "application/json")
                .withBody("""
                    {"paymentId": "pay-789", "status": "INITIATED"}
                    """)));

        var request = new CreateOrderRequest("product-123", 2, BigDecimal.valueOf(50.00));
        ResponseEntity<Order> response = restTemplate.postForEntity("/api/orders", request, Order.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.CREATED);

        // Verifica che il payment service sia stato chiamato
        wireMock.verify(1, postRequestedFor(urlPathEqualTo("/payments")));
    }

    @Test
    void createOrder_whenInventoryUnavailable_shouldReturn409() {
        wireMock.stubFor(get(urlPathMatching("/inventory/.*"))
            .willReturn(aResponse()
                .withStatus(200)
                .withBody("""{"available": false}""")));

        var request = new CreateOrderRequest("product-123", 100, BigDecimal.valueOf(50.00));
        ResponseEntity<ErrorResponse> response = restTemplate.postForEntity(
            "/api/orders", request, ErrorResponse.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.CONFLICT);

        // Verifica che il payment service NON sia stato chiamato
        wireMock.verify(0, postRequestedFor(urlPathEqualTo("/payments")));
    }
}
```

### Contract Testing — Pact (Java, Consumer side)

```xml
<!-- Consumer: OrderService che chiama PaymentService -->
<dependency>
    <groupId>au.com.dius.pact.consumer</groupId>
    <artifactId>junit5</artifactId>
    <version>4.6.12</version>
    <scope>test</scope>
</dependency>
```

```java
// PaymentServiceContractTest.java — sul lato Consumer
@ExtendWith(PactConsumerTestExt.class)
@PactTestFor(providerName = "payment-service", port = "8090")
class PaymentServiceContractTest {

    // Definisce il contratto: cosa si aspetta il consumer
    @Pact(consumer = "order-service")
    RequestResponsePact initiatePayment(PactDslWithProvider builder) {
        return builder
            .given("payment service is up")
            .uponReceiving("a request to initiate payment")
                .path("/payments")
                .method("POST")
                .headers(Map.of("Content-Type", "application/json"))
                .body(new PactDslJsonBody()
                    .stringValue("orderId", "order-456")
                    .decimalType("amount", 100.00))
            .willRespondWith()
                .status(201)
                .headers(Map.of("Content-Type", "application/json"))
                .body(new PactDslJsonBody()
                    .stringType("paymentId")        // tipo stringa, valore qualunque
                    .stringMatcher("status", "INITIATED|PENDING", "INITIATED"))
            .toPact();
    }

    @Test
    @PactTestFor(pactMethod = "initiatePayment")
    void testInitiatePayment_shouldReturnPaymentId(MockServer mockServer) {
        // Il client reale viene puntato sul MockServer di Pact
        var client = new PaymentClient(mockServer.getUrl());

        var result = client.initiate(new PaymentRequest("order-456", BigDecimal.valueOf(100.00)));

        assertThat(result.getPaymentId()).isNotBlank();
        assertThat(result.getStatus()).isEqualTo("INITIATED");
        // Il Pact file viene generato in target/pacts/
    }
}
```

```java
// PaymentServiceProviderVerificationTest.java — sul lato Provider
@Provider("payment-service")
@PactBroker(url = "${pact.broker.url}", authentication = @PactBrokerAuth(token = "${pact.broker.token}"))
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class PaymentServiceProviderVerificationTest {

    @LocalServerPort
    int port;

    @BeforeEach
    void setUp(PactVerificationContext context) {
        context.setTarget(new HttpTestTarget("localhost", port));
    }

    @TestTemplate
    @ExtendWith(PactVerificationInvocationContextProvider.class)
    void pactVerificationTestTemplate(PactVerificationContext context) {
        context.verifyInteraction();
    }

    // Stato provider: prepara il DB per la condizione "payment service is up"
    @State("payment service is up")
    void paymentServiceIsUp() {
        // Setup minimo — il service è già avviato
    }
}
```

### Unit Test — Python (pytest)

```python
# order_service.py
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

class InventoryClient(Protocol):
    def is_available(self, product_id: str, quantity: int) -> bool: ...

class PaymentClient(Protocol):
    def initiate(self, order_id: str, amount: Decimal) -> dict: ...

class OrderRepository(Protocol):
    def save(self, order: dict) -> dict: ...

class OrderService:
    def __init__(self, inventory: InventoryClient, payment: PaymentClient, repo: OrderRepository):
        self._inventory = inventory
        self._payment = payment
        self._repo = repo

    def create_order(self, product_id: str, quantity: int, unit_price: Decimal) -> dict:
        if not self._inventory.is_available(product_id, quantity):
            raise ValueError(f"Insufficient stock for {product_id}")

        order = {"product_id": product_id, "quantity": quantity,
                 "total": unit_price * quantity, "status": "PENDING"}
        saved = self._repo.save(order)
        self._payment.initiate(saved["id"], saved["total"])
        return saved
```

```python
# test_order_service.py
from decimal import Decimal
from unittest.mock import MagicMock, call
import pytest
from order_service import OrderService

@pytest.fixture
def inventory_mock():
    return MagicMock()

@pytest.fixture
def payment_mock():
    return MagicMock()

@pytest.fixture
def repo_mock():
    return MagicMock()

@pytest.fixture
def service(inventory_mock, payment_mock, repo_mock):
    return OrderService(inventory_mock, payment_mock, repo_mock)

def test_create_order_when_stock_available(service, inventory_mock, payment_mock, repo_mock):
    inventory_mock.is_available.return_value = True
    repo_mock.save.return_value = {"id": "order-456", "total": Decimal("100.00")}

    result = service.create_order("product-123", 2, Decimal("50.00"))

    assert result["id"] == "order-456"
    # Verifica che il pagamento sia stato iniziato con i valori corretti
    payment_mock.initiate.assert_called_once_with("order-456", Decimal("100.00"))

def test_create_order_when_insufficient_stock(service, inventory_mock, repo_mock, payment_mock):
    inventory_mock.is_available.return_value = False

    with pytest.raises(ValueError, match="Insufficient stock"):
        service.create_order("product-123", 100, Decimal("50.00"))

    repo_mock.save.assert_not_called()
    payment_mock.initiate.assert_not_called()
```

### Integration Test con Testcontainers — Python

```python
# test_order_repository.py
import pytest
import psycopg2
from testcontainers.postgres import PostgresContainer

# Fixture di scope "session" → il container viene avviato una volta per tutti i test
@pytest.fixture(scope="session")
def postgres_container():
    with PostgresContainer("postgres:16-alpine") as postgres:
        yield postgres

@pytest.fixture
def db_connection(postgres_container):
    conn = psycopg2.connect(postgres_container.get_connection_url())
    conn.autocommit = False  # usa transazioni per l'isolation
    yield conn
    conn.rollback()  # rollback dopo ogni test → stato pulito
    conn.close()

@pytest.fixture(autouse=True, scope="session")
def create_schema(postgres_container):
    conn = psycopg2.connect(postgres_container.get_connection_url())
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                product_id VARCHAR(100) NOT NULL,
                quantity INTEGER NOT NULL,
                total DECIMAL(10,2) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
    conn.commit()
    conn.close()

def test_save_order_persists_to_database(db_connection):
    from order_repository import PostgresOrderRepository
    repo = PostgresOrderRepository(db_connection)

    order = {"product_id": "product-123", "quantity": 2, "total": "100.00", "status": "PENDING"}
    saved = repo.save(order)

    assert saved["id"] is not None

    # Verifica che il dato sia nel DB
    with db_connection.cursor() as cur:
        cur.execute("SELECT * FROM orders WHERE id = %s", (saved["id"],))
        row = cur.fetchone()

    assert row is not None
    assert row[1] == "product-123"  # product_id
```

### Unit Test — Go

```go
// order_service_test.go
package order_test

import (
    "context"
    "errors"
    "testing"

    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/mock"
    "github.com/myapp/order"
)

// Mock generato automaticamente con mockery o scritto a mano
type MockInventoryClient struct {
    mock.Mock
}

func (m *MockInventoryClient) IsAvailable(ctx context.Context, productID string, quantity int) (bool, error) {
    args := m.Called(ctx, productID, quantity)
    return args.Bool(0), args.Error(1)
}

type MockPaymentClient struct {
    mock.Mock
}

func (m *MockPaymentClient) Initiate(ctx context.Context, orderID string, amount float64) error {
    args := m.Called(ctx, orderID, amount)
    return args.Error(0)
}

func TestCreateOrder_WhenStockAvailable_ShouldInitiatePayment(t *testing.T) {
    inventory := new(MockInventoryClient)
    payment := new(MockPaymentClient)
    repo := order.NewInMemoryRepository() // fake in-memory

    svc := order.NewService(inventory, payment, repo)

    inventory.On("IsAvailable", mock.Anything, "product-123", 2).Return(true, nil)
    payment.On("Initiate", mock.Anything, mock.AnythingOfType("string"), 100.0).Return(nil)

    result, err := svc.CreateOrder(context.Background(), order.CreateRequest{
        ProductID: "product-123",
        Quantity:  2,
        UnitPrice: 50.0,
    })

    assert.NoError(t, err)
    assert.NotEmpty(t, result.ID)
    payment.AssertCalled(t, "Initiate", mock.Anything, result.ID, 100.0)
    inventory.AssertExpectations(t)
    payment.AssertExpectations(t)
}

func TestCreateOrder_WhenInsufficientStock_ShouldReturnError(t *testing.T) {
    inventory := new(MockInventoryClient)
    payment := new(MockPaymentClient)
    repo := order.NewInMemoryRepository()

    svc := order.NewService(inventory, payment, repo)
    inventory.On("IsAvailable", mock.Anything, "product-123", 100).Return(false, nil)

    _, err := svc.CreateOrder(context.Background(), order.CreateRequest{
        ProductID: "product-123",
        Quantity:  100,
        UnitPrice: 50.0,
    })

    assert.ErrorIs(t, err, order.ErrInsufficientStock)
    payment.AssertNotCalled(t, "Initiate", mock.Anything, mock.Anything, mock.Anything)
}
```

---

## Best Practices

### Struttura dei Test — AAA (Arrange, Act, Assert)

!!! tip "Pattern AAA"
    Ogni test deve avere tre sezioni chiaramente separate: **Arrange** (prepara lo stato), **Act** (esegui il comportamento), **Assert** (verifica il risultato). Un test che non si adatta a questo pattern è probabilmente troppo complesso e dovrebbe essere suddiviso.

```java
@Test
void shouldCalculateTotalWithDiscount() {
    // Arrange
    var cart = Cart.builder()
        .item("product-1", 3, BigDecimal.valueOf(10.00))
        .item("product-2", 1, BigDecimal.valueOf(5.00))
        .discountCode("SAVE10")
        .build();

    // Act
    BigDecimal total = pricingService.calculateTotal(cart);

    // Assert
    assertThat(total).isEqualByComparingTo(BigDecimal.valueOf(31.50)); // (35 - 10%)
}
```

### Checklist Qualità dei Test

```
Test Checklist per ogni servizio:
  □ Unit test per ogni caso di business logic (happy path + edge cases + error cases)
  □ Integration test con DB reale (Testcontainers) per ogni query critica
  □ Component test per ogni endpoint API principale
  □ Contract test per ogni dipendenza HTTP esterna
  □ Test delle condizioni di errore: cosa succede quando le dipendenze falliscono?
  □ Test dell'idempotency: chiamate duplicate producono lo stesso risultato?
  □ Coverage minima del 70% su business logic (non su plumbing/configuration)
```

### Test dei Percorsi di Errore

!!! warning "Testare solo il happy path è insufficiente"
    In un sistema distribuito, i percorsi di errore (timeout, servizio down, risposta malformata) si verificano in produzione. Se non sono testati, vengono scoperti in produzione. Ogni chiamata esterna deve avere almeno un test per il comportamento di failure.

```java
@Test
void createOrder_whenPaymentServiceTimesOut_shouldReturnAcceptedAndQueue() {
    wireMock.stubFor(post(urlPathEqualTo("/payments"))
        .willReturn(aResponse()
            .withFixedDelay(5000)  // simula timeout di 5 secondi
            .withStatus(200)));

    var request = new CreateOrderRequest("product-123", 1, BigDecimal.valueOf(10.00));
    ResponseEntity<Order> response = restTemplate.postForEntity("/api/orders", request, Order.class);

    // Il servizio dovrebbe accettare l'ordine e accodarlo per retry
    assertThat(response.getStatusCode()).isEqualTo(HttpStatus.ACCEPTED);
    assertThat(response.getBody().getStatus()).isEqualTo("PAYMENT_PENDING");
}

@Test
void createOrder_whenPaymentServiceReturns500_shouldReturnServiceUnavailable() {
    wireMock.stubFor(post(urlPathEqualTo("/payments"))
        .willReturn(aResponse().withStatus(500)));

    var request = new CreateOrderRequest("product-123", 1, BigDecimal.valueOf(10.00));
    ResponseEntity<ErrorResponse> response = restTemplate.postForEntity(
        "/api/orders", request, ErrorResponse.class);

    assertThat(response.getStatusCode()).isEqualTo(HttpStatus.SERVICE_UNAVAILABLE);
}
```

---

## Troubleshooting

### Problema: I test di integrazione sono troppo lenti (>30 secondi per test)

**Sintomo:** La suite di test di integrazione impiega 10-20 minuti. I developer smettono di eseguirla localmente.

**Causa:** Un nuovo container Testcontainers viene avviato per ogni test invece di essere condiviso.

**Soluzione:**
```java
// ❌ Sbagliato: container ricreato per ogni test
@SpringBootTest
@Testcontainers
class SlowTest {
    @Container
    PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16"); // istanza, non static
}

// ✅ Corretto: container condiviso a livello di classe (con @Container static)
// Oppure usare un singleton pattern via Spring ApplicationContext
@SpringBootTest
@Testcontainers
class FastTest {
    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16");

    // Il container viene avviato una volta per tutti i test della classe
    // e la JVM lo riutilizza tra le classi di test se si usa Testcontainers Ryuk
}
```

```bash
# Verifica che Testcontainers Reuse sia abilitato in ~/.testcontainers.properties
testcontainers.reuse.enable=true
```

---

### Problema: I contract test falliscono sul provider ma non sul consumer

**Sintomo:** Il consumer test passa, il Pact file viene generato, ma la provider verification fallisce con `Interaction not matched`.

**Causa comune 1:** Lo stato provider (`@State`) non prepara correttamente i dati necessari. Il provider risponde con 404 o dati diversi da quelli attesi nel contratto.

**Causa comune 2:** Il contratto usa matchers troppo rigidi (valore esatto invece di tipo).

**Diagnosi:**
```bash
# Sul provider, abilita il logging dettagliato della verifica Pact
# application-test.properties
logging.level.au.com.dius.pact=DEBUG

# Cerca nella console i dettagli dell'interazione fallita:
# "Interaction: 'a request to initiate payment'"
# "Request: POST /payments ..."
# "Response: 404 Not Found"
# → il @State non ha inizializzato lo stato corretto
```

**Soluzione:**
```java
// Assicurati che lo @State prepari il database con i dati necessari
@State("order order-456 exists")
void orderExists() {
    orderRepository.save(Order.builder()
        .id("order-456")
        .status("PENDING")
        .totalAmount(BigDecimal.valueOf(100.00))
        .build());
}
```

---

### Problema: I mock rendono i test fragili al refactoring

**Sintomo:** Ogni refactoring interno (rinomina metodo, cambia struttura) rompe decine di test anche quando il comportamento esterno non è cambiato.

**Causa:** I test verificano i dettagli implementativi (quali metodi interni vengono chiamati) invece del comportamento osservabile (input/output del servizio).

**Soluzione:**
```java
// ❌ Fragile: verifica dettagli interni
@Test
void shouldProcessOrder() {
    orderService.process(order);
    // Questo test si rompe se rinomino validateOrder() in checkOrderValidity()
    verify(validator).validateOrder(order);
    verify(enricher).enrichWithPricing(order);
    verify(persister).persistOrder(order);
}

// ✅ Robusto: verifica il comportamento osservabile
@Test
void shouldProcessOrder_andPersistResult() {
    Order result = orderService.process(order);

    // Verifica solo l'output e gli effetti collaterali osservabili
    assertThat(result.getStatus()).isEqualTo(OrderStatus.PROCESSED);
    assertThat(orderRepository.findById(result.getId())).isPresent();
    // Non verifica come internamente il servizio raggiunge questo risultato
}
```

---

### Problema: Testcontainers fallisce in CI con "Cannot connect to Docker daemon"

**Sintomo:** I test passano localmente ma falliscono in CI con `Could not find a valid Docker environment`.

**Causa:** L'agente CI non ha accesso al Docker daemon, o usa un Docker-in-Docker non configurato correttamente.

**Soluzione per GitHub Actions:**
```yaml
# .github/workflows/test.yml
jobs:
  test:
    runs-on: ubuntu-latest  # ← ha Docker preinstallato

    steps:
      - uses: actions/checkout@v4

      - name: Set up JDK 21
        uses: actions/setup-java@v4
        with:
          java-version: '21'
          distribution: 'temurin'

      # Non serve setup Docker aggiuntivo su ubuntu-latest
      - name: Run tests
        run: ./mvnw test
        env:
          # Forza Testcontainers a usare il Docker socket standard
          DOCKER_HOST: unix:///var/run/docker.sock
          TESTCONTAINERS_RYUK_DISABLED: false  # mantieni Ryuk per cleanup automatico
```

```yaml
# Per GitLab CI con Docker-in-Docker
test:
  image: maven:3.9-eclipse-temurin-21
  services:
    - docker:dind
  variables:
    DOCKER_HOST: tcp://docker:2376
    DOCKER_TLS_CERTDIR: "/certs"
    TESTCONTAINERS_HOST_OVERRIDE: docker
  script:
    - mvn test
```

---

## Relazioni

??? info "Dev / Resilienza — Testare i pattern di resilienza"
    I pattern di resilienza (circuit breaker, retry, timeout) devono essere testati a livello di component test con WireMock. WireMock supporta scenari di fault injection: `withFixedDelay`, `withFault(Fault.CONNECTION_RESET_BY_PEER)`, `withStatus(503)`. → [Resilienza](../resilienza/_index.md)

??? info "Dev / API Design — Contract testing e versionamento"
    Il contract testing con Pact è strettamente correlato alla gestione del versionamento delle API. Un contratto Pact è di fatto un test di regressione automatizzato per la compatibilità backward dell'API. → [API Design](../api/_index.md)

??? info "Dev / Integrazioni — Testing di Saga e sistemi event-driven"
    Testare Saga e sistemi event-driven richiede embedded broker (Kafka EmbeddedKafka, RabbitMQ via Testcontainers) e asserzioni asincrone (Awaitility). → [Integrazioni](../integrazioni/_index.md)

??? info "CI/CD / Testing — Quality gates nella pipeline"
    La strategia di test descritta qui deve essere integrata nella pipeline CI/CD con quality gates: coverage threshold, contract verification automatica prima del deploy, smoke test post-deploy. → [Testing CI/CD](../../ci-cd/testing/_index.md)

??? info "Monitoring — Osservabilità durante i test"
    I component test con ambienti reali possono esporre metriche Prometheus. Verificare che i test non producano alert o metriche anomale è parte della contract verification di un servizio. → [Monitoring](../../monitoring/_index.md)

---

## Riferimenti

- [Testcontainers](https://testcontainers.com/) — Docker-based testing per qualsiasi dipendenza
- [Pact Documentation](https://docs.pact.io/) — Framework di riferimento per contract testing
- [Pact Broker](https://docs.pact.io/pact_broker) — Registry centralizzato per i contratti Pact
- [WireMock](https://wiremock.org/docs/) — HTTP mock server per Java e altri linguaggi
- [Martin Fowler: TestDouble](https://martinfowler.com/bliki/TestDouble.html) — Definizione autorevole dei tipi di test double
- [Martin Fowler: Test Pyramid](https://martinfowler.com/bliki/TestPyramid.html) — Il modello fondamentale
- [Mockito Documentation](https://javadoc.io/doc/org.mockito/mockito-core/latest/index.html) — Mock framework Java
- [pytest-mock](https://pytest-mock.readthedocs.io/) — Integrazione Mockito-style per pytest
- [testify/mock (Go)](https://pkg.go.dev/github.com/stretchr/testify/mock) — Mock framework per Go
- [Google Testing Blog](https://testing.googleblog.com/) — Best practice da Google Engineering
