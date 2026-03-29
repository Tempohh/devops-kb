---
title: "Developer Workflow per Microservizi"
slug: developer-workflow
category: dev
tags: [workflow, developer-experience, dx, inner-loop, devcontainer, skaffold, tilt, git, conventional-commits, trunk-based, testing, feature-flags]
search_keywords: [developer workflow, dev workflow, inner loop, outer loop, local development, sviluppo locale, docker compose local, skaffold, tilt, devcontainer, dev container, VS Code devcontainer, GitHub Codespaces, codespaces, remote development, trunk based development, TBD, gitflow, git flow, branching strategy, strategia branching, conventional commits, commit convenzionali, semantic-release, changelog automatico, automatic changelog, versioning automatico, pull request workflow, PR checklist, microservizi checklist, shift left testing, testcontainers, pact, contract testing, test contratto, consumer driven contract, feature toggle, feature flag, LaunchDarkly, unleash, flipt, developer experience, DX, ciclo sviluppo, development cycle, hot reload, live reload, kubectl, kube, local kubernetes, kind, minikube, k3d]
parent: dev/processi/_index
related: [ci-cd/pipeline, ci-cd/strategie/trunk-based-development, ci-cd/testing/contract-testing, containers/docker/compose, dev/testing/_index]
official_docs: https://skaffold.dev/docs/
status: complete
difficulty: intermediate
last_updated: 2026-03-29
---

# Developer Workflow per Microservizi

## Panoramica

Il workflow del developer di microservizi si divide in due cicli distinti: l'**inner loop** (tutto ciò che accade prima del commit — write, build, run, test localmente) e l'**outer loop** (CI/CD, peer review, deploy in staging/production). Ottimizzare l'inner loop è la leva con il maggiore impatto sulla produttività: ogni minuto risparmiato nel ciclo modifica→feedback si moltiplica per decine di iterazioni al giorno.

Per i microservizi, l'inner loop è intrinsecamente più complesso rispetto ai monoliti: il servizio su cui si lavora ha dipendenze esterne reali (database, broker, cache, altri servizi) che devono essere disponibili localmente o simulate in modo fedele. Le strategie principali sono tre: **Docker Compose** per dipendenze infrastrutturali, **Skaffold/Tilt** per il live reload su un cluster Kubernetes locale, **Devcontainer** per ambienti di sviluppo riproducibili e zero-setup.

**Quando usare Docker Compose:** sviluppo quotidiano su un singolo servizio, dipendenze infrastrutturali (DB, Kafka, Redis) ma non Kubernetes-specifiche. Rapido da avviare, overhead basso, ideale per unit/integration test.

**Quando usare Skaffold/Tilt:** il servizio dipende da feature Kubernetes native (ConfigMap, Secrets, RBAC, Sidecar injection), oppure si vuole validare il comportamento nel cluster prima del merge. Overhead maggiore, feedback più fedele all'ambiente production-like.

**Quando usare Devcontainer:** onboarding di nuovi developer, team distribuiti, ambienti standardizzati che devono essere identici su Windows/Mac/Linux senza "works on my machine".

---

## Concetti Chiave

!!! note "Inner Loop vs Outer Loop"
    **Inner Loop**: modifica codice → build → run → test → repeat. Tutto prima del commit. Deve essere il più veloce possibile: target < 5 secondi per il ciclo completo.

    **Outer Loop**: commit → push → CI → review → merge → deploy. Coinvolge il team e sistemi automatici. La velocità è importante ma la correttezza è prioritaria.

!!! note "Local Development Parity"
    Il principio di *development-production parity* (12-factor app) richiede che l'ambiente locale sia il più simile possibile alla produzione. Non deve essere identico (sarebbe troppo costoso), ma le differenze devono essere conosciute e documentate. Sorprese in production che non si replicano in locale sono il sintomo principale di scarsa parity.

!!! warning "Il costo nascosto del setup manuale"
    Un ambiente di sviluppo che richiede 4+ ore per essere configurato su una macchina nuova è un debito tecnico reale. Non solo rallenta l'onboarding: degrada silenziosamente perché le istruzioni nel README diventano obsolete nel tempo. Devcontainer e script di setup automatizzati sono l'investimento, non il lusso.

