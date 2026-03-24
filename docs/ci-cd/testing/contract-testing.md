---
title: "Contract Testing"
slug: contract-testing
category: ci-cd
tags: [contract-testing, pact, consumer-driven-contracts, microservices, api-testing, integration-testing]
search_keywords: [contract testing, pact, consumer driven contract, CDC, schema validation, provider verification, consumer verification, pact broker, breaking changes, microservices testing, API contract, integration testing microservices, test doubles, stub, mock, pactflow, async pact, event-driven contract, protobuf schema registry]
parent: ci-cd/testing/_index
related: [ci-cd/strategie/pipeline-security, ci-cd/github-actions/workflow-avanzati, ci-cd/gitlab-ci/pipeline-avanzato]
official_docs: https://docs.pact.io/
status: complete
difficulty: intermediate
last_updated: 2026-03-24
---

# Contract Testing

## Panoramica

Il contract testing è una tecnica di test che verifica la compatibilità tra servizi che comunicano tra loro (consumer e provider) attraverso un contratto formale e versionato. A differenza dei test di integrazione end-to-end, il contract testing non richiede che tutti i servizi siano attivi simultaneamente: ogni servizio viene testato in isolamento rispetto al contratto concordato.

Il problema che risolve è concreto: in un'architettura a microservizi, un team che modifica l'API di un provider può inavvertitamente rompere i consumer — spesso senza saperlo finché non arriva in produzione. Il contract testing sposta questa verifica nel CI/CD pipeline di entrambi i team, prima del deploy.

Il framework più diffuso è **Pact**, che implementa il pattern Consumer-Driven Contracts (CDC): è il consumer a definire cosa si aspetta, il provider a verificarlo. Esistono anche approcci basati su schema validation (JSON Schema, OpenAPI, AsyncAPI, Protobuf) che operano in modo simile ma su specifiche statiche.

**Quando usare il contract testing:**
- 3+ microservizi che comunicano tra loro via HTTP o messagging
- Team separati che possiedono servizi diversi
- Cicli di release indipendenti tra consumer e provider
- Necessità di sapere se una modifica al provider rompe un consumer *prima* del deploy

**Quando NON è la scelta giusta:**
- Monolite o moduli nello stesso deploy
- API pubblica (meglio versioning esplicito + API gateway)
- Meno di 2-3 servizi — l'overhead non vale

---

## Concetti Chiave

!!! note "Consumer e Provider"
    - **Consumer**: il servizio che chiama l'API (fa richieste HTTP, legge messaggi)
    - **Provider**: il servizio che espone l'API (risponde alle richieste, pubblica messaggi)
    - **Contratto (Pact file)**: documento JSON generato dal consumer che descrive le interazioni attese
    - **Pact Broker**: registry centralizzato dove vengono pubblicati i contratti e i risultati di verifica

!!! note "Consumer-Driven vs Schema-Driven"
    Nel pattern **Consumer-Driven**, il consumer scrive i test e genera il contratto; il provider lo verifica. Nei test **Schema-Driven**, si parte da una specifica OpenAPI/AsyncAPI e si valida che entrambi i lati la rispettino. I due approcci sono complementari.

!!! warning "Contract testing NON è un sostituto dei test E2E"
    Verifica la compatibilità dell'interfaccia, non il comportamento end-to-end del sistema. Serve comunque un livello di smoke test in staging, ma i contract test possono ridurre drasticamente quelli E2E lenti e fragili.

---

## Architettura / Come Funziona

### Flusso Consumer-Driven Contracts (Pact)

