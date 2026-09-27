---
title: "Node.js per Microservizi"
slug: nodejs
category: dev
tags: [nodejs, node, javascript, typescript, express, fastify, nestjs, event-loop, microservizi, bff]
search_keywords: [nodejs, node.js, node js, javascript backend, typescript backend, event loop, single thread, non-blocking io, libuv, express js, express framework, fastify framework, nestjs framework, nest.js, bff backend for frontend, async await, promise, unhandledrejection, uncaughtexception, graceful shutdown node, sigterm node, cluster module, pm2, node docker, multi-stage dockerfile node, node_env production, npm, pnpm, opentelemetry nodejs, auto-instrumentation node, node microservizi, node microservices, node LTS, v8 engine]
parent: dev/linguaggi/_index
related: [dev/linguaggi/go, dev/linguaggi/python, dev/resilienza/observability-code]
official_docs: https://nodejs.org/docs/latest/api/
status: complete
difficulty: intermediate
last_updated: 2026-09-27
---

# Node.js per Microservizi

## Panoramica

Node.js è un runtime JavaScript basato su V8 (motore Chrome) con I/O asincrono non bloccante gestito da libuv. È il runtime di riferimento per servizi I/O-bound — chiamate a database, API esterne, aggregazione dati — dove il tempo speso in attesa di rete/disco domina rispetto al calcolo CPU. Per questo motivo è la scelta tipica per BFF (Backend For Frontend): livelli di aggregazione che orchestrano molte chiamate downstream in parallelo senza fare lavoro CPU pesante.

Startup tipico ~200ms, memory footprint 50-100MB — nella fascia media rispetto a Go (10-30MB, <10ms) e Java Spring Boot (200-500MB, 2-5s). L'ecosistema npm è il più vasto in assoluto, con librerie per praticamente ogni integrazione. Il modello di concorrenza è single-thread con event loop: un solo thread esegue JavaScript, ma le operazioni I/O (network, filesystem, DB) sono delegate a libuv (thread pool o kernel async) e non bloccano il thread principale.

Quando usare Node.js: BFF e API gateway leggeri, servizi di aggregazione/orchestrazione con molte chiamate I/O parallele, real-time (WebSocket, SSE), team con competenze JavaScript/TypeScript full-stack condivise tra frontend e backend. Quando preferire altri linguaggi: workload CPU-bound intensivi (calcolo, elaborazione immagini/video pesante — Go o Java), applicazioni enterprise con scaffolding CRUD ricco e ORM maturo (Spring Boot, .NET), ML/AI training (Python).

---

## Concetti Chiave

### Event Loop e Modello di Concorrenza

Node.js esegue JavaScript su un singolo thread. Le operazioni I/O (letture file, query DB, richieste HTTP) vengono delegate a libuv, che le esegue tramite meccanismi asincroni del kernel (epoll/kqueue/IOCP) o un thread pool separato (default 4 thread, per DNS lookup, crypto, filesystem). Quando l'operazione completa, il callback/Promise viene accodato e l'event loop lo esegue al turno successivo.

```
┌───────────────────────────┐
│         timers            │  setTimeout, setInterval
├───────────────────────────┤
│    pending callbacks      │  callback I/O differiti
├───────────────────────────┤
│         poll               │  recupero nuovi eventi I/O, esecuzione callback
├───────────────────────────┤
│         check              │  setImmediate
├───────────────────────────┤
│    close callbacks         │  socket.on('close', ...)
└───────────────────────────┘
        (event loop gira in ciclo continuo)
```

Questo modello rende Node.js estremamente efficiente per migliaia di connessioni concorrenti I/O-bound (es. proxy, BFF), ma **inadatto** a codice CPU-bound sincrono: un loop pesante o una regex catastrofica blocca l'intero thread e nessun'altra richiesta viene servita nel frattempo.

!!! warning "Blocco dell'event loop"
    Qualsiasi funzione sincrona lunga (JSON.parse su payload enormi, cicli CPU-intensivi, crypto sincrono) blocca **tutte** le richieste concorrenti, non solo quella corrente. Spostare lavoro CPU-bound in `worker_threads` o in un servizio dedicato (es. Go).

### Async/Await e Gestione Errori

```javascript
// Pattern corretto — async/await con try/catch
async function fetchUserOrder(userId) {
  try {
    const user = await userService.findById(userId);
    const orders = await orderService.findByUser(user.id);
    return { user, orders };
  } catch (err) {
    logger.error({ err, userId }, 'fetchUserOrder failed');
    throw err; // ri-lanciare per gestione a livello superiore (middleware errori)
  }
}

// Fan-out parallelo — Promise.all invece di await sequenziali
async function aggregateDashboard(userId) {
  const [profile, orders, notifications] = await Promise.all([
    profileService.get(userId),
    orderService.list(userId),
    notificationService.list(userId),
  ]);
  return { profile, orders, notifications };
}
```