!!! tip "Separare le dipendenze infrastrutturali dal codice"
    Le configurazioni Docker Compose e Devcontainer devono vivere nel repository del servizio, non in un repo esterno. Questo garantisce che la configurazione locale sia sincronizzata con il codice: se introduci una nuova dipendenza (es. Redis), aggiorni `docker-compose.dev.yml` nello stesso commit.

---

## Ambiente Locale con Docker Compose

### Struttura Consigliata

Per un microservizio tipico, il file `docker-compose.dev.yml` gestisce le **sole dipendenze infrastrutturali** — non il servizio stesso, che gira nel processo del developer per abilitare il debug nativo.

```yaml
# docker-compose.dev.yml — dipendenze infrastrutturali per sviluppo locale
# Il servizio applicativo NON è qui: gira nel processo del developer (mvn spring-boot:run, go run ., etc.)

version: "3.9"

services:
  # ── PostgreSQL ────────────────────────────────────────────────────────────
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: dev
      POSTGRES_PASSWORD: dev
      POSTGRES_DB: orders_dev
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./scripts/db/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U dev -d orders_dev"]
      interval: 5s
      timeout: 5s
      retries: 10

  # ── Kafka (KRaft mode, no Zookeeper) ─────────────────────────────────────
  kafka:
    image: confluentinc/cp-kafka:7.6.0
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@localhost:9093
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: "true"
      CLUSTER_ID: "MkU3OEVBNTcwNTJENDM2Qk"
    ports:
      - "9092:9092"
    healthcheck:
      test: ["CMD", "kafka-broker-api-versions", "--bootstrap-server", "localhost:9092"]
      interval: 10s
      timeout: 10s
      retries: 10

  # ── Redis ─────────────────────────────────────────────────────────────────
  redis:
    image: redis:7-alpine
    command: redis-server --save "" --appendonly no  # no persistence in dev
    ports:
      - "6379:6379"

  # ── Kafka UI (opzionale, utile per debug) ─────────────────────────────────
  kafka-ui:
    image: provectuslabs/kafka-ui:latest
    depends_on:
      kafka:
        condition: service_healthy
    environment:
      KAFKA_CLUSTERS_0_NAME: local
      KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS: kafka:9092
    ports:
      - "8080:8080"

volumes:
  postgres_data:
```

### Makefile per Workflow Standard

```makefile
# Makefile — comandi standard per il developer
.PHONY: dev-up dev-down dev-logs dev-reset run test test-integration

## Avvia le dipendenze infrastrutturali
dev-up:
	docker compose -f docker-compose.dev.yml up -d
	@echo "Waiting for services to be healthy..."
	docker compose -f docker-compose.dev.yml wait postgres kafka redis

## Ferma e rimuove i container (preserva i volumi)
dev-down:
	docker compose -f docker-compose.dev.yml down

## Ferma e rimuove container + volumi (reset completo)
dev-reset:
	docker compose -f docker-compose.dev.yml down -v
	docker compose -f docker-compose.dev.yml up -d

## Log in tempo reale
dev-logs:
	docker compose -f docker-compose.dev.yml logs -f

## Avvia il servizio applicativo (esempio Spring Boot)
run: dev-up
	./mvnw spring-boot:run -Dspring-boot.run.profiles=local

## Test unitari (no dipendenze esterne)
test:
	./mvnw test -Dgroups="unit"

## Test di integrazione (richiedono dev-up)
test-integration: dev-up
	./mvnw test -Dgroups="integration"
```

---

## Inner Loop su Kubernetes con Skaffold e Tilt

### Quando Kubernetes Locale è Necessario

Docker Compose non è sufficiente quando:
- Il servizio usa **ConfigMap/Secret Kubernetes nativi** come sorgente di configurazione
- Ci sono **Sidecar injection** (Istio Envoy, Vault Agent, OpenTelemetry Collector)
- Si vuole testare **RBAC, NetworkPolicy, ResourceQuota** del servizio stesso
- Il servizio usa **Kubernetes API** direttamente (operators, controllers)

Per questi casi, il cluster locale può essere `kind`, `minikube`, o `k3d`.

