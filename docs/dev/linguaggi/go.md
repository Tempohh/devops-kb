---
title: "Go per Microservizi"
slug: go
category: dev
tags: [go, golang, microservizi, grpc, goroutine, concurrency, gin, echo, fiber, slog, zerolog, viper, grpc, testing]
search_keywords: [go, golang, go lang, go microservizi, go microservices, goroutine, channel, goroutine pool, go concorrenza, go concurrency, startup go, footprint go, gin framework, gin http, echo framework, echo go, fiber framework, fiber go, framework http go, go http server, structured logging go, slog go, slog stdlib, zerolog, zerolog go, go 1.21, go logging, context go, context.Context, context propagation, context cancellation, context timeout, context deadline, graceful shutdown go, signal.NotifyContext, grpc go, protoc-gen-go, grpc golang, protobuf go, proto go, viper config, viper golang, go config management, table-driven test, table driven test go, testify, testify go, go testing, mocking go, interface mocking go, GOMAXPROCS, automaxprocs, uber-go automaxprocs, go container, go kubernetes, go docker, go build container, go multistage dockerfile, go 1.21 slog, go modules, go mod, go embed]
parent: dev/linguaggi/_index
related: [networking/protocolli/grpc, dev/linguaggi/java-quarkus, dev/linguaggi/dotnet]
official_docs: https://go.dev/doc/
status: complete
difficulty: intermediate
last_updated: 2026-03-28
---

# Go per Microservizi

## Panoramica

Go (Golang) è il linguaggio di riferimento per microservizi ad alta concorrenza, bassa latenza e footprint minimo. Il runtime Go compila in un singolo binario statico senza dipendenze esterne: startup tipicamente <10ms, memoria RSS a idle di 10–20MB, e la capacità di gestire decine di migliaia di goroutine concorrenti con un overhead di pochi KB per goroutine — ordini di grandezza più efficienti dei thread OS (1–8MB di stack ciascuno). Questi numeri lo rendono ideale per sidecar, proxy, agent Kubernetes, e servizi gRPC interni dove ogni millisecondo di cold start e ogni megabyte di memoria contano.

Il modello di concorrenza Go è basato su CSP (Communicating Sequential Processes): le goroutine comunicano tramite channel invece di condividere memoria con lock. Il garbage collector è non generazionale e a bassa latenza (pause <1ms dalla versione 1.14+), adatto a workload real-time. L'ecosistema standard library è eccezionalmente ricco: HTTP/2, TLS, JSON, testing, profiling integrati senza dipendenze esterne.

Quando usare Go: sidecar e agent Kubernetes, proxy e gateway leggeri, servizi gRPC ad alto throughput, CLI tool, microservizi con requisiti stringenti di startup e memoria. Quando preferire altri linguaggi: applicazioni enterprise con ORM ricco e scaffolding CRUD (Spring Boot, .NET), ML/AI workload Python-first, team senza esperienza Go dove il productivity gain non giustifica la curva di apprendimento.

---

## Concetti Chiave

### Goroutine e Scheduler Go

Go usa un runtime scheduler M:N (M goroutine, N thread OS). Il numero di thread OS attivi è controllato da `GOMAXPROCS`, default uguale al numero di CPU logiche. Ogni goroutine nasce con 2–8KB di stack che cresce dinamicamente — non c'è limite fisso. Il scheduler usa work-stealing: thread OS idle rubano goroutine dalla coda di thread occupati.

```
Goroutines (migliaia)
    │
    ▼
Go Scheduler (M:N)
    │   ├── P0 (processor 0) ──→ M0 (thread OS)
    │   ├── P1 (processor 1) ──→ M1 (thread OS)
    │   └── P2 (processor 2) ──→ M2 (thread OS)
    │
    GOMAXPROCS = numero di P (default: numCPU)
```

### Channel e Comunicazione

