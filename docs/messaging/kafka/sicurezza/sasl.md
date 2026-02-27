---
title: "SASL — Autenticazione Kafka"
slug: sasl
category: messaging
tags: [kafka, sicurezza, sasl, autenticazione, scram, kerberos, oauth]
search_keywords: [sasl, sasl plain, sasl scram, sasl gssapi, kerberos, oauthbearer, autenticazione kafka, kafka auth, scram-sha-256, scram-sha-512, plain, username password kafka]
parent: messaging/kafka/sicurezza
related: [messaging/kafka/sicurezza/tls-ssl, messaging/kafka/sicurezza/acl-autorizzazione]
official_docs: https://kafka.apache.org/documentation/#security_sasl
status: complete
difficulty: advanced
last_updated: 2026-02-23
---

# SASL — Autenticazione Kafka

## Panoramica

SASL (Simple Authentication and Security Layer) è il framework standard usato da Kafka per autenticare client e broker. A differenza di TLS (che protegge il trasporto), SASL identifica **chi** si sta connettendo al cluster. Kafka supporta diversi meccanismi SASL, ognuno con caratteristiche di sicurezza e complessità operative diverse: da PLAIN (il più semplice, per ambienti interni con TLS) a GSSAPI/Kerberos (standard enterprise con Active Directory) fino a OAUTHBEARER (token JWT per architetture cloud-native). SASL si usa sempre in combinazione con TLS (`SASL_SSL`) in produzione, mai con `SASL_PLAINTEXT` che trasmette credenziali in chiaro.

!!! warning "SASL_PLAINTEXT è solo per sviluppo"
    Usare `SASL_PLAINTEXT` in produzione espone username e password sulla rete. In produzione usare sempre `SASL_SSL`.

---

## Concetti Chiave

### Meccanismi SASL supportati da Kafka

| Meccanismo | Sicurezza | Complessità | Caso d'uso |
|-----------|-----------|-------------|------------|
| **PLAIN** | Media (richiede TLS) | Bassa | Dev, ambienti interni semplici |
| **SCRAM-SHA-256** | Alta | Media | Produzione senza Kerberos |
| **SCRAM-SHA-512** | Alta | Media | Produzione senza Kerberos (raccomandato) |
| **GSSAPI (Kerberos)** | Molto alta | Alta | Enterprise con Active Directory |
| **OAUTHBEARER** | Alta | Media-Alta | Cloud-native, microservizi, SSO |

### Protocol stack Kafka con SASL

```
┌─────────────────────────────────────────────┐
│           Applicazione Kafka                │
├─────────────────────────────────────────────┤
│   Kafka Protocol (produce/fetch/metadata)   │
├─────────────────────────────────────────────┤
│        SASL (autenticazione)                │
├─────────────────────────────────────────────┤
│        TLS (cifratura trasporto)            │
├─────────────────────────────────────────────┤
│              TCP/IP                         │
└─────────────────────────────────────────────┘
```

---

## Come Funziona

### Flusso SASL PLAIN

```
Client                          Broker
  |                               |
  |──[TLS Handshake]─────────────>|
  |<─[TLS OK]─────────────────────|
  |──[SASL Handshake: PLAIN]─────>|
  |──[username + password]────────>| ← trasmessi in chiaro nel payload SASL
  |                               | (per questo SERVE TLS!)
  |<─[SASL OK / SASL ERROR]───────|
  |──[Kafka requests...]──────────>|
```

### Flusso SASL SCRAM

SCRAM (Salted Challenge Response Authentication Mechanism) non trasmette mai la password in chiaro:

```
1. Client invia: username + client-nonce
2. Server risponde: server-nonce + salt + iteration-count
3. Client calcola: client-proof (HMAC della password salata)
4. Server verifica: client-proof e invia server-signature
5. Client verifica: server-signature (mutua autenticazione)
```

Le credenziali SCRAM sono memorizzate nei metadata di ZooKeeper/KRaft come hash, non in plaintext.

---

## Configurazione & Pratica

### SASL SCRAM-SHA-512 — Configurazione Completa

#### 1. Configurazione Broker (`server.properties`)

```properties
# ─── Listeners ────────────────────────────────────────────────────────────────
listeners=SASL_SSL://0.0.0.0:9094
advertised.listeners=SASL_SSL://kafka-broker-1.example.com:9094
listener.security.protocol.map=SASL_SSL:SASL_SSL
security.inter.broker.protocol=SASL_SSL

# ─── SASL ─────────────────────────────────────────────────────────────────────
sasl.enabled.mechanisms=SCRAM-SHA-512
sasl.mechanism.inter.broker.protocol=SCRAM-SHA-512

# ─── TLS (necessario per SASL_SSL) ───────────────────────────────────────────
ssl.keystore.location=/etc/kafka/ssl/kafka.server.keystore.jks
ssl.keystore.password=changeit
ssl.key.password=changeit
ssl.truststore.location=/etc/kafka/ssl/kafka.truststore.jks
ssl.truststore.password=changeit
ssl.client.auth=none

# ─── JAAS Configuration per Inter-Broker (broker si autentica tra loro) ───────
# Alternativa: referenziare file JAAS esterno con -Djava.security.auth.login.config
```