### Skaffold — Configurazione Base

```yaml
# skaffold.yaml — inner loop su Kubernetes locale
apiVersion: skaffold/v4beta11
kind: Config
metadata:
  name: order-service

build:
  artifacts:
    - image: order-service
      docker:
        dockerfile: Dockerfile.dev   # Dockerfile ottimizzato per dev (no multi-stage finale)
      sync:
        # Hot reload: copia i file modificati nel container senza rebuild
        infer:
          - "src/**/*.java"
          - "src/**/*.go"
      hooks:
        after:
          - command: ["./scripts/wait-for-startup.sh"]
            container: true

deploy:
  kubectl:
    manifests:
      - k8s/dev/**/*.yaml   # manifest specifici per dev (risorse ridotte, debug abilitato)

portForward:
  - resourceType: service
    resourceName: order-service
    port: 8080
    localPort: 8080
  - resourceType: service
    resourceName: postgres
    port: 5432
    localPort: 5432

profiles:
  - name: debug
    activation:
      - command: debug
    patches:
      - op: add
        path: /build/artifacts/0/docker/buildArgs
        value:
          DEBUG_PORT: "5005"
```

```bash
# Comandi Skaffold quotidiani
skaffold dev                     # inner loop: watch + rebuild + redeploy automatico
skaffold dev --port-forward       # + port-forward automatico
skaffold debug                    # inner loop con debugger remoto abilitato (JDWP per Java)
skaffold run                      # deploy one-shot (no watch)
skaffold delete                   # rimuovi risorse dal cluster
```

### Tilt — Alternativa con UI

Tilt offre una web UI integrata per visualizzare lo stato di tutti i servizi e gli ultimi log. È preferibile a Skaffold quando si lavora su **più microservizi in parallelo** e si vuole visibilità aggregata.

```python
# Tiltfile — configurazione per un singolo servizio
# Sintassi: Python-like (Starlark)

# Build dell'immagine Docker con live update
docker_build(
    'order-service',
    '.',
    dockerfile='Dockerfile.dev',
    live_update=[
        # Sincronizza i file compilati senza rebuild completo
        sync('./target/classes', '/app/classes'),
        # Esegui un comando nel container dopo la sync
        run('touch /app/trigger-reload'),
    ]
)

# Deploy dei manifest Kubernetes
k8s_yaml(kustomize('./k8s/dev'))

# Configura port-forward e label nella UI
k8s_resource(
    'order-service',
    port_forwards=['8080:8080', '5005:5005'],
    labels=['services']
)

# Dipendenze infrastrutturali via Helm
helm_resource(
    'postgres',
    'bitnami/postgresql',
    flags=['--set', 'auth.postgresPassword=dev'],
    labels=['infra']
)
```

---

## Devcontainer — Ambienti Riproducibili

### Struttura del .devcontainer

```
.devcontainer/
├── devcontainer.json    # configurazione principale
├── Dockerfile           # immagine base personalizzata (opzionale)
└── scripts/
    └── postCreate.sh    # setup eseguito una volta dopo la creazione
```

```json
// .devcontainer/devcontainer.json
{
  "name": "Order Service Dev",
  "image": "mcr.microsoft.com/devcontainers/java:21-bullseye",

  // Feature standardizzate — aggiungono strumenti senza Dockerfile custom
  "features": {
    "ghcr.io/devcontainers/features/docker-in-docker:2": {},
    "ghcr.io/devcontainers/features/kubectl-helm-minikube:1": {
      "version": "1.29",
      "helm": "3.14"
    },
    "ghcr.io/devcontainers/features/java:1": {
      "version": "21",
      "jdkDistro": "ms"
    }
  },

  // Mount del Docker socket host (alternativa a Docker-in-Docker)
  "mounts": [
    "source=/var/run/docker.sock,target=/var/run/docker.sock,type=bind"
  ],

  // Estensioni VS Code pre-installate nel devcontainer
  "customizations": {
    "vscode": {
      "extensions": [
        "vmware.vscode-spring-boot",
        "redhat.java",
        "ms-kubernetes-tools.vscode-kubernetes-tools",
        "hashicorp.terraform",
        "sonarsource.sonarlint-vscode"
      ],
      "settings": {
        "java.configuration.updateBuildConfiguration": "automatic",
        "editor.formatOnSave": true
      }
    }
  },

  // Comandi lifecycle
  "postCreateCommand": ".devcontainer/scripts/postCreate.sh",
  "postStartCommand": "docker compose -f docker-compose.dev.yml up -d",

  // Port forward automatico
  "forwardPorts": [8080, 5432, 9092, 6379],

  "remoteUser": "vscode"
}
```