```
┌─────────────────────────────────────────────────────────────────┐
│  CONSUMER SIDE (es. Frontend / Service A)                       │
│                                                                 │
│  1. Scrivi il test consumer                                     │
│     - Definisci: request attesa, response minima richiesta      │
│  2. Esegui il test → Pact avvia un mock server                  │
│     - Il consumer chiama il mock, non il provider reale         │
│  3. Pact genera il contratto (pact file JSON)                   │
│  4. Pubblica il contratto sul Pact Broker                       │
└────────────────────────┬────────────────────────────────────────┘
                         │  contratto pubblicato
                         ▼
              ┌──────────────────┐
              │   Pact Broker    │  ← registry + webhook
              │  (o PactFlow)    │
              └────────┬─────────┘
                       │  contratto scaricato
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│  PROVIDER SIDE (es. Backend / Service B)                        │
│                                                                 │
│  5. Nel CI del provider: scarica il contratto dal broker        │
│  6. Avvia il provider reale (o un subset)                       │
│  7. Pact replay le interazioni del contratto sul provider       │
│  8. Verifica che le response reali matchino il contratto        │
│  9. Pubblica il risultato sul broker                            │
└─────────────────────────────────────────────────────────────────┘
```

### Struttura di un Pact file (JSON generato)

```json
{
  "consumer": { "name": "OrderService" },
  "provider": { "name": "ProductService" },
  "interactions": [
    {
      "description": "a request for product details",
      "request": {
        "method": "GET",
        "path": "/products/123",
        "headers": { "Accept": "application/json" }
      },
      "response": {
        "status": 200,
        "headers": { "Content-Type": "application/json" },
        "body": {
          "id": 123,
          "name": "Widget Pro",
          "price": 29.99
        }
      }
    }
  ],
  "metadata": {
    "pactSpecification": { "version": "2.0.0" }
  }
}
```

### Matchers (Pact v3+)

Il contratto non deve essere eccessivamente rigido. Pact fornisce matcher per verificare il tipo/formato invece del valore esatto:

```json
{
  "body": {
    "id": { "pact:matcher:type": "integer", "value": 123 },
    "name": { "pact:matcher:type": "type", "value": "Widget Pro" },
    "price": { "pact:matcher:type": "decimal", "value": 29.99 },
    "tags": {
      "pact:matcher:type": "eachLike",
      "value": "electronics",
      "min": 1
    }
  }
}
```

Questo permette al provider di cambiare valori (es. il prezzo) senza rompere il contratto, finché il tipo è corretto.

---

## Configurazione & Pratica

### Setup Pact — Consumer (Python)

```python
# tests/test_product_consumer.py
import pytest
from pact import Consumer, Provider, Like, Integer, EachLike
from myapp.clients import ProductClient

PACT_MOCK_HOST = "localhost"
PACT_MOCK_PORT = 1234

@pytest.fixture(scope="module")
def pact():
    pact = Consumer("OrderService").has_pact_with(
        Provider("ProductService"),
        host_name=PACT_MOCK_HOST,
        port=PACT_MOCK_PORT,
        pact_dir="./pacts",  # dove viene scritto il file JSON
    )
    pact.start_service()
    yield pact
    pact.stop_service()


def test_get_product(pact):
    expected_product = {
        "id": Like(123),          # qualunque integer
        "name": Like("Widget"),   # qualunque stringa
        "price": Like(29.99),     # qualunque numero
        "available": Like(True),
    }

    (
        pact
        .given("product 123 exists")
        .upon_receiving("a request for product 123")
        .with_request(
            method="GET",
            path="/products/123",
            headers={"Accept": "application/json"},
        )
        .will_respond_with(
            status=200,
            headers={"Content-Type": "application/json"},
            body=expected_product,
        )
    )

    with pact:
        client = ProductClient(base_url=f"http://{PACT_MOCK_HOST}:{PACT_MOCK_PORT}")
        product = client.get_product(123)

    assert product["id"] == 123
    assert "name" in product
```

### Setup Pact — Provider (Python + pytest)

```python
# tests/test_product_provider.py
import pytest
from pact import Verifier

PROVIDER_BASE_URL = "http://localhost:8000"
PACT_BROKER_URL = "http://pact-broker:9292"

def test_provider_verification():
    verifier = Verifier(
        provider="ProductService",
        provider_base_url=PROVIDER_BASE_URL,
    )

    output, _ = verifier.verify_with_broker(
        broker_url=PACT_BROKER_URL,
        broker_username="pactbroker",
        broker_password="pactbroker",
        publish_verification_results=True,
        provider_version="1.2.3",           # versione corrente del provider
        provider_version_branch="main",
        enable_pending=True,                # non blocca per contratti non verificati
        include_wip_pacts_since="2026-01-01",
    )

    assert output == 0, "Provider verification failed"
```