I channel sono il meccanismo di sincronizzazione primario Go. Un channel bufferizzato permette produzione/consumo asincroni; un channel non bufferizzato (capacità 0) forza sincronizzazione punto-punto.

```go
// Channel non bufferizzato — sincronizzazione punto-punto
done := make(chan struct{})
go func() {
    // lavoro...
    close(done) // segnala completamento
}()
<-done // blocca fino a completamento

// Channel bufferizzato — pool di worker
jobs := make(chan int, 100)
for i := 0; i < 4; i++ {
    go worker(jobs)
}
for j := range items {
    jobs <- j
}
close(jobs)
```

### GOMAXPROCS e Containerizzazione

In un container Kubernetes, il runtime Go vede le CPU fisiche dell'host, non il limite del container. Con `GOMAXPROCS=32` su un pod limitato a `0.5 CPU`, si creano 32 thread OS che competono su mezzo core — context switching eccessivo e performance peggiori.

**Soluzione: `uber-go/automaxprocs`** legge il `cpu.cfs_quota_us` del cgroup e imposta `GOMAXPROCS` automaticamente al valore corretto per il container.

```go
import _ "go.uber.org/automaxprocs"  // side-effect import nell'init

// In main.go — basta importare il package
// automaxprocs legge /sys/fs/cgroup/cpu.cfs_quota_us
// e chiama runtime.GOMAXPROCS(calcolato)
// Log output: "maxprocs: Updating GOMAXPROCS=2: determined from CPU quota"
```

```yaml
# Dockerfile multistage — binario statico per immagine scratch/distroless
FROM golang:1.22-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-s -w" -o service ./cmd/service

FROM gcr.io/distroless/static-debian12
COPY --from=builder /app/service /service
ENTRYPOINT ["/service"]
```

!!! warning "GOMAXPROCS in container senza automaxprocs"
    Senza `automaxprocs`, un pod con `resources.limits.cpu: 500m` su un nodo con 32 core usa `GOMAXPROCS=32`. Il risultato è 32 thread OS che competono su 0.5 core: throughput cala del 20-40% e la CPU throttling del kernel aumenta drasticamente. **Importare sempre `uber-go/automaxprocs` in main.go**.

---

## Framework HTTP — Gin, Echo, Fiber

Tutti e tre i framework si basano su `net/http` standard e sono production-ready. La scelta dipende da priorità di performance, API design e ecosistema.

| Aspetto | Gin | Echo | Fiber |
|---|---|---|---|
| Stars GitHub | ~80k | ~30k | ~34k |
| Performance | Alta (httprouter) | Alta (radix tree) | Molto alta (fasthttp) |
| Middleware standard | Vasto ecosistema | Buon ecosistema | Crescente |
| API style | Funzionale | Funzionale | Funzionale (Express-like) |
| Compatibilità `net/http` | Piena | Piena | **NO** (usa fasthttp) |
| Binding/Validation | Built-in (go-playground/validator) | Built-in | Built-in |
| Ideale per | Default choice, ecosistema maturo | API eleganti, middleware custom | Ultra-performance, migrazione da Node.js |

!!! warning "Fiber e net/http incompatibilità"
    Fiber usa `fasthttp` invece di `net/http`. Molte librerie Go standard e middleware OpenTelemetry/Prometheus assumono `net/http`. Prima di scegliere Fiber, verificare la compatibilità dell'intera dependency chain.

### Gin — Struttura Base

```go
package main

import (
    "net/http"
    "go.uber.org/automaxprocs"   // GOMAXPROCS automatico
    "github.com/gin-gonic/gin"
    "log/slog"
    "os"
)

func main() {
    logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))

    r := gin.New()
    r.Use(gin.Recovery())  // panic recovery middleware

    // Health endpoints separati da logica di business
    r.GET("/healthz", func(c *gin.Context) {
        c.JSON(http.StatusOK, gin.H{"status": "ok"})
    })
    r.GET("/readyz", func(c *gin.Context) {
        // verificare dipendenze (DB, cache, ecc.)
        c.JSON(http.StatusOK, gin.H{"status": "ready"})
    })

    v1 := r.Group("/api/v1")
    {
        v1.GET("/users/:id", getUser)
        v1.POST("/users", createUser)
    }

    logger.Info("server starting", "addr", ":8080")
    if err := r.Run(":8080"); err != nil {
        logger.Error("server failed", "error", err)
        os.Exit(1)
    }
}
```

