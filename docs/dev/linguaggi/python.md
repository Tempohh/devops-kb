---
title: "Python per Microservizi"
slug: python
category: dev
tags: [python, fastapi, uvicorn, gunicorn, asyncio, pydantic, sqlalchemy, microservizi]
search_keywords: [python, python microservizi, python microservices, fastapi, fast api, uvicorn, gunicorn, asyncio, async await, event loop, pydantic, pydantic v2, sqlalchemy, sqlalchemy async, asyncpg, motor mongodb, GIL, global interpreter lock, python concurrenza, python concurrency, python async, httpx, starlette, depends injection, dependency injection fastapi, openapi auto, swagger fastapi, python docker, python kubernetes, python container, python worker, python grpc, python flask, python django, python aiohttp, python thread pool, cpu bound io bound python, aiofiles, alembic, python orm, python type hints, python annotazioni tipo, anyio, trio, python performance, uvloop, gunicorn workers, uvicorn workers, multiprocessing python]
parent: dev/linguaggi/_index
related: [dev/linguaggi/go, dev/integrazioni/database-patterns, dev/runtime/resource-tuning]
official_docs: https://fastapi.tiangolo.com/
status: complete
difficulty: intermediate
last_updated: 2026-03-29
---

# Python per Microservizi

## Panoramica

Python è il linguaggio di elezione per microservizi ML/AI, pipeline di dati, scripting di automazione e backend REST dove la velocity di sviluppo e l'ecosistema di librerie contano più della latenza bruta. Il framework di riferimento moderno è **FastAPI**: async nativo, validazione Pydantic v2 con zero overhead, generazione automatica di documentazione OpenAPI/Swagger, e Dependency Injection dichiarativa. FastAPI si basa su **Starlette** per l'ASGI layer e **Pydantic** per la validazione — due librerie production-grade con anni di adozione enterprise.

Il deployment standard prevede **Uvicorn** come ASGI server (event loop asyncio con uvloop opzionale per performance +20-40%) dietro **Gunicorn** come process manager: Gunicorn gestisce il ciclo di vita dei worker, i segnali OS, e il pre-forking. Ogni worker Uvicorn è un processo Python indipendente che gestisce richieste async internamente, bypassando di fatto il GIL per I/O-bound workload.

Quando usare Python: integrazione ML (TensorFlow, PyTorch, scikit-learn, LangChain), pipeline ETL e data engineering, API REST rapidamente iterabili, team con forte competenza Python esistente, integrazione con ecosistema data science. Quando preferire Go o Java: latenza p99 sub-millisecondo, footprint memoria critico (<30MB), sidecar Kubernetes, workload CPU-intensive senza librerie C (NumPy/SciPy) — in quel caso il GIL è un vincolo reale.

---

## Concetti Chiave

### Il GIL — Global Interpreter Lock

Il GIL è un mutex nel CPython interpreter che garantisce che solo un thread esegua bytecode Python alla volta. Non è un bug: protegge la reference counting del garbage collector. Le implicazioni pratiche per i microservizi sono:

- **I/O-bound workload (HTTP, DB, file):** il GIL viene rilasciato durante operazioni I/O syscall → thread multipli o async/await sono efficaci
- **CPU-bound workload puro (calcolo numerico, parsing JSON massiccio):** il GIL serializza i thread → usare `multiprocessing`, worker Gunicorn separati, o librerie con release del GIL (NumPy, Pandas operano in C senza GIL)

```
Thread 1: [Python bytecode] ──── [rilascia GIL] ──── [attesa I/O] ──────────
Thread 2:                         [acquisce GIL] ─── [Python bytecode] ──────
                                  ↑ swap durante I/O syscall
```

!!! warning "CPU-bound e thread — anti-pattern comune"
    Usare `ThreadPoolExecutor` per operazioni CPU-bound in Python non porta benefici di parallelismo: i thread si serializzano sul GIL. Per CPU-bound vero usare `ProcessPoolExecutor` o `multiprocessing.Pool`, oppure librerie C-extension che rilasciano il GIL (NumPy, pandas, Pillow per image processing).

### asyncio e Event Loop

