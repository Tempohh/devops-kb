---
title: "RabbitMQ da Codice — Java, .NET, Go"
slug: rabbitmq-client
category: dev
tags: [rabbitmq, amqp, spring-amqp, masstransit, go, java, dotnet, messaging, consumer, producer]
search_keywords: [rabbitmq java, spring amqp, rabbittemplate, rabbitlistener, simplelistenercontainer, directexchange, topicexchange, fanoutexchange, jackson2jsonmessageconverter, pojo message, message converter java, rabbitmq spring boot, rabbitmq .net, masstransit, iconsumer, ibus publish, ibus send, request response masstransit, saga state machine, sagatransition, orchestration saga, masstransit di aspnet, rabbitmq go, amqp091-go, channel consume go, goroutine consumer, ack manuale, manual acknowledgement, nack rabbitmq, prefetch count, qos consumer, connection recovery, reconnect amqp, dead letter queue codice, dlq developer, dlx binding, consumer tag, exclusive consumer, rabbitmq client library, amqp client, message broker integration, microservizi rabbitmq, event-driven microservizi, publisher confirm java, transactional outbox pattern]
parent: dev/integrazioni/_index
related: [messaging/rabbitmq/architettura, messaging/rabbitmq/affidabilita, dev/linguaggi/java-spring-boot, dev/linguaggi/dotnet, dev/linguaggi/go]
official_docs: https://www.rabbitmq.com/client-libraries/java-api-guide
status: needs-review
difficulty: advanced
last_updated: 2026-10-04
last_verified: 2026-10-04
---

# RabbitMQ da Codice — Java, .NET, Go

## Panoramica

Integrare RabbitMQ da codice applicativo è un'attività **distinta** dalla gestione operativa del broker. L'operatore configura exchange, code, binding e policy — il developer scrive producer e consumer usando le librerie client del proprio linguaggio. Questo documento copre la prospettiva del developer: come pubblicare e consumare messaggi in modo affidabile, come configurare ack manuale, prefetch count, dead letter queue, e gestire la riconnessione automatica.

Le tre librerie trattate coprono i principali stack enterprise:

- **Spring AMQP** (Java/Spring Boot): la libreria ufficiale Spring per RabbitMQ, con astrazione annotation-driven e template imperativo.
- **MassTransit** (.NET): framework di alto livello per .NET che astrae il broker e aggiunge pattern come Request/Response e Saga.
- **amqp091-go** (Go): libreria low-level che espone direttamente il protocollo AMQP 0-9-1, adatta quando si vuole controllo completo.

!!! warning "Prerequisito: modello AMQP"
    Questo documento assume che tu conosca i concetti di exchange, queue, binding, routing key e acknowledge. Se non li conosci, leggi prima [Architettura AMQP](../../messaging/rabbitmq/architettura.md).

---

## Concetti Chiave

### Acknowledgement Manuale vs Automatico

| Modalità | Comportamento | Quando usarla |
|---|---|---|
| **Auto-ack** | Il broker considera il messaggio consegnato non appena il client lo riceve | Solo per messaggi idempotenti e non critici, o per lettura/analisi senza effetti |
| **Manual ack** | Il consumer invia esplicitamente `ack` o `nack` dopo l'elaborazione | **Default raccomandato** per qualsiasi logica di business |
| **nack + requeue=true** | Il messaggio torna in testa alla coda | Retry immediato — attenzione ai loop infiniti su errori non transitori |
| **nack + requeue=false** | Il messaggio viene scartato (o inviato alla DLX se configurata) | Errori non recuperabili; richiede DLQ configurata |

!!! warning "Auto-ack e perdita messaggi"
    Con auto-ack, se il processo crasha dopo aver ricevuto ma prima di aver elaborato il messaggio, il messaggio è perso definitivamente. Non usare auto-ack per elaborazioni con effetti collaterali (scrittura DB, chiamate HTTP, etc.).

### Prefetch Count (QoS)

Il prefetch count limita quanti messaggi non-acknowledged il broker può inviare contemporaneamente a un consumer. È il controllo fondamentale per evitare che un consumer lento si riempia di messaggi che non riesce a processare.

```
prefetch=1:   Consumer A ── [msg1] ── elabora ── ack ── [msg2] ...
              Consumer B ── [msg2] nel frattempo (load balancing reale)

prefetch=100: Consumer A ── [msg1..100] ── buffer locale pieno
              Consumer B ── nessun messaggio (starvation se A è lento)
```

!!! tip "Regola pratica per il prefetch"
    - Elaborazione veloce e I/O-bound: `prefetch=10..50`
    - Elaborazione lenta o CPU-bound: `prefetch=1..5`
    - Load balancing uniforme tra N consumer: `prefetch=1` garantisce round-robin reale

### Dead Letter Queue (DLX)

La DLQ (Dead Letter Queue) riceve i messaggi che non possono essere elaborati: nack con requeue=false, TTL scaduto, o coda piena. La configurazione della DLX avviene al momento della dichiarazione della coda, non nel codice consumer — ma il developer deve sapere che la DLX esiste e decidere quando fare `nack` invece di rilanciare l'eccezione.

---

## Spring AMQP (Java)

### Dipendenza Maven

```xml
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-amqp</artifactId>
</dependency>
```

### Configurazione Connessione

