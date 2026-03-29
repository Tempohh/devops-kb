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
last_updated: 2026-03-29
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

### Scenario 1 — ERR_SSL_PROTOCOL_ERROR / Handshake TLS fallito

**Sintomo:** Il browser mostra `ERR_SSL_PROTOCOL_ERROR` o `SSL_ERROR_HANDSHAKE_FAILURE_ALERT`; `curl` riporta `SSL routines:ssl3_get_server_certificate:certificate verify failed`.

**Causa:** Versione TLS non supportata (es. server accetta solo TLS 1.3 ma client supporta solo 1.2), cipher suite incompatibili, certificato scaduto o emesso da CA non riconosciuta.

**Soluzione:** Verificare la configurazione TLS del server e il certificato.

```bash
# Ispezionare certificato e handshake
openssl s_client -connect example.com:443 -showcerts

# Verificare scadenza certificato
echo | openssl s_client -connect example.com:443 2>/dev/null \
  | openssl x509 -noout -dates

# Testare versioni TLS specifiche
curl --tlsv1.2 https://example.com
curl --tlsv1.3 https://example.com

# Verifica con nmap
nmap --script ssl-enum-ciphers -p 443 example.com
```

---

### Scenario 2 — 502 Bad Gateway / 504 Gateway Timeout

**Sintomo:** Gli utenti ricevono `502 Bad Gateway` o `504 Gateway Timeout` dal reverse proxy (Nginx, ALB). Il backend è apparentemente up.

**Causa:** Il backend non risponde entro il timeout configurato nel proxy, la connessione viene rifiutata (backend crashato o porta sbagliata), oppure il proxy non riesce a raggiungere il backend (problema di rete/DNS interno).

**Soluzione:** Verificare health del backend e timeout del proxy.

```bash
# Testare backend direttamente (bypass proxy)
curl -v http://backend-host:8080/health

# Controllare log Nginx
tail -100 /var/log/nginx/error.log | grep "upstream"

# Verificare connettività da proxy a backend
nc -zv backend-host 8080

# Aumentare timeout in Nginx se il backend è lento
# In nginx.conf:
# proxy_connect_timeout 10s;
# proxy_read_timeout 60s;
# proxy_send_timeout 60s;

# Controllare processo backend
systemctl status app-service
journalctl -u app-service --since "10 minutes ago"
```

---

### Scenario 3 — ERR_TOO_MANY_REDIRECTS / Loop redirect

**Sintomo:** Il browser mostra `ERR_TOO_MANY_REDIRECTS`; `curl -L` va in loop tra 301 e 302.

**Causa:** Configurazione errata dei redirect HTTP→HTTPS quando il reverse proxy comunica con il backend in HTTP ma il backend reindirizza di nuovo a HTTPS, oppure conflitto tra redirect a www e non-www.

**Soluzione:** Correggere la chain di redirect e impostare correttamente `X-Forwarded-Proto`.

```bash
# Diagnosticare la chain di redirect
curl -v -L --max-redirs 5 http://example.com 2>&1 | grep -E "Location:|< HTTP"

# Verificare quanti redirect avvengono
curl -o /dev/null -s -w "Redirects: %{num_redirects}\nFinal URL: %{url_effective}\n" \
     -L http://example.com

# Fix tipico in Nginx (passare proto al backend)
# proxy_set_header X-Forwarded-Proto $scheme;

# Fix in applicazione Laravel/Rails: leggere X-Forwarded-Proto
# e non forzare redirect se già HTTPS
```

---

### Scenario 4 — 403 Forbidden inatteso / CORS Error

**Sintomo:** Le chiamate API restituiscono `403 Forbidden` senza motivo apparente, oppure il browser mostra `CORS policy: No 'Access-Control-Allow-Origin' header`.

**Causa:** Per il 403: rate limiting, IP ban, JWT scaduto/invalido, policy IAM restrittiva. Per CORS: il server non include gli header `Access-Control-Allow-Origin` per il dominio del client, o il preflight OPTIONS non viene gestito.

**Soluzione:** Diagnosticare la fonte del 403 e configurare CORS se necessario.

```bash
# Ispezionare risposta completa con headers
curl -v -H "Origin: https://frontend.example.com" \
        -H "Authorization: Bearer TOKEN" \
        https://api.example.com/resource

# Testare preflight CORS manualmente
curl -v -X OPTIONS \
     -H "Origin: https://frontend.example.com" \
     -H "Access-Control-Request-Method: POST" \
     -H "Access-Control-Request-Headers: Content-Type,Authorization" \
     https://api.example.com/resource

# Decodificare JWT per verificare scadenza
echo "TOKEN" | cut -d. -f2 | base64 -d 2>/dev/null | python3 -m json.tool

# Header Nginx per CORS (esempio)
# add_header 'Access-Control-Allow-Origin' 'https://frontend.example.com';
# add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS';
```

---

### Scenario 5 — Performance degradata / Lentezza inspiegabile

**Sintomo:** Le richieste HTTP sono lente anche per risorse piccole; il time-to-first-byte (TTFB) è alto; ogni richiesta sembra aprire una nuova connessione TCP.

**Causa:** Keep-alive disabilitato (ogni richiesta apre una nuova connessione TCP+TLS), HTTP/1.1 invece di HTTP/2, compressione assente, o cache non configurata.

**Soluzione:** Abilitare keep-alive, HTTP/2 e compressione.

```bash
# Misurare tempi dettagliati per ogni fase
curl -o /dev/null -s -w \
  "DNS: %{time_namelookup}s\nConnect: %{time_connect}s\nTLS: %{time_appconnect}s\nTTFB: %{time_starttransfer}s\nTotal: %{time_total}s\n" \
  https://example.com

# Verificare se HTTP/2 è attivo
curl -v --http2 https://example.com 2>&1 | grep -E "HTTP/[12]"

# Controllare headers di compressione nella risposta
curl -H "Accept-Encoding: gzip, br" -I https://example.com | grep -i "content-encoding"

# Verificare keep-alive
curl -v https://example.com 2>&1 | grep -i "keep-alive\|connection"
```

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
