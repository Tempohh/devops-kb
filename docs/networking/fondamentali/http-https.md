---
title: "HTTP e HTTPS"
slug: http-https
category: networking
tags: [http, https, web, protocolli, tls, ssl]
search_keywords: [hypertext transfer protocol, http/1.1, http/2, https, ssl, tls, request response, headers, metodi http, status code, cookie, session, rest, api, web server, secure, certificati]
parent: networking/fondamentali/_index
related: [networking/fondamentali/tls-ssl-basics, networking/protocolli/http2-http3, networking/sicurezza/firewall-waf]
official_docs: https://developer.mozilla.org/en-US/docs/Web/HTTP
status: complete
difficulty: beginner
last_updated: 2026-03-03
---

# HTTP e HTTPS

## Panoramica

HTTP (HyperText Transfer Protocol) è il protocollo applicativo fondamentale del Web, definito su TCP (porta 80) per la comunicazione client-server. Segue un modello request-response: il client invia una richiesta, il server risponde con dati e metadati. HTTPS è HTTP con crittografia TLS (Transport Layer Security), che opera sulla porta 443 e garantisce confidenzialità, integrità e autenticazione del server. Oggi HTTPS è lo standard de facto per qualsiasi servizio web.

HTTP è stateless per design: ogni richiesta è indipendente e il server non mantiene stato tra le richieste. La gestione dello stato avviene tramite meccanismi aggiuntivi come cookie, session token o JWT (JSON Web Token — token firmato crittograficamente che contiene informazioni sull'identità dell'utente, senza richiedere al server di memorizzare sessioni).

## Concetti Chiave

### Metodi HTTP

| Metodo | Significato | Idempotente | Body |
|--------|-------------|-------------|------|
| GET | Recupera una risorsa | Sì | No |
| POST | Crea una nuova risorsa | No | Sì |
| PUT | Sostituisce completamente una risorsa | Sì | Sì |
| PATCH | Modifica parzialmente una risorsa | No | Sì |
| DELETE | Elimina una risorsa | Sì | No |
| HEAD | Come GET ma senza body | Sì | No |
| OPTIONS | Descrive le opzioni di comunicazione | Sì | No |

!!! note "Idempotenza"
    Un'operazione idempotente produce lo stesso risultato se eseguita più volte. GET, PUT, DELETE sono idempotenti; POST non lo è (eseguirlo due volte crea due risorse).

### Status Codes

| Range | Categoria | Esempi comuni |
|-------|-----------|---------------|
| 1xx | Informational | 100 Continue |
| 2xx | Success | 200 OK, 201 Created, 204 No Content |
| 3xx | Redirection | 301 Moved Permanently, 302 Found, 304 Not Modified |
| 4xx | Client Error | 400 Bad Request, 401 Unauthorized, 403 Forbidden, 404 Not Found, 429 Too Many Requests |
| 5xx | Server Error | 500 Internal Server Error, 502 Bad Gateway, 503 Service Unavailable, 504 Gateway Timeout |

### Headers Principali

**Request Headers:**
```http
GET /api/users HTTP/1.1
Host: api.example.com
Authorization: Bearer eyJhbGciOiJIUzI1NiJ9...
Accept: application/json
Content-Type: application/json
User-Agent: Mozilla/5.0 ...
Cache-Control: no-cache
```

**Response Headers:**
```http
HTTP/1.1 200 OK
Content-Type: application/json
Content-Length: 1234
Cache-Control: max-age=3600
Set-Cookie: session=abc123; HttpOnly; Secure; SameSite=Strict
X-Request-Id: 7f3b2c1d
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

## Architettura / Come Funziona

### HTTP/1.1 — Request/Response Cycle

```
Client                          Server
  |                               |
  |── TCP Handshake (SYN/ACK) ──>|
  |── TLS Handshake (HTTPS) ───>|
  |                               |
  |── GET /api/users HTTP/1.1 ──>|
  |   Host: example.com           |
  |   Authorization: Bearer ...   |
  |                               |
  |<── HTTP/1.1 200 OK ──────────|
  |    Content-Type: application/json
  |    [body: JSON data]          |
  |                               |
```

### Come funziona HTTPS

1. **TCP Handshake**: connessione TCP standard sulla porta 443
2. **TLS Handshake**:
   - Client invia `ClientHello` con versioni TLS supportate e cipher suites
   - Server risponde con `ServerHello` + certificato X.509
   - Client verifica il certificato (CA chain, validità, hostname)
   - Scambio chiavi (ECDHE per perfect forward secrecy)
   - Deriva la session key simmetrica
3. **HTTP over TLS**: tutte le comunicazioni HTTP avvengono cifrate

### Keep-Alive e Connessioni

HTTP/1.1 introduce **persistent connections** (keep-alive): la stessa connessione TCP viene riusata per più richieste, evitando il costo del handshake per ogni richiesta.

```bash
# Header che controlla il comportamento
Connection: keep-alive
Keep-Alive: timeout=5, max=1000
```

!!! warning "Head-of-Line Blocking in HTTP/1.1"
    HTTP/1.1 soffre di HOL (Head-of-Line) blocking: le richieste vengono processate in ordine su una connessione — se la prima è lenta, blocca tutte le successive. I browser aprono 6-8 connessioni parallele per aggirarlo. HTTP/2 risolve questo con il multiplexing.

## Configurazione & Pratica

### curl — Tool di testing HTTP

```bash
# GET base
curl https://api.example.com/users