```yaml
# application.yml
spring:
  rabbitmq:
    host: rabbitmq.internal
    port: 5672
    username: app-user
    password: ${RABBITMQ_PASSWORD}   # mai hardcoded — leggi da env/secret
    virtual-host: /production
    connection-timeout: 5000
    # Senza questo il ConfirmCallback del RabbitTemplate NON viene mai invocato
    publisher-confirm-type: correlated
    # Publisher returns: necessari per ReturnsCallback (messaggi non instradabili)
    publisher-returns: true
    listener:
      simple:
        # Retry stateless in-process dei listener (NON della connessione):
        # ritenta la chiamata al metodo @RabbitListener prima di rifiutare il messaggio
        retry:
          enabled: true
          initial-interval: 2s
          max-attempts: 5
          multiplier: 2
```

!!! note "Retry della connessione"
    La riconnessione al broker è gestita automaticamente da `CachingConnectionFactory` (il client Java ha il connection recovery attivo di default). Le proprietà `listener.simple.retry` riguardano solo l'elaborazione dei messaggi.

### Dichiarazione Exchange, Queue, Binding via @Bean

!!! note "Jackson 3 (Spring AMQP 4.x / Boot 4)"
    In Spring AMQP 4.x `Jackson2JsonMessageConverter` è deprecato per la rimozione in favore di `JacksonJsonMessageConverter` (Jackson 3). Gli esempi sotto usano la classe Jackson 2 (Spring Boot 3.x / Spring AMQP 3.x); su Boot 4 sostituisci il tipo con `JacksonJsonMessageConverter`.

```java
import org.springframework.amqp.core.*;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class RabbitConfig {

    // DirectExchange: routing esatto sulla routing key
    @Bean
    public DirectExchange ordersExchange() {
        return new DirectExchange("orders.exchange", true, false);
        //                                            durable  autoDelete
    }

    // TopicExchange: routing con wildcard (* = 1 word, # = 0+ words)
    @Bean
    public TopicExchange eventsExchange() {
        return new TopicExchange("events.exchange");
    }

    // FanoutExchange: broadcast a tutte le code legate
    @Bean
    public FanoutExchange notificationsExchange() {
        return new FanoutExchange("notifications.exchange");
    }

    @Bean
    public Queue ordersQueue() {
        return QueueBuilder.durable("orders.queue")
            .withArgument("x-dead-letter-exchange", "orders.dlx")
            .withArgument("x-dead-letter-routing-key", "orders.dead")
            .withArgument("x-message-ttl", 300_000)  // 5 minuti TTL
            .build();
    }

    @Bean
    public Queue ordersDlq() {
        return QueueBuilder.durable("orders.dlq").build();
    }

    @Bean
    public DirectExchange ordersDlx() {
        return new DirectExchange("orders.dlx");
    }

    @Bean
    public Binding ordersBinding(Queue ordersQueue, DirectExchange ordersExchange) {
        return BindingBuilder.bind(ordersQueue)
            .to(ordersExchange)
            .with("order.created");
    }

    @Bean
    public Binding dlqBinding(Queue ordersDlq, DirectExchange ordersDlx) {
        return BindingBuilder.bind(ordersDlq)
            .to(ordersDlx)
            .with("orders.dead");
    }

    // Converter JSON: POJO ↔ JSON automatico
    // Spring AMQP 4.x (Boot 4 / Jackson 3): usa JacksonJsonMessageConverter (questo è deprecato)
    @Bean
    public Jackson2JsonMessageConverter messageConverter() {
        return new Jackson2JsonMessageConverter();
    }

    @Bean
    public RabbitTemplate rabbitTemplate(
            ConnectionFactory connectionFactory,
            Jackson2JsonMessageConverter converter) {
        RabbitTemplate template = new RabbitTemplate(connectionFactory);
        template.setMessageConverter(converter);
        // Publisher confirms: attendi conferma dal broker
        template.setConfirmCallback((correlationData, ack, cause) -> {
            if (!ack) {
                // `log` = logger SLF4J della classe (es. @Slf4j di Lombok)
                log.error("Messaggio non confermato dal broker: {}", cause);
                // logica di retry o dead letter applicativa
            }
        });
        return template;
    }
}
```

### Producer con RabbitTemplate

```java
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.stereotype.Service;

@Service
public class OrderProducer {

    private final RabbitTemplate rabbitTemplate;

    public OrderProducer(RabbitTemplate rabbitTemplate) {
        this.rabbitTemplate = rabbitTemplate;
    }

    public void publishOrderCreated(OrderCreatedEvent event) {
        // Pubblica POJO — Jackson2JsonMessageConverter serializza automaticamente
        rabbitTemplate.convertAndSend(
            "orders.exchange",   // exchange
            "order.created",     // routing key
            event                // payload — viene serializzato in JSON
        );
    }

    public void publishWithHeaders(OrderCreatedEvent event) {
        rabbitTemplate.convertAndSend("orders.exchange", "order.created", event,
            message -> {
                // Aggiungi header custom
                message.getMessageProperties().setHeader("source-service", "order-service");
                message.getMessageProperties().setHeader("tenant-id", event.getTenantId());
                message.getMessageProperties().setExpiration("60000"); // TTL messaggio
                return message;
            });
    }

    // Request/Reply sincrono (RPC over AMQP)
    public OrderConfirmation requestConfirmation(OrderRequest request) {
        return (OrderConfirmation) rabbitTemplate.convertSendAndReceive(
            "orders.exchange", "order.confirm", request);
        // Attenzione: blocking, timeout di default 5s
    }
}
```

