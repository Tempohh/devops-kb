---
title: "TLS/SSL in Kafka"
slug: tls-ssl
category: messaging
tags: [kafka, sicurezza, tls, ssl, crittografia, certificati]
search_keywords: [tls, ssl, kafka encryption, keystore, truststore, jks, pkcs12, cifratura, trasporto, certificati, openssl, keytool, mutual tls, mtls, one-way tls]
parent: messaging/kafka/sicurezza
related: [messaging/kafka/sicurezza/sasl, messaging/kafka/sicurezza/acl-autorizzazione]
official_docs: https://kafka.apache.org/documentation/#security_ssl
status: complete
difficulty: advanced
last_updated: 2026-02-23
---

# TLS/SSL in Kafka

## Panoramica

TLS (Transport Layer Security) in Kafka protegge la comunicazione in transito tra client e broker, e tra broker e broker, attraverso la cifratura del canale di trasporto. Senza TLS, credenziali e messaggi viaggiano in chiaro sulla rete, esponendosi a intercettazioni e attacchi man-in-the-middle. Kafka supporta TLS sia in modalità **one-way** (solo il server si autentica con un certificato) sia in modalità **mutual TLS (mTLS)**, in cui anche il client presenta un certificato. La configurazione richiede la gestione di **keystore** e **truststore** in formato JKS o PKCS12, e l'integrazione con il sistema di autenticazione (SASL o certificato client come principal).

!!! warning "TLS non è autenticazione"
    TLS cifra il canale ma non identifica automaticamente l'utente applicativo. Per l'autenticazione usare SASL o mTLS con `ssl.client.auth=required`. Per l'autorizzazione configurare le ACL.

---

## Concetti Chiave

### Keystore e Truststore

| Componente | Contenuto | Usato da |
|------------|-----------|----------|
| **Keystore** | Chiave privata + certificato del soggetto | Broker (server cert), Client in mTLS |
| **Truststore** | Certificati CA da cui ci si fida | Tutti i partecipanti |

- **JKS (Java KeyStore)**: formato nativo Java, deprecato in favore di PKCS12 nelle versioni recenti della JVM.
- **PKCS12 (.p12 / .pfx)**: standard industriale, interoperabile con OpenSSL.
- In Kafka è possibile usare entrambi; PKCS12 è raccomandato per nuove installazioni.

### One-Way TLS vs Mutual TLS (mTLS)

```
One-Way TLS:
  Client ──[verifica cert server]──> Broker
  (client non si autentica con certificato)

Mutual TLS (mTLS):
  Client ──[verifica cert server]──> Broker
  Broker ──[verifica cert client]──> Client
  (entrambi si autenticano con certificato)
```

Con mTLS il principal del client è estratto dal **Distinguished Name (DN)** del certificato, es. `CN=alice,OU=ingegneria,O=azienda`.

---

## Come Funziona

### Handshake TLS in Kafka

1. Il client si connette alla porta TLS del broker (es. `9093`).
2. Il broker invia il proprio certificato (firmato dalla CA).
3. Il client verifica il certificato contro il proprio truststore.
4. (Solo mTLS) Il broker richiede il certificato client; il client lo invia; il broker verifica.
5. Viene negoziata la cipher suite e stabilita la sessione cifrata.
6. Tutto il traffico successivo (autenticazione SASL, messaggi, metadata) viaggia cifrato.

### Porte Kafka per TLS

```
9092 → PLAINTEXT (no TLS)
9093 → SSL (TLS one-way o mTLS)
9094 → SASL_SSL (SASL autenticazione + TLS cifratura)
```

---

## Configurazione & Pratica

### Script Completo: Generazione CA, Certificati Server e Client

