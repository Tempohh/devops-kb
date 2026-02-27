---
title: "ACID, BASE e Teorema CAP"
slug: acid-base-cap
category: databases
tags: [acid, base, cap, consistenza, disponibilità, transazioni, distribuiti]
search_keywords: [acid properties, atomicity consistency isolation durability, base properties, eventually consistent, cap theorem, brewer theorem, pacelc, consistency availability partition tolerance, strong consistency, weak consistency, distributed database, two phase commit, 2pc, consensus, raft, paxos, linearizability, serializability, causal consistency]
parent: databases/fondamentali/_index
related: [databases/fondamentali/transazioni-concorrenza, databases/nosql/cassandra, databases/nosql/mongodb]
official_docs: https://martin.kleppmann.com/2015/05/11/please-stop-calling-databases-cp-or-ap.html
status: complete
difficulty: intermediate
last_updated: 2026-02-24
---

# ACID, BASE e Teorema CAP

## Panoramica

ACID e BASE descrivono due insiemi di garanzie che un database può offrire. Non sono opposti su uno spettro: sono scelte architetturali con trade-off diversi. Il teorema CAP formalizza i limiti dei sistemi distribuiti. Capire questi concetti a livello operativo — non solo le definizioni — è il prerequisito per ogni scelta di database architecture che non sia un lancio di moneta.

## ACID

ACID non descrive solo le transazioni — descrive il contratto di affidabilità di un database.

### Atomicity — Tutto o Niente

Una transazione è un'unità indivisibile. Se qualunque istruzione fallisce, tutte le operazioni precedenti della transazione vengono annullate (rollback). Non esistono stati intermedi visibili agli altri.

```sql
BEGIN;
  UPDATE conti SET saldo = saldo - 500 WHERE id = 1;  -- Addebito
  UPDATE conti SET saldo = saldo + 500 WHERE id = 2;  -- Accredito
COMMIT;  -- Entrambe o nessuna
```

**Implementazione**: i database usano un **WAL (Write-Ahead Log)** — ogni modifica viene scritta sul log prima di essere applicata alle pagine dati. In caso di crash durante una transazione, il database usa il WAL per fare rollback al riavvio.

### Consistency — Invarianti Garantite

La transizione tra stati del database deve rispettare tutte le vincoli di integrità definiti (constraint, foreign key, check). Questo è diverso dalla "consistency" nel CAP theorem — qui si parla di invarianti dello schema, non di coerenza tra repliche.

!!! warning "La C più fraintesa"
    La Consistency in ACID è responsabilità parziale del database (enforcing constraints) e parziale dell'applicazione (business rules). Un database può essere ACID e permettere ugualmente inconsistenze applicative se i constraint non sono definiti correttamente.

### Isolation — Visibilità delle Transazioni Concorrenti

Le transazioni concorrenti devono produrre risultati equivalenti alla loro esecuzione seriale. In pratica, il livello di isolamento determina quali "anomalie" di concorrenza sono permesse — vedi [Transazioni e Concorrenza](transazioni-concorrenza.md) per il dettaglio completo.

### Durability — Persistenza Garantita

Una transazione committata sopravvive a qualsiasi failure: crash del processo, riavvio del server, power failure. Implementata tramite fsync — i dati devono essere fisicamente scritti su disco (o storage non-volatile) prima che il COMMIT sia confermato al client.

!!! note "Il costo nascosto di Durability"
    `fsync` è lento. I database con durabilità completa sono limitati dall'I/O del disco. Le configurazioni che "ottimizzano le performance" spesso disabilitano `fsync` (es. `synchronous_commit=off` in PostgreSQL) — riducendo la durabilità a una best-effort. Utile per bulk load, pericoloso in produzione senza capire il trade-off.

---

## BASE — Basically Available, Soft state, Eventually consistent

BASE è il modello di consistenza alternativo scelto dai sistemi distribuiti che privilegiano la disponibilità e la tolleranza ai partition.

| Aspetto | Descrizione |
|---------|-------------|
| **Basically Available** | Il sistema risponde sempre, anche durante guasti parziali — possibilmente con dati stale |
| **Soft state** | Lo stato del sistema può cambiare nel tempo anche senza input (propagazione delle repliche) |
| **Eventually consistent** | Dopo un periodo senza nuove scritture, tutte le repliche convergeranno allo stesso stato |

"Eventually consistent" non specifica *quando* — può essere millisecondi o ore. In sistemi come Cassandra, il "when" dipende da hint handoff, compaction, e repair scheduling.

---

## Teorema CAP

Il teorema di Brewer (2000, formalizzato da Gilbert & Lynch 2002) afferma che un sistema distribuito può garantire al massimo **due** delle tre proprietà:

| Proprietà | Descrizione |
|-----------|-------------|
| **Consistency (C)** | Ogni lettura riceve la scrittura più recente o un errore — equivale a linearizability |
| **Availability (A)** | Ogni richiesta riceve una risposta (non un errore), anche se non è la più recente |
| **Partition Tolerance (P)** | Il sistema continua a funzionare anche se i messaggi tra nodi vengono persi |