### Consumer con @RabbitListener

```java
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.amqp.rabbit.listener.api.ChannelAwareMessageListener;
import org.springframework.amqp.support.AmqpHeaders;
import org.springframework.messaging.handler.annotation.Header;
import org.springframework.stereotype.Component;
import com.rabbitmq.client.Channel;

@Component
public class OrderConsumer {

    // Consumer semplice — con AcknowledgeMode.AUTO (default di Spring) il container
    // fa ack se il metodo ritorna. NON usare con la factory MANUAL di sotto: nessuno farebbe ack.
    @RabbitListener(queues = "orders.queue", concurrency = "3-10")
    //                                       min-max thread pool dinamico
    public void handleOrder(OrderCreatedEvent event) {
        processOrder(event);
        // Nessuna eccezione → ack
        // Eccezione non gestita → nack + requeue (default requeueRejected=true:
        // rischio loop infinito; MessageConversionException è invece scartata senza requeue)
    }

    // Consumer con ack manuale — massimo controllo (ackMode per-listener, Spring AMQP ≥ 2.3)
    @RabbitListener(queues = "orders.queue", ackMode = "MANUAL")
    public void handleOrderManualAck(
            OrderCreatedEvent event,
            Channel channel,
            @Header(AmqpHeaders.DELIVERY_TAG) long deliveryTag) throws IOException {

        try {
            processOrder(event);
            channel.basicAck(deliveryTag, false);  // false = ack solo questo messaggio
        } catch (TransientException e) {
            // Errore transitorio: requeue per retry
            channel.basicNack(deliveryTag, false, true);  // requeue=true
        } catch (PermanentException e) {
            // Errore permanente: invia alla DLQ
            channel.basicNack(deliveryTag, false, false);  // requeue=false → DLX
        }
    }

    // Consumer con header custom
    @RabbitListener(queues = "orders.queue")
    public void handleWithHeaders(
            OrderCreatedEvent event,
            @Header("tenant-id") String tenantId,
            @Header(required = false, value = "source-service") String sourceService) {
        // headers opzionali con required=false evitano eccezioni se header mancante
        processOrderForTenant(event, tenantId);
    }
}
```

### Configurazione Prefetch e Retry

```java
@Bean
public SimpleRabbitListenerContainerFactory rabbitListenerContainerFactory(
        ConnectionFactory connectionFactory,
        Jackson2JsonMessageConverter converter) {

    SimpleRabbitListenerContainerFactory factory =
        new SimpleRabbitListenerContainerFactory();
    factory.setConnectionFactory(connectionFactory);
    factory.setMessageConverter(converter);

    // Prefetch: quanti messaggi non-acked il broker invia per consumer
    factory.setPrefetchCount(10);

    // AUTO (default): il container fa ack/nack in base all'esito del metodo.
    // MANUAL: ogni listener deve chiamare channel.basicAck/Nack, altrimenti i messaggi
    // restano unacked e il prefetch si satura. Usalo solo se serve controllo fine.
    factory.setAcknowledgeMode(AcknowledgeMode.AUTO);

    // Retry stateless con backoff esponenziale, poi scarto verso la DLX.
    // (Lo stateful richiede un messageId univoco e non si combina con ack MANUAL.)
    RetryOperationsInterceptor retry = RetryInterceptorBuilder.stateless()
        .maxAttempts(3)
        .backOffOptions(1000, 2.0, 10000)  // initial, multiplier, max ms
        .recoverer(new RejectAndDontRequeueRecoverer()) // dopo 3 tentativi → DLQ
        .build();

    factory.setAdviceChain(retry);
    return factory;
}
```

!!! tip "Quorum queue"
    Per code nuove preferisci le **quorum queue** (`QueueBuilder.durable(...).quorum()`): sono il tipo replicato raccomandato (il mirroring delle classic queue è stato rimosso in RabbitMQ 4.0) e supportano `x-delivery-limit`, che interrompe i loop di requeue spedendo il messaggio alla DLX dopo N consegne.

---

## MassTransit (.NET)

### Pacchetti NuGet

```bash
dotnet add package MassTransit
dotnet add package MassTransit.RabbitMQ   # include MassTransit; DI via Microsoft.Extensions.DependencyInjection
```

!!! warning "Licenza e versioni"
    MassTransit v8 è open source (Apache 2.0); dalla v9 (annunciata ad aprile 2025, ora rilasciata) la licenza è **commerciale**. La v8 resta utilizzabile con licenza open source ma il supporto termina a fine 2026; esiste inoltre il fork community OpenTransit di v8. Verifica versione e termini prima di adottarlo in un nuovo progetto. Il codice sotto è per v8.

### Configurazione con DI ASP.NET Core