`asyncio` implementa un event loop single-thread che gestisce concorrenza tramite coroutine. Una coroutine sospesa (`await`) non occupa un thread — torna al loop che può eseguire altre coroutine. Questo permette a un singolo worker Uvicorn di gestire centinaia di richieste HTTP concorrenti consumando memoria trascurabile per coroutine.

```python
import asyncio

# Coroutine — sospende su await, non blocca il loop
async def fetch_user(user_id: str) -> dict:
    # await libera il loop mentre si attende la risposta DB
    user = await db.fetch_one("SELECT * FROM users WHERE id = $1", user_id)
    return user

# Concorrenza esplicita con asyncio.gather
async def fetch_dashboard(user_id: str):
    # Eseguiti concorrentemente — non sequenzialmente
    user, orders, notifications = await asyncio.gather(
        fetch_user(user_id),
        fetch_orders(user_id),
        fetch_notifications(user_id),
    )
    return {"user": user, "orders": orders, "notifications": notifications}
```

!!! warning "Bloccare il loop — anti-pattern critico"
    Qualsiasi operazione bloccante sincrona in una coroutine congela l'intero event loop e tutte le richieste in corso. `time.sleep()`, `requests.get()`, `open()` per file grandi — tutti bloccanti. Usare `asyncio.sleep()`, `httpx.AsyncClient`, `aiofiles`. Per codice legacy bloccante, wrappare con `loop.run_in_executor()`.

---

## FastAPI — Struttura Base

### App Principale con Lifespan

```python
# main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inizializzazione e cleanup risorse durante il ciclo di vita dell'app."""
    # Startup: connessione al DB, inizializzazione cache
    logger.info("Starting up...")
    await database.connect()
    await redis_client.ping()
    logger.info("Connections established")

    yield  # app è running qui

    # Shutdown: chiusura risorse
    logger.info("Shutting down...")
    await database.disconnect()
    await redis_client.close()

app = FastAPI(
    title="Order Service",
    version="1.0.0",
    lifespan=lifespan,
    # Disabilitare docs in produzione se necessario
    docs_url="/docs" if settings.ENV != "production" else None,
    redoc_url="/redoc" if settings.ENV != "production" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Health endpoints — separati dalla logica di business
@app.get("/healthz", tags=["health"])
async def healthz():
    return {"status": "ok"}

@app.get("/readyz", tags=["health"])
async def readyz():
    # Verificare dipendenze critiche
    try:
        await database.execute("SELECT 1")
        return {"status": "ready"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

# Inclusione router
app.include_router(users_router, prefix="/api/v1/users", tags=["users"])
app.include_router(orders_router, prefix="/api/v1/orders", tags=["orders"])
```

### Modelli Pydantic v2

Pydantic v2 (rilasciato 2023) è riscritto in Rust — validazione 5-50x più veloce di v1. La sintassi è quasi identica ma alcuni dettagli cambiano.

```python
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic import EmailStr, HttpUrl
from datetime import datetime
from typing import Optional
from enum import Enum
import uuid

class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"

class CreateOrderRequest(BaseModel):
    # Field con validazione inline
    customer_email: EmailStr
    items: list["OrderItem"] = Field(min_length=1, max_length=100)
    shipping_address: str = Field(min_length=10, max_length=500)
    notes: Optional[str] = Field(default=None, max_length=1000)

    @field_validator("items")
    @classmethod
    def validate_items_total(cls, items: list) -> list:
        total = sum(item.quantity * item.unit_price for item in items)
        if total > 100_000:
            raise ValueError("Ordine supera il limite di 100.000€")
        return items

class OrderItem(BaseModel):
    product_id: uuid.UUID
    quantity: int = Field(ge=1, le=1000)
    unit_price: float = Field(gt=0)

class OrderResponse(BaseModel):
    id: uuid.UUID
    status: OrderStatus
    customer_email: EmailStr
    items: list[OrderItem]
    total_amount: float
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True  # Pydantic v2: sostituisce orm_mode = True
    }

# Aggiornamento parziale — tutti i campi Optional
class UpdateOrderRequest(BaseModel):
    status: Optional[OrderStatus] = None
    notes: Optional[str] = Field(default=None, max_length=1000)

    model_config = {"extra": "forbid"}  # rifiuta campi non dichiarati
```

