---
title: "Integrazioni"
slug: integrazioni
category: dev
tags: [integrazioni, microservizi, comunicazione, sincrona, asincrona, saga, cqrs, event-sourcing, kafka, rabbitmq, rest, grpc]
search_keywords: [integrazioni, integrazione microservizi, microservices integration, comunicazione sincrona, comunicazione asincrona, synchronous communication, asynchronous communication, saga pattern, saga choreography, saga orchestration, cqrs, command query responsibility segregation, event sourcing, event-driven, event driven architecture, eda, domain events, kafka integration, rabbitmq integration, outbox pattern, transactional outbox, distributed transaction, transazione distribuita, two phase commit, 2pc, eventual consistency, consistenza eventuale, service integration, inter-service communication, http client, rest client, grpc client, message broker, dead letter queue, dlq, idempotency, idempotenza, exactly once, at least once, at most once, event store, aggregate, bounded context, choreography, orchestration, compensating transaction, transazione compensatoria, nats, grpc streaming, service bus, cloud events]
parent: dev/_index
related: [dev/api/_index, dev/resilienza/_index, messaging/_index, messaging/kafka/_index, messaging/rabbitmq/_index, messaging/kafka/pattern-microservizi/saga-pattern, messaging/kafka/pattern-microservizi/cqrs, messaging/kafka/pattern-microservizi/event-driven-architecture]
official_docs: https://microservices.io/patterns/index.html
status: complete
difficulty: intermediate
last_updated: 2026-03-28
---

# Integrazioni

## Panoramica

L'integrazione tra microservizi è il problema centrale dell'architettura distribuita: ogni servizio è autonomo, ma deve collaborare con altri per realizzare funzionalità di business. Come si comunicano? Chi aspetta chi? Cosa succede se un servizio è temporaneamente irraggiungibile?

Esistono due paradigmi fondamentali, con trade-off opposti:

- **Comunicazione sincrona (request/response)** — il chiamante aspetta la risposta prima di proseguire. Semplice da ragionare, ma crea **coupling temporale**: se il downstream è giù, l'upstream è bloccato.
- **Comunicazione asincrona (event-driven / message-based)** — il chiamante pubblica un messaggio o un evento e prosegue. Disaccoppiamento temporale massimo, ma aumenta la complessità di stato, debug, e gestione delle failure.

La scelta non è binaria: la maggior parte dei sistemi usa entrambi i paradigmi, con la sincrona per query e operazioni a bassa latenza, e l'asincrona per workflow complessi e operazioni distribuite.

!!! tip "Regola pratica: domanda guida"
    Chiediti: *"Il chiamante ha bisogno del risultato subito per continuare?"* Se sì → sincrona. Se no, o se l'operazione coinvolge più servizi in sequenza → valuta l'asincrona.

---

## Concetti Chiave

### Coupling Temporale

Il coupling temporale è il principale problema della comunicazione sincrona in cascata. Se il servizio A chiama B che chiama C, tutti e tre devono essere disponibili contemporaneamente per completare l'operazione.

```
Sincrona a cascata (problema):
  Client → OrderService → PaymentService → InventoryService → NotificationService

  Se NotificationService è down → InventoryService blocca → PaymentService blocca
  → OrderService ritorna errore al client

Asincrona (soluzione):
  Client → OrderService → [pubblica OrderPlaced event]
                                  ↓
                     PaymentService (consuma, pubblica PaymentProcessed)
                                  ↓
                     InventoryService (consuma, pubblica StockReserved)
                                  ↓
                     NotificationService (consuma, invia email)

  Se NotificationService è down → consumerà l'evento quando torna su
  → OrderService risponde al client immediatamente con 202 Accepted
```

### Garanzie di Consegna

Ogni sistema di messaggistica offre garanzie diverse sulla consegna dei messaggi:

| Garanzia | Significato | Implicazione |
|---|---|---|
| **At most once** | Consegnato 0 o 1 volte | Possibile perdita di messaggi. Accettabile per log, metriche. |
| **At least once** | Consegnato 1 o più volte | Possibili duplicati. Il consumatore deve essere **idempotente**. |
| **Exactly once** | Consegnato esattamente 1 volta | Garantito solo da Kafka con transazioni. Overhead significativo. |

!!! warning "Il default è at-least-once"
    La maggior parte dei message broker (Kafka, RabbitMQ) garantisce at-least-once per default. Ogni consumer deve essere progettato per gestire messaggi duplicati usando una **chiave di idempotency** (es. `orderId`, `eventId`).