```csharp
// Program.cs
using MassTransit;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddMassTransit(x =>
{
    // Registra tutti i consumer nella assembly corrente (alternativa: AddConsumer<T>() uno per uno)
    x.AddConsumers(typeof(Program).Assembly);

    // Configura il transport RabbitMQ
    x.UsingRabbitMq((context, cfg) =>
    {
        cfg.Host("rabbitmq.internal", "/production", h =>
        {
            h.Username("app-user");
            h.Password(builder.Configuration["RabbitMQ:Password"]);
        });

        // Configura receive endpoint per ogni consumer
        cfg.ReceiveEndpoint("orders-queue", e =>
        {
            // Prefetch count
            e.PrefetchCount = 10;

            // Dopo N tentativi il messaggio va in orders-queue_error.
            // L'ordine conta: i filtri sono middleware annidati, il retry deve
            // essere dichiarato PRIMA del consumer per avvolgerlo.
            e.UseMessageRetry(r => r.Exponential(3,
                TimeSpan.FromSeconds(1),
                TimeSpan.FromSeconds(30),
                TimeSpan.FromSeconds(2)));

            e.ConfigureConsumer<OrderCreatedConsumer>(context);
        });

        // Configura endpoint automatici per tutti i consumer registrati
        cfg.ConfigureEndpoints(context);
    });
});
```

### Definizione Messaggi (Contracts)

```csharp
// Contracts/OrderCreatedEvent.cs
// I messaggi MassTransit sono semplici POCO/record
public record OrderCreatedEvent
{
    public Guid OrderId { get; init; }
    public string CustomerId { get; init; } = default!;
    public decimal Total { get; init; }
    public DateTime CreatedAt { get; init; }
}

public record OrderConfirmationRequest
{
    public Guid OrderId { get; init; }
}

public record OrderConfirmationResponse
{
    public bool Confirmed { get; init; }
    public string? Reason { get; init; }
}
```

### Publisher

```csharp
using MassTransit;

public class OrderService
{
    private readonly IBus _bus;
    private readonly IPublishEndpoint _publishEndpoint;

    public OrderService(IBus bus, IPublishEndpoint publishEndpoint)
    {
        _bus = bus;
        _publishEndpoint = publishEndpoint;
    }

    // Publish: broadcast a tutti i consumer registrati per quel tipo di messaggio
    public async Task PublishOrderCreated(Order order, CancellationToken ct)
    {
        await _publishEndpoint.Publish(new OrderCreatedEvent
        {
            OrderId = order.Id,
            CustomerId = order.CustomerId,
            Total = order.Total,
            CreatedAt = DateTime.UtcNow
        }, ct);
    }

    // Send: indirizzo diretto a una coda specifica
    public async Task SendToQueue(OrderCreatedEvent evt, CancellationToken ct)
    {
        // "queue:" è l'indirizzo breve relativo al bus (host e virtual host già configurati);
        // la forma estesa include il vhost: rabbitmq://host/<vhost>/orders-queue
        var endpoint = await _bus.GetSendEndpoint(new Uri("queue:orders-queue"));
        await endpoint.Send(evt, ct);
    }

    // Request/Response: attendi risposta sincrona via AMQP
    public async Task<bool> RequestConfirmation(Guid orderId, CancellationToken ct)
    {
        var client = _bus.CreateRequestClient<OrderConfirmationRequest>();
        var response = await client.GetResponse<OrderConfirmationResponse>(
            new OrderConfirmationRequest { OrderId = orderId },
            ct,
            timeout: RequestTimeout.After(s: 10));
        return response.Message.Confirmed;
    }
}
```

### Consumer

```csharp
using MassTransit;

public class OrderCreatedConsumer : IConsumer<OrderCreatedEvent>
{
    private readonly IOrderRepository _repository;
    private readonly ILogger<OrderCreatedConsumer> _logger;

    public OrderCreatedConsumer(
        IOrderRepository repository,
        ILogger<OrderCreatedConsumer> logger)
    {
        _repository = repository;
        _logger = logger;
    }

    public async Task Consume(ConsumeContext<OrderCreatedEvent> context)
    {
        var evt = context.Message;
        _logger.LogInformation("Processing order {OrderId}", evt.OrderId);

        await _repository.Save(evt);

        // MassTransit fa ack automaticamente se il metodo torna senza eccezioni.
        // Eccezione non gestita → retry secondo la policy configurata.
        // Dopo N retry → invia alla fault queue (orders-queue_error).
    }
}

// Consumer Request/Response (lato server)
public class OrderConfirmationConsumer : IConsumer<OrderConfirmationRequest>
{
    public async Task Consume(ConsumeContext<OrderConfirmationRequest> context)
    {
        var confirmed = await CheckOrderValidity(context.Message.OrderId);
        await context.RespondAsync(new OrderConfirmationResponse
        {
            Confirmed = confirmed,
            Reason = confirmed ? null : "Insufficient inventory"
        });
    }
}
```

### Saga State Machine