```bash
#!/bin/bash
# .devcontainer/scripts/postCreate.sh — eseguito una sola volta alla creazione

set -euo pipefail

echo "=== Setting up Order Service dev environment ==="

# Installa dipendenze del progetto
./mvnw dependency:go-offline -q

# Configura git hooks (conventional commits, etc.)
npm install --prefix .husky

# Configura variabili d'ambiente locali
cp .env.example .env.local

# Pre-scarica immagini Docker per velocizzare il primo avvio
docker compose -f docker-compose.dev.yml pull

echo "=== Setup complete. Run 'make dev-up && make run' to start. ==="
```

---

## Branch Strategy

### Trunk-Based Development (Raccomandato per Microservizi)

```
main (trunk)
  │
  ├── commit A (feature piccola, diretta su main)
  │
  ├── feature/add-payment-method  ← branch vita max 1-2 giorni
  │   ├── commit B
  │   └── commit C
  │   └── PR → main (squash merge o merge commit)
  │
  ├── commit D (hotfix diretto)
  │
  └── release/1.2.0  ← branch di release, creato DOPO il tag, solo per hotfix
```

**TBD è la scelta giusta per microservizi** perché:
- Ogni servizio è deployato indipendentemente: non serve coordinare i branch tra team
- I feature flag gestiscono il disaccoppiamento integrazione/rilascio
- CI/CD è più semplice: c'è un solo branch di riferimento

### Gitflow — Quando Ha Senso

Gitflow mantiene senso in scenari specifici per microservizi:
- **Rilasci coordinati** tra più servizi con finestre di maintenance
- **Clienti enterprise** che richiedono versioni LTS con backport di security fix
- **SDK/librerie condivise** con semver rigoroso e cicli di deprecazione

```
# Gitflow per librerie condivise (non per servizi deployati continuamente)
main          → codice production
develop       → integrazione feature in corso
feature/xxx   → singola feature
release/1.x   → branch di stabilizzazione prima del tag
hotfix/xxx    → fix urgenti su main
```

!!! warning "Gitflow sui microservizi genera integration hell"
    Applicare Gitflow a un microservizio deployato 10 volte al giorno porta a merge conflict frequenti tra `feature` branches di lunga durata. Il costo di integrazione supera il beneficio di isolamento. Usa feature flags invece dei long-lived branches.

### Conventional Commits e Semantic-Release

```bash
# Formato conventional commits
<type>(<scope>): <descrizione imperativa>

# Tipi riconosciuti da semantic-release
feat:     → bump MINOR (1.X.0)  — nuova funzionalità
fix:      → bump PATCH (1.0.X)  — bugfix
perf:     → bump PATCH          — miglioramento performance
refactor: → nessun bump         — refactoring senza comportamento nuovo
test:     → nessun bump
docs:     → nessun bump
ci:       → nessun bump
chore:    → nessun bump

# Breaking change → bump MAJOR (X.0.0)
feat!: rimuovi endpoint v1 dell'API

# Esempio con scope
feat(payment): aggiungi supporto PayPal
fix(auth): correggi validazione JWT scaduto
perf(db): ottimizza query ordini con indice composito
```

```javascript
// .releaserc.json — configurazione semantic-release
{
  "branches": ["main"],
  "plugins": [
    "@semantic-release/commit-analyzer",
    "@semantic-release/release-notes-generator",
    ["@semantic-release/changelog", {
      "changelogFile": "CHANGELOG.md"
    }],
    ["@semantic-release/exec", {
      // Aggiorna la versione nel pom.xml / go.mod / pyproject.toml
      "prepareCmd": "mvn versions:set -DnewVersion=${nextRelease.version} -DgenerateBackupPoms=false"
    }],
    ["@semantic-release/git", {
      "assets": ["CHANGELOG.md", "pom.xml"],
      "message": "chore(release): ${nextRelease.version} [skip ci]"
    }],
    "@semantic-release/github"
  ]
}
```