### Echo — Middleware e Routing

```go
package main

import (
    "github.com/labstack/echo/v4"
    "github.com/labstack/echo/v4/middleware"
    "net/http"
)

func main() {
    e := echo.New()
    e.HideBanner = true

    // Middleware globali
    e.Use(middleware.RequestID())
    e.Use(middleware.Recover())
    e.Use(middleware.Logger())  // structured logging

    // Gruppi con middleware specifici
    api := e.Group("/api/v1", middleware.JWT([]byte(os.Getenv("JWT_SECRET"))))
    api.GET("/items/:id", getItem)
    api.POST("/items", createItem)

    e.Logger.Fatal(e.Start(":8080"))
}

// Handler con binding e validation automatica
func createItem(c echo.Context) error {
    var req CreateItemRequest
    if err := c.Bind(&req); err != nil {
        return echo.NewHTTPError(http.StatusBadRequest, err.Error())
    }
    if err := c.Validate(&req); err != nil {
        return echo.NewHTTPError(http.StatusUnprocessableEntity, err.Error())
    }
    // logica di business...
    return c.JSON(http.StatusCreated, item)
}
```

---

## Configurazione & Pratica

### Viper — Configurazione Multi-Source

Viper legge configurazione da file (YAML, TOML, JSON), variabili d'ambiente, e flag CLI. Supporta hot-reload e naming case-insensitive. In Kubernetes, la priorità consigliata è: env var > ConfigMap montato come file > default.

```go
package config

import (
    "github.com/spf13/viper"
    "strings"
)

type Config struct {
    Server   ServerConfig   `mapstructure:"server"`
    Database DatabaseConfig `mapstructure:"database"`
}

type ServerConfig struct {
    Port         int    `mapstructure:"port"`
    ReadTimeout  int    `mapstructure:"read_timeout"`
    WriteTimeout int    `mapstructure:"write_timeout"`
}

type DatabaseConfig struct {
    DSN          string `mapstructure:"dsn"`
    MaxOpenConns int    `mapstructure:"max_open_conns"`
    MaxIdleConns int    `mapstructure:"max_idle_conns"`
}

func Load() (*Config, error) {
    v := viper.New()

    // File di configurazione (opzionale — fallback su env vars)
    v.SetConfigName("config")
    v.SetConfigType("yaml")
    v.AddConfigPath("/etc/service/")   // ConfigMap montato
    v.AddConfigPath(".")               // sviluppo locale

    // Env vars — prefisso SERVICE_, separatore _ per nesting
    v.SetEnvPrefix("SERVICE")
    v.SetEnvKeyReplacer(strings.NewReplacer(".", "_"))
    v.AutomaticEnv()

    // Default
    v.SetDefault("server.port", 8080)
    v.SetDefault("server.read_timeout", 30)
    v.SetDefault("database.max_open_conns", 25)
    v.SetDefault("database.max_idle_conns", 5)

    if err := v.ReadInConfig(); err != nil {
        if _, ok := err.(viper.ConfigFileNotFoundError); !ok {
            return nil, err  // errore reale, non "file non trovato"
        }
    }

    var cfg Config
    if err := v.Unmarshal(&cfg); err != nil {
        return nil, err
    }
    return &cfg, nil
}
```

```yaml
# config.yaml (montato come ConfigMap)
server:
  port: 8080
  read_timeout: 30
  write_timeout: 30
database:
  max_open_conns: 25
  max_idle_conns: 5
# DSN viene da env var SERVICE_DATABASE_DSN (non in ConfigMap — è un secret)
```