### Setup Pact — Consumer (TypeScript / Jest)

```typescript
// src/__tests__/product.consumer.test.ts
import { Pact, Matchers } from "@pact-foundation/pact";
import { ProductClient } from "../clients/productClient";

const { like, integer } = Matchers;

const provider = new Pact({
  consumer: "OrderService",
  provider: "ProductService",
  port: 1234,
  log: process.env.LOG_LEVEL ?? "warn",
  dir: "./pacts",
});

describe("ProductService consumer", () => {
  beforeAll(() => provider.setup());
  afterAll(() => provider.finalize());
  afterEach(() => provider.verify());

  it("retrieves product details", async () => {
    await provider.addInteraction({
      state: "product 123 exists",
      uponReceiving: "a request for product 123",
      withRequest: {
        method: "GET",
        path: "/products/123",
        headers: { Accept: "application/json" },
      },
      willRespondWith: {
        status: 200,
        headers: { "Content-Type": "application/json" },
        body: {
          id: integer(123),
          name: like("Widget Pro"),
          price: like(29.99),
        },
      },
    });

    const client = new ProductClient("http://localhost:1234");
    const product = await client.getProduct(123);

    expect(product.id).toBeDefined();
    expect(product.name).toBeDefined();
  });
});
```

### Pact Broker — Deploy con Docker Compose

```yaml
# docker-compose.yml
version: "3.8"

services:
  pact-broker:
    image: pactfoundation/pact-broker:latest
    ports:
      - "9292:9292"
    environment:
      PACT_BROKER_DATABASE_URL: "postgres://pactbroker:password@postgres/pactbroker"
      PACT_BROKER_BASIC_AUTH_USERNAME: pactbroker
      PACT_BROKER_BASIC_AUTH_PASSWORD: pactbroker
      PACT_BROKER_PUBLIC_HEARTBEAT: "true"
    depends_on:
      - postgres

  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: pactbroker
      POSTGRES_USER: pactbroker
      POSTGRES_PASSWORD: password
    volumes:
      - pact_data:/var/lib/postgresql/data

volumes:
  pact_data:
```

### Pubblicare un contratto sul Broker

```bash
# Con pact-broker CLI
pact-broker publish ./pacts \
  --broker-base-url http://pact-broker:9292 \
  --broker-username pactbroker \
  --broker-password pactbroker \
  --consumer-app-version "$(git rev-parse --short HEAD)" \
  --branch "$(git branch --show-current)" \
  --tag "$(git branch --show-current)"
```

### can-i-deploy — Gate prima del deploy

Il comando `can-i-deploy` interroga il broker per verificare se una versione specifica è sicura da deployare:

```bash
# Verifica se OrderService@abc1234 può andare in produzione
pact-broker can-i-deploy \
  --pacticipant OrderService \
  --version "abc1234" \
  --to-environment production \
  --broker-base-url http://pact-broker:9292 \
  --broker-username pactbroker \
  --broker-password pactbroker

# Output esempio:
# Computer says yes \o/
# CONSUMER      | C.VERSION | PROVIDER       | P.VERSION | SUCCESS?
# OrderService  | abc1234   | ProductService | def5678   | true
```

Se un consumer non ha contratti verificati con il provider nella versione target, il comando fallisce e il deploy viene bloccato.

---

## Integrazione CI/CD

### GitHub Actions — Consumer Pipeline

```yaml
# .github/workflows/consumer-tests.yml
name: Consumer Contract Tests

on: [push, pull_request]

jobs:
  contract-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run consumer pact tests
        run: pytest tests/test_product_consumer.py -v
        # Genera ./pacts/OrderService-ProductService.json

      - name: Publish pact to broker
        run: |
          pip install pact-python
          pact-broker publish ./pacts \
            --broker-base-url ${{ vars.PACT_BROKER_URL }} \
            --broker-username ${{ secrets.PACT_BROKER_USER }} \
            --broker-password ${{ secrets.PACT_BROKER_PASSWORD }} \
            --consumer-app-version ${{ github.sha }} \
            --branch ${{ github.ref_name }}

      - name: Can I deploy?
        run: |
          pact-broker can-i-deploy \
            --pacticipant OrderService \
            --version ${{ github.sha }} \
            --to-environment production \
            --broker-base-url ${{ vars.PACT_BROKER_URL }} \
            --broker-username ${{ secrets.PACT_BROKER_USER }} \
            --broker-password ${{ secrets.PACT_BROKER_PASSWORD }}
```