```bash
# Setup husky + commitlint per validare i commit in locale
npm install --save-dev husky @commitlint/cli @commitlint/config-conventional

# .husky/commit-msg
#!/bin/sh
npx --no-install commitlint --edit "$1"

# commitlint.config.js
module.exports = { extends: ['@commitlint/config-conventional'] }
```

---

## Pull Request Workflow

### Checklist PR per Microservizi

Una PR su un microservizio deve rispondere a queste domande prima del merge:

```markdown
## Checklist PR — Order Service

### Funzionalità
- [ ] Il comportamento descrito nella task è implementato
- [ ] I casi limite (empty input, null, overflow) sono gestiti
- [ ] I log sono informativi ma non verbosi (no PII nei log)

### Testing
- [ ] Unit test per nuova logica (coverage >= 80% sulle righe modificate)
- [ ] Integration test con Testcontainers per nuove query DB
- [ ] Contract test Pact aggiornato se l'API è cambiata

### API Contract (se applicabile)
- [ ] OpenAPI spec aggiornata (se REST)
- [ ] Schema Avro/JSON aggiornato e versione bumped (se Kafka)
- [ ] Breaking changes documentate e gestite (deprecation, versioning)

### Security
- [ ] Nessuna secret hardcoded (secret scan automatico in CI)
- [ ] Input validati prima dell'uso (no SQL injection, XSS)
- [ ] Dipendenze nuove senza CVE critici/alti (OWASP Dependency Check)

### Performance
- [ ] Nessuna N+1 query introdotta (verificare con slow query log in test)
- [ ] Nessuna allocazione evitabile in hot path
- [ ] Se si usa una cache: invalidazione corretta documentata

### Operabilità
- [ ] Health check / readiness probe ancora funzionante
- [ ] Metriche Prometheus esposte per le nuove funzionalità rilevanti
- [ ] Feature flag aggiunto se la feature non è safe-to-release immediatamente
```

### Regole di Merge

```yaml
# Branch protection rules (GitHub) — esempio
required_status_checks:
  - build
  - test-unit
  - test-integration
  - security-scan (Trivy + Dependency Check)
  - contract-tests (Pact)

required_pull_request_reviews:
  required_approving_review_count: 1
  dismiss_stale_reviews: true
  require_code_owner_reviews: true  # CODEOWNERS per aree critiche

# Merge strategy per microservizi: squash merge
# → 1 commit per PR su main → history lineare → semantic-release funziona correttamente
merge_commit_allowed: false
squash_merge_allowed: true
rebase_merge_allowed: false
```

---

## Shift-Left Testing

### La Piramide del Testing per Microservizi

```
                    ▲
                   /E2E\        ← pochi, lenti, costo alto
                  /─────\         (Selenium, Cypress, k6)
                 /Contrat-\
                / to (Pact) \  ← verifica il contratto tra servizi
               /─────────────\   (consumer-driven, veloci)
              / Integration   \
             / (Testcontainers) \ ← dipendenze reali in container
            /───────────────────\  (PostgreSQL, Kafka, Redis)
           /    Unit Tests        \
          /─────────────────────────\ ← veloci, nessuna dipendenza esterna
         ▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔
```

### Testcontainers — Integration Test

```java
// Java — Integration test con Testcontainers
@SpringBootTest
@Testcontainers
class OrderRepositoryIntegrationTest {

    @Container
    static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:16-alpine")
        .withDatabaseName("orders_test")
        .withUsername("test")
        .withPassword("test");

    @Container
    static KafkaContainer kafka = new KafkaContainer(
        DockerImageName.parse("confluentinc/cp-kafka:7.6.0")
    );

    // Spring configura automaticamente il datasource con i valori del container
    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", postgres::getJdbcUrl);
        registry.add("spring.datasource.username", postgres::getUsername);
        registry.add("spring.datasource.password", postgres::getPassword);
        registry.add("spring.kafka.bootstrap-servers", kafka::getBootstrapServers);
    }

    @Autowired
    private OrderRepository orderRepository;

    @Test
    void shouldPersistAndRetrieveOrder() {
        var order = new Order(UUID.randomUUID(), "customer-1", BigDecimal.valueOf(99.99));
        orderRepository.save(order);

        var found = orderRepository.findById(order.getId());
        assertThat(found).isPresent();
        assertThat(found.get().getAmount()).isEqualByComparingTo(BigDecimal.valueOf(99.99));
    }
}
```