**`unhandledRejection` e `uncaughtException`**: una Promise rifiutata senza `.catch()`/`try-catch` genera un evento `unhandledRejection` sul processo. Da Node.js 15+ il comportamento default è terminare il processo (prima era solo un warning) — rilevante per crash in produzione non previsti.

```javascript
// Handler difensivi — ultima linea di difesa, MAI sostituto della gestione locale
process.on('unhandledRejection', (reason, promise) => {
  logger.fatal({ reason }, 'Unhandled Rejection — terminazione controllata');
  process.exit(1); // fail-fast: meglio un restart K8s che stato corrotto
});

process.on('uncaughtException', (err) => {
  logger.fatal({ err }, 'Uncaught Exception — terminazione controllata');
  process.exit(1);
});
```

!!! tip "Fail-fast su errori non gestiti"
    Non tentare di "recuperare" da `uncaughtException`/`unhandledRejection` e continuare l'esecuzione: lo stato del processo è potenzialmente corrotto. Loggare e terminare (`process.exit(1)`), lasciando che Kubernetes riavvii il pod. Il vero fix è intercettare l'errore nel punto in cui si verifica.

---

## Framework HTTP — Express vs Fastify vs NestJS

| Aspetto | Express | Fastify | NestJS |
|---|---|---|---|
| Filosofia | Minimalista, unopinionated | Performance-first, schema-based | Opinionated, enterprise (Angular-like) |
| Performance (req/s) | Base (~15-20k) | Alta (~35-45k, JSON schema compilato) | Media (overhead DI/decoratori, gira su Express o Fastify) |
| Validazione input | Manuale (middleware esterni: joi, zod) | Built-in via JSON Schema | Built-in via `class-validator` + DTO |
| TypeScript | Supportato ma non nativo | Supportato, tipizzazione buona | **Nativo** — TS è il linguaggio di default |
| Dependency Injection | No (manuale) | No (plugin system) | **Sì** — DI container completo |
| Curva apprendimento | Bassa | Bassa-media | Alta (moduli, provider, decoratori) |
| Ideale per | Prototipi, microservizi semplici | API ad alto throughput, microservizi performance-critical | Applicazioni enterprise, team grandi, architetture modulari |

!!! tip "Scelta per microservizi containerizzati"
    Per BFF e microservizi I/O-bound con requisiti di performance: **Fastify** (schema JSON validato a compile-time, overhead minimo). Per team enterprise che vogliono struttura simile a Spring/Angular con DI e moduli: **NestJS**. Express resta valido per servizi semplici o quando l'ecosistema di middleware esistente è un vincolo.

### Fastify — Struttura Base

```javascript
// server.js
import Fastify from 'fastify';

const fastify = Fastify({
  logger: { level: process.env.LOG_LEVEL || 'info' },
});

// Health endpoints separati da logica di business
fastify.get('/healthz', async () => ({ status: 'ok' }));
fastify.get('/readyz', async () => {
  // verificare dipendenze (DB, cache, ecc.)
  await db.query('SELECT 1');
  return { status: 'ready' };
});

// Route con JSON Schema — validazione + serializzazione veloce
const getUserSchema = {
  params: { type: 'object', properties: { id: { type: 'string' } }, required: ['id'] },
  response: {
    200: {
      type: 'object',
      properties: { id: { type: 'string' }, name: { type: 'string' } },
    },
  },
};

fastify.get('/api/v1/users/:id', { schema: getUserSchema }, async (request, reply) => {
  const user = await userService.findById(request.params.id);
  if (!user) return reply.code(404).send({ error: 'not found' });
  return user;
});

const start = async () => {
  try {
    await fastify.listen({ port: 8080, host: '0.0.0.0' });
  } catch (err) {
    fastify.log.error(err);
    process.exit(1);
  }
};
start();
```

### NestJS — Controller e DI

```typescript
// users.controller.ts
import { Controller, Get, Param, NotFoundException } from '@nestjs/common';
import { UsersService } from './users.service';

@Controller('api/v1/users')
export class UsersController {
  constructor(private readonly usersService: UsersService) {} // DI automatica

  @Get(':id')
  async getUser(@Param('id') id: string) {
    const user = await this.usersService.findById(id);
    if (!user) throw new NotFoundException('user not found');
    return user;
  }
}

// users.service.ts
import { Injectable } from '@nestjs/common';

@Injectable()
export class UsersService {
  constructor(private readonly repo: UserRepository) {}

  async findById(id: string) {
    return this.repo.findOne({ where: { id } });
  }
}
```