### Dependency Injection con Depends

Il sistema DI di FastAPI è basato su `Depends()`: le dipendenze sono funzioni (sync o async) dichiarate come parametri degli handler. FastAPI risolve il grafo automaticamente, gestisce scope e caching per richiesta.

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
import jwt

security = HTTPBearer()

# Dipendenza: sessione DB per richiesta
async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

# Dipendenza: utente autenticato
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.JWT_SECRET,
            algorithms=["HS256"]
        )
        user_id = payload.get("sub")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token scaduto")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token non valido")

    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Utente non trovato")
    return user

# Dipendenza: verifica ruolo (composta su get_current_user)
def require_role(*roles: str):
    async def check_role(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=403, detail="Permessi insufficienti")
        return current_user
    return check_role

# Handler che usa tutte le dipendenze
@router.post("/orders", response_model=OrderResponse, status_code=201)
async def create_order(
    request: CreateOrderRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("customer", "admin")),
):
    order = await order_service.create(db, request, current_user.id)
    return order
```

---

## Configurazione & Pratica

### Settings con Pydantic-Settings

```python
# config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import PostgresDsn, RedisDsn, field_validator
from typing import Optional

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Server
    ENV: str = "development"
    DEBUG: bool = False
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]

    # Database
    DATABASE_URL: PostgresDsn
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # Redis
    REDIS_URL: RedisDsn = "redis://localhost:6379/0"

    # Auth
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    # Osservabilità
    LOG_LEVEL: str = "INFO"
    OTEL_EXPORTER_OTLP_ENDPOINT: Optional[str] = None

# Singleton — importato da altri moduli
settings = Settings()
```

```bash
# .env (sviluppo locale — mai committare in git)
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/mydb
JWT_SECRET=dev-secret-change-in-production
REDIS_URL=redis://localhost:6379/0
LOG_LEVEL=DEBUG
```

### Logging Strutturato con structlog

```python
# logging_config.py
import structlog
import logging
import sys

def configure_logging(log_level: str = "INFO", json_output: bool = True):
    """Configura structlog per output JSON in produzione."""

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer() if json_output
                else structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper())
        ),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

# Uso in handler/service
import structlog
logger = structlog.get_logger(__name__)

async def create_order(db: AsyncSession, request: CreateOrderRequest) -> Order:
    log = logger.bind(customer_email=request.customer_email)
    log.info("creating_order", items_count=len(request.items))

    try:
        order = Order(**request.model_dump())
        db.add(order)
        await db.flush()
        log.info("order_created", order_id=str(order.id))
        return order
    except Exception as e:
        log.error("order_creation_failed", error=str(e))
        raise
```

### SQLAlchemy 2 Async

```python
# database.py
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Column, String, Float, DateTime, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

# Engine async — usa asyncpg come driver
engine = create_async_engine(
    str(settings.DATABASE_URL),  # postgresql+asyncpg://...
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,      # verifica connessioni stale prima dell'uso
    pool_recycle=3600,       # riciclo connessioni ogni ora
    echo=settings.DEBUG,     # log SQL in dev, mai in prod
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # oggetti usabili dopo commit senza re-fetch
)

class Base(DeclarativeBase):
    pass

# Modello ORM
class Order(Base):
    __tablename__ = "orders"

    id: uuid.UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_email: str = Column(String(255), nullable=False, index=True)
    status: str = Column(SAEnum(OrderStatus), nullable=False, default="pending")
    total_amount: float = Column(Float, nullable=False)
    created_at: datetime = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: datetime = Column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

# Query async — stile ORM
from sqlalchemy import select, update

