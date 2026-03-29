"""
Batch 4 — Sezione docs/dev/ (Sviluppo Microservizi)
18 task che coprono linguaggi, runtime tuning, integrazioni, sicurezza da codice,
resilienza da codice e processi enterprise.

Prospettiva: developer e PM tecnico, NON ops/infrastruttura.
Cross-reference verso sezioni esistenti per evitare ripetizioni.
"""

import yaml
from pathlib import Path
from datetime import datetime, timezone

STATE_FILE = Path(__file__).parent / "state.yaml"

with open(STATE_FILE, encoding="utf-8") as f:
    state = yaml.safe_load(f)

existing_paths = {item["path"] for item in state.get("queue", [])}

tasks = [
    # ── P1: Landing page ──────────────────────────────────────────────────────
    {
        "id": "401",
        "type": "new_topic",
        "path": "docs/dev/_index.md",
        "category": "dev",
        "priority": "P1",
        "status": "pending",
        "reason": (
            "Landing page della nuova sezione Sviluppo Microservizi. "
            "Panoramica della sezione, mappa di lettura per developer (linguaggio -> runtime -> integrazioni -> resilienza), "
            "differenza prospettiva developer vs ops (questa sezione) vs infrastruttura (containers/, security/, monitoring/). "
            "Creare anche docs/dev/.pages con navigazione delle sottocategorie."
        ),
        "worth_if": "Qualsiasi developer che costruisce microservizi su Kubernetes",
        "skip_if": "Se docs/dev/_index.md esiste gia'"
    },
    # ── P2: Linguaggi ─────────────────────────────────────────────────────────
    {
        "id": "402",
        "type": "new_topic",
        "path": "docs/dev/linguaggi/java-spring-boot.md",
        "category": "dev",
        "priority": "P2",
        "status": "pending",
        "reason": (
            "Spring Boot 3.x per microservizi Kubernetes: "
            "application.yml con Spring profiles e Spring Cloud Kubernetes config, "
            "@ConfigurationProperties, Actuator (health separati readiness/liveness, metriche Prometheus), "
            "Testcontainers per integration test, layered jar e Buildpacks per immagini ottimali, "
            "bootstrap con Spring Initializr. "
            "Related: docs/dev/runtime/jvm-tuning.md, docs/messaging/kafka/sviluppo/spring-kafka.md, "
            "docs/dev/resilienza/circuit-breaker.md."
        ),
        "worth_if": "Java developer che porta Spring Boot in Kubernetes",
        "skip_if": "Non pertinente - sviluppo Kafka Spring gia' coperto in messaging/"
    },
    {
        "id": "403",
        "type": "new_topic",
        "path": "docs/dev/linguaggi/java-quarkus.md",
        "category": "dev",
        "priority": "P2",
        "status": "pending",
        "reason": (
            "Quarkus cloud-native: differenze architetturali con Spring Boot (fast startup <50ms, low memory), "
            "native build con GraalVM e limitazioni, dev mode con live reload, "
            "CDI e MicroProfile (Health, Metrics, OpenAPI, Fault Tolerance), "
            "RESTEasy Reactive, Panache ORM, estensioni Quarkus principali. "
            "Quando scegliere Quarkus vs Spring: serverless, edge, Lambda. "
            "Related: docs/dev/linguaggi/java-spring-boot.md, docs/dev/runtime/jvm-tuning.md, "
            "docs/messaging/kafka/sviluppo/quarkus-kafka.md."
        ),
        "worth_if": "Java developer che valuta Quarkus per ambienti resource-constrained o serverless",
        "skip_if": "Solo se esiste gia' un file quarkus dedicato"
    },
    {
        "id": "404",
        "type": "new_topic",
        "path": "docs/dev/linguaggi/dotnet.md",
        "category": "dev",
        "priority": "P2",
        "status": "pending",
        "reason": (
            "ASP.NET Core 8+ per microservizi: Minimal API vs Controller pattern (quando usare quale), "
            "DI built-in e lifetime (Singleton/Scoped/Transient) per microservizi, "
            "IHostedService e BackgroundService per worker, "
            ".NET Aspire per orchestrazione locale, "
            "IConfiguration con appsettings/env vars/K8s ConfigMap, "
            "HealthChecks API built-in (AddCheck, MapHealthChecks, UI), "
            "gRPC con protobuf, Dockerfile multi-stage ottimale .NET. "
            "Related: docs/dev/runtime/resource-tuning.md, docs/dev/resilienza/health-checks.md, "
            "docs/dev/sicurezza/tls-da-codice.md, docs/dev/resilienza/circuit-breaker.md."
        ),
        "worth_if": "C# developer che costruisce microservizi per Kubernetes",
        "skip_if": "Non pertinente"
    },
    {
        "id": "405",
        "type": "new_topic",
        "path": "docs/dev/linguaggi/go.md",
        "category": "dev",
        "priority": "P2",
        "status": "pending",
        "reason": (
            "Go per microservizi: vantaggi (startup <10ms, footprint <15MB, goroutine), "
            "framework HTTP (Gin, Echo, Fiber — confronto), "
            "structured logging con slog (stdlib Go 1.21+) e zerolog, "
            "context propagation e cancellation (context.Context idiomatico), "
            "graceful shutdown con signal.NotifyContext, "
            "gRPC con protoc-gen-go, "
            "config via viper, "
            "testing idiomatico (table-driven, testify, mocking con interfaces). "
            "GOMAXPROCS e containerizzazione (uber-go/automaxprocs). "
            "Related: docs/dev/runtime/resource-tuning.md, docs/networking/protocolli/grpc.md, "
            "docs/dev/resilienza/health-checks.md."
        ),
        "worth_if": "Developer che sceglie Go per servizi ad alta concorrenza, bassa latenza o footprint minimo",
        "skip_if": "Non pertinente"
    },
    {
        "id": "418",
        "type": "new_topic",
        "path": "docs/dev/linguaggi/python.md",
        "category": "dev",
        "priority": "P3",
        "status": "pending",
        "reason": (
            "Python per microservizi: FastAPI (async, Pydantic v2, OpenAPI auto, Depends DI), "
            "deployment Uvicorn/Gunicorn con worker multipli, "
            "async/await e event loop (asyncio), "
            "database async (SQLAlchemy 2 async, asyncpg, Motor per MongoDB), "
            "GIL e implicazioni per CPU-bound vs I/O-bound, "
            "containerizzazione (workers per container, memoria per worker), "
            "quando Python e' appropriato vs Java/Go. "
            "Related: docs/dev/linguaggi/go.md, docs/dev/integrazioni/database-patterns.md."
        ),
        "worth_if": "Python developer che porta FastAPI/Django in Kubernetes o sceglie tra linguaggi per un nuovo servizio",
        "skip_if": "Non pertinente"
    },
    # ── P2: Runtime/Tuning ────────────────────────────────────────────────────
    {
        "id": "406",
        "type": "new_topic",
        "path": "docs/dev/runtime/jvm-tuning.md",
        "category": "dev",
        "priority": "P2",
        "status": "pending",
        "reason": (
            "JVM in container Kubernetes: "
            "-XX:MaxRAMPercentage vs -Xmx (container-aware JVM 11+), "
            "scelta GC: G1GC (default, bilanciato), ZGC (latenza sub-ms, Java 21), Shenandoah (Red Hat), "
            "heap sizing formula per microservizi (50-75% RAM limit), "
            "metaspace e codegen cache (-XX:ReservedCodeCacheSize), "
            "profiling con async-profiler e JFR/Mission Control, "
            "OOMKiller: come riconoscerlo (exit code 137) e prevenirlo, "
            "JVM 17 vs 21 per container (Virtual Threads, compact heap). "
            "Confronto JVM vs GraalVM native per startup/memory. "
            "Related: docs/dev/linguaggi/java-spring-boot.md, docs/dev/linguaggi/java-quarkus.md, "
            "docs/containers/kubernetes/resource-management.md."
        ),
        "worth_if": "Java developer o SRE che ottimizza microservizi Spring/Quarkus su Kubernetes",
        "skip_if": "Solo se containers/kubernetes/resource-management.md copre gia' JVM specifico (non lo fa)"
    },
    {
        "id": "407",
        "type": "new_topic",
        "path": "docs/dev/runtime/resource-tuning.md",
        "category": "dev",
        "priority": "P2",
        "status": "pending",
        "reason": (
            "Tuning risorse runtime per linguaggi diversi in container: "
            "GOMAXPROCS per Go (deve matchare CPU limits, automaxprocs), "
            ".NET thread pool sizing (ThreadPool.SetMinThreads, DOTNET_SYSTEM_NET_HTTP_SOCKETSHTTPHANDLER_HTTP3SUPPORT), "
            "Node.js UV_THREADPOOL_SIZE e cluster mode, "
            "Python worker per container (Gunicorn formula: 2*CPU+1). "
            "CPU throttling (CFS bandwidth, --cpu-period), "
            "memory over-commit e OOM, "
            "profiling in produzione: pprof (Go), dotnet-trace (.NET), async-profiler (JVM). "
            "Related: docs/dev/runtime/jvm-tuning.md, docs/containers/kubernetes/resource-management.md."
        ),
        "worth_if": "Dev o SRE che ottimizza microservizi multi-linguaggio in Kubernetes",
        "skip_if": "Solo se completamente coperto da jvm-tuning.md"
    },
    # ── P2: Sicurezza da codice ────────────────────────────────────────────────
    {
        "id": "408",
        "type": "new_topic",
        "path": "docs/dev/sicurezza/tls-da-codice.md",
        "category": "dev",
        "priority": "P2",
        "status": "pending",
        "reason": (
            "TLS/mTLS dalla prospettiva del codice applicativo — DIVERSO da security/pki-certificati/ (infrastruttura): "
            "Java: KeyStore/TrustStore (JKS, PKCS12), SSLContext factory, SSLSocketFactory, "
            "certificato client con HttpClient/RestTemplate/WebClient, hot reload senza restart; "
            ".NET: X509Certificate2, SslStream, HttpClientHandler con ClientCertificates, caricamento da PEM; "
            "Go: tls.Config, x509.CertPool, tls.LoadX509KeyPair, tls.Certificate, "
            "caricamento certificati da volume K8s montato. "
            "Rotation certificati senza restart applicativo, "
            "differenza trust del sistema vs bundle applicativo, "
            "debug TLS (javax.net.debug, SSLKEYLOGFILE). "
            "Related: docs/security/autenticazione/mtls-spiffe.md, docs/security/pki-certificati/cert-manager.md, "
            "docs/networking/fondamentali/tls-ssl-basics.md."
        ),
        "worth_if": "Developer che implementa mTLS tra microservizi o verso servizi esterni con TLS client auth",
        "skip_if": "Solo se security/autenticazione/mtls-spiffe.md copre gia' la parte codice applicativo (non lo fa)"
    },
    {
        "id": "409",
        "type": "new_topic",
        "path": "docs/dev/sicurezza/secrets-config.md",
        "category": "dev",
        "priority": "P2",
        "status": "pending",
        "reason": (
            "ConfigMap e Secrets Kubernetes dalla prospettiva del codice — DIVERSO da security/secret-management/ (ops): "
            "env vars vs volume montati (pro/con, quando usare quale), "
            "hot reload senza restart: Spring Cloud Kubernetes @RefreshScope, "
            ".NET IOptionsMonitor<T> con reload automatico, "
            "viper.WatchConfig (Go); "
            "Vault Agent Sidecar pattern da codice (token renewal, lease); "
            "External Secrets Operator — come appare al developer; "
            "Azure Key Vault SDK, AWS Secrets Manager SDK integration; "
            "Anti-pattern: secret in log (logback masking, .NET sensitive data), "
            "secret in stack trace, secret hard-coded. "
            "Related: docs/security/secret-management/kubernetes-secrets.md, "
            "docs/security/secret-management/vault.md."
        ),
        "worth_if": "Developer che configura microservizi sicuri su Kubernetes con gestione dinamica dei segreti",
        "skip_if": "Solo se kubernetes-secrets.md copre gia' la parte developer"
    },
    # ── P2: Resilienza da codice ───────────────────────────────────────────────
    {
        "id": "410",
        "type": "new_topic",
        "path": "docs/dev/resilienza/circuit-breaker.md",
        "category": "dev",
        "priority": "P2",
        "status": "pending",
        "reason": (
            "Circuit breaker e resilience patterns da codice applicativo: "
            "Resilience4j (Java): @CircuitBreaker, @Retry, @Bulkhead, @RateLimiter, "
            "fallback methods, configurazione @Bean vs properties, "
            "metrics con Micrometer + Prometheus, eventi CBStateTransition; "
            "Polly (.NET): ResiliencePipeline, AddRetry con exponential backoff e jitter, "
            "AddCircuitBreaker, AddTimeout, AddFallback; "
            "go-resilience / sony/gobreaker (Go): configurazione, test con clock stub. "
            "Differenza CB a livello app vs service mesh (Istio/Linkerd) — quando usare quale. "
            "Test con Testcontainers + Toxiproxy. "
            "Related: docs/networking/service-mesh/istio.md, "
            "docs/dev/linguaggi/java-spring-boot.md, docs/dev/linguaggi/dotnet.md."
        ),
        "worth_if": "Developer che costruisce servizi resilienti verso dipendenze esterne potenzialmente instabili",
        "skip_if": "Non pertinente"
    },
    {
        "id": "411",
        "type": "new_topic",
        "path": "docs/dev/resilienza/health-checks.md",
        "category": "dev",
        "priority": "P2",
        "status": "pending",
        "reason": (
            "Health check endpoint da codice e integrazione con Kubernetes probes: "
            "Spring Boot Actuator /actuator/health con readiness/liveness separati (K8s 2.3+), "
            "HealthIndicator custom (DB, Kafka, Redis), "
            "gruppo probes configuration in application.yml; "
            ".NET HealthChecks API: IHealthCheck, AddDbContextCheck, AddRedis, MapHealthChecks; "
            "Go /healthz e /readyz handler idiomatico con goroutine; "
            "Mapping corretto su Kubernetes: readiness (dipendenze), liveness (self), startup (init). "
            "Anti-pattern: liveness probe che chiama DB (causa restart a cascata), "
            "threshold troppo basse. "
            "Related: docs/containers/kubernetes/workloads.md, "
            "docs/dev/linguaggi/java-spring-boot.md, docs/dev/linguaggi/dotnet.md."
        ),
        "worth_if": "Developer che configura correttamente il lifecycle dei propri pod Kubernetes",
        "skip_if": "Non pertinente"
    },
    {
        "id": "412",
        "type": "new_topic",
        "path": "docs/dev/resilienza/observability-code.md",
        "category": "dev",
        "priority": "P2",
        "status": "pending",
        "reason": (
            "OpenTelemetry dalla prospettiva del codice — DIVERSO da monitoring/fondamentali/opentelemetry.md (concettuale): "
            "auto-instrumentation: Java agent (-javaagent), .NET zero-code (OTEL_DOTNET_AUTO_HOME), "
            "Go auto (limitata, configurazione); "
            "manual instrumentation: Tracer.StartSpan, span attributes, span events, status; "
            "context propagation W3C TraceContext tra microservizi HTTP/gRPC/Kafka; "
            "SDK configuration: exporter OTLP (grpc/http), sampling (head/tail), resource attributes; "
            "structured logging correlato con trace_id/span_id (MDC in Java, LogContext in .NET); "
            "Baggage per context cross-cutting. "
            "Related: docs/monitoring/fondamentali/opentelemetry.md, "
            "docs/monitoring/tools/jaeger-tempo.md."
        ),
        "worth_if": "Developer che strumenta microservizi per distributed tracing in produzione",
        "skip_if": "Verifica se monitoring/fondamentali/opentelemetry.md copre gia' instrumentazione da codice"
    },
    # ── P2: Integrazioni ─────────────────────────────────────────────────────
    {
        "id": "413",
        "type": "new_topic",
        "path": "docs/dev/integrazioni/rabbitmq-client.md",
        "category": "dev",
        "priority": "P2",
        "status": "pending",
        "reason": (
            "RabbitMQ da codice — DIVERSO da messaging/rabbitmq/ (operazionale): "
            "Spring AMQP (Java): @RabbitListener, RabbitTemplate, SimpleMessageListenerContainer, "
            "configurazione DirectExchange/TopicExchange/FanoutExchange via @Bean, "
            "messaggi come POJO con Jackson2JsonMessageConverter; "
            "MassTransit (.NET): IConsumer<T>, IBus.Publish/Send, Request/Response, "
            "saga state machine (SagaStateMachine), integrazione DI ASP.NET Core; "
            "amqp091-go (Go): Channel.Consume con goroutine, ack manuale, reconnect handler. "
            "Prefetch count, acknowledgement manuale, dead letter queue da codice, "
            "connection recovery automatica. "
            "Related: docs/messaging/rabbitmq/architettura.md, "
            "docs/messaging/rabbitmq/affidabilita.md."
        ),
        "worth_if": "Developer che integra microservizi con RabbitMQ",
        "skip_if": "Solo se messaging/rabbitmq/ copre gia' la parte client/developer"
    },
    {
        "id": "414",
        "type": "new_topic",
        "path": "docs/dev/integrazioni/database-patterns.md",
        "category": "dev",
        "priority": "P2",
        "status": "pending",
        "reason": (
            "Pattern di accesso ai database da microservizi — prospettiva developer/ORM: "
            "JPA/Hibernate (Java): N+1 query (EntityGraph, JOIN FETCH), lazy loading pitfall, "
            "@Transactional boundaries e propagation, second-level cache, "
            "Spring Data JPA Repository; "
            "Entity Framework Core (.NET): DbContext lifetime in DI (AddDbContext vs AddDbContextFactory), "
            "migrations in Kubernetes (init container), owned entities, compiled queries; "
            "GORM (Go): hooks, transactions, soft delete, batch operations; "
            "MongoDB: Spring Data MongoDB vs driver nativo, Motor (Python async); "
            "Connection pooling: HikariCP (Java), SqlClient (.NET), pgxpool (Go); "
            "Database per microservizio vs schema condiviso — trade-off. "
            "Related: docs/databases/postgresql/connection-pooling.md, "
            "docs/databases/nosql/mongodb.md, docs/databases/fondamentali/transazioni-concorrenza.md."
        ),
        "worth_if": "Developer che sceglie e ottimizza l'accesso ai dati nei propri microservizi",
        "skip_if": "Verifica databases/postgresql/connection-pooling.md — questo aggiunge ORM e pattern developer"
    },
    # ── P3: Processi ──────────────────────────────────────────────────────────
    {
        "id": "415",
        "type": "new_topic",
        "path": "docs/dev/processi/developer-workflow.md",
        "category": "dev",
        "priority": "P3",
        "status": "pending",
        "reason": (
            "Workflow quotidiano del developer di microservizi: "
            "local dev con Docker Compose (dipendenze locali: DB, Kafka, Redis), "
            "Skaffold e Tilt per inner loop su Kubernetes (hot reload), "
            "Devcontainers (VS Code, GitHub Codespaces), "
            "branch strategy: trunk-based development vs Gitflow (quando usare quale), "
            "conventional commits e changelog automatico (semantic-release), "
            "pull request workflow: checklist per microservizi (test coverage, security scan, perf baseline), "
            "shift-left testing: unit -> integration (Testcontainers) -> contract (Pact), "
            "feature toggles integration nel workflow. "
            "Related: docs/ci-cd/pipeline.md, docs/dev/processi/enterprise-sdlc.md."
        ),
        "worth_if": "Developer senior che vuole ottimizzare il ciclo di sviluppo per microservizi",
        "skip_if": "Non pertinente"
    },
    {
        "id": "416",
        "type": "new_topic",
        "path": "docs/dev/processi/enterprise-sdlc.md",
        "category": "dev",
        "priority": "P3",
        "status": "pending",
        "reason": (
            "SDLC enterprise per microservizi in team estesi: "
            "sprint planning con backlog tecnico e debt tecnico (quadrante Fowler), "
            "definition of done per un microservizio (quality gate: coverage >=80%, SAST green, "
            "performance baseline, health probe configurate, runbook scritto), "
            "feature flags: LaunchDarkly, Unleash, Flagsmith — integrazione nel SDLC e trunk-based, "
            "release management: semantic versioning, changelog automatico, hotfix process, "
            "architectural decision records (ADR) — template e processo, "
            "Tech Lead: responsabilita', RF (request for comments), coupling budget. "
            "Related: docs/dev/processi/developer-workflow.md, docs/dev/processi/pm-sviluppo.md, "
            "docs/ci-cd/pipeline.md."
        ),
        "worth_if": "Tech Lead o Senior Developer che struttura il processo in un team enterprise",
        "skip_if": "Non pertinente"
    },
    {
        "id": "417",
        "type": "new_topic",
        "path": "docs/dev/processi/pm-sviluppo.md",
        "category": "dev",
        "priority": "P3",
        "status": "pending",
        "reason": (
            "Project Manager lato sviluppo in contesto microservizi enterprise: "
            "Team Topologies (Skelton & Pais): stream-aligned, enabling, complicated-subsystem, platform team, "
            "interaction modes (collaboration, X-as-a-Service, facilitating); "
            "velocity e capacity planning tecnica (story points vs flow metrics); "
            "gestione del tech debt: quadrante Fowler, tech debt register, capacity allocation (20% regola); "
            "DORA metrics come KPI: lead time, deployment frequency, change failure rate, MTTR; "
            "governance delle dipendenze tra team/servizi: internal APIs contract, breaking changes policy; "
            "roadmap tecnica vs product roadmap — come allinearle; "
            "engineering metrics (non vanity): cycle time, PR size, code review turnaround. "
            "Related: docs/dev/processi/enterprise-sdlc.md, docs/monitoring/sre/incident-management.md."
        ),
        "worth_if": "PM tecnico, Engineering Manager, CTO che governa lo sviluppo di un sistema a microservizi",
        "skip_if": "Non pertinente"
    },
]

# Aggiungi solo task con path non ancora in coda
added = []
for task in tasks:
    if task["path"] in existing_paths:
        print(f"SKIP (gia' presente): {task['path']}")
        continue
    state["queue"].append(task)
    existing_paths.add(task["path"])
    added.append(task["id"])

state["total_ops"] = state.get("total_ops", 0) + len(added)

with open(STATE_FILE, "w", encoding="utf-8") as f:
    f.write("# Stato del sistema di automazione KB\n")
    f.write("# Aggiornato automaticamente - non modificare 'completed' manualmente\n\n")
    yaml.dump(state, f, allow_unicode=True, default_flow_style=False, sort_keys=False, width=120)

print(f"\nAggiunti {len(added)} task: {', '.join(added)}")
print("Sezione docs/dev/ pianificata:")
print("  P1: 1 task  (_index landing page)")
print("  P2: 13 task (linguaggi, runtime, sicurezza, resilienza, integrazioni)")
print("  P3: 4 task  (processi, PM, Python)")