### Il Partition Tolerance non è opzionale

In un sistema distribuito su rete reale, i network partition *accadono* — link che cadono, switch che si riavviano, datacenter che si isolano. Non è possibile scegliere di "non supportare" P. La scelta reale è:

```
Durante un partition:
  CP → Smettere di rispondere per preservare la consistency (es. Zookeeper, HBase)
  AP → Continuare a rispondere con dati potenzialmente stale (es. Cassandra, CouchDB)
```

I sistemi CA (senza P) esistono solo in contesti single-node — non sono distribuiti nel senso pratico.

### La critica al CAP: è troppo binario

Il CAP tratta consistenza e disponibilità come binari, ma nella realtà esistono sfumature:

- Un sistema CP può avere disponibilità parziale (risponde su alcune partizioni, non su altre)
- Un sistema AP può offrire consistenza "quasi-forte" con letture quorum
- La latenza non è considerata

### PACELC — L'estensione pratica

PACELC (Abadi, 2012) estende CAP aggiungendo la dimensione latenza:

```
IF Partition: scegli tra Availability e Consistency
ELSE (normale operazione): scegli tra Latency e Consistency
```

**Posizionamento dei sistemi:**

| Sistema | Partition | Normale | Note |
|---------|-----------|---------|------|
| DynamoDB | PA | EL | Eventual consistency di default |
| Cassandra | PA | EL | Consistency level configurabile |
| MongoDB | PC | EC | Single-doc ACID, replica lag |
| PostgreSQL | PC | EC | Replica synchronous/async |
| Zookeeper | PC | EC | CP strict, alta latenza in lettura |
| CockroachDB | PC | EC | Distributed SQL, Raft consensus |
| Spanner | PC | EC | TrueTime, strong consistency globale |

!!! info "Come usare PACELC nelle decisioni"
    Quando scegli un database distribuito, chiediti: **durante un partition accettabile perdere disponibilità (CP) o consistency (AP)?** E nella normale operazione: **puoi tollerare un po' di latency in più per avere strong consistency (EC), o serve la risposta più veloce possibile accettando eventual consistency (EL)?**

---

## Livelli di Consistenza — Spectrum Reale

Tra strong consistency e eventual consistency esiste uno spettro:

```
Più forte ←────────────────────────────────────────────→ Più debole

Linearizability → Serializability → Snapshot → Causal → Eventual
(real-time order)  (transaction order) (MVCC)   (causal) (best-effort)
```

| Livello | Garanzia | Implementazione tipica |
|---------|----------|----------------------|
| **Linearizability** | Ogni operazione sembra istantanea, ordine real-time rispettato | Raft/Paxos, Zookeeper |
| **Serializability** | L'esecuzione è equivalente a una seriale — può non riflettere ordine fisico | 2PL, MVCC + SSI |
| **Snapshot Isolation** | Ogni transazione vede uno snapshot coerente al suo inizio | MVCC (PostgreSQL, Oracle) |
| **Causal Consistency** | Le operazioni causalmente correlate sono viste nell'ordine corretto | Vector clocks (DynamoDB streams) |
| **Eventual Consistency** | Converge, ma nessuna garanzia sull'ordine o il timing | Cassandra (ONE), DNS |

---

## Due Phase Commit (2PC) — Transazioni Distribuite

Per garantire atomicity su più nodi (o microservizi), il protocollo 2PC coordina il commit:

```
Coordinator                 Partecipante A     Partecipante B
     │                           │                   │
     │── PREPARE ────────────────>│                   │
     │── PREPARE ─────────────────────────────────────>│
     │                           │                   │
     │<── VOTE YES ──────────────│                   │
     │<── VOTE YES ───────────────────────────────────│
     │                           │                   │
     │── COMMIT ─────────────────>│                   │
     │── COMMIT ───────────────────────────────────────>│
```

**Il problema del 2PC**: se il coordinator cade dopo aver ricevuto tutti i YES ma prima di inviare COMMIT, i partecipanti restano bloccati in uno stato incerto. È un protocollo bloccante.

**Alternative moderne:**
- **Saga pattern**: serie di transazioni locali con compensazioni (vedi Kafka)
- **Optimistic concurrency control**: versioning senza lock, retry su conflitto
- **Raft/Paxos consensus**: per sistemi come CockroachDB e Spanner

## Relazioni

??? info "Transazioni e Concorrenza — Approfondimento isolamento"
    I livelli di isolamento ACID in dettaglio operativo.

    **Approfondimento →** [Transazioni e Concorrenza](transazioni-concorrenza.md)

??? info "Cassandra — Sistema AP/EL"
    Come Cassandra implementa eventual consistency con consistency levels configurabili.

    **Approfondimento →** [Cassandra](../nosql/cassandra.md)

## Riferimenti

- [Kleppmann — Please stop calling databases CP or AP](https://martin.kleppmann.com/2015/05/11/please-stop-calling-databases-cp-or-ap.html)
- [PACELC — Abadi 2012](https://dl.acm.org/doi/10.1145/2360374.2360378)
- [Designing Data-Intensive Applications — Kleppmann](https://dataintensive.net/)