### Idempotency

Un consumer è idempotente se elaborare lo stesso messaggio più volte produce lo stesso effetto di elaborarlo una volta sola.

```python
# Non idempotente — doppia elaborazione → doppio addebito
def process_payment(event: dict):
    charge_customer(event["amount"])  # ❌ se eseguito due volte, addebita due volte

# Idempotente — doppia elaborazione sicura
def process_payment(event: dict):
    payment_id = event["paymentId"]
    if db.exists(f"processed_payment:{payment_id}"):
        return  # già elaborato — skip silenzioso
    charge_customer(event["amount"])
    db.set(f"processed_payment:{payment_id}", True, ttl=86400)  # 24h deduplication window
```

### Transazioni Distribuite e Eventual Consistency

In un sistema con database separati per servizio, **non esiste una transazione ACID distribuita** praticabile a larga scala. Le opzioni sono:

1. **Two-Phase Commit (2PC)** — coordinatore distribuito. Teoricamente corretto, ma lento, fragile e difficilmente scalabile. Evitare in produzione.
2. **Saga Pattern** — serie di transazioni locali compensabili. La soluzione raccomandata.
3. **Eventual Consistency** — accettare che i dati siano temporaneamente inconsistenti tra servizi, ma convergeranno allo stato corretto.

---

## Architettura / Come Funziona

### Comunicazione Sincrona: HTTP e gRPC

La comunicazione sincrona usa protocolli request/response. Il client conosce l'indirizzo del server (via Service Discovery o DNS in Kubernetes) e aspetta la risposta.

```
Flusso sincrono tipico in Kubernetes:

  OrderService Pod
       │
       │  HTTP POST /payments  (via Kubernetes Service DNS)
       │  payment-service.production.svc.cluster.local:8080
       ▼
  PaymentService Pod
       │
       │  risposta: 200 OK + PaymentResult
       ▼
  OrderService Pod  ← continua l'elaborazione
```