### Structured Logging — slog (Go 1.21+)

Go 1.21 ha introdotto `log/slog` nella standard library. Per servizi nuovi è la scelta consigliata: zero dipendenze esterne, API ergonomica, output JSON pronto per Loki/CloudWatch.

```go
package main

import (
    "log/slog"
    "os"
    "net/http"
    "context"
)

func main() {
    // Handler JSON per produzione, Text per sviluppo
    var handler slog.Handler
    if os.Getenv("ENV") == "production" {
        handler = slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{
            Level: slog.LevelInfo,
        })
    } else {
        handler = slog.NewTextHandler(os.Stdout, &slog.HandlerOptions{
            Level: slog.LevelDebug,
        })
    }
    logger := slog.New(handler)
    slog.SetDefault(logger)  // logger globale

    // Logging con attributi strutturati
    slog.Info("server starting", "port", 8080, "env", os.Getenv("ENV"))
    slog.Error("database connection failed",
        "error", err,
        "dsn_host", dbHost,   // mai loggare credenziali complete
        "retry_attempt", attempt,
    )

    // Logger contestuale con campi fissi (es. request_id, trace_id)
    reqLogger := logger.With(
        "request_id", requestID,
        "user_id", userID,
    )
    reqLogger.Info("processing request", "method", r.Method, "path", r.URL.Path)
}
```

### Zerolog — Alternativa a slog ad Alte Performance

Zerolog è preferito quando il logging è sul critical path (es. servizi che logano ogni richiesta ad alto RPS). Usa allocation-zero tramite method chaining.

```go
import "github.com/rs/zerolog/log"

// Setup globale
zerolog.TimeFieldFormat = zerolog.TimeFormatUnixMs
log.Logger = log.With().Str("service", "my-service").Logger()

// Logging zero-allocation
log.Info().
    Str("method", r.Method).
    Str("path", r.URL.Path).
    Int("status", statusCode).
    Dur("latency", time.Since(start)).
    Msg("request completed")

log.Error().
    Err(err).
    Str("operation", "db.query").
    Msg("query failed")
```

!!! tip "slog vs zerolog — quando scegliere"
    Usare **slog** (stdlib) per nuovi servizi: zero dipendenze, API stabile, sufficiente per 99% dei casi. Usare **zerolog** solo se il profiling dimostra che il logging è un bottleneck reale (servizi >50k RPS con logging per-request).

---

## context.Context — Propagation e Cancellation

`context.Context` è il meccanismo idiomatico Go per propagare cancellation, deadline e valori attraverso la call chain. Ogni funzione che fa I/O o operazioni bloccanti deve accettare un context come primo parametro.

```go
// Funzione che accetta context — pattern idiomatico
func fetchUser(ctx context.Context, userID string) (*User, error) {
    // Context propagato al DB driver — si cancella se il client disconnette
    row := db.QueryRowContext(ctx, "SELECT * FROM users WHERE id = $1", userID)

    var u User
    if err := row.Scan(&u.ID, &u.Name, &u.Email); err != nil {
        return nil, fmt.Errorf("fetchUser: %w", err)
    }
    return &u, nil
}

// Timeout esplicito per operazione critica
func processOrder(ctx context.Context, orderID string) error {
    // Timeout di 5s per questa operazione specifica
    ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
    defer cancel()  // SEMPRE defer cancel() per evitare context leak

    if err := fetchInventory(ctx, orderID); err != nil {
        return fmt.Errorf("processOrder: %w", err)
    }
    return nil
}

// Fan-out con cancellation automatica al primo errore
func fetchMultiple(ctx context.Context, ids []string) ([]*Item, error) {
    g, ctx := errgroup.WithContext(ctx)  // golang.org/x/sync/errgroup
    results := make([]*Item, len(ids))

    for i, id := range ids {
        i, id := i, id  // cattura per goroutine
        g.Go(func() error {
            item, err := fetchItem(ctx, id)
            if err != nil {
                return err  // cancella le altre goroutine
            }
            results[i] = item
            return nil
        })
    }

    if err := g.Wait(); err != nil {
        return nil, err
    }
    return results, nil
}
```