```csharp
using MassTransit;

// Stato persistito della saga
public class OrderSagaState : SagaStateMachineInstance
{
    public Guid CorrelationId { get; set; }  // chiave primaria saga
    public string CurrentState { get; set; } = default!;
    public Guid OrderId { get; set; }
    public DateTime CreatedAt { get; set; }
    public bool PaymentConfirmed { get; set; }
    public bool InventoryReserved { get; set; }
}

// State machine
public class OrderSaga : MassTransitStateMachine<OrderSagaState>
{
    public State WaitingForPayment { get; private set; } = default!;
    public State WaitingForInventory { get; private set; } = default!;
    public State Completed { get; private set; } = default!;
    public State Failed { get; private set; } = default!;

    public Event<OrderCreatedEvent> OrderCreated { get; private set; } = default!;
    public Event<PaymentConfirmedEvent> PaymentConfirmed { get; private set; } = default!;
    public Event<InventoryReservedEvent> InventoryReserved { get; private set; } = default!;
    public Event<PaymentFailedEvent> PaymentFailed { get; private set; } = default!;

    public OrderSaga()
    {
        InstanceState(x => x.CurrentState);

        Event(() => OrderCreated,
            x => x.CorrelateById(ctx => ctx.Message.OrderId));
        Event(() => PaymentConfirmed,
            x => x.CorrelateById(ctx => ctx.Message.OrderId));
        Event(() => InventoryReserved,
            x => x.CorrelateById(ctx => ctx.Message.OrderId));
        Event(() => PaymentFailed,
            x => x.CorrelateById(ctx => ctx.Message.OrderId));

        Initially(
            When(OrderCreated)
                .Then(ctx => {
                    ctx.Saga.OrderId = ctx.Message.OrderId;
                    ctx.Saga.CreatedAt = DateTime.UtcNow;
                })
                .TransitionTo(WaitingForPayment));

        During(WaitingForPayment,
            When(PaymentConfirmed)
                .Then(ctx => ctx.Saga.PaymentConfirmed = true)
                .TransitionTo(WaitingForInventory),
            When(PaymentFailed)
                .TransitionTo(Failed));

        During(WaitingForInventory,
            When(InventoryReserved)
                .Then(ctx => ctx.Saga.InventoryReserved = true)
                .TransitionTo(Completed)
                .Finalize());
    }
}

// Registrazione saga in Program.cs
// (PaymentConfirmedEvent, InventoryReservedEvent, PaymentFailedEvent: record con OrderId, definiti come OrderCreatedEvent)
//
// x.AddSagaStateMachine<OrderSaga, OrderSagaState>()
//     .InMemoryRepository();                                                    // solo test
//
// x.AddSagaStateMachine<OrderSaga, OrderSagaState>()
//     .EntityFrameworkRepository(r => r.ExistingDbContext<AppDbContext>());     // produzione
```

---

## amqp091-go (Go)

### Dipendenza

```bash
go get github.com/rabbitmq/amqp091-go
```

### Connessione e Reconnect Handler

```go
package rabbitmq

import (
    "log/slog"
    "sync"
    "time"

    amqp "github.com/rabbitmq/amqp091-go"
)

type Connection struct {
    mu      sync.RWMutex // protegge conn/channel: reconnectLoop li riscrive da un'altra goroutine
    conn    *amqp.Connection
    channel *amqp.Channel
    url     string
}

// NewConnection crea la connessione con retry esponenziale.
// Chiamare in una goroutine separata o come blocking call all'avvio.
func NewConnection(url string) (*Connection, error) {
    c := &Connection{url: url}
    if err := c.connect(); err != nil {
        return nil, err
    }
    // Avvia il reconnect handler in background
    go c.reconnectLoop()
    return c, nil
}

func (c *Connection) connect() error {
    conn, err := amqp.Dial(c.url)
    if err != nil {
        return err
    }
    ch, err := conn.Channel()
    if err != nil {
        conn.Close()
        return err
    }
    c.mu.Lock()
    c.conn = conn
    c.channel = ch
    c.mu.Unlock()
    slog.Info("AMQP connected")
    return nil
}

// reconnectLoop si mette in ascolto sulle notifiche di chiusura del broker
// e tenta di riconnettersi con backoff esponenziale.
func (c *Connection) reconnectLoop() {
    for {
        // NotifyClose ritorna un channel che riceve l'errore quando la connessione cade
        c.mu.RLock()
        conn := c.conn
        c.mu.RUnlock()
        closeCh := conn.NotifyClose(make(chan *amqp.Error, 1))
        err := <-closeCh  // blocca finché la connessione è aperta
        if err == nil {
            slog.Info("AMQP connection closed gracefully")
            return
        }
        slog.Error("AMQP connection lost, reconnecting", "err", err)

        backoff := time.Second
        for {
            time.Sleep(backoff)
            if connErr := c.connect(); connErr == nil {
                slog.Info("AMQP reconnected")
                break
            }
            backoff = min(backoff*2, 30*time.Second)
        }
    }
}

func (c *Connection) Channel() *amqp.Channel {
    c.mu.RLock()
    defer c.mu.RUnlock()
    return c.channel
}
func (c *Connection) Close() { c.mu.RLock(); defer c.mu.RUnlock(); c.conn.Close() }
```

!!! warning "Cosa NON fa questo handler"
    A differenza di Spring AMQP e MassTransit, **amqp091-go non ha auto-recovery**: dopo la riconnessione devi ridichiarare la topologia (`SetupTopology`) e **ri-registrare i consumer** (il canale `deliveries` vecchio viene chiuso), e i `Producer` che tengono un `*amqp.Channel` vecchio vanno ricreati con `Channel()`. Inoltre un `Close()` volontario produce `err == nil` su `NotifyClose`, quindi il loop termina correttamente.

### Producer

