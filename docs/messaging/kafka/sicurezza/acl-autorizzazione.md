---
title: "ACL e Autorizzazione in Kafka"
slug: acl-autorizzazione
category: messaging
tags: [kafka, sicurezza, acl, autorizzazione, rbac, minimo-privilegio]
search_keywords: [acl, kafka acl, autorizzazione kafka, aclauthorizer, kafka-acls, topic permission, consumer group acl, producer acl, super users, wildcard acl, opa kafka, ranger kafka, rbac kafka]
parent: messaging/kafka/sicurezza
related: [messaging/kafka/sicurezza/tls-ssl, messaging/kafka/sicurezza/sasl]
official_docs: https://kafka.apache.org/documentation/#security_authz
status: complete
difficulty: advanced
last_updated: 2026-02-23
---

# ACL e Autorizzazione in Kafka

## Panoramica

Le ACL (Access Control List) di Kafka definiscono **chi** può eseguire **quale operazione** su **quale risorsa**. Mentre SASL gestisce l'autenticazione (chi sei), le ACL gestiscono l'autorizzazione (cosa puoi fare). Il meccanismo di default è `AclAuthorizer`, che memorizza le ACL nei metadata del cluster (ZooKeeper o KRaft) e le valuta a ogni richiesta. Le ACL seguono il modello `Principal → Operation → Resource → Effect (Allow/Deny)`. Un principal non listato in nessuna ACL non ha accesso a nulla per default — tranne i super users che bypassano completamente la verifica.

!!! note "Prerequisito"
    Le ACL funzionano solo se `authorizer.class.name` è configurato nel broker. Senza autorizzatore, tutti i principal autenticati hanno accesso completo al cluster.

---

## Concetti Chiave

### Risorse Kafka

| Risorsa | Descrizione | Esempio |
|---------|-------------|---------|
| `Topic` | Topic Kafka | `orders`, `user-events` |
| `Group` | Consumer Group | `payment-service-cg` |
| `Cluster` | Il cluster Kafka stesso | Operazioni admin |
| `TransactionalId` | ID per producer transazionale | `tx-payment-producer` |
| `DelegationToken` | Token di delega | Autenticazione Kerberos delegata |

### Operazioni

| Operazione | Risorse applicabili | Significato |
|-----------|---------------------|-------------|
| `Read` | Topic, Group | Consumare messaggi, committare offset |
| `Write` | Topic | Produrre messaggi |
| `Create` | Cluster, Topic | Creare topic |
| `Delete` | Topic, Group | Eliminare topic o group |
| `Alter` | Topic, Cluster | Modificare configurazione |
| `Describe` | Topic, Group, Cluster | Visualizzare metadata |
| `DescribeConfigs` | Topic, Cluster | Visualizzare configurazioni |
| `AlterConfigs` | Topic, Cluster | Modificare configurazioni |
| `ClusterAction` | Cluster | Operazioni inter-broker |
| `IdempotentWrite` | Cluster | Produzione idempotente |
| `All` | Tutte | Tutte le operazioni |

### Formato Principal

Il principal è l'identità dell'utente autenticato. Il formato dipende dal meccanismo di autenticazione:

```
User:alice              ← SASL PLAIN/SCRAM
User:alice@EXAMPLE.COM  ← Kerberos
User:CN=alice,OU=eng    ← mTLS (DN del certificato)
```

---

## Come Funziona

### Processo di valutazione ACL

```
Richiesta in arrivo (es. alice vuole produrre su topic "orders")
         │
         ▼
  Autenticazione SASL → principal = User:alice
         │
         ▼
  AclAuthorizer.authorize(session, operation, resource)
         │
         ├─ Principal in super.users? → ALLOW (bypassa tutto)
         │
         ├─ Esiste una ACL DENY esplicita? → DENY
         │
         ├─ Esiste una ACL ALLOW corrispondente? → ALLOW
         │
         └─ Nessuna ACL trovata? → DENY (default)
```

!!! warning "DENY esplicito ha precedenza su ALLOW"
    Se esiste sia una ACL `Allow` che una `Deny` per lo stesso principal/operazione, la `Deny` vince sempre. Usare `Deny` con parsimonia.

---

## Configurazione & Pratica

### Configurazione Broker (`server.properties`)

```properties
# Abilitare l'autorizzatore ACL
authorizer.class.name=kafka.security.authorizer.AclAuthorizer

# Super users: bypassano completamente le ACL
# Formato: User:nome;User:nome2
super.users=User:kafka-admin;User:kafka-broker

# Comportamento quando non ci sono ACL configurate per una risorsa
# Se true: tutto è permesso in assenza di ACL (PERICOLOSO in produzione)
# Se false (default): tutto è negato in assenza di ACL
allow.everyone.if.no.acl.found=false
```