### GitHub Actions — Provider Pipeline

```yaml
# .github/workflows/provider-tests.yml
name: Provider Contract Verification

on: [push, pull_request]

jobs:
  provider-verification:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_PASSWORD: test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Start provider service
        run: |
          uvicorn myapp.main:app --host 0.0.0.0 --port 8000 &
          sleep 3  # attendi avvio

      - name: Run provider verification
        env:
          PACT_BROKER_URL: ${{ vars.PACT_BROKER_URL }}
          PACT_BROKER_USER: ${{ secrets.PACT_BROKER_USER }}
          PACT_BROKER_PASSWORD: ${{ secrets.PACT_BROKER_PASSWORD }}
        run: pytest tests/test_product_provider.py -v

      - name: Record provider deployment
        run: |
          pact-broker record-deployment \
            --pacticipant ProductService \
            --version ${{ github.sha }} \
            --environment production \
            --broker-base-url ${{ vars.PACT_BROKER_URL }} \
            --broker-username ${{ secrets.PACT_BROKER_USER }} \
            --broker-password ${{ secrets.PACT_BROKER_PASSWORD }}
```

---

## Contract Testing per Messaggi Asincroni

Pact supporta anche i contratti per event-driven architecture (Kafka, RabbitMQ, SNS):

```python
# Consumer: verifica di ricevere un messaggio con la struttura attesa
from pact import MessageConsumer, Provider, Like, Integer

pact = MessageConsumer("InventoryService").has_pact_with(
    Provider("OrderService"),
    pact_dir="./pacts",
)

def test_order_created_event():
    expected_message = {
        "orderId": Like("order-123"),
        "customerId": Like("cust-456"),
        "items": [
            {
                "productId": Like("prod-789"),
                "quantity": Integer(2),
            }
        ],
        "totalAmount": Like(59.98),
    }

    (
        pact
        .given("an order is created")
        .expects_to_receive("an OrderCreated event")
        .with_content(expected_message)
        .with_metadata({"contentType": "application/json"})
    )

    with pact:
        # Simula il processing del messaggio
        from myapp.handlers import handle_order_created
        handle_order_created({"orderId": "order-123", "customerId": "cust-456",
                               "items": [{"productId": "prod-789", "quantity": 2}],
                               "totalAmount": 59.98})
```

---

## Schema Validation con OpenAPI

Un approccio alternativo al Pact per team che già usano OpenAPI è la validazione dello schema:

```bash
# openapi-diff: confronta due versioni di spec OpenAPI
npx @openapitools/openapi-diff \
  openapi-v1.yaml \
  openapi-v2.yaml

# schemathesis: genera test da spec OpenAPI e li esegue sul provider reale
pip install schemathesis
schemathesis run http://localhost:8000/openapi.json \
  --checks all \
  --hypothesis-max-examples 50

# oasdiff: tool Go per breaking changes detection
oasdiff breaking openapi-v1.yaml openapi-v2.yaml
# Output: ERROR: api-path-removed /products/{id}
```

### Workflow OpenAPI-driven nel CI

```yaml
# Rileva breaking changes nell'OpenAPI spec
- name: Check for breaking changes
  run: |
    oasdiff breaking \
      https://raw.githubusercontent.com/org/repo/main/openapi.yaml \
      ./openapi.yaml \
      --fail-on-diff
```

---

## Best Practices

**Contratti minimal:** il consumer deve specificare solo i campi che usa effettivamente. Se usa solo `id` e `name`, il contratto non deve includere tutti gli altri campi — questo riduce i falsi positivi quando il provider aggiunge campi.