```go
// Go — Integration test con Testcontainers
func TestOrderRepository_Integration(t *testing.T) {
    if testing.Short() {
        t.Skip("skipping integration test")
    }

    ctx := context.Background()

    pgContainer, err := postgres.RunContainer(ctx,
        testcontainers.WithImage("postgres:16-alpine"),
        postgres.WithDatabase("orders_test"),
        postgres.WithUsername("test"),
        postgres.WithPassword("test"),
        testcontainers.WithWaitStrategy(
            wait.ForLog("database system is ready to accept connections").
                WithOccurrence(2).WithStartupTimeout(30*time.Second),
        ),
    )
    require.NoError(t, err)
    t.Cleanup(func() { pgContainer.Terminate(ctx) })

    connStr, _ := pgContainer.ConnectionString(ctx, "sslmode=disable")
    db, _ := sqlx.Connect("postgres", connStr)

    repo := NewOrderRepository(db)
    order := &Order{ID: uuid.New(), CustomerID: "c1", Amount: 99.99}

    err = repo.Save(ctx, order)
    require.NoError(t, err)

    found, err := repo.FindByID(ctx, order.ID)
    require.NoError(t, err)
    assert.Equal(t, order.Amount, found.Amount)
}
```

### Pact — Contract Testing

```java
// Consumer side — definisce il contratto atteso
@ExtendWith(PactConsumerTestExt.class)
@PactTestFor(providerName = "inventory-service", port = "8082")
class OrderServiceConsumerPactTest {

    @Pact(consumer = "order-service")
    public RequestResponsePact getProductAvailability(PactDslWithProvider builder) {
        return builder
            .given("product P1 exists with 10 units available")
            .uponReceiving("a request for product P1 availability")
                .path("/api/v1/products/P1/availability")
                .method("GET")
            .willRespondWith()
                .status(200)
                .body(new PactDslJsonBody()
                    .stringValue("productId", "P1")
                    .integerType("availableUnits", 10)
                    .booleanValue("inStock", true))
            .toPact();
    }

    @Test
    @PactTestFor(pactMethod = "getProductAvailability")
    void shouldFetchProductAvailability(MockServer mockServer) {
        var client = new InventoryClient(mockServer.getUrl());
        var availability = client.getAvailability("P1");

        assertThat(availability.isInStock()).isTrue();
        assertThat(availability.getAvailableUnits()).isGreaterThan(0);
    }
}
```

---

## Feature Toggles nel Workflow

### Integrazione Feature Flag nel Ciclo di Sviluppo

I feature toggle sono il meccanismo che disaccoppia il deployment dal release. Permettono di integrare codice incompleto su `main` senza esporlo agli utenti.

```java
// Feature toggle con Unleash (self-hosted) o LaunchDarkly
@Service
public class OrderService {

    private final Unleash unleash;
    private final OldPaymentProcessor oldProcessor;
    private final NewPaymentProcessor newProcessor;

    public PaymentResult processPayment(Order order) {
        // Toggle granulare: attivo solo per certi utenti/tenant durante rollout
        if (unleash.isEnabled("new-payment-processor",
                new UnleashContext.Builder()
                    .userId(order.getCustomerId())
                    .build())) {
            return newProcessor.process(order);
        }
        return oldProcessor.process(order);
    }
}
```

```yaml
# Ciclo di vita di un feature toggle
# 1. Introduce il toggle con la feature nascosta
# 2. Deploy → 0% utenti vedono la feature
# 3. Gradual rollout: 5% → 20% → 50% → 100%
# 4. Remove toggle: cleanup del codice, elimina il branch morto

# Regola: ogni toggle deve avere una data di scadenza nel commento
# // TODO(2026-06-01): remove NEW_PAYMENT_PROCESSOR toggle after full rollout
```