**Quando usare la comunicazione sincrona:**
- Query che richiedono risposta immediata (GET di una risorsa)
- Validazione in tempo reale (stock check prima di confermare l'ordine)
- Operazioni semplici a 2 servizi con SLA stringenti

**Pattern di service discovery in Kubernetes:**

```yaml
# Kubernetes Service — DNS automatico nel cluster
# Format: <service-name>.<namespace>.svc.cluster.local
# Esempio accesso cross-namespace:
# http://payment-service.payments.svc.cluster.local:8080

apiVersion: v1
kind: Service
metadata:
  name: payment-service
  namespace: payments
spec:
  selector:
    app: payment-service
  ports:
    - port: 8080
      targetPort: 8080
  type: ClusterIP
```

### Comunicazione Asincrona: Event-Driven Architecture

In un'architettura event-driven i servizi comunicano pubblicando **eventi di dominio** su un message broker (Kafka, RabbitMQ). I consumer sono disaccoppiati dai producer: non si conoscono direttamente.

```
Event-Driven con Kafka:

  OrderService                 Kafka                PaymentService
      │                    ┌──────────┐                   │
      │── OrderPlaced ──▶  │  Topic:  │ ──▶ consume ──── │
      │                    │  order.  │                   │── processa
      │                    │  events  │                   │
      │                    └──────────┘                   │── PaymentProcessed ──▶
      │                                                   │
      │                    ┌──────────┐
      │                    │  Topic:  │
      │◀── consume ────── │ payment. │
      │                    │  events  │
      │── aggiorna stato   └──────────┘
```

### Saga Pattern

Il Saga Pattern gestisce transazioni distribuite attraverso una sequenza di transazioni locali. Se una fallisce, vengono eseguite **transazioni compensatorie** per annullare gli effetti delle precedenti.

```
Saga Choreography (event-driven, nessun coordinatore centrale):

  OrderService         PaymentService        InventoryService
       │                     │                      │
       │── OrderPlaced ──▶   │                      │
       │                     │── PaymentProcessed ──▶│
       │                     │                      │── StockReserved ──▶ OrderService
       │                     │                      │
       │ (FAILURE SCENARIO)  │                      │
       │◀── PaymentFailed ───│                      │
       │── CancelOrder       │                      │
       │── OrderCancelled ──▶│── RefundPayment       │
                             │── PaymentRefunded ──▶│── ReleaseStock
```

```
Saga Orchestration (coordinatore centrale, più controllato):

  SagaOrchestrator
       │── cmd: ProcessPayment ──▶ PaymentService
       │◀── reply: PaymentProcessed
       │
       │── cmd: ReserveStock ──────▶ InventoryService
       │◀── reply: StockReserved
       │
       │── cmd: ConfirmOrder ──────▶ OrderService
       │◀── reply: OrderConfirmed
       │
       │  [FAILURE: StockReserved fails]
       │── cmd: CancelPayment ──────▶ PaymentService (compensating)
       │── cmd: CancelOrder ────────▶ OrderService (compensating)
```

### CQRS — Command Query Responsibility Segregation

CQRS separa le operazioni di **scrittura (Command)** dalle operazioni di **lettura (Query)** usando modelli dati distinti, ottimizzati per il loro scopo.

```
CQRS con Event Sourcing:

  Write Side (Command)              Read Side (Query)
  ────────────────────              ─────────────────
  HTTP POST /orders                 HTTP GET /orders/{id}
       │                                  │
       ▼                                  ▼
  Command Handler                   Query Handler
       │                                  │
       ▼                                  ▼
  Domain Aggregate               Read Model (DB ottimizzato)
  (valida, applica)              (denormalizzato per query)
       │                                  ▲
       ▼                                  │
  Event Store ──── events ──────────▶ Projection
  (append-only)                    (aggiorna read model
                                    ogni volta che arriva
                                    un nuovo evento)
```

---

## Configurazione & Pratica

### HTTP Client Sincrono — Java (Spring Boot)

```java
// OrderServiceClient.java — client HTTP sincrono con resilienza
@Component
public class PaymentServiceClient {

    private final WebClient webClient;

    public PaymentServiceClient(WebClient.Builder builder) {
        this.webClient = builder
            .baseUrl("http://payment-service.payments.svc.cluster.local:8080")
            .defaultHeader(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
            .build();
    }

    @CircuitBreaker(name = "paymentService", fallbackMethod = "paymentFallback")
    @Retry(name = "paymentService")
    @TimeLimiter(name = "paymentService")
    public CompletableFuture<PaymentResponse> processPayment(PaymentRequest request) {
        return webClient.post()
            .uri("/api/v1/payments")
            .header("Idempotency-Key", request.getIdempotencyKey())  // idempotency per retry sicuri
            .bodyValue(request)
            .retrieve()
            .onStatus(HttpStatus::is4xxClientError, resp ->
                resp.bodyToMono(ErrorResponse.class)
                    .flatMap(err -> Mono.error(new BusinessException(err.getCode()))))
            .bodyToMono(PaymentResponse.class)
            .toFuture();
    }

    public CompletableFuture<PaymentResponse> paymentFallback(
            PaymentRequest request, Throwable ex) {
        log.warn("PaymentService unavailable for orderId={}: {}", request.getOrderId(), ex.getMessage());
        // Accoda per processing asincrono
        paymentQueue.enqueue(request);
        return CompletableFuture.completedFuture(
            PaymentResponse.queued(request.getOrderId()));
    }
}
```

```yaml
# application.yml — configurazione resilienza per il client
resilience4j:
  circuitbreaker:
    instances:
      paymentService:
        failure-rate-threshold: 50
        minimum-number-of-calls: 5
        wait-duration-in-open-state: 20s
        sliding-window-size: 10
  retry:
    instances:
      paymentService:
        max-attempts: 3
        wait-duration: 300ms
        enable-exponential-backoff: true
        exponential-backoff-multiplier: 2
        retry-exceptions:
          - java.net.SocketTimeoutException
          - org.springframework.web.reactive.function.client.WebClientRequestException
        ignore-exceptions:
          - com.example.exceptions.BusinessException
  timelimiter:
    instances:
      paymentService:
        timeout-duration: 5s
```

### HTTP Client Sincrono — Go

```go
// integration/payment_client.go
package integration

import (
    "bytes"
    "context"
    "encoding/json"
    "fmt"
    "net/http"
    "time"
)

type PaymentClient struct {
    baseURL    string
    httpClient *http.Client
}

func NewPaymentClient(baseURL string) *PaymentClient {
    return &PaymentClient{
        baseURL: baseURL,
        httpClient: &http.Client{
            Timeout: 10 * time.Second,
            Transport: &http.Transport{
                MaxIdleConns:        100,
                MaxIdleConnsPerHost: 20,
                IdleConnTimeout:     90 * time.Second,
            },
        },
    }
}

func (c *PaymentClient) ProcessPayment(ctx context.Context, req PaymentRequest) (*PaymentResponse, error) {
    body, _ := json.Marshal(req)

    httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost,
        c.baseURL+"/api/v1/payments", bytes.NewReader(body))
    if err != nil {
        return nil, fmt.Errorf("building request: %w", err)
    }
    httpReq.Header.Set("Content-Type", "application/json")
    httpReq.Header.Set("Idempotency-Key", req.IdempotencyKey)

    resp, err := c.httpClient.Do(httpReq)
    if err != nil {
        return nil, fmt.Errorf("calling payment service: %w", err)
    }
    defer resp.Body.Close()

    if resp.StatusCode >= 400 {
        var errResp ErrorResponse
        json.NewDecoder(resp.Body).Decode(&errResp)
        return nil, &ServiceError{StatusCode: resp.StatusCode, Code: errResp.Code}
    }

    var result PaymentResponse
    if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
        return nil, fmt.Errorf("decoding response: %w", err)
    }
    return &result, nil
}
```

### Outbox Pattern — Garantire la Pubblicazione degli Eventi

Il problema del dual-write: non si può scrivere sul database locale E pubblicare su Kafka in modo atomico. Il Transactional Outbox Pattern risolve questo.

```java
// 1. Nella stessa transazione DB: salva l'entità E l'evento nella tabella outbox
@Transactional
public Order createOrder(CreateOrderCommand cmd) {
    Order order = Order.create(cmd.getItems(), cmd.getCustomerId());
    orderRepository.save(order);

    // Salva l'evento nella tabella outbox — stessa transazione DB
    OutboxEvent event = OutboxEvent.builder()
        .aggregateId(order.getId().toString())
        .aggregateType("Order")
        .eventType("OrderPlaced")
        .payload(objectMapper.writeValueAsString(order.toEvent()))
        .build();
    outboxRepository.save(event);  // se la transazione rollback, anche l'evento viene perso

    return order;
}

// 2. Un relay separato (Debezium CDC o polling) pubblica gli eventi outbox su Kafka
// Debezium legge i cambiamenti dalla tabella outbox via Change Data Capture
// e li pubblica automaticamente — zero codice custom per la pubblicazione
```

```sql
-- Tabella outbox standard
CREATE TABLE outbox_events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_id   VARCHAR(255) NOT NULL,
    aggregate_type VARCHAR(100) NOT NULL,
    event_type     VARCHAR(100) NOT NULL,
    payload        JSONB NOT NULL,
    created_at     TIMESTAMP WITH TIME ZONE DEFAULT now(),
    published_at   TIMESTAMP WITH TIME ZONE,
    INDEX idx_outbox_unpublished (created_at) WHERE published_at IS NULL
);
```

### Saga Orchestration — Implementazione con Spring State Machine

```java
// PlaceOrderSaga.java — saga orchestrata con Spring State Machine
@Component
public class PlaceOrderSaga {

    // Stati della saga
    public enum State {
        IDLE, PAYMENT_PENDING, STOCK_PENDING, CONFIRMED, CANCELLED
    }

    // Transizioni
    public enum Event {
        START, PAYMENT_SUCCESS, PAYMENT_FAILED, STOCK_SUCCESS, STOCK_FAILED
    }

    @Autowired
    private PaymentServiceClient paymentClient;
    @Autowired
    private InventoryServiceClient inventoryClient;
    @Autowired
    private SagaStateRepository sagaStateRepo;

    @SagaEventHandler(associationProperty = "orderId")
    public void handle(OrderPlacedEvent event) {
        // Passo 1: avvia la saga, stato iniziale → PAYMENT_PENDING
        sagaStateRepo.save(new SagaState(event.getOrderId(), State.PAYMENT_PENDING));

        paymentClient.processPayment(new ProcessPaymentCommand(
            event.getOrderId(),
            event.getAmount(),
            event.getCustomerId()
        ));
    }

    @SagaEventHandler(associationProperty = "orderId")
    public void handle(PaymentProcessedEvent event) {
        sagaStateRepo.update(event.getOrderId(), State.STOCK_PENDING);

        inventoryClient.reserveStock(new ReserveStockCommand(
            event.getOrderId(),
            event.getItems()
        ));
    }

    @SagaEventHandler(associationProperty = "orderId")
    public void handle(PaymentFailedEvent event) {
        // Transazione compensatoria
        sagaStateRepo.update(event.getOrderId(), State.CANCELLED);
        orderClient.cancelOrder(new CancelOrderCommand(event.getOrderId(), event.getReason()));
    }

    @SagaEventHandler(associationProperty = "orderId")
    public void handle(StockReservedEvent event) {
        sagaStateRepo.update(event.getOrderId(), State.CONFIRMED);
        orderClient.confirmOrder(new ConfirmOrderCommand(event.getOrderId()));
    }

    @SagaEventHandler(associationProperty = "orderId")
    public void handle(StockReservationFailedEvent event) {
        // Transazione compensatoria — rimborsa il pagamento
        sagaStateRepo.update(event.getOrderId(), State.CANCELLED);
        paymentClient.refundPayment(new RefundPaymentCommand(event.getOrderId()));
        orderClient.cancelOrder(new CancelOrderCommand(event.getOrderId(), "STOCK_UNAVAILABLE"));
    }
}
```

### CQRS — Implementazione con Kafka e PostgreSQL

```java
// Write side: Command Handler
@Service
public class OrderCommandHandler {

    @CommandHandler
    @Transactional
    public String handle(CreateOrderCommand cmd) {
        // 1. Carica o crea aggregate
        OrderAggregate order = new OrderAggregate(cmd.getOrderId());
        order.apply(new OrderCreatedEvent(cmd.getOrderId(), cmd.getItems(), cmd.getCustomerId()));

        // 2. Salva eventi nell'event store (outbox)
        eventStore.append(order.getUncommittedEvents());

        return order.getId();
    }
}

// Projection: aggiorna il read model ogni volta che arriva un evento
@Component
@KafkaListener(topics = "order-events", groupId = "order-read-model")
public class OrderProjection {

    @KafkaHandler
    public void on(OrderCreatedEvent event) {
        orderReadModelRepository.save(
            OrderReadModel.builder()
                .orderId(event.getOrderId())
                .status("CREATED")
                .customerId(event.getCustomerId())
                .items(event.getItems())
                .createdAt(Instant.now())
                .build()
        );
    }

    @KafkaHandler
    public void on(OrderStatusChangedEvent event) {
        orderReadModelRepository.updateStatus(event.getOrderId(), event.getNewStatus());
    }
}

// Read side: Query Handler usa il read model ottimizzato
@RestController
@RequestMapping("/api/v1/orders")
public class OrderQueryController {

    @GetMapping("/{orderId}")
    public OrderView getOrder(@PathVariable String orderId) {
        // Query sul read model — nessun aggregato da ricostruire
        return orderReadModelRepository.findById(orderId)
            .map(OrderView::from)
            .orElseThrow(() -> new OrderNotFoundException(orderId));
    }

    @GetMapping
    public Page<OrderView> listOrders(
            @RequestParam(required = false) String status,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size) {
        // Query ottimizzata con indici sul read model
        return orderReadModelRepository.findByStatusOrderByCreatedAtDesc(status,
            PageRequest.of(page, size)).map(OrderView::from);
    }
}
```

### Kafka Consumer Idempotente — Python

```python
# consumer/order_consumer.py
from confluent_kafka import Consumer, KafkaError
import json
import redis
import logging

logger = logging.getLogger(__name__)

consumer = Consumer({
    'bootstrap.servers': 'kafka.messaging.svc.cluster.local:9092',
    'group.id': 'payment-service-consumer',
    'auto.offset.reset': 'earliest',
    'enable.auto.commit': False,      # commit manuale — solo dopo elaborazione riuscita
    'max.poll.interval.ms': 300000,   # 5 minuti massimo per elaborare un batch
})
consumer.subscribe(['order.events'])

dedup_cache = redis.Redis(host='redis.cache.svc.cluster.local', decode_responses=True)

def process_order_placed(event: dict) -> None:
    order_id = event['orderId']
    dedup_key = f"processed:order_placed:{order_id}"

    # Controllo idempotency — skip se già elaborato
    if dedup_cache.exists(dedup_key):
        logger.info("Skipping duplicate event for orderId=%s", order_id)
        return

    # Elaborazione business logic
    payment_result = charge_customer(
        customer_id=event['customerId'],
        amount=event['amount'],
        idempotency_key=order_id,   # anche il downstream deve essere idempotente
    )

    # Pubblica evento risultante PRIMA di fare commit
    produce_payment_event(order_id, payment_result)

    # Registra elaborazione completata (TTL 24h per deduplication)
    dedup_cache.setex(dedup_key, 86400, '1')

def consume_loop():
    try:
        while True:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() != KafkaError._PARTITION_EOF:
                    logger.error("Consumer error: %s", msg.error())
                continue

            event = json.loads(msg.value().decode('utf-8'))
            event_type = event.get('eventType')

            try:
                if event_type == 'OrderPlaced':
                    process_order_placed(event)
                # commit solo dopo elaborazione riuscita
                consumer.commit(asynchronous=False)
            except Exception as e:
                logger.error("Failed to process event %s: %s", event_type, e)
                # non committare — il messaggio sarà riprocessato
    finally:
        consumer.close()
```

---

## Best Practices

### Scegliere Sincrona vs Asincrona

```
Usa comunicazione SINCRONA quando:
  ✅ Il client ha bisogno della risposta per proseguire (es. stock check, auth)
  ✅ L'operazione è semplice (1-2 servizi)
  ✅ SLA di latenza < 100ms richiesto
  ✅ Operazioni di lettura (query) — nessuna modifica di stato

Usa comunicazione ASINCRONA quando:
  ✅ L'operazione coinvolge 3+ servizi in sequenza
  ✅ Il workflow può richiedere secondi o minuti (es. payment + fraud check + email)
  ✅ Il servizio chiamato non deve essere sempre disponibile
  ✅ Operazioni di scrittura che modificano più aggregate
  ✅ Notifiche, fanout a molti consumer (es. "order confirmed" → email, SMS, analytics)

⚠ Attenzione: non abusare dell'asincrona per semplicità apparente
  L'asincrona richiede: idempotency, ordering, error handling, monitoring DLQ
  Il debug di un workflow asincrono fallito è molto più complesso
```

!!! tip "Pattern: Async con risposta sincrona"
    Per operazioni user-facing che richiedono feedback immediato ma sono internamente asincrone: restituisci `202 Accepted` con un `jobId`. Il client fa polling su `GET /jobs/{jobId}` per lo stato. Eviti il coupling temporale mantenendo buona UX.

### Gestione della Dead Letter Queue (DLQ)

!!! warning "La DLQ non è il cestino — è una coda di lavoro"
    Ogni messaggio in DLQ rappresenta un'operazione di business non completata. Devi monitorare la DLQ con alert, avere un processo di replay, e capire perché i messaggi ci sono finiti.

```yaml
# Kafka — configurazione DLQ con Spring Kafka
spring:
  kafka:
    consumer:
      group-id: payment-service-consumer
    listener:
      ack-mode: manual_immediate

# Nel codice:
# @RetryableTopic(attempts = "3", backoff = @Backoff(delay = 1000, multiplier = 2),
#                 dltTopicSuffix = ".DLT")
# @KafkaListener(topics = "order.events")
# Il DLT (Dead Letter Topic) conterrà i messaggi falliti dopo 3 tentativi
```

### Versioning degli Eventi

```java
// Usa un campo version o eventType con versione nei payload degli eventi
// Mantieni backward compatibility — non rimuovere mai campi esistenti

// V1 (originale)
{
  "eventType": "OrderPlaced",
  "version": "1",
  "orderId": "123",
  "amount": 99.99
}

// V2 (aggiunta campo opzionale — backward compatible)
{
  "eventType": "OrderPlaced",
  "version": "2",
  "orderId": "123",
  "amount": 99.99,
  "currency": "EUR"   // nuovo campo opzionale — i consumer V1 lo ignorano
}

// Consumer defensivo — ignora campi sconosciuti, usa default per campi mancanti
@KafkaHandler
public void on(OrderPlacedEvent event) {
    String currency = event.getCurrency() != null ? event.getCurrency() : "EUR"; // default
    // ...
}
```

---

## Troubleshooting

### Problema: Doppia elaborazione degli eventi — ordine creato due volte

**Sintomo:** Un ordine viene creato due volte in produzione. I log mostrano che lo stesso evento `OrderPlaced` è stato elaborato da due istanze del consumer o due volte dalla stessa istanza.

**Causa:** Consumer non idempotente. In caso di riassegnazione delle partizioni Kafka (consumer crash, scaling) o di un commit fallito, il messaggio viene riprocessato senza verifica di duplicati.

**Soluzione:**
```python
# Aggiungere una chiave di idempotency univoca basata sull'eventId o orderId
def process_order_placed(event: dict) -> None:
    dedup_key = f"processed:{event['eventId']}"

    # SET NX (set only if not exists) — atomico in Redis
    was_set = redis_client.set(dedup_key, "1", nx=True, ex=86400)
    if not was_set:
        logger.info("Duplicate event %s — skipping", event['eventId'])
        return

    # Procedi con l'elaborazione
    create_order(event)
```

---

### Problema: Saga bloccata in stato intermedio — ordine né confermato né annullato

**Sintomo:** Un ordine rimane in stato `PAYMENT_PENDING` per ore. Il payment service non ha risposto né con successo né con fallimento. Il cliente non sa cosa è successo al suo ordine.

**Causa:** Il saga orchestrator non ha un meccanismo di timeout. Un evento di risposta perso o un servizio che non risponde mai blocca la saga indefinitamente.

**Soluzione:**
```java
// Aggiungere un timeout alla saga con un scheduled job
@Scheduled(fixedDelay = 60000) // ogni minuto
public void recoverStuckSagas() {
    Instant timeout = Instant.now().minus(Duration.ofMinutes(5));
    List<SagaState> stuck = sagaStateRepo.findByStateAndCreatedAtBefore(
        State.PAYMENT_PENDING, timeout);

    for (SagaState saga : stuck) {
        log.warn("Saga timeout for orderId={} — triggering compensation", saga.getOrderId());
        // Emetti un evento di fallimento per avviare la compensazione
        eventBus.publish(new SagaTimeoutEvent(saga.getOrderId(), saga.getCurrentState()));
    }
}
```

---

### Problema: Event ordering — eventi elaborati fuori ordine

**Sintomo:** L'evento `OrderCancelled` viene elaborato prima di `OrderCreated`. Il read model mostra ordini in stato CANCELLED che non esistono nel sistema.

**Causa:** In Kafka il solo ordinamento garantito è **within-partition**. Se il producer non usa una partition key consistente (o usa partizioni diverse), gli eventi dello stesso ordine possono finire su partizioni diverse e arrivare in ordine arbitrario ai consumer.

**Soluzione:**
```java
// Usare sempre orderId come partition key per garantire ordering per aggregate
producer.send(new ProducerRecord<>(
    "order-events",
    order.getId().toString(),  // partition key = orderId → stessa partizione → ordering garantito
    event.toJson()
));

// Nel consumer: gestire gli eventi con versioning ottimistico
@KafkaHandler
public void on(OrderStatusChangedEvent event) {
    orderReadModelRepository.updateStatusIfVersionGreater(
        event.getOrderId(),
        event.getNewStatus(),
        event.getVersion()  // ignora eventi con version <= version corrente
    );
}
```

---

### Problema: Circuit breaker aperto su dipendenza critica — come degradare gracefully

**Sintomo:** Il circuit breaker verso il `ProductService` è aperto. L'endpoint `GET /orders` non riesce a recuperare i dettagli prodotto e restituisce 500 a tutti i client.

**Causa:** Il fallback non è definito o restituisce un errore invece di un valore di default sicuro.

**Soluzione:**
```java
@CircuitBreaker(name = "productService", fallbackMethod = "productFallback")
public List<ProductDetails> getProductDetails(List<String> productIds) {
    return productServiceClient.getDetails(productIds);
}

// Fallback: restituisci dati minimali dal cache o placeholder
public List<ProductDetails> productFallback(List<String> productIds, Throwable ex) {
    log.warn("ProductService unavailable, using cached/minimal details: {}", ex.getMessage());

    // Prova prima il cache locale
    List<ProductDetails> cached = productCache.getMany(productIds);
    if (!cached.isEmpty()) {
        return cached;  // dati potenzialmente stale ma funzionali
    }

    // Fallback finale: placeholder con solo l'id
    return productIds.stream()
        .map(id -> ProductDetails.minimal(id, "Dettagli non disponibili"))
        .collect(toList());
    // L'ordine viene mostrato parzialmente — meglio che un errore 500
}
```

---

### Problema: Messaggi accumulati nella DLQ senza alert

**Sintomo:** La DLQ Kafka accumula messaggi per giorni senza che nessuno lo noti. Ordini non processati, pagamenti non confermati.

**Causa:** Assenza di monitoring sulla DLQ. La DLQ viene trattata come cestino invece che come coda di lavoro.

**Soluzione:**
```yaml
# Alert Prometheus/Alertmanager sulla DLQ
groups:
  - name: kafka-dlq-alerts
    rules:
      - alert: DLQMessagesAccumulating
        expr: |
          kafka_consumer_group_lag{topic=~".*\\.DLT"} > 0
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "DLQ {{ $labels.topic }} ha {{ $value }} messaggi non processati"
          runbook: "https://wiki.internal/runbooks/kafka-dlq-recovery"

      - alert: DLQMessagesHighVolume
        expr: |
          kafka_consumer_group_lag{topic=~".*\\.DLT"} > 10
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "DLQ {{ $labels.topic }} critica: {{ $value }} messaggi"
```

---

## Relazioni

??? info "Dev / API Design — contratti per la comunicazione sincrona"
    La comunicazione sincrona si basa su contratti API (OpenAPI per REST, Protobuf per gRPC). Il versionamento delle API è critico per evitare breaking changes nei client. → [API Design](../api/_index.md)

??? info "Dev / Resilienza — circuit breaker e retry sulle chiamate sincrone"
    Ogni chiamata sincrona a un servizio esterno deve avere circuit breaker, retry con backoff e timeout. La resilienza è il complemento obbligatorio della comunicazione sincrona. → [Resilienza](../resilienza/_index.md)

??? info "Messaging / Kafka — implementazione event-driven e Saga"
    I pattern di integrazione asincrona si implementano su Kafka: Saga Pattern, CQRS, Outbox Pattern, Event Sourcing sono documentati in dettaglio con esempi pratici. → [Kafka Patterns](../../messaging/kafka/pattern-microservizi/_index.md)

??? info "Messaging / Kafka / Saga Pattern — dettaglio implementativo"
    Implementazione completa del Saga Pattern con Kafka: choreography vs orchestration, transazioni compensatorie, timeout handling, idempotency. → [Saga Pattern](../../messaging/kafka/pattern-microservizi/saga-pattern.md)

??? info "Messaging / Kafka / CQRS — dettaglio implementativo"
    CQRS con Kafka e Event Sourcing: event store, projections, eventual consistency, query optimization. → [CQRS](../../messaging/kafka/pattern-microservizi/cqrs.md)

??? info "Messaging / RabbitMQ — alternative a Kafka per integrazioni asincrone"
    RabbitMQ come alternativa a Kafka per message routing flessibile, workload distribution, e scenari con messaggi a basso volume ma alta priorità di routing. → [RabbitMQ](../../messaging/rabbitmq/_index.md)

??? info "Messaging / Kafka / Outbox Pattern — garantire la pubblicazione eventi"
    Il Transactional Outbox Pattern con Debezium CDC garantisce che gli eventi vengano pubblicati su Kafka esattamente una volta, in modo atomico con la transazione DB. → [Outbox Pattern](../../messaging/kafka/pattern-microservizi/outbox-pattern.md)

---

## Riferimenti

- [microservices.io — Patterns](https://microservices.io/patterns/index.html) — Catalogo completo dei pattern di integrazione per microservizi (Chris Richardson)
- [microservices.io — Saga Pattern](https://microservices.io/patterns/data/saga.html) — Definizione e varianti del Saga Pattern
- [microservices.io — CQRS](https://microservices.io/patterns/data/cqrs.html) — CQRS applicato ai microservizi
- [microservices.io — Transactional Outbox](https://microservices.io/patterns/data/transactional-outbox.html) — Outbox pattern per guaranteed delivery
- [Building Microservices (book)](https://www.oreilly.com/library/view/building-microservices-2nd/9781492034018/) — Sam Newman, cap. 4-5 su comunicazione e integrazione
- [Enterprise Integration Patterns (book)](https://www.enterpriseintegrationpatterns.com/) — Hohpe & Woolf, il riferimento classico per i pattern di messaggistica
- [CloudEvents Specification](https://cloudevents.io/) — Standard CNCF per il formato degli eventi cloud-native
- [Axon Framework](https://docs.axoniq.io/reference-guide/) — Framework Java per CQRS e Event Sourcing
- [Temporal](https://temporal.io/) — Workflow engine per saga e orchestrazione distribuita di lunga durata