```go
package rabbitmq

import (
    "context"
    "encoding/json"
    "fmt"
    "time"

    amqp "github.com/rabbitmq/amqp091-go"
)

type Producer struct {
    channel *amqp.Channel
}

func NewProducer(ch *amqp.Channel) *Producer {
    return &Producer{channel: ch}
}

// Publish pubblica un messaggio JSON su un exchange con routing key.
func (p *Producer) Publish(
    ctx context.Context,
    exchange, routingKey string,
    payload any,
) error {
    body, err := json.Marshal(payload)
    if err != nil {
        return fmt.Errorf("marshal payload: %w", err)
    }

    return p.channel.PublishWithContext(ctx,
        exchange,   // exchange
        routingKey, // routing key
        false,      // mandatory: false = non ritornare errore se nessuna coda è legata
        false,      // immediate: deprecato in RabbitMQ 3+, sempre false
        amqp.Publishing{
            ContentType:  "application/json",
            DeliveryMode: amqp.Persistent, // sopravvive al restart del broker
            Timestamp:    time.Now(),
            Body:         body,
            Headers: amqp.Table{
                "source-service": "order-service",
            },
        },
    )
}
```

### Consumer con Ack Manuale e Goroutine

```go
package rabbitmq

import (
    "context"
    "encoding/json"
    "fmt"
    "log/slog"

    amqp "github.com/rabbitmq/amqp091-go"
)

type OrderCreatedEvent struct {
    OrderId    string  `json:"order_id"`
    CustomerId string  `json:"customer_id"`
    Total      float64 `json:"total"`
}

type Consumer struct {
    channel *amqp.Channel
}

func NewConsumer(ch *amqp.Channel) (*Consumer, error) {
    // Imposta prefetch count: massimo N messaggi non-acked per consumer
    if err := ch.Qos(10, 0, false); err != nil {
        //             prefetchCount, prefetchSize (ignorato), global
        return nil, fmt.Errorf("set qos: %w", err)
    }
    return &Consumer{channel: ch}, nil
}

// Start avvia il loop di consumo in una goroutine dedicata.
// Il contesto permette uno shutdown pulito.
func (c *Consumer) Start(ctx context.Context, queue string) error {
    // Registra il consumer — il broker inizierà a consegnare messaggi
    deliveries, err := c.channel.Consume(
        queue,
        "",    // consumer tag — vuoto = generato automaticamente dal broker
        false, // autoAck — false = ack manuale obbligatorio
        false, // exclusive — true = solo questo consumer sulla coda
        false, // noLocal — ignorato da RabbitMQ
        false, // noWait
        nil,   // arguments
    )
    if err != nil {
        return fmt.Errorf("consume %s: %w", queue, err)
    }

    go func() {
        for {
            select {
            case <-ctx.Done():
                slog.Info("consumer shutting down", "queue", queue)
                return
            case delivery, ok := <-deliveries:
                if !ok {
                    slog.Warn("deliveries channel closed", "queue", queue)
                    return
                }
                c.handleDelivery(delivery)
            }
        }
    }()

    return nil
}

func (c *Consumer) handleDelivery(d amqp.Delivery) {
    var event OrderCreatedEvent
    if err := json.Unmarshal(d.Body, &event); err != nil {
        slog.Error("invalid message format", "err", err, "body", string(d.Body))
        // Formato non valido: nack senza requeue → DLQ
        _ = d.Nack(false, false)
        return
    }

    if err := processOrder(event); err != nil {
        if isTransient(err) {
            // Errore transitorio: requeue per retry
            slog.Warn("transient error, requeueing", "order_id", event.OrderId, "err", err)
            _ = d.Nack(false, true)
        } else {
            // Errore permanente: DLQ
            slog.Error("permanent error, dead lettering", "order_id", event.OrderId, "err", err)
            _ = d.Nack(false, false)
        }
        return
    }

    // Elaborazione completata con successo: ack
    if err := d.Ack(false); err != nil {
        slog.Error("ack failed", "err", err)
        // Il broker considererà il messaggio ancora in-flight; verrà reconsegnato al reconnect
    }
}
```

### Dichiarazione Exchange e Queue

```go
// SetupTopology dichiara exchange, code e binding idempotentemente
// (import necessari: "fmt" e amqp "github.com/rabbitmq/amqp091-go").
// Chiamare all'avvio prima di pubblicare o consumare.
// Idempotente solo se gli argomenti coincidono con quelli esistenti:
// altrimenti il broker risponde PRECONDITION_FAILED e chiude il canale.
func SetupTopology(ch *amqp.Channel) error {
    // Dichiara exchange principale
    if err := ch.ExchangeDeclare(
        "orders.exchange", // nome
        "direct",          // tipo: direct, fanout, topic, headers
        true,              // durable
        false,             // autoDelete
        false,             // internal
        false,             // noWait
        nil,
    ); err != nil {
        return fmt.Errorf("declare exchange: %w", err)
    }

    // Dichiara dead letter exchange
    if err := ch.ExchangeDeclare("orders.dlx", "direct", true, false, false, false, nil); err != nil {
        return fmt.Errorf("declare dlx: %w", err)
    }

    // Dichiara coda con DLX configurata
    if _, err := ch.QueueDeclare(
        "orders.queue",
        true,  // durable
        false, // autoDelete
        false, // exclusive
        false, // noWait
        amqp.Table{
            "x-dead-letter-exchange":    "orders.dlx",
            "x-dead-letter-routing-key": "orders.dead",
            "x-message-ttl":             int32(300_000), // 5 min TTL
        },
    ); err != nil {
        return fmt.Errorf("declare queue: %w", err)
    }

    // Dichiara DLQ
    if _, err := ch.QueueDeclare("orders.dlq", true, false, false, false, nil); err != nil {
        return fmt.Errorf("declare dlq: %w", err)
    }

    // Binding: coda → exchange con routing key
    if err := ch.QueueBind("orders.queue", "order.created", "orders.exchange", false, nil); err != nil {
        return fmt.Errorf("bind queue: %w", err)
    }

    if err := ch.QueueBind("orders.dlq", "orders.dead", "orders.dlx", false, nil); err != nil {
        return fmt.Errorf("bind dlq: %w", err)
    }

    return nil
}
```