!!! warning "Debito tecnico dei feature toggle"
    Ogni toggle non rimosso è dead code condizionale che aumenta la complessità cognitiva. Imposta una scadenza esplicita per ogni toggle e metti il cleanup nel backlog. Un toggle scaduto è un bug in attesa di manifestarsi.

!!! tip "Feature toggle per testing in produzione"
    I feature toggle permettono anche il **canary testing in produzione**: il toggle viene attivato per un sottoinsieme di utenti reali, si osservano metriche e error rate, e si fa rollback immediato se qualcosa va storto — senza richiedere un re-deploy.

---

## Best Practices

### Inner Loop
- Tieni il ciclo modifica→feedback sotto i **5 secondi** per hot reload, sotto i 30 secondi per rebuild completo
- Usa **layer caching Docker** aggressivo: installa dipendenze in uno step separato dal codice sorgente
- Configura **live reload nativo** del framework (Spring DevTools, Air per Go, watchexec) invece di riavviare il processo manualmente
- Mantieni un file `.env.local` non tracciato da git per le variabili che variano per developer (credenziali, endpoint locali)

### Git e Commit
- **Un commit = una cosa**: non mescolare refactoring con nuove feature nello stesso commit
- Esegui `git add -p` (patch mode) per committare solo le modifiche rilevanti, non tutti i file modificati
- Il messaggio di commit deve rispondere a "**perché** è stata fatta questa modifica", non "cosa fa" (il codice mostra già il cosa)

### Pull Request
- **PR piccole**: massimo 400 linee cambiate. PR grandi sono costose da revieware e tendono ad essere mergate senza review seria
- Includi sempre un **test che prima fallisce** nelle PR di bugfix — prova che il bug esiste e che il fix lo risolve
- Usa i **draft PR** per visibilità anticipata: apri la PR come draft appena inizi il lavoro, così il team vede cosa stai facendo

### Testing
- I test **unitari** devono essere deterministici e **senza I/O**: nessun file system, nessun network, nessun clock reale
- I test **di integrazione** con Testcontainers devono essere taggati e separati dagli unit test (possono richiedere 30-60s)
- Non testare i dettagli di implementazione: testa il **comportamento osservabile** (input → output), non i metodi privati

---

## Troubleshooting

### Docker Compose — Container non si avvia

**Sintomo:** `docker compose up` mostra container in `Exit 1` o `unhealthy`.

**Causa frequente:** porta già occupata da un'altra istanza, o healthcheck fallisce perché il DB impiega troppo.

```bash
# Diagnosi
docker compose -f docker-compose.dev.yml ps         # stato di tutti i container
docker compose -f docker-compose.dev.yml logs kafka  # log di un container specifico
lsof -i :5432                                        # chi usa la porta 5432

# Fix: forza la rimozione e ricrea
docker compose -f docker-compose.dev.yml down -v
docker compose -f docker-compose.dev.yml up -d --force-recreate
```

### Skaffold — Rebuild troppo lento

**Sintomo:** ogni salvataggio file scatena un rebuild completo da zero (5+ minuti).

**Causa:** il Dockerfile non ha layer caching per le dipendenze, o la `sync` non è configurata.

```yaml
# skaffold.yaml — aggiungi sync per i file sorgente
build:
  artifacts:
    - image: order-service
      sync:
        manual:
          - src: "src/**/*.java"
            dest: /app/src
            strip: src/
      local:
        useBuildkit: true        # abilita BuildKit per caching
        concurrency: 0           # usa tutti i core disponibili
```

### Conventional Commits — commitlint rifiuta il commit

**Sintomo:** `husky` blocca il commit con `⧗ input: feat add new feature` → `✖ subject may not be empty`.

**Causa:** formato errato (spazio mancante, tipo non riconosciuto, subject vuoto dopo i due punti).

