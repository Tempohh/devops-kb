---
title: "Clustering e High Availability"
slug: clustering-ha
category: messaging
tags: [rabbitmq, clustering, ha, network-partitions, erlang, quorum-queues, mnesia, raft]
search_keywords: [rabbitmq cluster setup, rabbitmq high availability, network partition rabbitmq, split-brain rabbitmq, pause-minority rabbitmq, erlang distribution, mnesia rabbitmq, quorum queues ha, disk node ram node rabbitmq, rabbitmq cluster operator]
parent: messaging/rabbitmq/_index
related: [messaging/rabbitmq/affidabilita, messaging/rabbitmq/deployment, messaging/rabbitmq/features-avanzate]
official_docs: https://www.rabbitmq.com/docs/clustering
status: complete
difficulty: advanced
last_updated: 2026-02-25
---

# Clustering e High Availability

## Architettura del Cluster RabbitMQ

Un cluster RabbitMQ è un gruppo di nodi Erlang che condividono lo stato tramite **Erlang Distribution** (il protocollo nativo di comunicazione del runtime Erlang) e il database distribuito **Mnesia**.

```
Cluster RabbitMQ — 3 Nodi

  rabbit@node-1          rabbit@node-2          rabbit@node-3
  ──────────────         ──────────────         ──────────────
  ┌────────────┐         ┌────────────┐         ┌────────────┐
  │ Mnesia     │◄───────►│ Mnesia     │◄───────►│ Mnesia     │
  │ (metadata) │         │ (metadata) │         │ (metadata) │
  ├────────────┤         ├────────────┤         ├────────────┤
  │ Exchange:  │         │ Exchange:  │         │ Exchange:  │
  │ orders ✓   │         │ orders ✓   │         │ orders ✓   │
  │ events ✓   │         │ events ✓   │         │ events ✓   │
  ├────────────┤         ├────────────┤         ├────────────┤
  │ Queue:     │         │ Queue:     │         │ Queue:     │
  │ orders     │         │  (ref)     │         │  (ref)     │
  │ [master]   │         │            │         │            │
  └────────────┘         └────────────┘         └────────────┘

  Stato condiviso via Mnesia (replicato):
  - Exchange definitions
  - Queue metadata (nome, proprietà, chi è il leader)
  - Binding
  - User/vhost/permission
  - Policy

  Queue data (messaggi effettivi):
  - Classic Queues: solo sul nodo leader (non replicati, salvo mirroring deprecato)
  - Quorum Queues: replicati con Raft su N nodi configurati
  - Streams: replicati con Raft
```

**Cosa è replicato e cosa no:**

```
REPLICATO su tutti i nodi (Mnesia):
  ✓ Exchange definitions
  ✓ Queue metadata
  ✓ Binding
  ✓ Users, VHosts, Permissions
  ✓ Policies
  ✓ Runtime parameters (Federation, Shovel)

NON REPLICATO per default (Classic Queues):
  ✗ Messaggi nelle Classic Queues
  ✗ I messaggi esistono SOLO sul nodo che contiene la queue

REPLICATO per Quorum Queues / Streams:
  ✓ Tutti i messaggi (Raft log replicato su quorum di nodi)
```

---

## Erlang Distribution — La Fondazione del Cluster

Erlang Distribution è il protocollo che permette ai processi Erlang di comunicarsi tra nodi. RabbitMQ lo usa nativamente — ogni nodo è un nodo Erlang con un nome univoco.

```
Erlang Distribution — Dettagli Tecnici

  Nome nodo: rabbit@hostname
             └──┬──┘ └──┬──┘
              app     hostname
              name   (FQDN o short)

  Comunicazione: TCP porta 25672 (empd: Erlang Port Mapper Daemon)
  Autenticazione: Erlang Cookie (file ~/.erlang.cookie, identico su tutti i nodi)

  rabbit@node-1 ◄──TCP 25672──► rabbit@node-2
  rabbit@node-2 ◄──TCP 25672──► rabbit@node-3
  rabbit@node-1 ◄──TCP 25672──► rabbit@node-3

  Full mesh: ogni nodo comunica con ogni altro nodo.
  N=3: 3 connessioni
  N=5: 10 connessioni
  N=7: 21 connessioni
  → Il clustering RabbitMQ è progettato per cluster piccoli (3-7 nodi LAN)
```