---

## Configurazione & Pratica

### TypeScript come Default

Per microservizi enterprise, TypeScript è oggi lo standard de facto: tipizzazione statica riduce classi intere di bug a runtime (proprietà undefined, mismatch di tipo su risposte API) e migliora la manutenibilità su team grandi.

```json
// tsconfig.json — configurazione consigliata per servizi Node.js
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "outDir": "./dist",
    "rootDir": "./src",
    "sourceMap": true
  },
  "include": ["src/**/*"]
}
```

```bash
# Build e avvio produzione — MAI eseguire ts-node in produzione
npm run build        # tsc → compila in dist/
node dist/server.js  # esecuzione JS compilato, no overhead di transpile runtime
```

### Containerizzazione — Multi-Stage Dockerfile

```dockerfile
# Dockerfile multi-stage — immagine finale minimale, no devDependencies
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci                     # install riproducibile da lockfile
COPY . .
RUN npm run build              # compila TypeScript in dist/

FROM node:20-alpine AS production
WORKDIR /app
ENV NODE_ENV=production
COPY package*.json ./
RUN npm ci --omit=dev          # solo dependencies di produzione
COPY --from=builder /app/dist ./dist

# Utente non-root — best practice sicurezza container
USER node
EXPOSE 8080
CMD ["node", "dist/server.js"]
```

!!! warning "NODE_ENV=production obbligatorio"
    Senza `NODE_ENV=production`, Express e molti middleware attivano branch di sviluppo (stack trace dettagliati nelle risposte, cache dei template disabilitata, logging verboso) con impatto misurabile su performance e superficie di esposizione di dettagli interni. Impostarlo sempre esplicitamente nell'immagine di produzione, non affidarsi al default del runtime.

### Graceful Shutdown — Gestione SIGTERM

Kubernetes invia `SIGTERM` al pod prima di terminarlo (default grace period 30s). Senza gestione esplicita, le connessioni in corso vengono interrotte bruscamente.

```javascript
// graceful-shutdown.js
let isShuttingDown = false;

async function gracefulShutdown(signal) {
  if (isShuttingDown) return;
  isShuttingDown = true;
  logger.info({ signal }, 'shutdown signal received');

  // 1. Smettere di accettare nuove connessioni
  server.close(() => {
    logger.info('http server closed');
  });

  // 2. Readiness probe deve iniziare a fallire SUBITO (rimuove il pod dagli endpoint)
  isReady = false;

  // 3. Chiudere risorse (pool DB, connessioni Kafka/Redis) con timeout
  try {
    await Promise.race([
      Promise.all([dbPool.end(), redisClient.quit()]),
      new Promise((_, reject) => setTimeout(() => reject(new Error('shutdown timeout')), 25000)),
    ]);
    logger.info('resources closed cleanly');
    process.exit(0);
  } catch (err) {
    logger.error({ err }, 'forced shutdown after timeout');
    process.exit(1);
  }
}

process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));
process.on('SIGINT', () => gracefulShutdown('SIGINT'));
```

!!! tip "Readiness probe e connection draining"
    Impostare `isReady = false` **prima** di chiudere il server HTTP, così la readiness probe Kubernetes fallisce e il pod viene rimosso dagli endpoint del Service prima che smetta di accettare richieste — evita errori 502/connection refused durante il rollout.

---

## Cluster Module vs Scaling Orizzontale K8s

Node.js è single-thread: un singolo processo sfrutta **un solo core CPU**, anche su macchine multi-core. Ci sono due strategie per sfruttare più core:

1. **`cluster` module** — forka N processi worker nello stesso pod/container, tutti in ascolto sulla stessa porta, load-balanced dal master via round-robin.
2. **Scaling orizzontale via K8s replica** — un processo per pod, N pod (replica), load-balancing gestito dal Service Kubernetes.

| Aspetto | `cluster` module | Replica K8s |
|---|---|---|
| Isolamento failure | Basso — crash del master impatta tutti i worker | Alto — un pod crash non impatta gli altri |
| Osservabilità | Complessa (metriche aggregate per processo) | Nativa (1 pod = 1 set di metriche) |
| Gestione memoria condivisa | In-process (stesso host) | Richiede cache esterna (Redis) |
| Standard in ambienti K8s | Sconsigliato | **Raccomandato** |