```bash
#!/bin/bash
# Script per generare CA self-signed, certificati broker e client per Kafka TLS
# Prerequisiti: openssl, keytool (JDK)

set -euo pipefail

PASSWORD="changeit"
VALIDITY=3650  # giorni
CA_ALIAS="kafka-ca"
BROKER_HOSTNAME="kafka-broker-1.example.com"
CLIENT_CN="alice"

# ─── 1. Generare la Certificate Authority (CA) ───────────────────────────────
echo "==> Generazione CA..."
openssl req -new -x509 -keyout ca-key.pem -out ca-cert.pem \
  -days "$VALIDITY" \
  -passout pass:"$PASSWORD" \
  -subj "/CN=kafka-ca/OU=infra/O=azienda/L=Roma/ST=Lazio/C=IT"

# ─── 2. Creare il Truststore e importare la CA ────────────────────────────────
echo "==> Creazione truststore..."
keytool -keystore kafka.truststore.jks \
  -alias "$CA_ALIAS" \
  -importcert -file ca-cert.pem \
  -storepass "$PASSWORD" \
  -noprompt

# ─── 3. Generare il certificato del Broker ────────────────────────────────────
echo "==> Generazione certificato broker..."
# Creare keystore broker con chiave privata
keytool -keystore kafka.server.keystore.jks \
  -alias "$BROKER_HOSTNAME" \
  -keyalg RSA -keysize 4096 \
  -validity "$VALIDITY" \
  -genkey \
  -storepass "$PASSWORD" \
  -keypass "$PASSWORD" \
  -dname "CN=$BROKER_HOSTNAME,OU=infra,O=azienda,L=Roma,ST=Lazio,C=IT" \
  -ext "SAN=DNS:$BROKER_HOSTNAME,DNS:kafka-broker-1,IP:10.0.0.1"

# Generare CSR (Certificate Signing Request)
keytool -keystore kafka.server.keystore.jks \
  -alias "$BROKER_HOSTNAME" \
  -certreq -file broker.csr \
  -storepass "$PASSWORD"

# Firmare la CSR con la CA
openssl x509 -req -CA ca-cert.pem -CAkey ca-key.pem \
  -in broker.csr -out broker-signed.pem \
  -days "$VALIDITY" \
  -CAcreateserial \
  -passin pass:"$PASSWORD" \
  -extensions v3_req \
  -extfile <(printf "[v3_req]\nsubjectAltName=DNS:%s,DNS:kafka-broker-1,IP:10.0.0.1" "$BROKER_HOSTNAME")

# Importare CA e certificato firmato nel keystore broker
keytool -keystore kafka.server.keystore.jks \
  -alias "$CA_ALIAS" \
  -importcert -file ca-cert.pem \
  -storepass "$PASSWORD" -noprompt

keytool -keystore kafka.server.keystore.jks \
  -alias "$BROKER_HOSTNAME" \
  -importcert -file broker-signed.pem \
  -storepass "$PASSWORD" -noprompt

echo "==> Keystore broker creato: kafka.server.keystore.jks"

# ─── 4. Generare il certificato Client (per mTLS) ─────────────────────────────
echo "==> Generazione certificato client ($CLIENT_CN)..."
keytool -keystore kafka.client.keystore.jks \
  -alias "$CLIENT_CN" \
  -keyalg RSA -keysize 4096 \
  -validity "$VALIDITY" \
  -genkey \
  -storepass "$PASSWORD" \
  -keypass "$PASSWORD" \
  -dname "CN=$CLIENT_CN,OU=ingegneria,O=azienda,L=Roma,ST=Lazio,C=IT"

keytool -keystore kafka.client.keystore.jks \
  -alias "$CLIENT_CN" \
  -certreq -file client.csr \
  -storepass "$PASSWORD"

openssl x509 -req -CA ca-cert.pem -CAkey ca-key.pem \
  -in client.csr -out client-signed.pem \
  -days "$VALIDITY" \
  -CAcreateserial \
  -passin pass:"$PASSWORD"

keytool -keystore kafka.client.keystore.jks \
  -alias "$CA_ALIAS" \
  -importcert -file ca-cert.pem \
  -storepass "$PASSWORD" -noprompt

keytool -keystore kafka.client.keystore.jks \
  -alias "$CLIENT_CN" \
  -importcert -file client-signed.pem \
  -storepass "$PASSWORD" -noprompt

echo "==> Tutti i certificati generati con successo."
echo "    File prodotti: kafka.truststore.jks, kafka.server.keystore.jks, kafka.client.keystore.jks"
```

### Configurazione Broker (`server.properties`)

```properties
# ─── Listeners ───────────────────────────────────────────────────────────────
listeners=PLAINTEXT://0.0.0.0:9092,SSL://0.0.0.0:9093
advertised.listeners=PLAINTEXT://kafka-broker-1.example.com:9092,SSL://kafka-broker-1.example.com:9093
listener.security.protocol.map=PLAINTEXT:PLAINTEXT,SSL:SSL

# ─── TLS Broker Configuration ────────────────────────────────────────────────
ssl.keystore.location=/etc/kafka/ssl/kafka.server.keystore.jks
ssl.keystore.password=changeit
ssl.key.password=changeit
ssl.truststore.location=/etc/kafka/ssl/kafka.truststore.jks
ssl.truststore.password=changeit

# ─── Versione e Cipher Suite ─────────────────────────────────────────────────
ssl.enabled.protocols=TLSv1.3,TLSv1.2
ssl.protocol=TLSv1.3
# Lasciare vuoto per usare i default JVM (raccomandato)
# ssl.cipher.suites=TLS_AES_256_GCM_SHA384,TLS_CHACHA20_POLY1305_SHA256

# ─── Comunicazione Inter-Broker ──────────────────────────────────────────────
security.inter.broker.protocol=SSL
ssl.client.auth=none   # Cambiare in 'required' per mTLS

# ─── mTLS: richiedi certificato dal client ───────────────────────────────────
# ssl.client.auth=required
# ssl.principal.mapping.rules=RULE:^CN=([a-zA-Z0-9.]*).*$/$1/L,DEFAULT
```

### Configurazione Client (`client.properties`)

