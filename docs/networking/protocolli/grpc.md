---
title: "gRPC"
slug: grpc
category: networking
tags: [grpc, protobuf, rpc, microservizi, streaming, http2, performance]
search_keywords: [google remote procedure call, protocol buffers, protobuf, grpc streaming, unary, server streaming, client streaming, bidirectional streaming, .proto, service definition, grpc-gateway, grpc-web, service mesh, deadline, interceptor, reflection]
parent: networking/protocolli/_index
related: [networking/protocolli/http2-http3, networking/protocolli/websocket, networking/service-mesh/istio, networking/api-gateway/pattern-base]
official_docs: https://grpc.io/docs/
status: reviewed
difficulty: intermediate
last_updated: 2026-10-03
last_verified: 2026-10-03
---

# gRPC

## Panoramica

gRPC (Google Remote Procedure Call) è un framework RPC open source ad alte prestazioni che usa **Protocol Buffers** (protobuf) come linguaggio di serializzazione e **HTTP/2** come trasporto. Permette di chiamare funzioni su un server remoto come se fossero locali, con generazione automatica del codice client/server da un file `.proto` che definisce il contratto del servizio.

gRPC è lo standard de facto per la comunicazione service-to-service nei microservizi: è fortemente tipizzato, efficiente (serializzazione binaria ~10x più compatta di JSON), supporta streaming bidirezionale e funziona in modo nativo con Kubernetes e service mesh come Istio. Non è adatto per browser (limitazioni HTTP/2) o API pubbliche (protobuf richiede schema condiviso).

## Concetti Chiave

### Protocol Buffers (Protobuf)

Il file `.proto` è il contratto del servizio: definisce i messaggi (strutture dati) e i servizi (funzioni RPC). Il compilatore `protoc` genera codice client e server in oltre 10 linguaggi.

```protobuf
// user.proto
syntax = "proto3";

package user.v1;

import "google/protobuf/timestamp.proto";  // necessario per google.protobuf.Timestamp

option go_package = "github.com/example/user/v1";

// Definizione dei messaggi
message GetUserRequest {
  string user_id = 1;  // Field number, non cambiare mai
}

message User {
  string id = 1;
  string name = 2;
  string email = 3;
  repeated string roles = 4;  // Array
  google.protobuf.Timestamp created_at = 5;
}

message ListUsersResponse {
  repeated User users = 1;
  string next_page_token = 2;
}

message ListUsersRequest {
  int32 page_size = 1;
  string page_token = 2;
}

message CreateUserRequest {
  string name = 1;
  string email = 2;
}

message BatchCreateResponse {
  int32 created_count = 1;
}

message ChatMessage {
  string sender_id = 1;
  string text = 2;
}

// Definizione del servizio
service UserService {
  // Unary RPC
  rpc GetUser(GetUserRequest) returns (User);

  // Server streaming RPC
  rpc ListUsers(ListUsersRequest) returns (stream User);

  // Client streaming RPC
  rpc BatchCreateUsers(stream CreateUserRequest) returns (BatchCreateResponse);

  // Bidirectional streaming RPC
  rpc Chat(stream ChatMessage) returns (stream ChatMessage);
}
```

### Tipi di RPC

| Tipo | Client invia | Server risponde | Use Case |
|------|-------------|-----------------|----------|
| Unary | 1 richiesta | 1 risposta | CRUD classico, query |
| Server streaming | 1 richiesta | N risposte | Feed dati, log streaming, large datasets |
| Client streaming | N richieste | 1 risposta | Upload file, batch insert |
| Bidirectional streaming | N richieste | N risposte | Chat, gaming, real-time sync |

### Protobuf vs JSON/XML

| Aspetto | Protobuf | JSON | XML |
|---------|----------|------|-----|
| Formato | Binario | Testo | Testo |
| Dimensione | ~1x (baseline) | ~5-10x | ~10-15x |
| Parsing speed | ~10x più veloce | 1x | ~0.5x |
| Human readable | No | Sì | Sì |
| Schema | Obbligatorio | Opzionale | Opzionale |
| Browser support | Limitato | Nativo | Nativo |

## Architettura / Come Funziona

### Stack gRPC

```
Applicazione
     │
  gRPC Stub (generato da protoc)
     │  ← Serializzazione Protobuf
  HTTP/2 Layer
     │  ← Multiplexing, header compression
    TLS
     │
    TCP
```