#### 2. File JAAS (`kafka_server_jaas.conf`)

```
KafkaServer {
    org.apache.kafka.common.security.scram.ScramLoginModule required
    username="kafka-broker"
    password="broker-password-super-sicura";
};

KafkaClient {
    org.apache.kafka.common.security.scram.ScramLoginModule required
    username="kafka-broker"
    password="broker-password-super-sicura";
};
```

```bash
# Avviare il broker con il file JAAS
export KAFKA_OPTS="-Djava.security.auth.login.config=/etc/kafka/kafka_server_jaas.conf"
kafka-server-start.sh /etc/kafka/server.properties
```

#### 3. Creare utenti SCRAM con `kafka-configs.sh`

```bash
# Creare l'utente inter-broker (deve esistere PRIMA di avviare i broker con SCRAM)
kafka-configs.sh \
  --bootstrap-server kafka-broker-1.example.com:9094 \
  --alter \
  --add-config 'SCRAM-SHA-512=[iterations=8192,password=broker-password-super-sicura]' \
  --entity-type users \
  --entity-name kafka-broker

# Creare un utente producer
kafka-configs.sh \
  --bootstrap-server kafka-broker-1.example.com:9094 \
  --alter \
  --add-config 'SCRAM-SHA-512=[iterations=8192,password=alice-producer-pwd]' \
  --entity-type users \
  --entity-name alice

# Creare un utente consumer
kafka-configs.sh \
  --bootstrap-server kafka-broker-1.example.com:9094 \
  --alter \
  --add-config 'SCRAM-SHA-512=[iterations=8192,password=bob-consumer-pwd]' \
  --entity-type users \
  --entity-name bob

# Listare tutti gli utenti SCRAM
kafka-configs.sh \
  --bootstrap-server kafka-broker-1.example.com:9094 \
  --describe \
  --entity-type users

# Eliminare un utente
kafka-configs.sh \
  --bootstrap-server kafka-broker-1.example.com:9094 \
  --alter \
  --delete-config 'SCRAM-SHA-512' \
  --entity-type users \
  --entity-name alice
```

#### 4. Configurazione Client (`client-scram.properties`)

```properties
security.protocol=SASL_SSL
sasl.mechanism=SCRAM-SHA-512

# Truststore per verificare il certificato del broker
ssl.truststore.location=/path/to/kafka.truststore.jks
ssl.truststore.password=changeit

# Credenziali SASL (inline — preferire JAAS file in produzione)
sasl.jaas.config=org.apache.kafka.common.security.scram.ScramLoginModule required \
  username="alice" \
  password="alice-producer-pwd";
```

---

### SASL PLAIN — Configurazione

```properties
# Broker server.properties
sasl.enabled.mechanisms=PLAIN
sasl.mechanism.inter.broker.protocol=PLAIN
```

```
# kafka_server_jaas.conf per PLAIN
KafkaServer {
    org.apache.kafka.common.security.plain.PlainLoginModule required
    username="admin"
    password="admin-secret"
    user_admin="admin-secret"
    user_alice="alice-password"
    user_bob="bob-password";
};
```

!!! warning "PLAIN: utenti definiti nel JAAS file"
    Con PLAIN gli utenti sono statici nel file JAAS del broker. Non c'è un comando per aggiungere utenti a runtime. Per aggiornare gli utenti è necessario modificare il file JAAS e riavviare i broker. Per ambienti dinamici, usare SCRAM.

---

### SASL GSSAPI/Kerberos — Configurazione

```properties
# Broker server.properties
sasl.enabled.mechanisms=GSSAPI
sasl.kerberos.service.name=kafka
```

```
# kafka_server_jaas.conf per Kerberos
KafkaServer {
    com.sun.security.auth.module.Krb5LoginModule required
    useKeyTab=true
    storeKey=true
    keyTab="/etc/kafka/kafka.service.keytab"
    principal="kafka/kafka-broker-1.example.com@EXAMPLE.COM";
};
```