async def get_orders_by_customer(
    db: AsyncSession,
    customer_email: str,
    limit: int = 20,
    offset: int = 0,
) -> list[Order]:
    result = await db.execute(
        select(Order)
        .where(Order.customer_email == customer_email)
        .order_by(Order.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()

async def bulk_update_status(
    db: AsyncSession,
    order_ids: list[uuid.UUID],
    new_status: str,
) -> int:
    result = await db.execute(
        update(Order)
        .where(Order.id.in_(order_ids))
        .values(status=new_status, updated_at=datetime.utcnow())
        .returning(Order.id)
    )
    return len(result.fetchall())
```

```bash
# Alembic — migrazioni DB
pip install alembic

# Inizializzazione (una tantum)
alembic init alembic

# Generazione migrazione automatica da modelli ORM
alembic revision --autogenerate -m "add_orders_table"

# Applicazione migrazione
alembic upgrade head

# Rollback alla revisione precedente
alembic downgrade -1
```

### Motor — MongoDB Async

```python
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from typing import Optional

# Client Motor (thread-safe, condiviso tra richieste)
mongo_client = AsyncIOMotorClient(settings.MONGODB_URL)
db_motor = mongo_client[settings.MONGODB_DATABASE]

# Collection tipizzata
events_collection = db_motor["events"]

async def save_event(event: dict) -> str:
    result = await events_collection.insert_one(event)
    return str(result.inserted_id)

async def find_events_by_aggregate(
    aggregate_id: str,
    event_type: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    query = {"aggregate_id": aggregate_id}
    if event_type:
        query["type"] = event_type

    cursor = events_collection.find(query).sort("timestamp", 1).limit(limit)
    events = []
    async for event in cursor:
        event["_id"] = str(event["_id"])  # ObjectId → str per JSON
        events.append(event)
    return events
```

---

## Deployment — Uvicorn e Gunicorn

### Dockerfile Multi-Stage

```dockerfile
# Dockerfile
FROM python:3.12-slim AS builder

WORKDIR /app
RUN pip install --no-cache-dir uv  # uv è 10-100x più veloce di pip

COPY pyproject.toml uv.lock ./
# Installazione dipendenze in layer separato per cache Docker
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev


FROM python:3.12-slim AS runtime

# Utente non-root per sicurezza
RUN useradd --create-home --no-log-init appuser
WORKDIR /app
USER appuser

# Copia solo il virtualenv e il codice (non build tools)
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --from=builder --chown=appuser:appuser /app/src /app/src

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

# Gunicorn come process manager, Uvicorn come worker class
CMD ["gunicorn", "src.main:app", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--workers", "2", \
     "--bind", "0.0.0.0:8000", \
     "--timeout", "30", \
     "--graceful-timeout", "30", \
     "--keep-alive", "5", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info"]
```

### Numero di Worker — Formula e Ragionamento

```bash
# Formula classica Gunicorn per worker sync (non adatta a async):
# workers = (2 × CPU) + 1

# Per Uvicorn workers (async, I/O-bound):
# workers = 1 o 2 per container con resources.limits.cpu: 1
# workers = 2-4 per container con resources.limits.cpu: 2-4

# Ogni worker è un processo Python separato — moltiplicatore di memoria:
# 1 worker FastAPI ≈ 80-150 MB RSS
# 4 workers = 320-600 MB
# → calibrare resources.requests.memory di conseguenza

# Variabile d'ambiente per configurazione dinamica
GUNICORN_CMD_ARGS="--workers=2 --worker-class=uvicorn.workers.UvicornWorker"

# Alternativa: Uvicorn diretto (senza Gunicorn) — solo per dev o single-container
uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 1 --loop uvloop
```

```yaml
# Kubernetes Deployment — configurazione risorse
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
spec:
  replicas: 3
  template:
    spec:
      containers:
        - name: order-service
          image: myregistry/order-service:1.0.0
          ports:
            - containerPort: 8000
          env:
            - name: WORKERS
              value: "2"
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: order-service-secrets
                  key: database-url
          resources:
            requests:
              cpu: "500m"
              memory: "256Mi"
            limits:
              cpu: "1000m"
              memory: "512Mi"   # 2 workers × ~150MB + overhead
          readinessProbe:
            httpGet:
              path: /readyz
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /healthz
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 15
```

!!! tip "uvloop — boost performance event loop"
    `uvloop` è un'implementazione dell'event loop asyncio basata su `libuv` (la stessa usata da Node.js). Sostituisce l'event loop Python puro con +20-40% throughput per I/O-bound. Installare con `pip install uvloop` e usare `--loop uvloop` con Uvicorn, oppure dichiararlo in `pyproject.toml` come dipendenza opzionale.

---

## Best Practices

**Separazione tra handler e service layer:** gli handler FastAPI devono solo fare validazione input, chiamare il service layer, e formattare la risposta. La logica di business va nel service layer — testabile senza il framework HTTP.

```python
# router/orders.py — solo orchestrazione
@router.post("/", response_model=OrderResponse, status_code=201)
async def create_order(
    request: CreateOrderRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    order_svc: OrderService = Depends(get_order_service),
):
    return await order_svc.create_order(db, request, current_user.id)

# service/orders.py — logica di business pura
class OrderService:
    def __init__(self, event_publisher: EventPublisher):
        self.event_publisher = event_publisher

    async def create_order(
        self,
        db: AsyncSession,
        request: CreateOrderRequest,
        user_id: uuid.UUID,
    ) -> Order:
        # Verifica stock, calcola prezzi, pubblica evento
        ...
```

!!! tip "Dipendenze come classi vs funzioni"
    Per dipendenze con stato (es. service con configurazione iniettata), usare classi con `__call__`. Questo permette di iniettare sottocomponenti (repository, publisher) mantenendo il ciclo di vita gestito da FastAPI.

!!! warning "N+1 query con ORM — da evitare esplicitamente"
    SQLAlchemy async non fa eager loading automatico per relazioni. Una lista di `Order` con `items` lazy-loaded genera N+1 query. Usare sempre `selectinload()` o `joinedload()` per relazioni necessarie: `select(Order).options(selectinload(Order.items))`.

**Pagination standardizzata:** implementare sempre cursore o offset/limit nei list endpoint. Returnare sempre il count totale e i metadati di paginazione nel response model.

**Gestione errori centralizzata:**

```python
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})

@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("unhandled_exception", error=str(exc), path=request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
```

---

## Troubleshooting

### Event loop bloccato — latenze alte su tutte le richieste

**Sintomo:** Tutte le richieste rallentano in modo uniforme (non solo alcune), latenza media alta ma nessun errore, CPU di un worker al 100%.

**Causa:** Una coroutine esegue operazione bloccante sincrona senza rilasciare il loop: `requests.get()`, `time.sleep()`, accesso al filesystem con `open()` su file grandi, parsing JSON sincrono su payload molto grandi.

**Diagnosi:**
```python
# Middleware per loggare le richieste lente
import time
@app.middleware("http")
async def log_slow_requests(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    duration = time.monotonic() - start
    if duration > 1.0:  # soglia: 1 secondo
        logger.warning("slow_request",
            path=request.url.path,
            duration_s=round(duration, 3))
    return response
```

**Soluzione:**
```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=4)

# Wrappare codice bloccante in executor
async def process_large_file(path: str) -> dict:
    loop = asyncio.get_running_loop()
    # run_in_executor esegue in thread pool — non blocca il loop
    result = await loop.run_in_executor(executor, _sync_process_file, path)
    return result

def _sync_process_file(path: str) -> dict:
    # Operazione bloccante — OK perché in thread pool
    with open(path) as f:
        return json.load(f)
```

---

### Worker che crashano sotto carico — OOMKilled

**Sintomo:** Pod Kubernetes riavviato con stato `OOMKilled`, memory usage cresce progressivamente, errori `Cannot allocate memory` nei log.

**Causa 1:** Memory leak nei worker — oggetti Python non deallocati, reference circolari, cache in-memory non bounded.
**Causa 2:** Numero di worker troppo alto per il memory limit del container.

**Diagnosi:**
```bash
# Verificare memory per worker
kubectl top pods -l app=order-service

# Memory limit del container
kubectl get pod order-service-xxx -o jsonpath='{.spec.containers[0].resources.limits.memory}'

# Tracciare memory in Python
pip install memory-profiler
# @profile decorator su funzioni sospette
```

**Soluzione:**
```bash
# Ridurre workers nel Deployment env
- name: WORKERS
  value: "1"  # da 4 a 1 se memory limit è 256Mi

# Oppure aumentare memory limit
resources:
  limits:
    memory: "512Mi"  # base: ~150MB per worker + headroom

# Gunicorn max_requests per restart automatico dei worker (previene leak)
gunicorn ... --max-requests 1000 --max-requests-jitter 100
```

---

### Connessioni DB esaurite — `QueuePool limit of size X overflow Y reached`

**Sintomo:** Errore `QueuePool limit of size 5 overflow 10 reached` sotto carico, latenza DB aumenta, richieste in timeout.

**Causa:** Pool SQLAlchemy esaurito — troppi worker o troppe query concorrenti per la dimensione del pool.

**Soluzione:**
```python
# Ogni worker ha il proprio pool — pool_size × numero_workers = connessioni totali verso DB
# Con 4 workers e pool_size=10: fino a 40 connessioni verso Postgres
# Postgres default max_connections = 100 → dimensionare di conseguenza

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=5,          # connessioni persistenti per worker
    max_overflow=10,      # connessioni temporanee extra
    pool_timeout=30,      # wait massimo per connessione dal pool
    pool_pre_ping=True,   # verifica connessioni stale
)

# Se si usa PgBouncer (connection pooler) davanti a Postgres:
# pool_size=1, max_overflow=0 — PgBouncer gestisce il pooling reale
```

---

### Import circolari — `ImportError: cannot import name X from Y`

**Sintomo:** Errore al startup `ImportError: cannot import name 'User' from 'src.models'`, funziona in sviluppo ma fallisce con Gunicorn multi-worker.

**Causa:** Import circolari tra moduli Python — frequente con SQLAlchemy models, Pydantic schemas, e dipendenze FastAPI.

**Soluzione:**
```python
# Anti-pattern — import circolare
# models.py
from schemas import UserResponse  # ← importa da schemas

# schemas.py
from models import User  # ← importa da models  → CIRCOLARE

# Soluzione: TYPE_CHECKING guard per import usati solo nei type hint
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.models import User  # importato solo per type checker, non a runtime

# Oppure: spostare tipi condivisi in un modulo separato (src/types.py)
```

---

## Relazioni

??? info "Go per Microservizi — Quando preferire Go"
    Python e Go coprono casi d'uso distinti. Go è preferibile per sidecar Kubernetes, proxy, CLI, servizi con requisiti stringenti di startup (<10ms) e memoria (<30MB RSS). FastAPI Uvicorn ha startup ~500ms e ~80-150MB per worker.

    **Approfondimento completo →** [Go per Microservizi](go.md)

??? info "Database Patterns — Async e Connection Pooling"
    SQLAlchemy 2 async e asyncpg si integrano con i pattern di repository, Unit of Work, e transazioni distribuite descritti in questa sezione.

    **Approfondimento completo →** [Database Patterns](../integrazioni/database-patterns.md)

??? info "Resource Tuning — Calibrazione Memory per Worker"
    La calibrazione di `resources.requests` e `resources.limits` per pod Python dipende direttamente dal numero di worker Gunicorn. La sezione resource-tuning descrive la metodologia generale.

    **Approfondimento completo →** [Resource Tuning](../runtime/resource-tuning.md)

---

## Riferimenti

- [FastAPI Documentation](https://fastapi.tiangolo.com/) — guida completa e tutorial
- [Pydantic v2 Docs](https://docs.pydantic.dev/latest/) — validazione, migration da v1
- [SQLAlchemy 2.0 Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html) — ORM async ufficiale
- [Uvicorn Deployment](https://www.uvicorn.org/deployment/) — configurazione Uvicorn e Gunicorn
- [Gunicorn Configuration](https://docs.gunicorn.org/en/stable/configure.html) — worker types, tuning
- [Motor Documentation](https://motor.readthedocs.io/en/stable/) — MongoDB driver async Python
- [structlog](https://www.structlog.org/en/stable/) — structured logging per Python
- [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) — gestione configurazione
- [asyncio — Python docs](https://docs.python.org/3/library/asyncio.html) — event loop, coroutine, task
- [uvloop](https://github.com/MagicStack/uvloop) — event loop ad alte performance
- [uv — Python package manager](https://docs.astral.sh/uv/) — alternativa veloce a pip/poetry