```bash
# Setup manuale cluster (3 nodi)
# Prerequisiti: stesso Erlang cookie su tutti i nodi

# Su tutti i nodi:
echo "my-secret-cookie" > ~/.erlang.cookie
chmod 400 ~/.erlang.cookie

# Avvia RabbitMQ su tutti i nodi con nomi appropriati
# Variabile RABBITMQ_NODENAME

# Su node-2 e node-3: join al cluster (node-1 è il seed)
rabbitmqctl stop_app
rabbitmqctl reset
rabbitmqctl join_cluster rabbit@node-1
rabbitmqctl start_app

# Verifica cluster
rabbitmqctl cluster_status
# Output:
# Cluster name: rabbit@node-1
# Disk Nodes: rabbit@node-1, rabbit@node-2, rabbit@node-3
# Running Nodes: rabbit@node-1, rabbit@node-2, rabbit@node-3
# Partitions: []  ← nessuna partizione di rete attiva
```

!!! warning "Erlang Cookie"
    Il cookie Erlang è un segreto condiviso che autentica i nodi nel cluster. Deve essere identico su tutti i nodi e protetto (chmod 400). Se è diverso, i nodi non si connettono. Non confondere con le credenziali utente AMQP — è a un layer più basso.

---

## Disk Nodes vs RAM Nodes

RabbitMQ distingue tra nodi che persistono i metadati su disco e nodi che li mantengono solo in RAM.

```
Disk Node vs RAM Node

  Disk Node:
  - Metadati Mnesia salvati su disco
  - Può essere riavviato senza perdere la configurazione del cluster
  - Necessario: almeno 1 (o tutti) i nodi devono essere disk node

  RAM Node:
  - Metadati Mnesia solo in memoria
  - Riavvio = perde lo stato del cluster (richiede rejoin)
  - Vantaggio: operazioni su exchange/queue/binding leggermente più veloci
  - Svantaggio: se tutti i RAM nodes riavviano insieme → cluster broken

  RACCOMANDAZIONE: usare TUTTI disk node in produzione.
  I RAM node sono un'ottimizzazione legacy raramente necessaria oggi.
```

```bash
# Verificare tipo nodo
rabbitmqctl cluster_status
# "Disc Nodes" vs "RAM Nodes" nella lista

# Convertire un nodo in RAM node (prima di join o con change_cluster_node_type)
rabbitmqctl change_cluster_node_type ram
# Convertire in disk node
rabbitmqctl change_cluster_node_type disc
```

---

## Network Partitions — Il Problema Centrale

Le **partizioni di rete** sono lo scenario più pericoloso per un cluster RabbitMQ. Una partizione si verifica quando i nodi non riescono più a comunicare tra loro ma rimangono operativi.

```
Network Partition — Split-Brain

  Prima della partizione:
  node-1 ◄──────────────► node-2 ◄──────────────► node-3
  (leader q1, q2)                              (replica q1, q2)

  Partizione di rete: [node-1] ✗ [node-2, node-3]

  node-1: "Sono da solo. Gli altri sono morti. Sono ancora il cluster."
          → Continua ad accettare publish su q1, q2
          → Crea nuovi exchange, binding

  node-2/3: "node-1 è morto. Eleggono nuovo leader."
            → node-2 diventa leader di q1, q2
            → Accettano publish su q1, q2

  Risultato: DUE broker indipendenti scrivono sui MEDESIMI nomi di queue.
             Messaggi divergenti. Stato inconsistente.
             Quando la partizione si risolve → RabbitMQ NON sa come mergeare.
```

**Strategie di partition handling:**

```bash
# Configurato in rabbitmq.conf
cluster_partition_handling = ...
```

| Strategia | Comportamento | Quando usare |
|-----------|---------------|--------------|
| `ignore` | Nodi continuano a operare indipendentemente durante la partizione. Admin deve risolvere manualmente. | **Evitare** — split-brain garantito |
| `pause_minority` | I nodi nella partizione **minore** si sospendono (rifiutano connections). La partizione **maggiore** continua normalmente. | **Raccomandato** per cluster dispari (3, 5 nodi) — no split-brain, disponibilità ridotta in minoranza |
| `pause_if_all_down` | Si sospende solo se tutti i nodi listati sono irraggiungibili. | Cluster con topologia specifica (es. 2 nodi + tiebreaker) |
| `autoheal` | Dopo la partizione, i nodi della partizione "perdente" si riavviano e fanno rejoin (perdendo i messaggi locali non replicati). | Quando la disponibilità è più importante dei messaggi in-flight non replicati |

