---
title: "WebSocket"
slug: websocket
category: networking
tags: [websocket, realtime, bidirezionale, http, protocolli, push, streaming]
search_keywords: [websocket protocol, ws, wss, full-duplex, bidirectional, real-time, long polling, server-sent events, sse, socket.io, upgrade header, handshake, pub-sub, chat, notifiche, live updates]
parent: networking/protocolli/_index
related: [networking/fondamentali/http-https, networking/protocolli/http2-http3, networking/protocolli/grpc]
official_docs: https://www.rfc-editor.org/rfc/rfc6455
status: reviewed
difficulty: intermediate
last_updated: 2026-10-03
last_verified: 2026-10-03
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
  |   Client→Server: text frame  {"type":"msg","text":"ciao"}
  |   Server→Client: text frame  {"type":"msg","from":"Bob","text":"ciao"}
  |   Server→Client: Ping frame (opcode 0x9, control frame)
  |   Client→Server: Pong frame (opcode 0xA, control frame)
```

Il campo `Sec-WebSocket-Accept` è la codifica base64 dello SHA-1 di `Sec-WebSocket-Key` concatenata con un GUID fisso (`258EAFA5-E914-47DA-95CA-C5AB0DC85B11`). Prova che il server ha capito il protocollo WebSocket (evita che un server HTTP qualsiasi o una cache intermedia scambi la richiesta per una normale) — non autentica né il server né il client.

!!! note "Masking"
    Tutti i frame **client→server** sono mascherati (campo `MASK=1`, chiave XOR di 32 bit casuale per frame): serve a impedire che un client malevolo faccia interpretare dati scelti da lui come richieste HTTP a proxy intermedi (cache poisoning). I frame server→client non sono mascherati.

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

Ping e Pong sono **control frame** del protocollo, distinti dai messaggi applicativi. L'API `WebSocket` del browser non permette di inviare ping né di osservare i pong: il browser risponde ai ping da solo. Per un heartbeat lato client (es. rilevare un server muto) serve quindi un messaggio applicativo `{"type":"ping"}`.

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
    # least_conn è adatto (le connessioni sono long-lived: round-robin può sbilanciare).
    # ip_hash serve solo se il protocollo richiede sticky session (es. fallback long-polling di Socket.IO)
}

server {
    listen 443 ssl;
    http2 on;   # nginx >= 1.25.1 (la forma "listen ... http2" è deprecata). I browser fanno comunque l'upgrade WebSocket su HTTP/1.1
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

- **Autenticazione**: WebSocket non ha un meccanismo di auth nativo e l'API del browser non permette header custom (`Authorization`). Opzioni: cookie `HttpOnly`/`Secure`/`SameSite` sull'handshake; ticket monouso a vita breve ottenuto via REST e passato nell'URL; oppure token inviato come primo messaggio. Evitare JWT long-lived in `?token=...`: finisce nei log di proxy e server
- **Controllo `Origin`**: i browser inviano `Origin` nell'handshake ma la same-origin policy **non** si applica a WebSocket. Se l'auth è via cookie, senza verifica dell'`Origin` lato server un sito terzo può aprire il socket con le credenziali della vittima (Cross-Site WebSocket Hijacking, CSWSH). Validare `Origin` contro una allowlist e rifiutare con `403`
- **Heartbeat**: implementare ping/pong per rilevare connessioni morte (proxy e firewall chiudono connessioni inattive dopo 60-120s)
- **Riconnessione esponenziale**: il client deve riconnettersi automaticamente con backoff esponenziale + jitter
- **Messaggio con schema**: definire un formato JSON consistente con `type`, `payload`, `id` per ogni messaggio
- **Limitare la dimensione dei messaggi**: prevenire abusi con una dimensione massima per frame
- **Rate limiting**: controllare la frequenza dei messaggi per client
- **Scalabilità**: usare un message broker (Redis Pub/Sub, Kafka) per distribuire messaggi su più istanze del server

## Troubleshooting

### Scenario 1 — Handshake fallisce: nessun `101 Switching Protocols`

**Sintomo:** Il client riceve `200 OK` o `400 Bad Request` invece di `101 Switching Protocols`. La connessione WebSocket non si stabilisce mai.

**Causa:** Il reverse proxy (Nginx, HAProxy, AWS ALB) non propaga gli header `Upgrade` e `Connection: upgrade` (Nginx per default parla HTTP/1.0 verso l'upstream e li scarta), oppure la richiesta arriva su HTTP/2, dove il meccanismo `Upgrade` non esiste (WebSocket su HTTP/2 richiede l'extended CONNECT di RFC 8441, supportato solo da alcuni stack).

**Soluzione:** Aggiungere nella configurazione del proxy gli header obbligatori per il protocollo WebSocket upgrade, e forzare HTTP/1.1 sul backend.

```nginx
location /ws {
    proxy_pass http://websocket_backend;
    proxy_http_version 1.1;                        # WebSocket richiede HTTP/1.1
    proxy_set_header Upgrade $http_upgrade;        # Propaga l'header Upgrade
    proxy_set_header Connection "upgrade";         # Necessario per il cambio protocollo
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}
```

Per verificare gli header inviati dal client:
```bash
curl -v \
  -H "Upgrade: websocket" \
  -H "Connection: Upgrade" \
  -H "Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==" \
  -H "Sec-WebSocket-Version: 13" \
  https://example.com/ws