**Provider States:** usare gli stati (`given(...)`) per preparare il provider in condizioni riproducibili. Ogni stato deve essere idempotente e resettabile tra i test.

**Versioning semantico:** taggare i contratti con il branch e la versione (`main`, `feat/xyz`). Usare `can-i-deploy` come gate obbligatorio prima di ogni deploy in produzione.

**Pending pacts:** attivare `enable_pending=True` nel provider per non bloccare la verifica del provider su contratti di nuovi consumer non ancora verificati. I contratti pending non causano fallimento, ma compaiono nel report.

**WIP pacts:** `include_wip_pacts_since` include i contratti in-progress (non ancora verificati) nelle run di verifica, consentendo ai provider di fare "early feedback" ai consumer.

!!! warning "Anti-pattern: contratti troppo rigidi"
    Specificare valori esatti (`"name": "Widget Pro"`) invece di matcher (`Like("Widget Pro")`) porta a falsi positivi ogni volta che i dati di test cambiano. Usare sempre i matcher per i valori non funzionali.

!!! warning "Anti-pattern: contratti che duplicano i test unitari"
    I contract test verificano la compatibilità dell'interfaccia, non la logica di business. Non testare scenari di errore complessi o logica interna tramite contratti.

!!! tip "Webhook per notifiche immediate"
    Configurare i webhook nel Pact Broker per notificare il provider quando il consumer pubblica un nuovo contratto — così la verifica avviene subito, non solo nel prossimo CI run del provider.

---

## Troubleshooting

**Il provider verification fallisce con "Interaction not found"**
: Lo stato (`given`) non corrisponde a nessun handler nel provider. Verificare che il test provider definisca tutti gli stati usati nel consumer.

**can-i-deploy restituisce "no"**
: Il contratto non è stato ancora verificato dal provider per quella combinazione versione/ambiente. Controllare nel broker UI se la verifica è completata o in errore.

**Pact file non viene generato**
: Il test consumer non entra nel blocco `with pact:` o l'asserzione fallisce prima della chiamata. Il file viene scritto solo se il test ha eseguito almeno un'interazione.

**Provider risponde ma la verifica fallisce su un campo**
: Controllare se si sta usando `Like()` o un valore esatto. Un valore esatto nel contratto fallisce se il provider restituisce qualcosa di diverso (es. prezzo aggiornato).

**Encoding issues nel JSON del pact file**
: Assicurarsi che il provider ritorni `Content-Type: application/json; charset=utf-8`. Pact confronta le response come JSON, ma problemi di encoding possono causare mismatch.

---

## Relazioni

??? info "Pipeline Security — Supply Chain"
    I contract test sono un layer di sicurezza: prevengono che breaking changes vengano deployati in produzione. Si integrano nel gate `can-i-deploy` prima del deploy stage.

    **Approfondimento →** [Pipeline Security](../strategie/pipeline-security.md)

??? info "GitHub Actions — Workflow Avanzati"
    I job di consumer verification e provider verification si integrano nei workflow GitHub Actions come step dedicati dopo i test unitari.

    **Approfondimento →** [GitHub Actions Workflow Avanzati](../github-actions/workflow-avanzati.md)

??? info "GitLab CI — Pipeline Avanzato"
    In GitLab CI, il contract testing si implementa come stage separato (`contract-test`) con artefatti che includono i pact files da pubblicare al broker.

    **Approfondimento →** [GitLab CI Pipeline Avanzato](../gitlab-ci/pipeline-avanzato.md)

---

## Riferimenti

- [Pact Documentation](https://docs.pact.io/) — documentazione ufficiale Pact
- [PactFlow](https://pactflow.io/how-pact-works/) — Pact Broker SaaS con funzionalità avanzate
- [Pact Specification](https://github.com/pact-foundation/pact-specification) — specifica del formato contratto
- [schemathesis](https://schemathesis.readthedocs.io/) — property-based testing da OpenAPI spec
- [oasdiff](https://github.com/Tufin/oasdiff) — breaking changes detection per OpenAPI
- [Martin Fowler — Contract Test](https://martinfowler.com/bliki/ContractTest.html) — articolo fondante del pattern