---

## Best Practices

!!! tip "Progetta i messaggi come eventi immutabili"
    Un messaggio deve contenere tutti i dati necessari all'elaborazione senza che il consumer faccia query al DB del producer. Includi ID, timestamp, e i dati rilevanti. Non includere dati enormi: usa un riferimento (ID) e fai il consumer recuperare i dettagli se necessario.

!!! warning "Idempotenza obbligatoria"
    I messaggi possono essere consegnati **più di una volta** — il broker può riconsegnarli dopo un restart o se il consumer crasha prima dell'ack. Il consumer **deve** essere idempotente: elaborare due volte lo stesso messaggio non deve produrre effetti duplicati. Usa l'ID del messaggio come chiave di deduplicazione.

**Pattern consigliati:**

| Pattern | Quando usarlo | Note |
|---|---|---|
| **Transactional Outbox** | Vuoi garantire che il messaggio venga pubblicato se e solo se la transazione DB viene committata | Evita la doppia scrittura (DB + broker) non atomica. Si scrive il messaggio in una tabella nella stessa transazione e un relay lo pubblica. MassTransit ha un outbox integrato (`AddEntityFrameworkOutbox`); in Spring/Go va implementato a mano o con CDC |
| **Dead Letter Queue** | Qualsiasi coda che non può permettersi di perdere messaggi | Sempre: monitora la DLQ con alert |
| **Prefetch = 1 per consumer lenti** | Elaborazione CPU-bound o con dipendenze esterne lente | Garantisce load balancing reale tra istanze |
| **Publisher Confirms** | Vuoi certezza che il broker abbia preso in carico il messaggio (per quorum queue: replicato su maggioranza) | Costo alto se attendi la conferma messaggio per messaggio; usa conferme asincrone o in batch |
| **Heartbeat** | Connessioni long-lived su infrastruttura con firewall/NAT | Default RabbitMQ: 60s; abbassa a 30s se usi NAT aggressivo |

**Anti-pattern da evitare:**

- **Messaggi enormi**: oltre ~64KB rallenta il broker e la rete. Per payload grandi usa object storage (S3/blob) e includi nel messaggio solo il riferimento.
- **Fire-and-forget senza DLQ**: se non hai una DLQ, i messaggi che falliscono spariscono silenziosamente.
- **Nack con requeue=true senza limite**: crea loop infiniti su errori permanenti. Usa sempre un retry limit (Spring AMQP: `RetryInterceptor`; MassTransit: `UseMessageRetry`; Go: contatore nel consumer).
- **Condividere un channel tra goroutine** (Go): un `amqp.Channel` non è pensato per uso concorrente (publish interleaved, confirm ambigui). Usa un channel per goroutine; la `Connection` può essere condivisa.
- **Hardcodare credenziali**: usa variabili d'ambiente, Kubernetes secrets, o Vault.

---

## Troubleshooting

### Consumer non riceve messaggi

**Sintomo:** La coda ha messaggi (`messages_ready > 0`), ma il consumer non li processa.

**Causa 1 — Prefetch saturo:** Il consumer ha già N messaggi non-acked e il prefetch count è N.
```bash
# Consumer registrati (con prefetch_count e ack_required) sul vhost
rabbitmqctl list_consumers -p /production
# Se messages_unacknowledged è uguale al prefetch totale dei consumer → saturi
rabbitmqctl list_queues -p /production name messages_ready messages_unacknowledged consumers
```
**Soluzione:** Aumenta il prefetch count, oppure verifica che l'elaborazione stia completando e facendo ack.

**Causa 2 — Binding mancante:** La coda non è legata all'exchange con la routing key giusta.
```bash
rabbitmqctl list_bindings | grep orders.queue
# Se non appare il binding atteso → il producer pubblica su exchange/routing_key sbagliati
```

**Causa 3 — Consumer esclusivo o ack mancante:** un altro consumer `exclusive` detiene la coda (il secondo riceve `ACCESS_REFUSED`), oppure con ack MANUAL il listener non chiama mai `basicAck` (stesso sintomo della Causa 1). Un consumer tag duplicato sullo stesso channel viene invece rifiutato dal broker con `NOT_ALLOWED`.

---

### Messaggi in DLQ

<!-- CURRENCY: flag esatti di rabbitmqadmin v2 per get/publish non verificati (2026-10) — controllare `rabbitmqadmin get --help` / `publish --help` -->
**Sintomo:** La DLQ si riempie, la coda principale si svuota.

