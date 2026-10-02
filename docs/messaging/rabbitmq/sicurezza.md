---
title: "Sicurezza RabbitMQ — OAuth2, mTLS, Permessi, Hardening"
slug: sicurezza
category: messaging
tags: [rabbitmq, sicurezza, oauth2, mtls, sasl, autenticazione, autorizzazione, rbac, hardening]
search_keywords: [rabbitmq security, rabbitmq oauth2, rabbitmq_auth_backend_oauth2, rabbitmq jwt, rabbitmq keycloak, rabbitmq entra id, rabbitmq azure ad, ssl_cert_login_from, sasl external rabbitmq, rabbitmq mtls client cert, rabbitmq set_permissions, rabbitmq topic permissions, rabbitmq user tags, rabbitmq management rbac, rabbitmq guest user, rabbitmq hardening, rabbitmq access_refused, rabbitmq ldap tag, rabbitmq scope mapping]
parent: messaging/rabbitmq/_index
related: [messaging/rabbitmq/deployment, messaging/kafka/sicurezza/sasl, security/autenticazione/oauth2-oidc, security/autorizzazione/rbac-abac-rebac]
official_docs: https://www.rabbitmq.com/docs/access-control
status: complete
difficulty: advanced
last_updated: 2026-10-02
---

# Sicurezza RabbitMQ — OAuth2, mTLS, Permessi, Hardening

## Panoramica