```ini
# rabbitmq.conf — configurazione raccomandata per cluster 3 nodi
cluster_partition_handling = pause_minority

# Con pause_minority:
# - Cluster 3 nodi: 1 nodo si isola → si sospende, 2 nodi continuano
# - Cluster 5 nodi: 2 nodi si isolano → si sospendono, 3 nodi continuano
# - Cluster 2 nodi: PROBLEMATICO — entrambe le partizioni hanno size=1
#                   → entrambi si sospendono → cluster down completo
#                   Per 2 nodi: usare pause_if_all_down o autoheal
```

!!! warning "Cluster a 2 nodi"
    Un cluster RabbitMQ a 2 nodi con `pause_minority` causa downtime completo durante qualsiasi partizione di rete (anche momentanea), perché entrambi i nodi sono "minoranza" rispetto all'altro. **Usare sempre cluster a 3+ nodi (dispari) per produzione.**

---

## Quorum Queues e Network Partitions

Le Quorum Queues gestiscono le partizioni in modo molto più robusto grazie a Raft:

```
Quorum Queue con Network Partition

  Cluster 3 nodi, quorum=2:

  Partizione: [node-1] | [node-2, node-3]

  node-1 (isolato):
  - Ha un follower locale della quorum queue
  - Non può formare quorum (ha solo 1/3 voti)
  - → Si mette offline per le operazioni di write sulla queue
  - → Continua a servire le read (stale reads) o blocca del tutto

  node-2 e node-3:
  - Formano quorum (2/3 voti)
  - Eleggono un nuovo leader su node-2 o node-3
  - Continuano a operare normalmente

  Recupero:
  - node-1 si riconnette → sincronizza il Raft log dal nuovo leader
  - Nessuna perdita di dati committed
  - Nessun intervento manuale richiesto
```

---

## Policy Management

Le **Policy** sono il meccanismo principale per configurare il comportamento delle queue e degli exchange senza doverli ricreare.

```
Policy — Pattern-Based Configuration

  Una policy è una regola che si applica a tutti gli exchange/queue
  il cui nome matcha un'espressione regolare.

  Priority delle policy: la policy con priorità più alta "vince".
  Le policy del cluster sovrascrivono quelle dell'operator.
```

```bash
# Esempi di policy comuni

# 1. Quorum Queue per tutte le queue in produzione
rabbitmqctl set_policy ha-quorum \
    ".*" \
    '{"queue-mode":"quorum"}' \
    --apply-to queues \
    --priority 1

# 2. DLX per tutte le queue che iniziano con "orders"
rabbitmqctl set_policy orders-dlx \
    "^orders" \
    '{"dead-letter-exchange":"dlx",
      "dead-letter-routing-key":"dead"}' \
    --apply-to queues \
    --priority 5

# 3. TTL per queue di notifiche temporanee
rabbitmqctl set_policy notifications-ttl \
    "^notifications\." \
    '{"message-ttl":3600000,
      "max-length":100000}' \
    --apply-to queues \
    --priority 3

# Lista policy attive
rabbitmqctl list_policies

# Operator policies (non sovrascrivibili dai consumer) — solo admin
rabbitmqctl set_operator_policy max-queues \
    ".*" \
    '{"max-length":1000000}' \
    --apply-to queues
```

**Policy via Management HTTP API:**

```bash
# Equivalente via API REST
curl -u guest:guest -X PUT \
    http://rabbitmq:15672/api/policies/%2F/ha-quorum \
    -H "Content-Type: application/json" \
    -d '{
        "pattern": ".*",
        "definition": {"x-queue-type": "quorum"},
        "apply-to": "queues",
        "priority": 1
    }'
```

---

## Mnesia — Limitazioni e Implicazioni

Mnesia è il database distribuito interno di Erlang che RabbitMQ usa per la metadata. Capirne i limiti è essenziale per il troubleshooting.