**Causa principale:** Il consumer fa `nack` con `requeue=false` (o lancia eccezioni dopo N retry).

!!! note "rabbitmqadmin v1 deprecato"
    `rabbitmqadmin` v1 non è più sviluppato; la v2 (`rabbitmqadmin-ng`) usa flag long (`--queue`, ...) invece di `key=value`. I comandi `get` e `publish` della v2 sono pensati solo per sviluppo/test: verifica i flag con `--help`. Gli esempi sotto usano la sintassi v1.

```bash
# Peek del primo messaggio della DLQ (sintassi rabbitmqadmin v1)
rabbitmqadmin get queue=orders.dlq count=1 requeue=true
# Controlla l'header x-death per il motivo del dead-lettering
```
**Soluzione:** Correggi il bug nel consumer, poi rimetti i messaggi nella coda originale. Per pochi messaggi, ripubblicali a mano; per volumi alti usa uno **Shovel** (plugin) o la funzione "move messages" della management UI:
```bash
rabbitmqadmin publish exchange=orders.exchange routing_key=order.created < message.json
```

---

### Connection Reset / Broken Pipe

**Sintomo (Go):** `Exception (504) Reason: "channel/connection is not open"` o `io: read/write on closed pipe`.

**Causa:** La connessione è caduta (network glitch, broker restart, heartbeat timeout).
**Soluzione:** Implementa il reconnect handler (vedi sezione Go sopra). Verifica che il heartbeat sia abilitato:
```go
conn, err := amqp.DialConfig(url, amqp.Config{
    Heartbeat: 30 * time.Second,  // default: 10s in amqp091-go
    Vhost:     "/production",
})
```

---

### Spring AMQP: `AmqpRejectAndDontRequeueException`

**Sintomo:** I messaggi finiscono in DLQ dopo un solo tentativo invece di essere ritentati.

**Causa:** Il consumer lancia `AmqpRejectAndDontRequeueException` (o una sua sottoclasse; anche `MessageConversionException` e simili "fatal" sono trattate così) che Spring AMQP interpreta come "non ritentare, rifiuta senza requeue → DLQ".
```java
// Corretto per errori PERMANENTI (payload malformato): va subito in DLQ, senza sprecare retry
throw new AmqpRejectAndDontRequeueException("invalid format");

// Per errori TRANSITORI lancia un'eccezione normale: scatta il retry configurato
throw new IllegalStateException("downstream non disponibile");
```
Se vedi questo comportamento su errori che ritenevi transitori, cerca chi lancia (o wrappa) quell'eccezione.

---

### MassTransit: messaggi nella fault queue invece di retry

**Sintomo:** I messaggi vanno subito in `queue-name_error` senza i 3 retry attesi.

**Causa:** `UseMessageRetry` deve essere configurato **prima** di `ConfigureConsumer`, altrimenti non avvolge il consumer e non viene applicato (i filtri sono middleware annidati nell'ordine di dichiarazione).
```csharp
// SBAGLIATO
cfg.ReceiveEndpoint("orders-queue", e =>
{
    e.ConfigureConsumer<OrderCreatedConsumer>(context);
    e.UseMessageRetry(r => r.Exponential(3, ...));  // troppo tardi
});

// CORRETTO
cfg.ReceiveEndpoint("orders-queue", e =>
{
    e.UseMessageRetry(r => r.Exponential(3, ...));  // prima del consumer
    e.ConfigureConsumer<OrderCreatedConsumer>(context);
});
```

---

## Relazioni

Questo documento copre la prospettiva del **developer** che integra RabbitMQ da codice. Per gli aspetti operativi e infrastrutturali:

??? info "Architettura AMQP — Exchange, Queue, Binding"
    Il modello concettuale AMQP 0-9-1: come funzionano i 4 tipi di exchange, le proprietà delle code, il channel multiplexing e il default exchange.

    **Approfondimento completo →** [Architettura AMQP](../../messaging/rabbitmq/architettura.md)

??? info "Affidabilità RabbitMQ — Publisher Confirms, HA Queues"
    Garanzie di consegna lato broker: publisher confirms, quorum queues, mirroring, at-least-once vs exactly-once.

    **Approfondimento completo →** [Affidabilità RabbitMQ](../../messaging/rabbitmq/affidabilita.md)

??? info "Java Spring Boot — Context applicativo"
    Configurazione Spring Boot, DI, profiles, e integrazione con l'ecosistema Spring.

    **Approfondimento completo →** [Java Spring Boot](../linguaggi/java-spring-boot.md)

??? info ".NET — Context applicativo"
    Configurazione ASP.NET Core, dependency injection, middleware e hosting model.

    **Approfondimento completo →** [.NET](../linguaggi/dotnet.md)

---

## Riferimenti

- [RabbitMQ Java Client API Guide](https://www.rabbitmq.com/client-libraries/java-api-guide)
- [Spring AMQP Reference](https://docs.spring.io/spring-amqp/reference/)
- [MassTransit Documentation](https://masstransit.io/documentation)
- [amqp091-go GitHub](https://github.com/rabbitmq/amqp091-go)
- [RabbitMQ Tutorials](https://www.rabbitmq.com/tutorials)
- [Publisher Confirms — RabbitMQ](https://www.rabbitmq.com/docs/confirms)
