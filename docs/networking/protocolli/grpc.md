---
title: "gRPC"
slug: grpc
category: networking
tags: [grpc, protobuf, rpc, microservizi, streaming, http2, performance]
search_keywords: [google remote procedure call, protocol buffers, protobuf, grpc streaming, unary, server streaming, client streaming, bidirectional streaming, .proto, service definition, grpc-gateway, grpc-web, service mesh, deadline, interceptor, reflection]
parent: networking/protocolli/_index
related: [networking/protocolli/http2-http3, networking/protocolli/websocket, networking/service-mesh/istio, networking/api-gateway/pattern-base]
official_docs: https://grpc.io/docs/
status: complete
difficulty: intermediate
last_updated: 2026-02-24
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
| 7 | PERMISSION_DENIED | Autorizzazione negata |
| 8 | RESOURCE_EXHAUSTED | Rate limit, quota esaurita |
| 13 | INTERNAL | Errore interno server |
| 14 | UNAVAILABLE | Servizio non disponibile |

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
    // dipendenze (db, cache, ecc.)
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
    conn, err := grpc.Dial(
        "user-service:50051",
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
- **Health checks**: implementare `grpc.health.v1.Health` — riconosciuto da Kubernetes liveness probe
- **Error handling**: usare sempre `status.Errorf(codes.X, "messaggio")` — mai errori Go grezzi
- **Backward compatibility protobuf**: non rimuovere/rinominare field; aggiungere field con nuovi numeri; usare `optional` per field opzionali

!!! warning "gRPC e Load Balancer L4"
    HTTP/2 multiplexing fa sì che tutte le richieste gRPC vadano sulla stessa connessione TCP. I load balancer L4 (AWS NLB, ELB classico) non bilanciano a livello di chiamata gRPC. Usare un LB L7 (AWS ALB, Nginx, Envoy) o il load balancing client-side.

## Troubleshooting

| Sintomo | Causa | Soluzione |
|---------|-------|-----------|
| `DEADLINE_EXCEEDED` | Timeout troppo basso o server lento | Aumentare deadline, ottimizzare server |
| `UNAVAILABLE` dopo deploy | Load balancer non aggiornato | Implementare retry con backoff esponenziale |
| Tutto il traffico su 1 pod | LB L4 non bilancia HTTP/2 | Usare LB L7 o load balancing client-side |
| Errori schema dopo aggiornamento | Field number modificato | Mai modificare field numbers esistenti |
| Browser non si connette | HTTP/2 non negoziato o gRPC-Web non abilitato | Usare grpc-gateway o grpc-web proxy |

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