### Comandi `kafka-acls.sh`

#### Sintassi generale

```bash
kafka-acls.sh \
  --bootstrap-server kafka-broker-1.example.com:9094 \
  --command-config /path/to/admin.properties \
  [--add | --remove | --list] \
  [--allow-principal | --deny-principal] User:NOME \
  [--operation OPERAZIONE] \
  [--topic NOME_TOPIC | --group NOME_GROUP | --cluster] \
  [--resource-pattern-type literal | prefixed]
```

#### ACL Producer — accesso a un topic specifico

```bash
# Alice può produrre sul topic "orders"
kafka-acls.sh \
  --bootstrap-server kafka-broker-1.example.com:9094 \
  --command-config admin.properties \
  --add \
  --allow-principal User:alice \
  --operation Write \
  --operation Describe \
  --topic orders

# Per la produzione idempotente (acks=all), aggiungere ClusterAction su Cluster
kafka-acls.sh \
  --bootstrap-server kafka-broker-1.example.com:9094 \
  --command-config admin.properties \
  --add \
  --allow-principal User:alice \
  --operation IdempotentWrite \
  --cluster
```

#### ACL Consumer — consumer group completo

```bash
# Bob può consumare dal topic "orders" usando il consumer group "order-processor"
# Richiede: Read sul Topic + Read sul Group

kafka-acls.sh \
  --bootstrap-server kafka-broker-1.example.com:9094 \
  --command-config admin.properties \
  --add \
  --allow-principal User:bob \
  --operation Read \
  --operation Describe \
  --topic orders

kafka-acls.sh \
  --bootstrap-server kafka-broker-1.example.com:9094 \
  --command-config admin.properties \
  --add \
  --allow-principal User:bob \
  --operation Read \
  --group order-processor
```

#### ACL con prefisso (Wildcard su prefisso)

```bash
# alice-service può produrre su tutti i topic che iniziano con "alice-"
kafka-acls.sh \
  --bootstrap-server kafka-broker-1.example.com:9094 \
  --command-config admin.properties \
  --add \
  --allow-principal User:alice-service \
  --operation Write \
  --operation Describe \
  --topic alice- \
  --resource-pattern-type prefixed
```

#### ACL Admin — permessi di gestione cluster

```bash
# L'utente "kafka-admin" può creare e cancellare topic
kafka-acls.sh \
  --bootstrap-server kafka-broker-1.example.com:9094 \
  --command-config admin.properties \
  --add \
  --allow-principal User:kafka-admin \
  --operation Create \
  --operation Delete \
  --operation Alter \
  --operation DescribeConfigs \
  --operation AlterConfigs \
  --cluster

# Permesso su tutti i topic (wildcard letterale con *)
kafka-acls.sh \
  --bootstrap-server kafka-broker-1.example.com:9094 \
  --command-config admin.properties \
  --add \
  --allow-principal User:kafka-admin \
  --operation All \
  --topic '*'
```

#### Listare ACL

```bash
# Tutte le ACL
kafka-acls.sh \
  --bootstrap-server kafka-broker-1.example.com:9094 \
  --command-config admin.properties \
  --list

# ACL per un topic specifico
kafka-acls.sh \
  --bootstrap-server kafka-broker-1.example.com:9094 \
  --command-config admin.properties \
  --list \
  --topic orders

# ACL per un principal
kafka-acls.sh \
  --bootstrap-server kafka-broker-1.example.com:9094 \
  --command-config admin.properties \
  --list \
  --allow-principal User:alice
```

#### Rimuovere ACL

```bash
kafka-acls.sh \
  --bootstrap-server kafka-broker-1.example.com:9094 \
  --command-config admin.properties \
  --remove \
  --allow-principal User:alice \
  --operation Write \
  --topic orders
```

---

### Esempio Completo: Architettura Multi-Team