!!! warning "Cluster module in Kubernetes — anti-pattern"
    Usare `cluster` **dentro** un pod Kubernetes duplica la complessità che K8s già risolve a livello di orchestrazione (scaling, health check, restart) e complica readiness/liveness probe (quale worker rispondere?). In ambienti K8s-native: **un processo Node.js per container**, scaling orizzontale via `replicas` + `HorizontalPodAutoscaler`. Riservare `cluster`/`worker_threads` a deployment non containerizzati o per parallelizzare lavoro CPU-bound isolato (non per scaling generale delle richieste).

```yaml
# HorizontalPodAutoscaler — scaling orizzontale invece di cluster module
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: bff-service
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: bff-service
  minReplicas: 3
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

---

## Observability — OpenTelemetry Auto-Instrumentation

```bash
npm install --save @opentelemetry/api @opentelemetry/sdk-node \
  @opentelemetry/auto-instrumentations-node \
  @opentelemetry/exporter-trace-otlp-http
```

```javascript
// tracing.js — DEVE essere importato prima di qualsiasi altro modulo applicativo
import { NodeSDK } from '@opentelemetry/sdk-node';
import { getNodeAutoInstrumentations } from '@opentelemetry/auto-instrumentations-node';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';
import { resourceFromAttributes } from '@opentelemetry/resources';
import { ATTR_SERVICE_NAME } from '@opentelemetry/semantic-conventions';

const sdk = new NodeSDK({
  resource: resourceFromAttributes({
    [ATTR_SERVICE_NAME]: process.env.OTEL_SERVICE_NAME || 'bff-service',
  }),
  traceExporter: new OTLPTraceExporter({
    url: process.env.OTEL_EXPORTER_OTLP_ENDPOINT || 'http://otel-collector:4318/v1/traces',
  }),
  instrumentations: [getNodeAutoInstrumentations({
    '@opentelemetry/instrumentation-fs': { enabled: false }, // troppo rumoroso
  })],
});

sdk.start();

process.on('SIGTERM', () => sdk.shutdown().finally(() => process.exit(0)));
```

```bash
# Avvio con instrumentation caricata per prima — node -r (require) o import esplicito
node --import ./tracing.js dist/server.js
```

L'auto-instrumentation copre automaticamente HTTP, Express/Fastify, driver DB comuni (pg, mysql2, mongodb), Redis, e propaga i trace context (`traceparent`) tra chiamate downstream — fondamentale per BFF che aggregano più servizi, dove la latenza va attribuita al servizio a monte responsabile.

---

## Best Practices

**Struttura del progetto:**

```
service/
├── src/
│   ├── server.ts             # entrypoint — bootstrap, wiring DI
│   ├── config/                # caricamento config da env
│   ├── controllers/           # route handler (HTTP layer)
│   ├── services/               # business logic
│   ├── repositories/           # accesso dati
│   └── types/                  # interfacce/DTO TypeScript
├── dist/                       # output compilato (gitignored)
├── tsconfig.json
├── package.json
└── package-lock.json
```

!!! tip "npm ci invece di npm install in CI/build"
    `npm ci` installa esattamente le versioni bloccate in `package-lock.json` e fallisce se lockfile e `package.json` sono disallineati — build riproducibili. `npm install` può modificare il lockfile silenziosamente. Usare sempre `npm ci` in Dockerfile e pipeline CI.

**Gestione configurazione:** leggere configurazione solo da variabili d'ambiente (12-factor), validarle all'avvio con uno schema (`zod`, `joi`) invece di scoprire un valore mancante a runtime nel percorso di una richiesta.

```typescript
// config.ts — validazione fail-fast all'avvio
import { z } from 'zod';

const envSchema = z.object({
  PORT: z.coerce.number().default(8080),
  DATABASE_URL: z.string().url(),
  LOG_LEVEL: z.enum(['debug', 'info', 'warn', 'error']).default('info'),
});