```properties
# Client kerberos.properties
security.protocol=SASL_SSL
sasl.mechanism=GSSAPI
sasl.kerberos.service.name=kafka
sasl.jaas.config=com.sun.security.auth.module.Krb5LoginModule required \
  useKeyTab=true \
  storeKey=true \
  keyTab="/home/alice/alice.keytab" \
  principal="alice@EXAMPLE.COM";
```

---

### SASL OAUTHBEARER — Configurazione con token JWT

```properties
# Broker server.properties
sasl.enabled.mechanisms=OAUTHBEARER
sasl.oauthbearer.token.endpoint.url=https://auth.example.com/oauth2/token
sasl.login.callback.handler.class=org.apache.kafka.common.security.oauthbearer.secured.OAuthBearerLoginCallbackHandler
sasl.server.callback.handler.class=org.apache.kafka.common.security.oauthbearer.secured.OAuthBearerValidatorCallbackHandler
sasl.oauthbearer.jwks.endpoint.url=https://auth.example.com/.well-known/jwks.json
sasl.oauthbearer.expected.audience=kafka-cluster
```

```properties
# Client oauth.properties
security.protocol=SASL_SSL
sasl.mechanism=OAUTHBEARER
sasl.oauthbearer.token.endpoint.url=https://auth.example.com/oauth2/token
sasl.login.callback.handler.class=org.apache.kafka.common.security.oauthbearer.secured.OAuthBearerLoginCallbackHandler
sasl.jaas.config=org.apache.kafka.common.security.oauthbearer.OAuthBearerLoginModule required \
  clientId="kafka-client-id" \
  clientSecret="kafka-client-secret" \
  scope="kafka.read kafka.write";
```

---

## Best Practices

!!! tip "SCRAM-SHA-512 come default per nuovi cluster"
    SCRAM-SHA-512 offre il miglior equilibrio tra sicurezza e semplicità operativa per cluster che non richiedono integrazione Kerberos/AD. Preferire SHA-512 a SHA-256 per una security posture più robusta.

- **Usare sempre `SASL_SSL`**: mai `SASL_PLAINTEXT` in produzione.
- **Non usare l'account admin Kafka per applicazioni**: creare utenti dedicati per ogni servizio con il minimo privilegio.
- **Rotazione periodica delle password**: con SCRAM si può aggiornare la password di un utente a runtime senza downtime.
- **Separare il meccanismo inter-broker**: il meccanismo usato dai broker per comunicare tra loro può essere diverso da quello esposto ai client.
- **Secrets management**: non inserire password in JAAS file versionati. Usare variabili d'ambiente o Vault.
- **OAUTHBEARER per cloud-native**: se si usa già un IdP (Keycloak, Okta, Azure AD), OAUTHBEARER permette SSO e centralizzazione degli accessi.

---

## Troubleshooting

### Errore: `Authentication failed: Invalid username or password`

```bash
# Verificare che l'utente esista nello store SCRAM
kafka-configs.sh \
  --bootstrap-server kafka-broker-1.example.com:9094 \
  --describe \
  --entity-type users \
  --entity-name alice
```

Se non restituisce configurazioni, l'utente non è stato creato. Eseguire il comando `--alter --add-config`.

### Errore: `SaslException: Client sent an invalid token`

**Causa**: Mismatch tra il meccanismo configurato nel client (`sasl.mechanism`) e quello abilitato sul broker (`sasl.enabled.mechanisms`).

**Soluzione**: Verificare che entrambi usino lo stesso meccanismo (es. entrambi `SCRAM-SHA-512`).

### Errore: `Login failure: unable to obtain password from user`

**Causa**: Il file JAAS non è stato specificato o ha errori di sintassi.

```bash
# Abilitare debug SASL
export KAFKA_OPTS="-Djava.security.auth.login.config=/etc/kafka/kafka_server_jaas.conf \
  -Dsun.security.krb5.debug=true"
```

### Errore Kerberos: `Clock skew too great`

**Causa**: La differenza di orario tra il client e il KDC (Key Distribution Center) supera i 5 minuti (limite Kerberos default).

**Soluzione**: Sincronizzare NTP su tutti i nodi. Verificare con `date` e `chronyc tracking`.

---

## Riferimenti

- [Documentazione ufficiale Kafka SASL](https://kafka.apache.org/documentation/#security_sasl)
- [RFC 5802 — SCRAM](https://www.rfc-editor.org/rfc/rfc5802)
- [Confluent SASL Guide](https://docs.confluent.io/platform/current/kafka/authentication_sasl/index.html)
- [OAUTHBEARER KIP-768](https://cwiki.apache.org/confluence/display/KAFKA/KIP-768%3A+Extend+SASL%2FOAUTHBEARER+with+Support+for+OIDC)
- [MIT Kerberos Documentation](https://web.mit.edu/kerberos/krb5-latest/doc/)