### Flusso di una chiamata Unary

```
Client                          Server
  |                               |
  |── HTTP/2 HEADERS ────────────>|
  |   :method POST                |
  |   :path /user.v1.UserService/GetUser
  |   content-type: application/grpc
  |   grpc-timeout: 5S            |
  |                               |
  |── HTTP/2 DATA ───────────────>|
  |   [Protobuf serialized body]  |
  |   Length-Prefix + Message     |
  |                               |
  |<── HTTP/2 HEADERS ─────────── |
  |    :status 200                |
  |<── HTTP/2 DATA ─────────────── |
  |    [Protobuf serialized User] |
  |<── HTTP/2 HEADERS (trailers) ─ |
  |    grpc-status: 0             |
  |    grpc-message: (empty)      |
```

### Status Codes gRPC

| Code | Nome | Uso |
|------|------|-----|
| 0 | OK | Successo |
| 1 | CANCELLED | Cancellato dal client |
| 2 | UNKNOWN | Errore generico server |
| 3 | INVALID_ARGUMENT | Input non valido |
| 4 | DEADLINE_EXCEEDED | Timeout |
| 5 | NOT_FOUND | Risorsa non trovata |
| 6 | ALREADY_EXISTS | Risorsa già esistente (create duplicata) |
| 7 | PERMISSION_DENIED | Identità nota ma non autorizzata |
| 8 | RESOURCE_EXHAUSTED | Rate limit, quota esaurita |
| 9 | FAILED_PRECONDITION | Stato del sistema non adatto all'operazione (non ritentare finché non cambia) |
| 10 | ABORTED | Conflitto di concorrenza (es. transazione); ritentare a livello di transazione |
| 12 | UNIMPLEMENTED | Metodo non implementato/esposto dal server |
| 13 | INTERNAL | Errore interno server |
| 14 | UNAVAILABLE | Servizio non disponibile — transitorio, **ritentabile** |
| 16 | UNAUTHENTICATED | Credenziali mancanti o non valide |