export const config = envSchema.parse(process.env); // crash immediato se invalido
```

---

## Troubleshooting

### Memory leak — RSS cresce indefinitamente

**Sintomo:** `process.memoryUsage().rss` cresce nel tempo senza stabilizzarsi, pod terminato da OOMKilled sotto carico prolungato.

**Causa:** Closure che trattengono riferimenti (cache non limitate, event listener non rimossi, timer non cancellati con `clearInterval`).

```bash
# Snapshot heap per analisi offline (Chrome DevTools)
node --inspect dist/server.js
# In produzione — generare heap snapshot on-demand senza restart
kill -USR2 <pid>   # richiede libreria heapdump o v8.writeHeapSnapshot()
```

**Soluzione:** Usare cache con limite esplicito (`lru-cache`), rimuovere sempre listener registrati dinamicamente (`emitter.off()`), verificare con `--inspect` + Chrome DevTools Memory tab che gli oggetti si liberino tra GC successivi.

---

### Event loop bloccato — latenza p99 alta su tutte le richieste

**Sintomo:** Tutte le richieste concorrenti rallentano insieme (non solo una), `event loop lag` alto nelle metriche.

**Causa:** Operazione sincrona CPU-bound (parsing JSON enorme, regex complessa, crypto sincrono) esegue sul thread principale bloccando l'intero event loop.

```javascript
// Diagnostica — misurare event loop lag
import { monitorEventLoopDelay } from 'perf_hooks';
const histogram = monitorEventLoopDelay({ resolution: 20 });
histogram.enable();
setInterval(() => logger.info({ p99: histogram.percentile(99) }, 'event loop lag'), 10000);
```

**Soluzione:** Spostare lavoro CPU-bound in `worker_threads`, o usare versioni async delle API (`crypto.pbkdf2` invece di `pbkdf2Sync`), o delegare a un servizio dedicato scritto in un linguaggio più adatto al CPU-bound (Go).

---

### `unhandledRejection` in produzione — crash improvvisi

**Sintomo:** Processo termina inaspettatamente, log mostra `UnhandledPromiseRejectionWarning` o il processo termina senza log chiaro (comportamento default Node.js 15+).

**Causa:** Promise rifiutata senza `.catch()` in un percorso di codice non testato (es. race condition, chiamata async fuori da try/catch).

**Soluzione:** Audit sistematico di tutte le chiamate `async` per garantire try/catch o `.catch()` esplicito; handler `process.on('unhandledRejection')` come rete di sicurezza (loggare e terminare controllatamente, non ignorare).

```javascript
// Anti-pattern — Promise "fire and forget" senza gestione errori
someAsyncOperation(); // se rifiuta, unhandledRejection

// Corretto
someAsyncOperation().catch((err) => logger.error({ err }, 'operation failed'));
```

---

### Connection pool DB esaurito sotto carico

**Sintomo:** Errori `timeout acquiring connection from pool`, latenza crescente sotto carico, query in coda.

**Causa:** Pool dimensionato troppo piccolo rispetto alla concorrenza reale, oppure connessioni non rilasciate (query senza `finally`/`release()`).

**Soluzione:**
```javascript
import { Pool } from 'pg';

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  max: 20,                      // dimensionare sul carico reale, non di default
  idleTimeoutMillis: 30000,
  connectionTimeoutMillis: 5000, // fail-fast invece di attesa indefinita
});

// SEMPRE rilasciare la connessione, anche in caso di errore
async function queryUser(id) {
  const client = await pool.connect();
  try {
    return await client.query('SELECT * FROM users WHERE id = $1', [id]);
  } finally {
    client.release(); // torna al pool a prescindere dall'esito
  }
}
```

---

## Relazioni

??? info "OpenTelemetry e Observability — Approfondimento"
    L'auto-instrumentation Node.js copre HTTP, framework, driver DB/cache e propaga trace context tra servizi — essenziale per BFF che aggregano più downstream.

    **Approfondimento completo →** [Observability nel codice](../resilienza/observability-code.md)

??? info "Go e Python — Alternative per Microservizi I/O e CPU"
    Per workload CPU-bound o requisiti di startup/footprint estremi, Go è l'alternativa naturale. Per data science/ML, Python resta la scelta di riferimento.

    **Approfondimento completo →** [Go](go.md) | [Python](python.md)

---

## Riferimenti

- [Node.js Documentation ufficiale](https://nodejs.org/docs/latest/api/) — API reference completa
- [Node.js Event Loop, Timers, and process.nextTick()](https://nodejs.org/en/learn/asynchronous-work/event-loop-timers-and-nexttick) — guida ufficiale event loop
- [Fastify Documentation](https://fastify.dev/docs/latest/) — framework HTTP ad alte performance
- [NestJS Documentation](https://docs.nestjs.com/) — framework enterprise con DI
- [Express Documentation](https://expressjs.com/) — framework HTTP minimalista
- [OpenTelemetry Node.js](https://opentelemetry.io/docs/languages/js/) — auto-instrumentation e tracing
- [Node.js Docker Best Practices](https://github.com/nodejs/docker-node/blob/main/docs/BestPractices.md) — guida ufficiale containerizzazione
- [node-postgres (pg)](https://node-postgres.com/) — driver PostgreSQL con connection pooling