```go
// Context values — solo per dati cross-cutting (request_id, trace_id)
// NON usare per dipendenze o configurazione
type contextKey string
const requestIDKey contextKey = "request_id"

func WithRequestID(ctx context.Context, id string) context.Context {
    return context.WithValue(ctx, requestIDKey, id)
}

func RequestIDFromContext(ctx context.Context) string {
    if id, ok := ctx.Value(requestIDKey).(string); ok {
        return id
    }
    return ""
}
```

!!! warning "Context leak — defer cancel() obbligatorio"
    `context.WithTimeout` e `context.WithCancel` allocano risorse interne non rilasciate fino a cancellazione o scadenza. Senza `defer cancel()` si crea un goroutine leak. La regola è assoluta: **ogni `WithTimeout`/`WithCancel`/`WithDeadline` deve avere il proprio `defer cancel()`**.

---

## Graceful Shutdown

Il graceful shutdown in Go usa `signal.NotifyContext` (Go 1.16+) per intercettare SIGTERM/SIGINT e dare tempo al server di completare le richieste in corso prima di terminare.

```go
package main

import (
    "context"
    "log/slog"
    "net/http"
    "os"
    "os/signal"
    "syscall"
    "time"

    "github.com/gin-gonic/gin"
    _ "go.uber.org/automaxprocs"
)

func main() {
    router := setupRouter()

    srv := &http.Server{
        Addr:         ":8080",
        Handler:      router,
        ReadTimeout:  30 * time.Second,
        WriteTimeout: 30 * time.Second,
        IdleTimeout:  120 * time.Second,
    }

    // Avvio server in goroutine separata
    go func() {
        slog.Info("server listening", "addr", srv.Addr)
        if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
            slog.Error("server error", "error", err)
            os.Exit(1)
        }
    }()

    // Attesa segnale — SIGTERM (Kubernetes) o SIGINT (Ctrl+C)
    ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGTERM, syscall.SIGINT)
    defer stop()

    <-ctx.Done()  // blocca fino a segnale
    slog.Info("shutdown signal received")

    // Grace period: 30s per completare richieste in corso
    shutdownCtx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
    defer cancel()

    if err := srv.Shutdown(shutdownCtx); err != nil {
        slog.Error("graceful shutdown failed", "error", err)
        os.Exit(1)
    }

    slog.Info("server stopped gracefully")
}
```

---

## gRPC con protoc-gen-go

```protobuf
// api/user/v1/user.proto
syntax = "proto3";
package user.v1;
option go_package = "github.com/myorg/service/api/user/v1;userv1";

service UserService {
    rpc GetUser(GetUserRequest) returns (GetUserResponse);
    rpc ListUsers(ListUsersRequest) returns (stream User);  // server streaming
}

message GetUserRequest { string id = 1; }
message GetUserResponse { User user = 1; }
message User {
    string id = 1;
    string name = 2;
    string email = 3;
}
```

