---
title: "WebSocket"
slug: websocket
category: networking
tags: [websocket, realtime, bidirezionale, http, protocolli, push, streaming]
search_keywords: [websocket protocol, ws, wss, full-duplex, bidirectional, real-time, long polling, server-sent events, sse, socket.io, upgrade header, handshake, pub-sub, chat, notifiche, live updates]
parent: networking/protocolli/_index
related: [networking/fondamentali/http-https, networking/protocolli/http2-http3, networking/protocolli/grpc]
official_docs: https://www.rfc-editor.org/rfc/rfc6455
status: complete
difficulty: intermediate
last_updated: 2026-02-24
---

# WebSocket

## Panoramica

WebSocket (RFC 6455) è un protocollo di comunicazione **full-duplex** e persistente su una singola connessione TCP. A differenza di HTTP — request/response e stateless — WebSocket stabilisce un canale bidirezionale dove sia client che server possono inviare messaggi in qualsiasi momento, senza che il client debba fare una nuova richiesta. Usa porte 80 (ws://) e 443 (wss:// con TLS).

WebSocket è la tecnologia standard per applicazioni real-time: chat, notifiche push, trading in tempo reale, gaming multiplayer, dashboard live, collaborative editing. Non è adatto per trasferimenti di file, REST API standard o comunicazioni una-tantum.

## Concetti Chiave

### WebSocket vs Alternative Real-Time

| Tecnica | Direzione | Persistente | Complessità | Use Case |
|---------|-----------|-------------|-------------|----------|
| HTTP Polling | Client→Server ogni N sec | No | Bassa | Semplice, bassa frequenza |
| Long Polling | Server push (hold) | No | Media | Fallback per browser vecchi |
| SSE (Server-Sent Events) | Solo Server→Client | Sì | Bassa | Notifiche, feed, log streaming |
| **WebSocket** | **Full-duplex** | **Sì** | **Media** | **Chat, gaming, collaborazione** |
| gRPC Streaming | Full-duplex | Sì | Alta | Service-to-service |

### Quando usare WebSocket vs SSE

- **WebSocket**: quando il client deve inviare messaggi frequenti al server (chat, gaming, editor collaborativo)
- **SSE**: quando il flusso è solo server→client (notifiche, prezzi in tempo reale, log streaming) — SSE è più semplice, usa HTTP standard, si riconnette automaticamente

!!! tip "SSE prima di WebSocket"
    SSE spesso copre il 90% dei casi "real-time". Considera WebSocket solo quando hai genuinamente bisogno di comunicazione bidirezionale ad alta frequenza.

## Architettura / Come Funziona

### WebSocket Handshake (Upgrade da HTTP)

```
Client                                Server
  |                                      |
  |── HTTP GET /chat HTTP/1.1 ──────────>|
  |   Host: example.com                  |
  |   Upgrade: websocket                 |
  |   Connection: Upgrade                |
  |   Sec-WebSocket-Key: dGhlIHNhbXBsZS...|
  |   Sec-WebSocket-Version: 13          |
  |                                      |
  |<── HTTP/1.1 101 Switching Protocols ─|
  |    Upgrade: websocket                |
  |    Connection: Upgrade               |
  |    Sec-WebSocket-Accept: s3pPLMBiTxaQ...|
  |                                      |
  |══ WebSocket frames (full-duplex) ════|
  |   Client→Server: {"type":"msg","text":"ciao"}
  |   Server→Client: {"type":"msg","from":"Bob","text":"ciao"}
  |   Server→Client: {"type":"ping"}
  |   Client→Server: {"type":"pong"}
```

Il campo `Sec-WebSocket-Accept` è il SHA-1 della `Sec-WebSocket-Key` concatenata con un GUID fisso — meccanismo anti-cache, non autentica il server.

### Frame WebSocket

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-------+-+-------------+-------------------------------+
|F|R|R|R| opcode|M| Payload len |    Extended payload length    |
|I|S|S|S|  (4)  |A|     (7)    |             (16/64)           |
|N|V|V|V|       |S|             |   (if payload len==126/127)   |
| |1|2|3|       |K|             |                               |
+-+-+-+-+-------+-+-------------+-------------------------------+
```

**Opcode principali:**
- `0x1` Text frame
- `0x2` Binary frame
- `0x8` Connection close
- `0x9` Ping
- `0xA` Pong

### Heartbeat (Ping/Pong)

Le connessioni WebSocket inattive vengono chiuse da proxy e firewall. Il meccanismo ping/pong mantiene viva la connessione:

```
Server → Client: Ping frame (ogni 30s)
Client → Server: Pong frame (automatico o esplicito)
```

## Configurazione & Pratica

### Server Node.js con ws

```javascript
const WebSocket = require('ws');
const wss = new WebSocket.Server({ port: 8080 });

wss.on('connection', (ws, req) => {
  console.log(`Client connesso da ${req.socket.remoteAddress}`);

  // Heartbeat setup
  ws.isAlive = true;
  ws.on('pong', () => { ws.isAlive = true; });

  ws.on('message', (message) => {
    const data = JSON.parse(message);
    console.log('Ricevuto:', data);

    // Broadcast a tutti i client connessi
    wss.clients.forEach((client) => {
      if (client.readyState === WebSocket.OPEN) {
        client.send(JSON.stringify({ from: 'server', ...data }));
      }
    });
  });

  ws.on('close', () => {
    console.log('Client disconnesso');
  });

  ws.send(JSON.stringify({ type: 'welcome', message: 'Connesso!' }));
});

// Controllo heartbeat ogni 30 secondi
const interval = setInterval(() => {
  wss.clients.forEach((ws) => {
    if (!ws.isAlive) return ws.terminate();
    ws.isAlive = false;
    ws.ping();
  });
}, 30000);

wss.on('close', () => clearInterval(interval));
```

### Client JavaScript (Browser)

```javascript
const ws = new WebSocket('wss://example.com/ws');

ws.addEventListener('open', () => {
  console.log('Connesso');
  ws.send(JSON.stringify({ type: 'subscribe', channel: 'updates' }));
});

ws.addEventListener('message', (event) => {
  const data = JSON.parse(event.data);
  console.log('Messaggio ricevuto:', data);
});

ws.addEventListener('close', (event) => {
  console.log(`Connessione chiusa: ${event.code} - ${event.reason}`);
  // Riconnessione esponenziale
  setTimeout(reconnect, Math.min(1000 * 2 ** reconnectAttempts, 30000));
});

ws.addEventListener('error', (error) => {
  console.error('Errore WebSocket:', error);
});

// Chiusura pulita
function closeConnection() {
  ws.close(1000, 'Client chiusura volontaria');
}
```

### Nginx — Proxy WebSocket

```nginx
upstream websocket_backend {
    server 127.0.0.1:8080;
    # Per WebSocket non usare least_conn o ip_hash — le connessioni sono già persistenti
}

server {
    listen 443 ssl http2;
    server_name example.com;

    location /ws {
        proxy_pass http://websocket_backend;

        # Header necessari per l'upgrade WebSocket
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;

        # Timeout estesi per connessioni persistenti
        proxy_read_timeout  3600s;
        proxy_send_timeout  3600s;
        proxy_connect_timeout 10s;
    }
}
```

### WebSocket in Kubernetes (Ingress)

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: websocket-ingress
  annotations:
    nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"
    nginx.ingress.kubernetes.io/proxy-http-version: "1.1"
    # Le annotazioni Upgrade/Connection sono gestite automaticamente dall'ingress controller
spec:
  rules:
  - host: example.com
    http:
      paths:
      - path: /ws
        pathType: Prefix
        backend:
          service:
            name: websocket-service
            port:
              number: 8080
```

## Best Practices

- **Autenticazione**: WebSocket non ha un meccanismo di auth nativo — usare JWT nell'URL (`?token=...`) o cookie HttpOnly per il primo handshake HTTP
- **Heartbeat**: implementare ping/pong per rilevare connessioni morte (proxy e firewall chiudono connessioni inattive dopo 60-120s)
- **Riconnessione esponenziale**: il client deve riconnettersi automaticamente con backoff esponenziale + jitter
- **Messaggio con schema**: definire un formato JSON consistente con `type`, `payload`, `id` per ogni messaggio
- **Limitare la dimensione dei messaggi**: prevenire abusi con una dimensione massima per frame
- **Rate limiting**: controllare la frequenza dei messaggi per client
- **Scalabilità**: usare un message broker (Redis Pub/Sub, Kafka) per distribuire messaggi su più istanze del server

## Troubleshooting

| Sintomo | Causa | Soluzione |
|---------|-------|-----------|
| `101 non ricevuto` | Proxy non supporta Upgrade | Configurare `proxy_set_header Upgrade` in Nginx |
| Connessione chiusa dopo 60s | Proxy timeout su connessione inattiva | Aumentare `proxy_read_timeout`, abilitare heartbeat |
| Messaggi non consegnati su restart | Server stateless, client su altra istanza | Implementare message broker (Redis PubSub) |
| Handshake fallisce su HTTPS | Usare `wss://` non `ws://` su HTTPS | Assicurarsi di usare `wss://` |
| Alta latenza | Nagle algorithm attivo | Impostare `TCP_NODELAY` sul socket server |

## Relazioni

??? info "Server-Sent Events — Alternativa unidirezionale"
    Per flussi solo server→client SSE è più semplice di WebSocket.

    **Approfondimento →** [HTTP/2 e HTTP/3](http2-http3.md)

??? info "gRPC Streaming — Alternativa per microservizi"
    gRPC offre streaming bidirezionale type-safe per service-to-service.

    **Approfondimento →** [gRPC](grpc.md)

## Riferimenti

- [RFC 6455 — The WebSocket Protocol](https://www.rfc-editor.org/rfc/rfc6455)
- [MDN WebSocket API](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)
- [ws — Node.js WebSocket library](https://github.com/websockets/ws)