```
Mnesia — Caratteristiche e Limiti

  ✓ Database in-memory con journaling su disco
  ✓ ACID per transazioni locali
  ✓ Replicazione automatica nel cluster
  ✓ Performante per set di dati piccoli

  ✗ Non progettato per dataset grandi
    → Migliaia di queue/exchange hanno impatto sulle performance
  ✗ Può corrrompersi in seguito a crash brutali durante la scrittura
    → Soluzione: backup + reset del nodo + rejoin
  ✗ Partizionamento complesso da risolvere manualmente
  ✗ Non scalabile orizzontalmente (tutti i nodi hanno tutti i metadati)

  LIMITE PRATICO: non avere più di ~10.000 queue contemporanee per cluster.
  Se hai bisogno di molte più queue: architecture review, stream processing, o
  virtualizzare tramite routing key invece di code separate.
```

**Recupero da Mnesia corrotto:**

```bash
# Se un nodo non parte per Mnesia corrotto:

# 1. Verifica i log
tail -f /var/log/rabbitmq/rabbit@nodename.log

# 2. Se è corruzione Mnesia, resetta il nodo
rabbitmqctl stop_app
rabbitmqctl reset        # CANCELLA tutti i dati locali del nodo
rabbitmqctl start_app
rabbitmqctl join_cluster rabbit@other-node  # rejoins il cluster

# ATTENZIONE: reset cancella i messaggi nelle Classic Queues locali.
# Le Quorum Queues si risincronizzano dal cluster dopo il reset.
```

---

## Load Balancing e Client Connections

I client devono connettersi a qualsiasi nodo del cluster. Esistono diverse strategie:

```
Connection Topology

  Approccio 1 — HAProxy (raccomandato on-premise):
  ──────────────────────────────────────────────────
  Clients
    │
    ▼
  HAProxy (TCP load balancer)
    │  healthcheck: nc -z node 5672
    ├──► rabbit@node-1:5672
    ├──► rabbit@node-2:5672
    └──► rabbit@node-3:5672

  haproxy.cfg:
  listen rabbitmq
      bind *:5672
      mode tcp
      balance roundrobin
      option tcp-check
      server rabbit1 node-1:5672 check inter 5s
      server rabbit2 node-2:5672 check inter 5s
      server rabbit3 node-3:5672 check inter 5s

  Approccio 2 — Kubernetes Service (cluster K8s):
  → Vedi deployment.md per RabbitMQ Cluster Operator

  Approccio 3 — Client-side (con retry):
  connection = pika.BlockingConnection(
      pika.ConnectionParameters(
          host='rabbitmq',   # DNS che risolve a un IP del cluster
          connection_attempts=3,
          retry_delay=2,
          socket_timeout=10
      )
  )
  # Limitazione: sticky connection, no automatic failover
  # Se il nodo cade, il client deve riconnettersi manualmente
```

**Topology recovery (libreria-side):**

```python
# aio-pika con topology recovery automatica
import aio_pika

connection = await aio_pika.connect_robust(
    "amqp://user:pass@rabbitmq/",
    reconnect_interval=5,           # secondi tra i tentativi di reconnect
    fail_fast=True,                 # errore immediato se il primo connect fallisce
    timeout=10
)
# connect_robust ridichiarerà automaticamente exchange, queue e binding
# dopo una reconnessione — questo è essenziale per HA
```

---

## Manutenzione del Cluster

```bash
# Rolling upgrade (zero-downtime per quorum queues)
# 1. Prendi un nodo fuori dal load balancer
# 2. Drain le connessioni
rabbitmqctl drain        # rabbitmq 3.12+: smette di accettare nuove connections

# 3. Fai il maintenance del nodo
# 4. Riavvia il nodo
systemctl restart rabbitmq-server

# 5. Verifica che si sia riconnesso al cluster
rabbitmqctl cluster_status

# 6. Torna ad accettare connessioni
rabbitmqctl revive       # rimuove il drain

# Monitoraggio cluster health
rabbitmqctl node_health_check    # verifica i componenti del nodo
rabbitmq-diagnostics check_port_connectivity   # verifica connettività porte
rabbitmq-diagnostics check_if_node_is_mirror_sync_critical  # check quorum
```

---

## Riferimenti

- [RabbitMQ Clustering Guide](https://www.rabbitmq.com/docs/clustering)
- [Network Partitions](https://www.rabbitmq.com/docs/partitions)
- [Quorum Queues](https://www.rabbitmq.com/docs/quorum-queues)
- [Policies](https://www.rabbitmq.com/docs/parameters#policies)
- [Mnesia/Schema Recovery](https://www.rabbitmq.com/docs/clustering#restarting)
- [Erlang Distribution](https://www.erlang.org/doc/reference_manual/distributed)