RabbitMQ espone due superfici distinte da proteggere: il protocollo **AMQP** (porta 5672/5671, usato dai client applicativi) e la **Management UI/HTTP API** (porta 15672, usata da operatori e tool di monitoring). Entrambe condividono lo stesso backend di autenticazione/autorizzazione, ma con modelli di permesso leggermente diversi: l'uno basato su regex su risorse (queue, exchange), l'altro su **user tags** (ruoli grossolani per l'interfaccia web).

Questo articolo copre quattro aree che `deployment.md` tratta solo come sotto-sezioni operative (TLS di trasporto, un CRD `Permission` di esempio): il plugin **OAuth2** come backend di autenticazione centralizzato (Keycloak/Entra ID), l'autenticazione via **certificato client mTLS** (SASL EXTERNAL), il modello di permessi avanzato con le sue regex, e una checklist di hardening per produzione. Non tratta TLS di trasporto "puro" (già documentato in `deployment.md`) né il clustering Erlang (vedi `clustering-ha.md`).

A differenza di Kafka — dove SASL (`messaging/kafka/sicurezza/sasl.md`) e ACL (`acl-autorizzazione.md`) sono moduli separati e intercambiabili — RabbitMQ usa un sistema di **auth backend a catena** (`auth_backends`): più backend possono essere concatenati, con fallback in ordine (es. prova OAuth2, poi internal database). Questo è utile quando si vuole migrare gradualmente da utenti locali a un IdP esterno.

!!! warning "OAuth2 autentica, non autorizza da solo"
    Il plugin OAuth2 di RabbitMQ valida il JWT e ne estrae gli **scope**, ma è RabbitMQ stesso — non l'IdP — a tradurre quegli scope in permessi AMQP (configure/write/read) tramite convenzioni di naming. Un JWT valido con scope sbagliati produce comunque `ACCESS_REFUSED`.

---

## Concetti Chiave

### Auth backend a catena

```
auth_backends.1 = oauth2     # primo tentativo: valida JWT
auth_backends.2 = internal   # fallback: utenti nel database Mnesia/Khepri
```

RabbitMQ prova i backend nell'ordine indicato finché uno non autentica con successo. Questo permette una migrazione incrementale: service account legacy restano su `internal`, nuovi client usano `oauth2`.

### Due piani di autorizzazione separati

| Piano | Meccanismo | Granularità |
|---|---|---|
| **AMQP (dati)** | `set_permissions` — regex su configure/write/read, per vhost | Risorsa (queue/exchange specifica via regex) |
| **Management UI (operatività)** | **user tags**: `administrator`, `monitoring`, `policymaker`, `management` | Ruolo grossolano, non per-risorsa |

Un utente con tag `monitoring` vede metriche e connessioni ma non può creare code; `policymaker` può gestire policy (HA, TTL) ma non vedere tutte le connessioni; solo `administrator` ha accesso completo, incluso gestione utenti e permessi.

### SASL EXTERNAL vs SASL PLAIN

SASL PLAIN (username/password) richiede comunque TLS per non esporre le credenziali — è quanto già mostrato in `deployment.md`. **SASL EXTERNAL** è diverso: il client non invia alcuna credenziale applicativa. L'identità deriva dal **certificato client presentato durante il TLS handshake** (mTLS): RabbitMQ estrae CN o SAN dal certificato e lo mappa a uno username tramite `ssl_cert_login_from`.

!!! tip "Quando preferire SASL EXTERNAL"
    In ambienti con PKI interna già matura (service mesh, cert-manager che ruota certificati automaticamente), SASL EXTERNAL elimina la gestione di password/secret per i service account: l'identità è legata al certificato, che ha già un ciclo di vita di rotazione gestito.

### Scope-to-permission mapping OAuth2

Il plugin `rabbitmq_auth_backend_oauth2` si aspetta scope nel formato:

```
<resource_server_id>.<permission>:<vhost>/<resource-pattern>
```

Esempio: `rabbitmq.configure:production/orders.*` concede `configure` su tutte le risorse che iniziano con `orders.` nel vhost `production`. Lo scope `rabbitmq.tag:administrator` assegna invece un user tag per la Management UI.

---

## Architettura / Come Funziona

### Flusso OAuth2 con Keycloak/Entra ID

```
Client                    RabbitMQ Broker              IdP (Keycloak/Entra ID)
  |                             |                              |
  |──[1. richiede token]───────────────────────────────────────>|
  |<─[2. JWT access_token]───────────────────────────────────────|
  |──[3. AMQP connect, SASL OAUTHBEARER, token=JWT]──>|          |
  |                             |──[4. valida firma JWT]───────>| (JWKS endpoint)
  |                             |<─[5. JWKS pubkey]─────────────|
  |                             |  6. verifica: exp, aud, iss
  |                             |  7. estrae scope → permessi
  |<─[8. CONNECTION OK / ACCESS_REFUSED]──────────────|          |
```

Il broker **non chiama l'IdP ad ogni richiesta**: valida il JWT localmente usando la chiave pubblica (JWKS, cacheable) e verifica `exp` (scadenza), `aud` (audience = resource_server_id configurato), `iss` (issuer). Questo rende la validazione a basso overhead anche sotto carico.

### Flusso SASL EXTERNAL (mTLS client-cert)

```
Client (cert: CN=orders-service)      RabbitMQ Broker
  |──[TLS handshake, client presenta cert]────────>|
  |<─[TLS OK, broker verifica cert contro CA]───────|
  |──[AMQP connect, SASL EXTERNAL, nessuna pwd]────>|
  |                                                 | estrae CN="orders-service"
  |                                                 | applica ssl_cert_login_from=common_name
  |                                                 | username effettivo = "orders-service"
  |<─[CONNECTION OK se utente "orders-service" esiste]|
```

Differenza chiave rispetto al TLS "solo trasporto" già mostrato in `deployment.md`: lì `ssl_options.fail_if_no_peer_cert = true` impone mTLS ma l'**identità applicativa** arriva ancora via SASL PLAIN (username/password separati). Con SASL EXTERNAL il certificato **è** la credenziale di autenticazione, non solo il canale cifrato.

---

## Configurazione & Pratica

### 1. OAuth2 con Keycloak — Cluster Operator CRD completo

```yaml
apiVersion: rabbitmq.com/v1beta1
kind: RabbitmqCluster
metadata:
  name: rabbitmq-prod
spec:
  replicas: 3
  rabbitmq:
    additionalPlugins:
      - rabbitmq_auth_backend_oauth2
    additionalConfig: |
      auth_backends.1 = oauth2
      auth_backends.2 = internal

      # ─── OAuth2 provider (Keycloak) ────────────────────────────
      auth_oauth2.resource_server_id = rabbitmq
      auth_oauth2.issuer = https://keycloak.example.com/realms/platform
      auth_oauth2.jwks_url = https://keycloak.example.com/realms/platform/protocol/openid-connect/certs

      # Verifica audience: il JWT deve contenere questo valore in "aud"
      auth_oauth2.verify_aud = true

      # Validazione scope: lo scope deve matchare resource_server_id
      auth_oauth2.scope_prefix = rabbitmq.

      # Mappa il claim "scope" (default) — alternativa: "roles" per Entra ID
      # auth_oauth2.scope_claim = scope

      # Management UI: abilita login OAuth2 interattivo (redirect a Keycloak)
      management.oauth_enabled = true
      management.oauth_client_id = rabbitmq-management
      management.oauth_provider_url = https://keycloak.example.com/realms/platform
  secretBackend:
    vault: {}
```

```yaml
# Esempio equivalente per Entra ID (Azure AD) — differenze principali:
# - issuer e jwks_url puntano al tenant Azure
# - gli scope arrivano spesso nel claim "roles" invece di "scope"
apiVersion: rabbitmq.com/v1beta1
kind: RabbitmqCluster
metadata:
  name: rabbitmq-prod-azure
spec:
  rabbitmq:
    additionalPlugins:
      - rabbitmq_auth_backend_oauth2
    additionalConfig: |
      auth_backends.1 = oauth2
      auth_oauth2.resource_server_id = rabbitmq
      auth_oauth2.issuer = https://login.microsoftonline.com/<tenant-id>/v2.0
      auth_oauth2.jwks_url = https://login.microsoftonline.com/<tenant-id>/discovery/v2.0/keys
      auth_oauth2.scope_claim = roles
      auth_oauth2.additional_scopes_key = extra_scopes
```

Un client che richiede il token a Keycloak e si connette:

```bash
# 1. Ottenere il token (client_credentials grant per service account)
TOKEN=$(curl -s -X POST https://keycloak.example.com/realms/platform/protocol/openid-connect/token \
  -d "client_id=orders-service" \
  -d "client_secret=${CLIENT_SECRET}" \
  -d "grant_type=client_credentials" \
  -d "scope=rabbitmq.configure:production/orders.* rabbitmq.write:production/orders.* rabbitmq.read:production/orders.*" \
  | jq -r .access_token)

# 2. Connettersi usando il JWT come "password" SASL OAUTHBEARER (client AMQP generico, es. pika/amqp)
# In pratica la libreria client passa il token come credenziale SASL; esempio concettuale:
python3 -c "
import pika
credentials = pika.PlainCredentials('', '$TOKEN')  # username vuoto, token come password
params = pika.ConnectionParameters(host='rabbitmq-prod', port=5671, credentials=credentials, ssl_options=pika.SSLOptions(context))
"
```

### 2. SASL EXTERNAL (mTLS client-cert) — `rabbitmq.conf`

```ini
# ─── TLS listener con mTLS obbligatorio ──────────────────────────────
listeners.ssl.default = 5671
ssl_options.cacertfile = /etc/rabbitmq/tls/ca.crt
ssl_options.certfile   = /etc/rabbitmq/tls/server.crt
ssl_options.keyfile    = /etc/rabbitmq/tls/server.key
ssl_options.verify     = verify_peer
ssl_options.fail_if_no_peer_cert = true

# ─── Auth backend: solo autenticazione via certificato ───────────────
auth_backends.1 = internal

# Abilita SASL EXTERNAL e mappa l'identità dal certificato client
auth_mechanisms.1 = EXTERNAL

# Estrae lo username dal Common Name del certificato client
# Alternative: distinguished_name (intero DN), subject_alt_name
ssl_cert_login_from = common_name

# Con subject_alt_name serve specificare quale SAN estrarre, es. DNS o URI:
# ssl_cert_login_from = subject_alt_name
# ssl_cert_login_alt_name_type = dns
```

```bash
# Creare l'utente che corrisponde al CN del certificato client (nessuna password reale usata in auth,
# ma RabbitMQ richiede comunque un hash — usare una stringa casuale mai utilizzata)
rabbitmqctl add_user orders-service "$(openssl rand -base64 32)"
rabbitmqctl set_permissions -p production orders-service "^orders\." "^orders\." "^orders\."

# Il certificato client deve avere CN=orders-service
openssl req -new -key orders-service.key -out orders-service.csr \
  -subj "/CN=orders-service/O=Platform"
```

### 3. Permission model avanzato — regex e topic permissions

`set_permissions` accetta tre regex POSIX: **configure** (creare/eliminare risorse), **write** (pubblicare), **read** (consumare/bindare):

```bash
# Sintassi: rabbitmqctl set_permissions -p <vhost> <user> <configure> <write> <read>

# Permesso corretto: accesso solo a code/exchange che iniziano con "orders."
rabbitmqctl set_permissions -p production orders-service \
  "^orders\..*" "^orders\..*" "^orders\..*"

# ERRORE COMUNE: dimenticare l'escape del punto — "orders." matcha QUALSIASI carattere dopo "orders"
# Questo permetterebbe accesso anche a "ordersXsensitive" (bug di sicurezza silenzioso)
rabbitmqctl set_permissions -p production orders-service \
  "orders." "orders." "orders."   # ← SBAGLIATO, non fare così

# ERRORE COMUNE: regex vuota "" NON significa "nessun permesso", significa "nessuna risorsa matcha mai"
# per negare completamente un permesso è corretto, ma va usato consapevolmente
rabbitmqctl set_permissions -p production readonly-user "" "" "^reports\..*"
```

**Topic permissions** aggiungono un ulteriore livello, specifico per exchange di tipo `topic`: filtrano le routing key che un utente può usare in write/read, indipendentemente dai permessi su exchange/queue:

```bash
# Sintassi: rabbitmqctl set_topic_permissions -p <vhost> <user> <exchange> <write-regex> <read-regex>

# L'utente può pubblicare solo su routing key che iniziano con "eu." sull'exchange "events"
rabbitmqctl set_topic_permissions -p production orders-service events \
  "^eu\..*" "^eu\..*"

# Verificare i permessi applicati
rabbitmqctl list_permissions -p production
rabbitmqctl list_topic_permissions -p production
rabbitmqctl list_user_permissions orders-service
```

**Permessi su vhost vs risorsa**: i permessi `set_permissions` sono sempre scoped a un vhost — non esiste un permesso "globale" che attraversi vhost diversi. Un utente multi-tenant deve avere permessi configurati esplicitamente per ciascun vhost a cui accede:

```bash
rabbitmqctl set_permissions -p tenant-a svc-user "^tenant-a\..*" "^tenant-a\..*" "^tenant-a\..*"
rabbitmqctl set_permissions -p tenant-b svc-user "^tenant-b\..*" "^tenant-b\..*" "^tenant-b\..*"
```

### 4. User tags e Management UI RBAC

```bash
# Tag disponibili: administrator, monitoring, policymaker, management, (none)
rabbitmqctl add_user ops-readonly "$(openssl rand -base64 24)"
rabbitmqctl set_user_tags ops-readonly monitoring

rabbitmqctl add_user ops-policy "$(openssl rand -base64 24)"
rabbitmqctl set_user_tags ops-policy policymaker

rabbitmqctl add_user ops-admin "$(openssl rand -base64 24)"
rabbitmqctl set_user_tags ops-admin administrator
```

| Tag | Può vedere | Può modificare |
|---|---|---|
| `monitoring` | Tutte le connessioni, canali, metriche, nodi | Nulla (read-only) |
| `policymaker` | Le proprie risorse + policy | Policy, parametri, proprie code/exchange |
| `management` | Solo le proprie risorse | Le proprie code/exchange/binding |
| `administrator` | Tutto | Tutto, incluso utenti/permessi/vhost |

Federazione LDAP per i tag — mappare gruppi LDAP a tag RabbitMQ senza gestire utenti locali:

```ini
# rabbitmq.conf
auth_backends.1 = ldap
auth_backends.2 = internal

auth_ldap.servers.1 = ldap.example.com
auth_ldap.user_dn_pattern = cn=${username},ou=users,dc=example,dc=com

# Mappa il gruppo LDAP "rabbitmq-admins" al tag "administrator"
auth_ldap.tag_queries.administrator.base = ou=groups,dc=example,dc=com
auth_ldap.tag_queries.administrator.filter = (&(objectClass=group)(cn=rabbitmq-admins)(member=${user_dn}))

auth_ldap.tag_queries.monitoring.base = ou=groups,dc=example,dc=com
auth_ldap.tag_queries.monitoring.filter = (&(objectClass=group)(cn=rabbitmq-monitoring)(member=${user_dn}))
```

---

## Best Practices

!!! warning "Disabilitare l'utente guest in produzione"
    L'utente `guest`/`guest` esiste di default e, da RabbitMQ 3.3+, può connettersi **solo da localhost** per policy di default — ma se il broker è esposto con `loopback_users = none` (comune in container/K8s dove "localhost" è il pod stesso), `guest` diventa accessibile da chiunque in rete. Eliminarlo sempre:
    ```bash
    rabbitmqctl delete_user guest
    ```

- **Minimo privilegio sulle regex**: ogni service account deve avere permessi `configure`/`write`/`read` limitati a un prefisso di naming dedicato (es. `^orders\.`), mai `.*`.
- **Un service account per servizio**: evitare credenziali condivise tra microservizi — rompe l'audit trail e impedisce la rotazione selettiva.
- **Rotazione credenziali**: per utenti `internal` con password, ruotare periodicamente con `rabbitmqctl change_password`; per OAuth2, la rotazione è gestita dall'IdP (token a vita breve, refresh automatico); per SASL EXTERNAL, dal ciclo di vita del certificato (cert-manager).
- **Disabilitare plugin non necessari**: `rabbitmq_management` espone un'API HTTP ricca — se non serve accesso web, considerare di esporlo solo su rete interna o disabilitarlo (`rabbitmq-plugins disable rabbitmq_management`) sui nodi broker puri, mantenendolo su nodi dedicati.
- **Audit del management plugin esposto**: se la Management UI è raggiungibile da internet (anche dietro reverse proxy), applicare rate limiting e MFA a livello di IdP (OAuth2), mai fare login diretto `internal` da rete pubblica.
- **TLS obbligatorio per OAuth2 e SASL EXTERNAL**: entrambi i meccanismi perdono ogni garanzia di sicurezza su connessioni non cifrate — forzare sempre `SASL_SSL`-equivalente (listener TLS, `fail_if_no_peer_cert` per mTLS).

!!! tip "Verificare i permessi prima del deploy, non dopo l'incidente"
    `rabbitmqctl list_permissions` e `list_topic_permissions` dovrebbero far parte della pipeline di CI per ambienti production — un test automatico che verifica che nessun service account abbia regex `.*` non intenzionali previene silenziosamente la maggior parte degli incidenti di questa sezione.

---

## Troubleshooting

### Errore: `ACCESS_REFUSED - access to queue 'orders.created' in vhost 'production' refused for user 'orders-service'`

**Causa**: La regex di `write`/`read` configurata con `set_permissions` non matcha il nome esatto della risorsa — tipicamente un punto non escapato (`orders.` matcha anche `ordersX`, ma se la regex è `^orders\.created$` e la queue si chiama `orders.created.v2`, non matcha per l'ancora `$`).

**Soluzione**:
```bash
rabbitmqctl list_permissions -p production
# Verificare visivamente la regex, poi correggere:
rabbitmqctl set_permissions -p production orders-service \
  "^orders\..*" "^orders\..*" "^orders\..*"
```

### Errore: JWT valido ma connessione rifiutata — scope non riconosciuto

**Sintomo**: Keycloak restituisce un token valido (verificabile su jwt.io), ma RabbitMQ rifiuta la connessione o nega i permessi attesi.

**Causa**: lo scope nel JWT non rispetta il formato `<resource_server_id>.<permission>:<vhost>/<pattern>`, oppure `auth_oauth2.resource_server_id` nel broker non coincide con il prefisso usato nello scope (es. broker configurato con `resource_server_id = rabbitmq` ma JWT contiene scope `messaging.write:...`).

**Soluzione**:
```bash
# Decodificare il JWT per ispezionare il claim scope
echo "$TOKEN" | cut -d. -f2 | base64 -d | jq .

# Verificare che il prefisso corrisponda esattamente a resource_server_id configurato nel broker
grep resource_server_id /etc/rabbitmq/rabbitmq.conf
```
Se il client-side ottiene scope dal client Keycloak sbagliato (client scope mapper mancante), correggere il mapper del client OAuth2 nell'IdP, non la configurazione RabbitMQ.

### Errore: `{sasl_external_authentication_failed, ...}` con SASL EXTERNAL

**Causa**: `ssl_cert_login_from` punta a `common_name` ma il certificato client ha il nome identificativo nel SAN (Subject Alternative Name) invece del CN — comune con certificati emessi da cert-manager, che spesso popola solo SAN per policy X.509 moderne.

**Soluzione**:
```ini
# Passare a subject_alt_name se i certificati moderni non popolano il CN
ssl_cert_login_from = subject_alt_name
ssl_cert_login_alt_name_type = dns
```
Verificare il contenuto del certificato:
```bash
openssl x509 -in client.crt -noout -text | grep -A1 "Subject Alternative Name"
```

### Sintomo: utenti LDAP autenticano ma non ricevono il tag atteso (nessun accesso Management UI)

**Causa**: `auth_ldap.tag_queries.<tag>.filter` usa un attributo LDAP (`member`) che non corrisponde allo schema del directory server (alcuni usano `memberUid` o `uniqueMember`).

**Soluzione**:
```bash
# Testare la query LDAP manualmente con ldapsearch prima di fidarsi della config RabbitMQ
ldapsearch -x -H ldap://ldap.example.com -b "ou=groups,dc=example,dc=com" \
  "(&(objectClass=group)(cn=rabbitmq-admins)(member=cn=alice,ou=users,dc=example,dc=com))"
```
Adattare `tag_queries` all'attributo che effettivamente restituisce risultati.

---

## Relazioni

??? info "TLS di trasporto e CRD Permission base — Approfondimento"
    `deployment.md` mostra già la configurazione TLS di trasporto (certificati, cifrari) e un esempio base di CRD `Permission` per il Cluster Operator. Questo articolo si concentra sui meccanismi di autenticazione (OAuth2, mTLS come identità) e sul modello di permessi avanzato che `deployment.md` non approfondisce.

    **Deployment e TLS di base →** [Deployment](deployment.md)

??? info "SASL in Kafka — Confronto"
    Kafka usa SASL come framework di autenticazione indipendente da TLS, con meccanismi intercambiabili (PLAIN, SCRAM, GSSAPI, OAUTHBEARER). RabbitMQ adotta un approccio simile con OAUTHBEARER/OAuth2 ma aggiunge SASL EXTERNAL per l'identità basata su certificato, assente nel modello Kafka standard.

    **Approfondimento Kafka →** [SASL — Autenticazione Kafka](../kafka/sicurezza/sasl.md)

??? info "OAuth2/OIDC generico e RBAC — Approfondimento"
    I concetti di scope, issuer, JWKS validation sono generici OAuth2/OIDC, non specifici RabbitMQ. Il modello RBAC con user tags è un caso applicato dei pattern RBAC generali.

    **OAuth2/OIDC →** [OAuth2 e OIDC](../../security/autenticazione/oauth2-oidc.md)
    **RBAC/ABAC/ReBAC →** [RBAC, ABAC, ReBAC](../../security/autorizzazione/rbac-abac-rebac.md)

## Riferimenti

- [Access Control — RabbitMQ Docs](https://www.rabbitmq.com/docs/access-control)
- [OAuth 2 Plugin — rabbitmq_auth_backend_oauth2](https://www.rabbitmq.com/docs/oauth2)
- [TLS Support — RabbitMQ Docs](https://www.rabbitmq.com/docs/ssl)
- [LDAP Plugin — RabbitMQ Docs](https://www.rabbitmq.com/docs/ldap)
- [Management Plugin RBAC — RabbitMQ Docs](https://www.rabbitmq.com/docs/management#permissions)