```bash
# Diagnosi: valida manualmente il messaggio
echo "feat: add payment validation" | npx commitlint

# Pattern corretti
feat: add payment validation
fix(auth): handle expired JWT correctly
feat!: remove deprecated v1 endpoints  # breaking change

# Pattern errati — commitlint rifiuta
feat add payment         # mancano i due punti
Feature: add payment     # tipo con maiuscola
feat:add payment         # manca spazio dopo i due punti
```

### Testcontainers — test lenti in CI

**Sintomo:** i test di integrazione impiegano 10+ minuti in CI perché ogni test avvia nuovi container.

**Causa:** i container vengono ricreati per ogni classe di test invece di essere riusati.

```java
// Fix: usa Singleton Container pattern
// Classe base condivisa — i container sono avviati una volta sola per JVM
abstract class AbstractIntegrationTest {

    static final PostgreSQLContainer<?> POSTGRES;
    static final KafkaContainer KAFKA;

    static {
        POSTGRES = new PostgreSQLContainer<>("postgres:16-alpine")
            .withReuse(true);  // riusa il container tra run diverse (Testcontainers Desktop)
        KAFKA = new KafkaContainer(DockerImageName.parse("confluentinc/cp-kafka:7.6.0"))
            .withReuse(true);

        POSTGRES.start();
        KAFKA.start();
    }

    @DynamicPropertySource
    static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", POSTGRES::getJdbcUrl);
        registry.add("spring.kafka.bootstrap-servers", KAFKA::getBootstrapServers);
    }
}
```

### Feature Toggle — comportamento inconsistente tra ambienti

**Sintomo:** la feature funziona in staging ma non in produzione (o viceversa), pur avendo lo stesso codice.

**Causa:** lo stato del toggle è diverso tra ambienti, oppure il contesto utente passato alla valutazione è diverso.

```bash
# Diagnosi: verifica lo stato del toggle su Unleash
curl -H "Authorization: *:development.secret" \
  "https://unleash.internal/api/admin/features/new-payment-processor"

# Verifica anche i segmenti e le strategie per ambiente:
# - "gradual rollout" con seed diverso tra ambienti può dare risultati diversi
# - "user with id" richiede che userId sia popolato correttamente nel contesto
```

---

## Relazioni

??? info "CI/CD Pipeline — L'outer loop"
    Il workflow del developer termina al push. Da lì, la pipeline CI/CD prende in carico: build, test, security scan, deploy. → [Pipeline CI/CD](../../ci-cd/pipeline.md)

??? info "Trunk-Based Development — Approfondimento"
    La strategia di branching consigliata per microservizi, con feature flags, branch by abstraction, e continuous integration. → [Trunk-Based Development](../../ci-cd/strategie/trunk-based-development.md)

??? info "Contract Testing — Pact in dettaglio"
    Consumer-driven contract testing con Pact Broker, verifica automatica in CI, e gestione delle breaking changes. → [Contract Testing](../../ci-cd/testing/contract-testing.md)

??? info "Docker Compose — Riferimento completo"
    Networking, volumi, health check, e pattern avanzati di Compose per sviluppo e testing. → [Docker Compose](../../containers/docker/compose.md)

??? info "Testing — Strategia completa"
    Testing unitario, di integrazione, e chaos engineering per microservizi. → [Testing](../testing/_index.md)

---

## Riferimenti

- [Skaffold Documentation](https://skaffold.dev/docs/) — configurazione dettagliata, pipeline di build, profili
- [Tilt Documentation](https://docs.tilt.dev/) — Tiltfile API reference, live update
- [Devcontainers Specification](https://containers.dev/) — spec ufficiale, feature catalog
- [Conventional Commits](https://www.conventionalcommits.org/) — specifica formato commit
- [semantic-release](https://semantic-release.gitbook.io/) — rilascio automatizzato basato su conventional commits
- [Testcontainers](https://testcontainers.com/) — librerie per Java, Go, Python, Node.js
- [Pact Documentation](https://docs.pact.io/) — consumer-driven contract testing
- [Unleash Feature Toggle](https://docs.getunleash.io/) — feature management self-hosted
- [Martin Fowler — Feature Toggles](https://martinfowler.com/articles/feature-toggles.html) — guida definitiva ai tipi di toggle
- [Google Engineering Practices — Code Review](https://google.github.io/eng-practices/review/) — standard per PR review