# GET con headers custom
curl -H "Authorization: Bearer TOKEN" \
     -H "Accept: application/json" \
     https://api.example.com/users

# POST con body JSON
curl -X POST \
     -H "Content-Type: application/json" \
     -d '{"name": "Alice", "email": "alice@example.com"}' \
     https://api.example.com/users

# Verbose — mostra headers e dettagli TLS
curl -v https://api.example.com/users

# Segui redirect
curl -L https://api.example.com/old-path

# Mostra solo status code
curl -o /dev/null -s -w "%{http_code}" https://api.example.com/health

# Test TLS/certificato
curl --cert client.crt --key client.key \
     --cacert ca.crt \
     https://secure.example.com/api
```

### Nginx — Configurazione HTTPS

```nginx
server {
    listen 80;
    server_name example.com;
    # Redirect HTTP → HTTPS
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name example.com;

    ssl_certificate     /etc/ssl/certs/example.crt;
    ssl_certificate_key /etc/ssl/private/example.key;

    # TLS 1.2+ only, strong ciphers
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    ssl_prefer_server_ciphers on;

    # HSTS — forza HTTPS per 1 anno
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    # Security headers
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options DENY;
    add_header Content-Security-Policy "default-src 'self'";

    location / {
        proxy_pass http://backend:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Caching HTTP

```http
# Cache per 1 ora
Cache-Control: max-age=3600

# Cache pubblica (CDN) + privata (browser) — 1h CDN, 5min browser
Cache-Control: public, max-age=3600, s-maxage=300

# Non cacheable
Cache-Control: no-store

# Rivalidare sempre
Cache-Control: no-cache

# ETag per conditional requests
ETag: "33a64df551425fcc55e4d42a148795d9f25f89d4"

# Conditional request — risposta 304 Not Modified se invariato
If-None-Match: "33a64df551425fcc55e4d42a148795d9f25f89d4"
```

## Best Practices

**Sicurezza:**
- Usare sempre HTTPS, mai HTTP in produzione
- Abilitare HSTS con `includeSubDomains` e `preload`
- Impostare security headers: `X-Content-Type-Options`, `X-Frame-Options`, `CSP`
- Cookie sicuri: `HttpOnly`, `Secure`, `SameSite=Strict`
- Rate limiting per prevenire abusi (429 Too Many Requests)

**Performance:**
- Abilitare HTTP/2 (multiplexing, header compression, server push)
- Configurare caching appropriato con `Cache-Control` e `ETag`
- Compressione gzip/brotli per le risposte
- Minimizzare i redirect (ogni redirect aggiunge un RTT — Round-Trip Time, il tempo per un pacchetto di andare dal client al server e tornare)

**API Design:**
- Usare il metodo HTTP corretto (GET per lettura, POST per creazione, ecc.)
- Restituire status code appropriati — mai 200 OK per errori
- Versionare le API: `/api/v1/`, `/api/v2/`
- Usare `Content-Type: application/json` consistentemente

## Troubleshooting

| Sintomo | Cause Probabili | Soluzione |
|---------|-----------------|-----------|
| `ERR_SSL_PROTOCOL_ERROR` | TLS mismatch, certificato invalido | Verificare versione TLS, validità certificato |
| `403 Forbidden` | Permessi, IP block, CORS (Cross-Origin Resource Sharing — meccanismo che controlla quali domini possono fare richieste cross-origin) | Controllare autorizzazioni, CORS policy |
| `502 Bad Gateway` | Backend down, timeout | Verificare health del backend |
| `504 Gateway Timeout` | Backend lento | Aumentare timeout, ottimizzare backend |
| `ERR_TOO_MANY_REDIRECTS` | Loop redirect | Controllare configurazione redirect HTTP↔HTTPS |
| Lentezza inspiegabile | Keep-alive disabilitato, no HTTP/2 | Abilitare keep-alive e HTTP/2 |

## Relazioni

??? info "TLS/SSL — Approfondimento"
    HTTP non garantisce sicurezza da solo. HTTPS aggiunge TLS per cifratura e autenticazione.

    **Approfondimento →** [TLS/SSL Basics](tls-ssl-basics.md)

??? info "HTTP/2 e HTTP/3 — Versioni avanzate"
    HTTP/2 risolve HOL blocking con multiplexing. HTTP/3 usa QUIC su UDP.

    **Approfondimento →** [HTTP/2 e HTTP/3](../protocolli/http2-http3.md)

## Riferimenti

- [MDN HTTP Documentation](https://developer.mozilla.org/en-US/docs/Web/HTTP)
- [RFC 9110 — HTTP Semantics](https://www.rfc-editor.org/rfc/rfc9110)
- [OWASP HTTP Security Headers](https://owasp.org/www-project-secure-headers/)
