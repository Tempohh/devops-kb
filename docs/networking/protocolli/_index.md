---
title: "Protocolli di Rete"
slug: protocolli
category: networking
tags: [protocolli, tcp, udp, http2, http3, grpc, websocket, quic]
search_keywords: [tcp udp protocolli, http2 multiplexing, http3 quic, grpc protocol buffers, websocket realtime, quic protocol]
parent: networking
status: complete
difficulty: intermediate
last_updated: 2026-02-24
---

# Protocolli di Rete

I protocolli di rete definiscono le regole e i formati con cui i sistemi comunicano tra loro. La scelta del protocollo corretto influenza direttamente performance, affidabilità, latenza e complessità architetturale di un sistema distribuito.

Questa sezione copre i principali protocolli utilizzati in contesti DevOps e cloud-native: dal livello di trasporto (TCP/UDP) fino ai protocolli applicativi moderni (HTTP/2, HTTP/3, gRPC, WebSocket, QUIC).

---

## Contenuti

| Argomento | Difficoltà | Descrizione |
|-----------|-----------|-------------|
| [TCP e UDP](tcp-udp.md) | Intermedio | Fondamenti del livello di trasporto: connection-oriented vs connectionless, handshake, flow control, congestion control |
| [HTTP/2 e HTTP/3](http2-http3.md) | Intermedio | Evoluzione di HTTP: multiplexing, HPACK compression, migrazione a QUIC |
| [QUIC](quic.md) | Avanzato | Protocollo di trasporto next-generation su UDP: 0-RTT, stream multipli, connection migration |
| [WebSocket](websocket.md) | Intermedio | Comunicazione full-duplex persistente: upgrade handshake, scaling, sticky sessions |
| [gRPC](grpc.md) | Avanzato | Framework RPC ad alte prestazioni: Protocol Buffers, 4 pattern di comunicazione, integrazione Kubernetes |

---

## Come Scegliere il Protocollo

```
Hai bisogno di comunicazione in tempo reale bidirezionale?
  ├── Sì → WebSocket (chat, gaming, live dashboard)
  └── No
      ├── Hai bisogno di streaming server → client?
      │   └── Sì → Server-Sent Events o gRPC Server Streaming
      └── No
          ├── Microservizi interni ad alte performance?
          │   └── Sì → gRPC (+ Protocol Buffers)
          └── No
              ├── API pubblica o browser-facing?
              │   └── Sì → HTTP/2 o HTTP/3 (REST o GraphQL)
              └── Applicazioni latency-sensitive (DNS, gaming, IoT)?
                  └── Sì → UDP diretto o QUIC
```

---

## Relazioni con Altri Argomenti

- **Load Balancing**: ogni protocollo richiede considerazioni specifiche per il bilanciamento del carico (es. sticky sessions per WebSocket, L4 vs L7 per gRPC)
- **Service Mesh**: Istio e Envoy gestiscono mTLS e load balancing a livello di protocollo
- **Networking Fondamentali**: la comprensione del modello OSI e del DNS è prerequisita per questa sezione
