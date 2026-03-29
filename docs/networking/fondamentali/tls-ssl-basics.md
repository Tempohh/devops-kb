---
title: "TLS/SSL — Basi"
slug: tls-ssl-basics
category: networking
tags: [tls, ssl, sicurezza, crittografia, certificati, https, pki]
search_keywords: [transport layer security, secure socket layer, tls 1.3, handshake, certificato x.509, ca, certificate authority, pki, public key infrastructure, crittografia asimmetrica, symmetric encryption, ecdhe, perfect forward secrecy, mtls, mutual tls, self-signed, let's encrypt, openssl]
parent: networking/fondamentali/_index
related: [networking/fondamentali/http-https, networking/sicurezza/firewall-waf, security/certificati]
official_docs: https://www.rfc-editor.org/rfc/rfc8446
status: complete
difficulty: intermediate
last_updated: 2026-03-29
---

# TLS/SSL — Basi

## Panoramica

TLS (Transport Layer Security) è il protocollo crittografico che garantisce comunicazioni sicure su reti non affidabili. SSL (Secure Sockets Layer) è il predecessore ormai obsoleto: nei contesti attuali "SSL" è usato impropriamente per indicare TLS. TLS opera al layer 4/5, wrappando qualsiasi protocollo applicativo (HTTP, SMTP, LDAP, ecc.) per aggiungere **confidenzialità** (cifratura), **integrità** (HMAC — Hash-based Message Authentication Code: codice che verifica che i dati non siano stati alterati in transito) e **autenticazione** (certificati).

TLS 1.3 (RFC 8446, 2018) è la versione corrente: più veloce (1-RTT — un solo Round-Trip Time per completare l'handshake invece di 2), più sicura (rimozione di cipher suite deboli), e con perfect forward secrecy obbligatorio. TLS 1.0 e 1.1 sono deprecati; TLS 1.2 è ancora accettabile ma TLS 1.3 è da preferire.

## Concetti Chiave

### PKI — Public Key Infrastructure

La PKI è il sistema di fiducia su cui si basa TLS:

- **Certificato X.509**: documento digitale che lega un'identità (hostname, organizzazione) a una chiave pubblica
- **CA (Certificate Authority)**: entità fidata che firma e valida i certificati
- **Certificate Chain**: il certificato di un server è firmato da una CA intermedia, che è firmata da una Root CA
- **Root CA**: CA al vertice della gerarchia; i browser/OS includono un set di Root CA fidate ("trust store")

```
Root CA (trust store del browser)
  └── Intermediate CA (firmata dalla Root CA)
        └── Certificato server example.com (firmato dalla Intermediate CA)
```

### Crittografia Asimmetrica vs Simmetrica

TLS usa entrambe in fasi distinte:

| Fase | Tipo | Algoritmo (TLS 1.3) | Scopo |
|------|------|---------------------|-------|
| Handshake | Asimmetrica | ECDHE + firma RSA/ECDSA (Elliptic Curve Digital Signature Algorithm) | Autenticazione + scambio chiavi |
| Dati | Simmetrica | AES-256-GCM, ChaCha20-Poly1305 | Cifratura efficiente del traffico |

!!! note "Perfect Forward Secrecy"
    ECDHE (Elliptic Curve Diffie-Hellman Ephemeral) genera chiavi di sessione temporanee per ogni connessione. Anche se la chiave privata del server venisse compromessa in futuro, le sessioni passate restano protette perché le chiavi efimere non vengono mai memorizzate.

### Versioni TLS

| Versione | Anno | Stato | Note |
|----------|------|-------|------|
| SSL 3.0 | 1996 | Deprecato | POODLE attack |
| TLS 1.0 | 1999 | Deprecato (RFC 8996) | BEAST attack |
| TLS 1.1 | 2006 | Deprecato (RFC 8996) | |
| TLS 1.2 | 2008 | Accettabile | Ancora largo uso |
| TLS 1.3 | 2018 | **Raccomandato** | Più veloce e sicuro |

## Architettura / Come Funziona

### TLS 1.3 Handshake (1-RTT)

```
Client                                    Server
  |                                          |
  |── ClientHello ──────────────────────────>|
  |   (TLS version, cipher suites, key share)|
  |                                          |
  |<── ServerHello ───────────────────────── |
  |    (cipher suite, key share)             |
  |<── Certificate ────────────────────────── |
  |    (server cert + chain)                 |
  |<── CertificateVerify ──────────────────── |
  |    (firma con chiave privata server)     |
  |<── Finished ───────────────────────────── |
  |                                          |
  |── Finished ────────────────────────────>|
  |                                          |
  |══ Dati cifrati (Application Data) ══════|
```

In TLS 1.3 il server può inviare dati cifrati già dopo il primo RTT. TLS 1.3 supporta anche **0-RTT** (Zero Round-Trip Time — il client invia dati già nel primo pacchetto usando i parametri di una sessione precedente, senza attendere il completamento dell'handshake; attenzione: vulnerabile a replay attacks).

### mTLS — Mutual TLS

In TLS standard solo il server si autentica. In mTLS **entrambi** i lati si autenticano:

```
Client                                    Server
  |── ClientHello ──────────────────────────>|
  |<── ServerHello + Certificate ────────────|
  |── Certificate (client cert) ───────────>|  ← differenza mTLS
  |── CertificateVerify ─────────────────────>|  ← differenza mTLS
  |── Finished ────────────────────────────>|
  |<── Finished ───────────────────────────── |
```

mTLS è usato per:
- Service-to-service communication (service mesh: Istio, Linkerd)
- API con client autenticati
- Zero Trust architectures

## Configurazione & Pratica

### OpenSSL — Comandi Fondamentali

```bash
# Verifica certificato remoto
openssl s_client -connect example.com:443 -servername example.com

# Informazioni su un certificato
openssl x509 -in certificate.crt -text -noout

# Verifica scadenza
openssl x509 -in certificate.crt -noout -dates

# Genera chiave privata RSA 4096-bit
openssl genrsa -out private.key 4096

# Genera chiave EC (più veloce, stessa sicurezza)
openssl ecparam -genkey -name prime256v1 -out ec-private.key

# Genera CSR (Certificate Signing Request)
openssl req -new -key private.key -out certificate.csr \
  -subj "/CN=example.com/O=My Org/C=IT"

# Self-signed certificate (test/dev only)
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem \
  -days 365 -nodes -subj "/CN=localhost"

# Verifica catena di certificati
openssl verify -CAfile ca-bundle.crt certificate.crt

# Testa cipher suite specifiche
openssl s_client -connect example.com:443 -cipher ECDHE-RSA-AES256-GCM-SHA384
```

### Let's Encrypt con Certbot

```bash
# Installa certbot
apt install certbot python3-certbot-nginx

# Ottieni certificato con validazione HTTP (Nginx)
certbot --nginx -d example.com -d www.example.com

# Ottieni certificato standalone (ferma temporaneamente il web server)
certbot certonly --standalone -d example.com

# Rinnova automaticamente (eseguito da systemd timer o cron)
certbot renew --quiet

# Verifica rinnovo
certbot renew --dry-run

# Certificati salvati in:
# /etc/letsencrypt/live/example.com/fullchain.pem  ← cert + chain
# /etc/letsencrypt/live/example.com/privkey.pem    ← chiave privata
```

### Configurazione Nginx TLS Ottimale

```nginx
ssl_protocols TLSv1.2 TLSv1.3;

# Cipher suites TLS 1.3 (automatiche), + buone per TLS 1.2
ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
ssl_prefer_server_ciphers off;  # In TLS 1.3 il client sceglie

# Session resumption (migliora performance)
ssl_session_cache   shared:SSL:10m;
ssl_session_timeout 1d;
ssl_session_tickets off;  # Disabilitare per PFS

# OCSP Stapling (OCSP = Online Certificate Status Protocol — protocollo per verificare se un certificato è ancora valido o è stato revocato) — il server include lo status del certificato nella risposta
ssl_stapling on;
ssl_stapling_verify on;
resolver 1.1.1.1 8.8.8.8 valid=300s;

# HSTS (HTTP Strict Transport Security) — istruisce il browser a usare sempre HTTPS per questo dominio
add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
```

### Configurazione mTLS con Nginx

```nginx
server {
    listen 443 ssl http2;
    server_name api.example.com;

    ssl_certificate     /etc/ssl/server.crt;
    ssl_certificate_key /etc/ssl/server.key;

    # mTLS: richiede e verifica il certificato client
    ssl_client_certificate /etc/ssl/ca.crt;
    ssl_verify_client on;
    ssl_verify_depth 2;

    location / {
        # Passa il CN del certificato client come header
        proxy_set_header X-Client-Cert-CN $ssl_client_s_dn_cn;
        proxy_pass http://backend;
    }
}
```

## Best Practices

- **Usare TLS 1.3** dove possibile; TLS 1.2 come fallback minimo
- **Mai usare certificati self-signed in produzione** — usare Let's Encrypt (gratuito) o una CA aziendale
- **Monitorare la scadenza** dei certificati: impostare alert a 30/14/7 giorni prima
- **HSTS con preload**: dopo il deploy verificare su [hstspreload.org](https://hstspreload.org)
- **OCSP Stapling**: riduce latenza e carica la CRL/OCSP offline
- **Ruotare i certificati** prima della scadenza, automatizzare con certbot/cert-manager
- **Non disabilitare la verifica** del certificato (es. `--insecure` in curl, `verify=False` in Python) — anche in ambienti di test

## Troubleshooting

### Scenario 1 — Certificato scaduto

**Sintomo:** Il browser mostra `NET::ERR_CERT_DATE_INVALID`; openssl restituisce `certificate has expired`.

**Causa:** Il certificato ha superato la data di scadenza in `notAfter`. Frequente se il rinnovo automatico (certbot timer, cert-manager) è fallito silenziosamente.

**Soluzione:** Rinnovare il certificato e verificare la pipeline di rinnovo automatico.

```bash
# Controlla scadenza del certificato remoto
echo | openssl s_client -connect example.com:443 -servername example.com 2>/dev/null \
  | openssl x509 -noout -dates

# Rinnova con certbot
certbot renew --cert-name example.com --force-renewal

# Verifica che il timer di rinnovo sia attivo
systemctl status certbot.timer

# In Kubernetes con cert-manager: forza il rinnovo
kubectl annotate certificate example-cert -n mynamespace \
  cert-manager.io/force-renewal="$(date +%s)"
```

### Scenario 2 — Verifica certificato fallita (CA non fidata)

**Sintomo:** `certificate verify failed: unable to get local issuer certificate`; in curl `SSL certificate problem: unable to get local issuer certificate`.

**Causa:** La CA che ha firmato il certificato non è nel trust store del client. Comune con CA aziendali interne, certificati self-signed, o catene incomplete (manca la CA intermedia).

**Soluzione:** Aggiungere la CA al trust store oppure fornire esplicitamente la catena al client.

```bash
# Verifica la catena restituita dal server
openssl s_client -connect example.com:443 -servername example.com -showcerts 2>/dev/null \
  | grep -E "s:|i:"

# Verifica con una CA specifica
openssl verify -CAfile /path/to/ca-bundle.crt /path/to/server.crt

# Aggiungi CA aziendale al trust store (Debian/Ubuntu)
cp my-corporate-ca.crt /usr/local/share/ca-certificates/
update-ca-certificates

# Aggiungi CA al trust store (RHEL/CentOS)
cp my-corporate-ca.crt /etc/pki/ca-trust/source/anchors/
update-ca-trust extract

# curl: specifica la CA senza modificare il sistema
curl --cacert /path/to/ca.crt https://internal.example.com
```

### Scenario 3 — Handshake failure (versione TLS o cipher incompatibili)

**Sintomo:** `SSL handshake failure`, `no shared cipher`, oppure connessione rifiutata senza errore TLS specifico. Frequente dopo aggiornamenti di configurazione server o durante migrazione a TLS 1.3.

**Causa:** Il client e il server non hanno in comune nessuna versione TLS o cipher suite. Ad esempio: server configurato solo TLS 1.3, client legacy supporta solo TLS 1.2; oppure cipher suite rimosse per hardening.

**Soluzione:** Identificare quale versione/cipher il client supporta e allineare la configurazione server.

```bash
# Testa quali versioni TLS il server accetta
for ver in ssl3 tls1 tls1_1 tls1_2 tls1_3; do
  echo -n "$ver: "
  openssl s_client -connect example.com:443 -$ver 2>&1 | grep -E "Protocol|Cipher|handshake failure" | head -2
done

# Elenca le cipher suite supportate dal server
nmap --script ssl-enum-ciphers -p 443 example.com

# Verifica la configurazione attuale di Nginx
nginx -T | grep -E "ssl_protocols|ssl_ciphers"

# Test con cipher specifica
openssl s_client -connect example.com:443 -cipher ECDHE-RSA-AES256-GCM-SHA384
```

### Scenario 4 — OCSP Stapling non funzionante

**Sintomo:** Nginx log mostra `OCSP_basic_verify() failed`; `ssl_stapling` abilitato ma il browser non riceve la risposta OCSP. Latenza aggiuntiva sulle connessioni HTTPS.

**Causa:** Il server non riesce a raggiungere il responder OCSP della CA (problema DNS o rete), oppure il resolver configurato in Nginx non è accessibile dal server.

**Soluzione:** Verificare la connettività al responder OCSP e la configurazione del resolver.

```bash
# Ottieni l'URL del responder OCSP dal certificato
openssl x509 -in /etc/ssl/server.crt -noout -ocsp_uri

# Verifica manuale OCSP stapling
openssl s_client -connect example.com:443 -servername example.com -status 2>/dev/null \
  | grep -A 10 "OCSP response"

# Test diretto del responder OCSP
openssl ocsp -issuer /etc/ssl/intermediate.crt \
             -cert /etc/ssl/server.crt \
             -url http://ocsp.example-ca.com \
             -resp_text

# Verifica che il resolver Nginx raggiunga internet
# In nginx.conf: resolver deve essere un DNS pubblico o interno funzionante
nginx -t && grep resolver /etc/nginx/nginx.conf

# Ricarica Nginx dopo la correzione
nginx -s reload
```

## Relazioni

??? info "HTTP e HTTPS — Protocollo applicativo"
    TLS è il livello di sicurezza su cui opera HTTPS.

    **Approfondimento →** [HTTP e HTTPS](http-https.md)

??? info "Firewall e WAF — Protezione perimetrale"
    TLS si integra con WAF per ispezione del traffico cifrato (TLS termination).

    **Approfondimento →** [Firewall e WAF](../sicurezza/firewall-waf.md)

## Riferimenti

- [RFC 8446 — TLS 1.3](https://www.rfc-editor.org/rfc/rfc8446)
- [SSL Labs — Test TLS Configuration](https://www.ssllabs.com/ssltest/)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [Mozilla SSL Configuration Generator](https://ssl-config.mozilla.org/)