```go
// Generazione codice
// buf generate  (consigliato — usa buf.gen.yaml)
// oppure: protoc --go_out=. --go-grpc_out=. api/user/v1/user.proto

// Implementazione server
package server

import (
    "context"
    userv1 "github.com/myorg/service/api/user/v1"
    "google.golang.org/grpc/codes"
    "google.golang.org/grpc/status"
)

type UserServiceServer struct {
    userv1.UnimplementedUserServiceServer  // forward compatibility
    repo UserRepository
}

func (s *UserServiceServer) GetUser(ctx context.Context, req *userv1.GetUserRequest) (*userv1.GetUserResponse, error) {
    if req.Id == "" {
        return nil, status.Error(codes.InvalidArgument, "id is required")
    }

    user, err := s.repo.FindByID(ctx, req.Id)
    if err != nil {
        if errors.Is(err, ErrNotFound) {
            return nil, status.Error(codes.NotFound, "user not found")
        }
        return nil, status.Error(codes.Internal, "internal error")
    }

    return &userv1.GetUserResponse{
        User: &userv1.User{Id: user.ID, Name: user.Name, Email: user.Email},
    }, nil
}

// Avvio server gRPC
func StartGRPCServer(addr string, svc *UserServiceServer) error {
    lis, err := net.Listen("tcp", addr)
    if err != nil {
        return err
    }

    s := grpc.NewServer(
        grpc.ChainUnaryInterceptor(
            otelgrpc.UnaryServerInterceptor(),  // OpenTelemetry tracing
            grpc_recovery.UnaryServerInterceptor(),  // panic recovery
        ),
    )
    userv1.RegisterUserServiceServer(s, svc)
    reflection.Register(s)  // abilita grpcurl/grpc-gateway in dev

    return s.Serve(lis)
}
```

---

## Testing Idiomatico

### Table-Driven Tests

Il pattern table-driven è lo standard Go per testare múltipli scenari. Ogni riga della tabella è un test case con input, output atteso e nome descrittivo.

```go
package service_test

import (
    "context"
    "testing"
    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/require"
)

func TestCalculateDiscount(t *testing.T) {
    tests := []struct {
        name          string
        orderTotal    float64
        customerTier  string
        expectedDisc  float64
        expectError   bool
    }{
        {
            name:         "gold customer — 20% discount",
            orderTotal:   100.0,
            customerTier: "gold",
            expectedDisc: 20.0,
        },
        {
            name:         "standard customer — no discount",
            orderTotal:   100.0,
            customerTier: "standard",
            expectedDisc: 0.0,
        },
        {
            name:        "invalid tier — error",
            orderTotal:  100.0,
            customerTier: "unknown",
            expectError: true,
        },
        {
            name:        "zero order — zero discount",
            orderTotal:  0.0,
            customerTier: "gold",
            expectedDisc: 0.0,
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            discount, err := CalculateDiscount(tt.orderTotal, tt.customerTier)

            if tt.expectError {
                require.Error(t, err)
                return
            }

            require.NoError(t, err)
            assert.InDelta(t, tt.expectedDisc, discount, 0.001)
        })
    }
}
```

### Mocking con Interfacce

Go non ha generics per i mock nella stdlib. Il pattern corretto è definire interfacce locali e implementare mock a mano (o con `mockery`/`gomock` per grandi codebase).

```go
// Interfaccia definita dove viene USATA, non dove viene implementata
type UserRepository interface {
    FindByID(ctx context.Context, id string) (*User, error)
    Save(ctx context.Context, user *User) error
}

// Mock manuale — semplice e leggibile per pochi metodi
type mockUserRepository struct {
    findByIDFunc func(ctx context.Context, id string) (*User, error)
    saveFunc     func(ctx context.Context, user *User) error
}

func (m *mockUserRepository) FindByID(ctx context.Context, id string) (*User, error) {
    return m.findByIDFunc(ctx, id)
}

func (m *mockUserRepository) Save(ctx context.Context, user *User) error {
    return m.saveFunc(ctx, user)
}

// Test con mock
func TestUserService_GetUser(t *testing.T) {
    tests := []struct {
        name       string
        userID     string
        repoUser   *User
        repoErr    error
        expectErr  bool
    }{
        {
            name:     "user found",
            userID:   "user-123",
            repoUser: &User{ID: "user-123", Name: "Alice"},
        },
        {
            name:      "user not found",
            userID:    "missing",
            repoErr:   ErrNotFound,
            expectErr: true,
        },
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            repo := &mockUserRepository{
                findByIDFunc: func(_ context.Context, id string) (*User, error) {
                    return tt.repoUser, tt.repoErr
                },
            }
            svc := NewUserService(repo)

            user, err := svc.GetUser(context.Background(), tt.userID)
            if tt.expectErr {
                require.Error(t, err)
            } else {
                require.NoError(t, err)
                assert.Equal(t, tt.repoUser.ID, user.ID)
            }
        })
    }
}
```