```properties
# ─── Connessione SSL ─────────────────────────────────────────────────────────
security.protocol=SSL

# Truststore: verifica il certificato del broker
ssl.truststore.location=/path/to/kafka.truststore.jks
ssl.truststore.password=changeit

# ─── Opzionale: Keystore client (richiesto solo per mTLS) ────────────────────
ssl.keystore.location=/path/to/kafka.client.keystore.jks
ssl.keystore.password=changeit
ssl.key.password=changeit

ssl.enabled.protocols=TLSv1.3,TLSv1.2
```

### Verifica della connessione TLS con `openssl`

```bash
# Verificare che il broker esponga il certificato corretto
openssl s_client -connect kafka-broker-1.example.com:9093 \
  -CAfile ca-cert.pem \
  -showcerts

# Output atteso: verificare "Verify return code: 0 (ok)"

# Testare con kafka-console-producer usando TLS
kafka-console-producer.sh \
  --bootstrap-server kafka-broker-1.example.com:9093 \
  --topic test \
  --producer.config client.properties
```

### Configurazione con PKCS12 (alternativa moderna)

```bash
# Convertire JKS esistente in PKCS12
keytool -importkeystore \
  -srckeystore kafka.server.keystore.jks -srcstoretype JKS \
  -destkeystore kafka.server.keystore.p12 -deststoretype PKCS12 \
  -srcstorepass changeit -deststorepass changeit

# Nel server.properties
ssl.keystore.type=PKCS12
ssl.keystore.location=/etc/kafka/ssl/kafka.server.keystore.p12
ssl.truststore.type=PKCS12
ssl.truststore.location=/etc/kafka/ssl/kafka.truststore.p12
```

---

## Best Practices

!!! tip "Gestione password sicura"
    Non inserire le password in chiaro in `server.properties`. Usare file di password separati con permessi `600`, oppure un secret manager (Vault, AWS Secrets Manager) e referenziarli tramite variabili d'ambiente o Kafka Config Providers.

- **Usare TLSv1.3**: disabilitare esplicitamente TLSv1.0 e TLSv1.1 con `ssl.enabled.protocols=TLSv1.3,TLSv1.2`.
- **Impostare SAN (Subject Alternative Names)**: i certificati senza SAN vengono rifiutati dai client moderni. Includere sempre hostname e IP.
- **Rotazione certificati**: automatizzare con cert-manager (Kubernetes) o un processo di rinnovo con `keytool`. Pianificare con 30 giorni di anticipo.
- **Separare i certificati per ruolo**: CA, broker, client devono avere certificati distinti.
- **Monitorare la scadenza**: configurare alert Prometheus con `ssl_expiry_days_remaining` (dal JMX exporter).
- **Inter-broker TLS**: abilitare sempre `security.inter.broker.protocol=SSL` in produzione.
- **mTLS per service-to-service**: preferire mTLS quando i client sono servizi interni, SASL per utenti applicativi.

---

## Troubleshooting

### Errore: `PKIX path building failed`

```
javax.net.ssl.SSLHandshakeException: PKIX path building failed:
sun.security.provider.certpath.SunCertPathBuilderException: unable to find valid certification path to requested target
```

**Causa**: Il truststore del client non contiene il certificato della CA che ha firmato il certificato del broker.

**Soluzione**:
```bash
# Verificare cosa contiene il truststore
keytool -list -keystore kafka.truststore.jks -storepass changeit

# Importare la CA mancante
keytool -keystore kafka.truststore.jks \
  -alias kafka-ca \
  -importcert -file ca-cert.pem \
  -storepass changeit -noprompt
```

### Errore: `SSL handshake failed` con mTLS

**Causa**: Il broker richiede il certificato client (`ssl.client.auth=required`) ma il client non ha il keystore configurato.

**Soluzione**: Verificare `ssl.keystore.location` nel `client.properties`.

### Errore: `Hostname verification failed`

```
javax.net.ssl.SSLPeerUnverifiedException: Hostname 10.0.0.1 not in certificate
```

**Causa**: Il certificato del broker non include l'IP o l'hostname usato nella connessione nei SAN.

**Soluzione**: Rigenerare il certificato includendo l'hostname/IP corretto nelle Subject Alternative Names.

### Debug TLS a livello Java

```bash
# Abilitare debug TLS nella JVM Kafka
export KAFKA_OPTS="-Djavax.net.debug=ssl:handshake:verbose"
kafka-console-producer.sh --bootstrap-server ...
```

---

## Riferimenti

- [Documentazione ufficiale Kafka TLS](https://kafka.apache.org/documentation/#security_ssl)
- [OpenSSL man page](https://www.openssl.org/docs/man3.0/man1/openssl-req.html)
- [Java Keytool reference](https://docs.oracle.com/en/java/javase/17/docs/specs/man/keytool.html)
- [Confluent TLS Guide](https://docs.confluent.io/platform/current/kafka/encryption.html)
- [RFC 8446 — TLS 1.3](https://www.rfc-editor.org/rfc/rfc8446)