# Atteso nella risposta: HTTP/1.1 101 Switching Protocols
# curl non parla WebSocket: dopo il 101 resta appeso, interrompere con Ctrl+C (o aggiungere --max-time 5).
# Aggiungere --http1.1 per evitare la negoziazione HTTP/2 via ALPN. Alternativa: websocat
```

---

### Scenario 2 — Connessione si chiude inaspettatamente dopo 60-120 secondi

**Sintomo:** Il client riceve un evento `close` con codice `1006` (abnormal closure) dopo circa 60-120 secondi di inattività, anche senza che nessuno dei due lati abbia chiuso esplicitamente.

**Causa:** I proxy intermedi (Nginx, AWS ELB, CDN) hanno timeout configurati per le connessioni "idle". Una connessione WebSocket senza traffico viene considerata morta e terminata.

**Soluzione:** Combinare due azioni: aumentare i timeout sul proxy E abilitare il heartbeat ping/pong lato server.

```nginx
# Nginx: aumentare i timeout per connessioni WebSocket
location /ws {
    proxy_read_timeout  3600s;   # Default: 60s — insufficiente per WebSocket
    proxy_send_timeout  3600s;
    proxy_connect_timeout 10s;
}
```

```javascript
// Node.js ws: heartbeat ogni 30s per mantenere viva la connessione
const interval = setInterval(() => {
  wss.clients.forEach((ws) => {
    if (ws.isAlive === false) {
      console.log('Client non risponde al ping — terminato');
      return ws.terminate();
    }
    ws.isAlive = false;
    ws.ping();  // Invia ping; il client risponde con pong automaticamente
  });
}, 30000);
```

---

### Scenario 3 — Messaggi persi dopo scaling orizzontale o restart del server

**Sintomo:** Con più istanze del server (pod Kubernetes, auto-scaling), i messaggi inviati da un client non raggiungono altri client connessi su istanze diverse. Oppure i messaggi si perdono durante un restart.

**Causa:** Lo stato delle connessioni WebSocket è in-memory e locale a ciascuna istanza. Il broadcast `wss.clients.forEach(...)` raggiunge solo i client connessi alla stessa istanza.

**Soluzione:** Aggiungere un message broker (Redis Pub/Sub è il più comune) come layer di distribuzione tra istanze.

```javascript
const Redis = require('ioredis');
const pub = new Redis({ host: 'redis-host' });
const sub = new Redis({ host: 'redis-host' });

// Subscribe al canale condiviso
sub.subscribe('broadcast-channel');
sub.on('message', (channel, message) => {
  // Distribuisci ai client locali di questa istanza
  wss.clients.forEach((client) => {
    if (client.readyState === WebSocket.OPEN) {
      client.send(message);
    }
  });
});

// Quando un messaggio arriva da un client, pubblicalo su Redis
ws.on('message', (message) => {
  pub.publish('broadcast-channel', message);  // Tutte le istanze lo riceveranno
});
```

!!! warning "Garanzie di consegna"
    Redis Pub/Sub è *at-most-once*: se un'istanza è in restart o disconnessa, perde i messaggi pubblicati nel frattempo. Per consegna affidabile o replay dopo riconnessione usare Redis Streams o Kafka, e far inviare al client l'ultimo `id` ricevuto per recuperare il gap.

Verifica la connettività Redis:
```bash
redis-cli -h redis-host ping
redis-cli -h redis-host monitor  # Solo debug: rallenta sensibilmente Redis, evitare in produzione
```

---

### Scenario 4 — Handshake fallisce su HTTPS / `wss://` non funziona

**Sintomo:** La connessione WebSocket funziona in locale (`ws://localhost`), ma fallisce in produzione su HTTPS con errore `Mixed Content` o `ERR_SSL_PROTOCOL_ERROR`.

**Causa:** Su una pagina caricata via HTTPS, il browser blocca connessioni WebSocket non sicure (`ws://`). Bisogna usare `wss://` (WebSocket over TLS) che usa la stessa porta 443 e lo stesso certificato TLS del sito.

**Soluzione:** Usare sempre `wss://` in produzione. Il certificato TLS viene gestito dal proxy (Nginx/ALB), non dall'applicazione WebSocket.

```javascript
// Sbagliato in produzione su HTTPS
const ws = new WebSocket('ws://example.com/ws');

// Corretto — usa lo schema della pagina corrente
const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
```

Verifica il certificato e la connessione TLS:
```bash
# Testa che wss:// funzioni (richiede websocat)
websocat wss://example.com/ws

# Oppure con openssl per verificare il certificato
openssl s_client -connect example.com:443 -servername example.com
```

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