```bash
# Esecuzione test con race detector — sempre in CI
go test -race ./...

# Test con coverage e output verbose
go test -v -coverprofile=coverage.out ./...
go tool cover -html=coverage.out  # report HTML

# Benchmark
go test -bench=. -benchmem ./pkg/...

# Generazione mock con mockery (alternativa per interfacce numerose)
go install github.com/vektra/mockery/v2@latest
mockery --name=UserRepository --outpkg=mocks --output=./internal/mocks
```

---

## Best Practices

**Struttura del progetto:** seguire la convenzione `cmd/` per i main package, `internal/` per codice non esportabile fuori dal modulo, `pkg/` per librerie riutilizzabili, `api/` per definizioni protobuf/OpenAPI.

```
service/
├── cmd/
│   └── service/
│       └── main.go          # entrypoint — wiring DI, avvio server
├── internal/
│   ├── config/              # viper config loading
│   ├── handler/             # HTTP/gRPC handler
│   ├── service/             # business logic — dipende da interfacce
│   ├── repository/          # implementazione accesso dati
│   └── model/               # struct dominio
├── api/
│   └── user/v1/
│       └── user.proto
├── go.mod
└── go.sum
```

!!! tip "Errori — wrapping idiomatico"
    Usare sempre `fmt.Errorf("operation: %w", err)` per wrappare errori con contesto. Questo permette `errors.Is()` e `errors.As()` nella call chain e genera stack trace leggibili nei log. Non usare `errors.New()` per errori che devono propagare contesto.

!!! tip "HTTP server timeout — configurare sempre"
    Un `http.Server` senza timeout espliciti è vulnerabile a Slowloris e connessioni pendenti. Impostare sempre `ReadTimeout`, `WriteTimeout` e `IdleTimeout`. Per handler lenti usare `context.WithTimeout` nella logica, non aumentare `WriteTimeout` globalmente.

**Gestione delle dipendenze:** `go mod tidy` prima di ogni commit. Fissare le versioni minori in `go.mod` per build riproducibili. Usare `go mod vendor` in ambienti air-gapped.

---

## Troubleshooting

### goroutine leak — numero goroutine cresce indefinitamente

**Sintomo:** `runtime.NumGoroutine()` cresce nel tempo, memoria in aumento, profiling `/debug/pprof/goroutine` mostra goroutine bloccate in attesa di channel.

**Causa:** Channel mai chiuso, `context.WithTimeout`/`WithCancel` senza `defer cancel()`, goroutine avviate senza meccanismo di terminazione.

```bash
# Diagnostica via pprof (esporre in dev, non in prod)
curl http://localhost:6060/debug/pprof/goroutine?debug=2 | head -100

# In main.go per pprof server separato in dev
import _ "net/http/pprof"
go func() { log.Println(http.ListenAndServe("localhost:6060", nil)) }()
```

**Soluzione:** Verificare che ogni goroutine abbia un path di terminazione. Usare `errgroup` per fan-out controllato. Aggiungere test con `goleak`:
```go
import "go.uber.org/goleak"
func TestMain(m *testing.M) { goleak.VerifyTestMain(m) }
```

---

### CPU throttling in Kubernetes — latenza p99 alta

**Sintomo:** Latenza p99 >>p50, metriche Kubernetes `container_cpu_cfs_throttled_seconds_total` alta.

**Causa:** `GOMAXPROCS` impostato al numero di CPU del nodo host invece del quota del container (mancanza di `automaxprocs`). Il GC Go schedula goroutine sui thread, e con troppi thread sul runtime Go si genera eccessivo context switching.

**Soluzione:**
```go
// main.go
import _ "go.uber.org/automaxprocs"  // imposta GOMAXPROCS corretto automaticamente
```