```bash
#!/bin/bash
# Scenario: team-payments (producer), team-analytics (consumer), kafka-admin (admin)

BOOTSTRAP="kafka-broker-1.example.com:9094"
CONFIG="admin.properties"

# ─── Team Payments: produce su payments-* ────────────────────────────────────
kafka-acls.sh --bootstrap-server $BOOTSTRAP --command-config $CONFIG \
  --add --allow-principal User:payments-producer \
  --operation Write --operation Describe \
  --topic payments- --resource-pattern-type prefixed

kafka-acls.sh --bootstrap-server $BOOTSTRAP --command-config $CONFIG \
  --add --allow-principal User:payments-producer \
  --operation IdempotentWrite --cluster

# ─── Team Analytics: consuma da payments-* con group analytics-cg ────────────
kafka-acls.sh --bootstrap-server $BOOTSTRAP --command-config $CONFIG \
  --add --allow-principal User:analytics-consumer \
  --operation Read --operation Describe \
  --topic payments- --resource-pattern-type prefixed

kafka-acls.sh --bootstrap-server $BOOTSTRAP --command-config $CONFIG \
  --add --allow-principal User:analytics-consumer \
  --operation Read \
  --group analytics-cg

# ─── kafka-admin: gestione completa ──────────────────────────────────────────
kafka-acls.sh --bootstrap-server $BOOTSTRAP --command-config $CONFIG \
  --add --allow-principal User:kafka-admin \
  --operation All --cluster

kafka-acls.sh --bootstrap-server $BOOTSTRAP --command-config $CONFIG \
  --add --allow-principal User:kafka-admin \
  --operation All --topic '*'

kafka-acls.sh --bootstrap-server $BOOTSTRAP --command-config $CONFIG \
  --add --allow-principal User:kafka-admin \
  --operation All --group '*'

echo "ACL configurate con successo."
```

---

## Best Practices

!!! tip "Principio del minimo privilegio"
    Concedere solo le operazioni strettamente necessarie. Un producer non ha bisogno di `Read`; un consumer non ha bisogno di `Write`. Non usare `All` o wildcard `*` per utenti applicativi.

- **Un utente per servizio**: ogni microservizio deve avere la propria identità Kafka, non condividere credenziali.
- **Prefisso per namespace**: usare `--resource-pattern-type prefixed` per assegnare a un team tutti i topic con un prefisso comune (es. `team-payments-`).
- **Evitare Deny espliciti**: preferire la negazione per default (assenza di ACL Allow). Le ACL Deny complicano il debug.
- **Automatizzare le ACL come codice**: gestire le ACL tramite Terraform (provider Kafka), script versionati in git, o Strimzi KafkaTopic/KafkaUser in Kubernetes.
- **Audit log**: abilitare `log4j.logger.kafka.authorizer.logger=INFO` per loggare ogni decisione di autorizzazione.
- **Revisionare periodicamente**: rimuovere ACL di utenti/servizi dismessi.

### Alternative all'AclAuthorizer

| Soluzione | Descrizione | Quando usarla |
|-----------|-------------|--------------|
| **OPA (Open Policy Agent)** | Policy-as-code, regole Rego | Logiche di autorizzazione complesse |
| **Apache Ranger** | UI grafica, audit centralizzato | Ambienti enterprise con Hadoop |
| **Confluent RBAC** | Role-based, integrazione LDAP | Confluent Platform |

---

## Troubleshooting

### Errore: `Authorization failed` con messaggio generico

```bash
# Abilitare il log dell'authorizer sul broker
# In log4j.properties:
log4j.logger.kafka.authorizer.logger=DEBUG, authorizerAppender
log4j.additivity.kafka.authorizer.logger=false
```

Il log mostrerà righe come:
```
Principal = User:alice is Denied Operation = WRITE from host = 10.0.0.5 on resource = Topic:LITERAL:orders
```

### Errore: Il consumer non riesce a committare gli offset

**Causa**: Mancano i permessi `Read` sul Consumer Group.

```bash
# Verificare le ACL del group
kafka-acls.sh --bootstrap-server $BOOTSTRAP --command-config admin.properties \
  --list --group order-processor
```

### Errore: `Producer failed: Not authorized to access TransactionalId`

**Causa**: Un producer transazionale necessita di permessi su `TransactionalId`.

```bash
kafka-acls.sh --bootstrap-server $BOOTSTRAP --command-config admin.properties \
  --add --allow-principal User:payments-producer \
  --operation Write --operation Describe \
  --transactional-id payments-tx-id
```

### Errore: `Not authorized to create topics`

**Causa**: Manca l'ACL `Create` sul `Cluster`.

```bash
kafka-acls.sh --bootstrap-server $BOOTSTRAP --command-config admin.properties \
  --add --allow-principal User:kafka-admin \
  --operation Create --cluster
```

---

## Riferimenti

- [Documentazione ufficiale Kafka Authorization](https://kafka.apache.org/documentation/#security_authz)
- [Confluent ACL Guide](https://docs.confluent.io/platform/current/kafka/authorization.html)
- [OPA Kafka Plugin](https://github.com/StyraInc/opa-kafka-plugin)
- [Apache Ranger Kafka Plugin](https://ranger.apache.org/apache-ranger-2-0.html)
- [Strimzi KafkaUser CRD](https://strimzi.io/docs/operators/latest/configuring.html#type-KafkaUser-reference)