!!! note "Quali codici ritentare"
    Di norma solo `UNAVAILABLE` è sicuro da ritentare automaticamente (e `DEADLINE_EXCEEDED`/`ABORTED` solo se l'operazione è idempotente). Ritentare `INVALID_ARGUMENT` o `FAILED_PRECONDITION` non può mai riuscire. Distinguere `UNAUTHENTICATED` (chi sei?) da `PERMISSION_DENIED` (non puoi farlo) evita loop di re-login inutili sul client.

## Configurazione & Pratica

### Implementazione Go

```go
// server/main.go
package main

import (
    "context"
    "net"
    "log"

    "google.golang.org/grpc"
    "google.golang.org/grpc/codes"
    "google.golang.org/grpc/status"
    pb "github.com/example/user/v1"
)

type userServer struct {
    pb.UnimplementedUserServiceServer
    db UserStore // dipendenze (db, cache, ecc.); interfaccia con FindUser(ctx, id)
}

func (s *userServer) GetUser(ctx context.Context, req *pb.GetUserRequest) (*pb.User, error) {
    if req.UserId == "" {
        return nil, status.Error(codes.InvalidArgument, "user_id è obbligatorio")
    }

    // Logica di business...
    user, err := s.db.FindUser(ctx, req.UserId)
    if err != nil {
        return nil, status.Errorf(codes.NotFound, "utente %s non trovato", req.UserId)
    }

    return user, nil
}

func main() {
    lis, _ := net.Listen("tcp", ":50051")

    // Interceptor per logging e auth
    grpcServer := grpc.NewServer(
        grpc.ChainUnaryInterceptor(
            loggingInterceptor,
            authInterceptor,
        ),
    )

    pb.RegisterUserServiceServer(grpcServer, &userServer{})

    log.Println("gRPC server in ascolto su :50051")
    if err := grpcServer.Serve(lis); err != nil {
        log.Fatalf("Failed to serve: %v", err)
    }
}
```

```go
// client/main.go
package main

import (
    "context"
    "log"
    "time"

    "google.golang.org/grpc"
    "google.golang.org/grpc/credentials/insecure"
    pb "github.com/example/user/v1"
)

func main() {
    // grpc.Dial è deprecato: NewClient non connette subito (lazy) e usa il resolver DNS di default
    conn, err := grpc.NewClient(
        "dns:///user-service:50051",
        grpc.WithTransportCredentials(insecure.NewCredentials()),
        grpc.WithDefaultCallOptions(grpc.WaitForReady(true)),
    )
    if err != nil {
        log.Fatalf("Connessione fallita: %v", err)
    }
    defer conn.Close()

    client := pb.NewUserServiceClient(conn)

    // Deadline (timeout) per la chiamata
    ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
    defer cancel()

    user, err := client.GetUser(ctx, &pb.GetUserRequest{UserId: "user-123"})
    if err != nil {
        log.Fatalf("GetUser fallito: %v", err)
    }

    log.Printf("Utente: %s (%s)", user.Name, user.Email)
}
```

### Compilazione del file .proto

```bash
# Installa protoc e plugin Go
go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest

# Genera codice Go
protoc --go_out=. --go_opt=paths=source_relative \
       --go-grpc_out=. --go-grpc_opt=paths=source_relative \
       proto/user.proto

# Genera codice Python
python -m grpc_tools.protoc -I. \
  --python_out=. --grpc_python_out=. \
  proto/user.proto

# Genera per più linguaggi in un colpo solo (con Buf)
buf generate
```

### Testing con grpcurl

```bash
# Lista servizi disponibili (richiede server reflection)
grpcurl -plaintext localhost:50051 list

# Descrivi un servizio
grpcurl -plaintext localhost:50051 describe user.v1.UserService

# Chiama un metodo
grpcurl -plaintext \
  -d '{"user_id": "user-123"}' \
  localhost:50051 \
  user.v1.UserService/GetUser

# Con autenticazione JWT
grpcurl \
  -H "Authorization: Bearer TOKEN" \
  -d '{"user_id": "user-123"}' \
  api.example.com:443 \
  user.v1.UserService/GetUser
```

### Kubernetes — gRPC con Ingress

!!! warning "ingress-nginx è stato ritirato"
    Il progetto Kubernetes `ingress-nginx` è stato dismesso a marzo 2026 (nessuna patch di sicurezza). Per nuovi deployment preferire **Gateway API** con `GRPCRoute` (GA) su un'implementazione attiva (Envoy Gateway, Istio, Cilium, NGINX Gateway Fabric). L'esempio sotto resta valido per cluster esistenti.

```yaml
# Per gRPC su Kubernetes con NGINX Ingress Controller
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: grpc-ingress
  annotations:
    nginx.ingress.kubernetes.io/backend-protocol: "GRPC"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - api.example.com
    secretName: api-tls
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /user.v1.UserService
        pathType: Prefix
        backend:
          service:
            name: user-service
            port:
              number: 50051
```

## Best Practices

- **Versionare i servizi**: usare package `service.v1`, `service.v2` — non modificare field numbers nei messaggi
- **Deadline everywhere**: ogni chiamata deve avere un timeout; propagare il context con deadline ai chiamati
- **Interceptor per cross-cutting concerns**: logging, auth, tracing, rate limiting — non nel business logic
- **Server reflection**: abilitare in dev/staging per grpcurl; disabilitare in produzione se non necessario
- **Health checks**: implementare `grpc.health.v1.Health`; Kubernetes lo interroga nativamente con `livenessProbe`/`readinessProbe: grpc: {port: 50051}` (GA dalla 1.27), senza binari `grpc_health_probe` nell'immagine
- **Error handling**: usare sempre `status.Errorf(codes.X, "messaggio")` — mai errori Go grezzi
- **Backward compatibility protobuf**: non rimuovere/rinominare field; aggiungere field con nuovi numeri; usare `optional` per field opzionali

!!! warning "gRPC e Load Balancer L4"
    HTTP/2 multiplexing fa sì che tutte le richieste gRPC vadano sulla stessa connessione TCP. I load balancer L4 (AWS NLB, ELB classico) non bilanciano a livello di chiamata gRPC. Usare un LB L7 (AWS ALB, Nginx, Envoy) o il load balancing client-side.

## Troubleshooting

### Scenario 1 — `DEADLINE_EXCEEDED`

**Sintomo**: le chiamate falliscono con `rpc error: code = DeadlineExceeded` anche se il server risponde.

**Causa**: la deadline (il client la invia come timeout *residuo* nell'header `grpc-timeout`; ogni hop la ricalcola dal proprio `ctx`) è più bassa della latenza reale, oppure una catena di servizi consuma il budget prima dell'ultimo hop.

**Soluzione**: misurare la latenza per metodo, alzare la deadline dove giustificato e propagare sempre il `ctx` ai servizi a valle, così il budget residuo è coerente.

```bash
# Misura il tempo reale della chiamata (-max-time = deadline lato client)
grpcurl -plaintext -max-time 10 -d '{"user_id":"user-123"}' \
  localhost:50051 user.v1.UserService/GetUser
```

### Scenario 2 — `UNAVAILABLE` dopo un deploy

**Sintomo**: picco di errori `UNAVAILABLE` durante il rolling update.

**Causa**: il client riusa connessioni HTTP/2 verso pod terminati; il pod riceve SIGTERM prima che l'endpoint sia rimosso dal Service.

**Soluzione**: retry con backoff esponenziale (service config), `preStop` sleep e shutdown graceful (`GracefulStop()`) per drenare gli stream in corso.

```bash
# Verifica che il pod risponda al health check gRPC standard
grpcurl -plaintext localhost:50051 grpc.health.v1.Health/Check
kubectl rollout status deployment/user-service
kubectl get endpoints user-service
```

### Scenario 3 — Tutto il traffico su un solo pod

**Sintomo**: un pod è saturo, gli altri sono idle, pur con più repliche.

**Causa**: un LB L4 (o un Service ClusterIP) bilancia per connessione TCP; HTTP/2 multiplexa tutte le chiamate su una sola connessione long-lived.

**Soluzione**: usare un LB L7 (Envoy, NGINX, Istio) oppure un Service *headless* con load balancing client-side `round_robin`.

```bash
# Service headless: il DNS restituisce tutti i pod IP
kubectl get svc user-service -o jsonpath='{.spec.clusterIP}'   # deve essere None
# Lato client Go: dial con dns:/// e policy round_robin
#   grpc.NewClient("dns:///user-service-headless:50051",
#     grpc.WithDefaultServiceConfig(`{"loadBalancingConfig":[{"round_robin":{}}]}`))
```

### Scenario 4 — Errori di deserializzazione dopo un aggiornamento dello schema

**Sintomo**: campi vuoti o errori `proto: cannot parse invalid wire-format data` tra versioni diverse di client e server.

**Causa**: un field number è stato cambiato o riusato; sul wire protobuf identifica i campi solo per numero, non per nome.

**Soluzione**: non modificare mai i numeri esistenti, marcare i campi rimossi con `reserved`, e controllare le breaking change in CI.

```bash
# Rileva breaking change rispetto al branch main
buf breaking --against '.git#branch=main'
```

### Scenario 5 — Il browser non si connette

**Sintomo**: `fetch` o client JS fallisce con errore di rete/protocollo verso il servizio gRPC.

**Causa**: i browser non espongono trailer e framing HTTP/2 di gRPC, quindi non possono parlare gRPC nativo.

**Soluzione**: esporre gRPC-Web tramite proxy (Envoy `grpc_web` filter) oppure un'API REST con grpc-gateway.

```bash
# Verifica che il proxy risponda a una richiesta gRPC-Web
curl -i -X POST https://api.example.com/user.v1.UserService/GetUser \
  -H "content-type: application/grpc-web+proto" -H "x-grpc-web: 1"
```

## Relazioni

??? info "HTTP/2 — Trasporto gRPC"
    gRPC usa HTTP/2 per multiplexing e header compression.

    **Approfondimento →** [HTTP/2 e HTTP/3](http2-http3.md)

??? info "Istio — Service Mesh con supporto gRPC nativo"
    Istio comprende il protocollo gRPC e offre load balancing L7 su singola chiamata.

    **Approfondimento →** [Istio](../service-mesh/istio.md)

## Riferimenti

- [gRPC Documentation](https://grpc.io/docs/)
- [Protocol Buffers Language Guide](https://protobuf.dev/programming-guides/proto3/)
- [Google API Design Guide](https://cloud.google.com/apis/design)
- [Buf — Modern Protobuf tooling](https://buf.build/docs/)