Verificare nel log di avvio: `maxprocs: Updating GOMAXPROCS=2: determined from CPU quota`.

---

### Data race — panic o comportamento non deterministico

**Sintomo:** Crash intermittente con `DATA RACE` nei log, comportamento non riproducibile, valori corrotti.

**Causa:** Accesso concorrente non sincronizzato a variabili condivise (map, slice, struct senza mutex).

**Soluzione:** Eseguire sempre i test con `-race`. Per map condivise usare `sync.Map` o proteggere con `sync.RWMutex`. Per contatori usare `sync/atomic`.

```go
// Anti-pattern — map non thread-safe
var cache = map[string]*Item{}
go func() { cache["key"] = item }()  // DATA RACE

// Soluzione 1 — sync.RWMutex
var (
    mu    sync.RWMutex
    cache = map[string]*Item{}
)
mu.Lock()
cache["key"] = item
mu.Unlock()

// Soluzione 2 — sync.Map (ottimizzata per molte goroutine)
var cache sync.Map
cache.Store("key", item)
val, ok := cache.Load("key")
```

---

### Connessioni DB esaurite — `sql: database is closed` o timeout

**Sintomo:** Errori `context deadline exceeded` su query DB, `sql: database is closed` sotto carico, connessioni in attesa nel pool.

**Causa:** Pool DB configurato con limiti troppo bassi rispetto al carico, o connessioni non rilasciate (missing `rows.Close()`/`stmt.Close()`).

**Soluzione:**
```go
db, err := sql.Open("postgres", dsn)
if err != nil { ... }

// Configurazione pool — calibrare sul workload reale
db.SetMaxOpenConns(25)                  // max connessioni aperte verso DB
db.SetMaxIdleConns(5)                   // connessioni idle mantenute in pool
db.SetConnMaxLifetime(5 * time.Minute)  // rotazione connessioni (evita conn stale)
db.SetConnMaxIdleTime(1 * time.Minute)  // rilascio connessioni idle

// SEMPRE defer close su rows
rows, err := db.QueryContext(ctx, query, args...)
if err != nil { return err }
defer rows.Close()  // senza questo, la connessione non torna al pool
```

---

## Relazioni

??? info "gRPC — Approfondimento Protocollo"
    Go è il linguaggio di riferimento per implementazioni gRPC. `protoc-gen-go` genera codice type-safe da file `.proto`. Per service mesh (Istio, Linkerd) il transport è trasparente.

    **Approfondimento completo →** [gRPC](../../networking/protocolli/grpc.md)

??? info "ASP.NET Core e Java Quarkus — Alternative per Microservizi"
    Per team C# o Java con requisiti simili (alta concorrenza, bassa latenza, Kubernetes-native) vedere i confronti con questi framework.

    **Approfondimento completo →** [ASP.NET Core](dotnet.md) | [Java Quarkus](java-quarkus.md)

---

## Riferimenti

- [Go Documentation ufficiale](https://go.dev/doc/) — spec del linguaggio, tour, FAQ
- [Effective Go](https://go.dev/doc/effective_go) — idiomatic Go patterns
- [Go Modules Reference](https://go.dev/ref/mod) — gestione dipendenze
- [uber-go/automaxprocs](https://github.com/uber-go/automaxprocs) — GOMAXPROCS containerizzazione
- [Gin Web Framework](https://gin-gonic.com/docs/) — documentazione Gin
- [Echo Framework](https://echo.labstack.com/) — documentazione Echo
- [Viper](https://github.com/spf13/viper) — configurazione multi-source
- [zerolog](https://github.com/rs/zerolog) — zero-allocation structured logging
- [Protocol Buffers Go](https://protobuf.dev/getting-started/gotutorial/) — tutorial gRPC+protobuf Go
- [testify](https://github.com/stretchr/testify) — assert/require/mock
- [goleak](https://github.com/uber-go/goleak) — goroutine leak detector nei test
