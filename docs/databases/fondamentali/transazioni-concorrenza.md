---
title: "Transazioni e Concorrenza"
slug: transazioni-concorrenza
category: databases
tags: [transazioni, concorrenza, mvcc, isolamento, lock, deadlock, postgresql]
search_keywords: [transaction isolation level, read uncommitted, read committed, repeatable read, serializable, dirty read, non repeatable read, phantom read, write skew, lost update, mvcc multi version concurrency control, optimistic locking, pessimistic locking, row level lock, advisory lock, deadlock detection, 2pl two phase locking, serializable snapshot isolation, ssi]
parent: databases/fondamentali/_index
related: [databases/fondamentali/acid-base-cap, databases/postgresql/mvcc-vacuum, databases/sql-avanzato/query-optimizer]
official_docs: https://www.postgresql.org/docs/current/transaction-iso.html
status: complete
difficulty: advanced
last_updated: 2026-03-29
---

# Transazioni e Concorrenza

## Panoramica

La concorrenza è il problema più sottile nei database. I bug da race condition sono rari in sviluppo (traffico basso, dati pochi), esplodono in produzione, e sono difficili da riprodurre. La radice è sempre la stessa: il livello di isolamento scelto non corrisponde alle garanzie che l'applicazione assume.

## Anomalie di Concorrenza

Prima di scegliere un livello di isolamento, è necessario capire quali anomalie esistono.

### Dirty Read

Una transazione legge dati scritti da un'altra transazione non ancora committata.

```sql
-- Transazione A
BEGIN;
UPDATE conti SET saldo = saldo + 1000 WHERE id = 1;
-- NON ha ancora fatto COMMIT

-- Transazione B (a livello READ UNCOMMITTED)
SELECT saldo FROM conti WHERE id = 1;
-- Legge il +1000 non committato
-- Se A fa ROLLBACK, B ha letto dati che non esistono
```

### Non-Repeatable Read

Stessa query nella stessa transazione restituisce risultati diversi perché un'altra transazione ha committato una modifica nel frattempo.

```sql
-- Transazione A
BEGIN;
SELECT saldo FROM conti WHERE id = 1;  -- Legge 1000

-- Nel frattempo, Transazione B commatta:
UPDATE conti SET saldo = 500 WHERE id = 1;

-- Transazione A
SELECT saldo FROM conti WHERE id = 1;  -- Legge 500 — diverso!
```

### Phantom Read

Una query che usa un range di righe restituisce righe diverse a causa di INSERT/DELETE committate da un'altra transazione.

```sql
-- Transazione A
SELECT COUNT(*) FROM ordini WHERE status = 'pending';  -- 5

-- Transazione B commatta:
INSERT INTO ordini(status) VALUES('pending');

-- Transazione A
SELECT COUNT(*) FROM ordini WHERE status = 'pending';  -- 6 — "fantasma"!
```

### Write Skew — L'Anomalia Più Insidiosa

Due transazioni leggono gli stessi dati, prendono decisioni basate su quei dati, e scrivono in modo incompatibile. **Non è rilevato da livelli di isolamento fino a Serializable.**

```sql
-- Regola: almeno un medico deve essere "on call" in ogni momento
-- Transazione A (Medico Alice): "Sono l'unico on call?"
SELECT COUNT(*) FROM medici WHERE on_call = true;  -- 2

-- Transazione B (Medico Bob): stessa verifica, stesso risultato: 2

-- Transazione A: ci sono 2, posso togliermi
UPDATE medici SET on_call = false WHERE nome = 'Alice';

-- Transazione B: ci sono 2, posso togliermi
UPDATE medici SET on_call = false WHERE nome = 'Bob';

-- RISULTATO: 0 medici on call — VIOLAZIONE DELLA REGOLA
-- Entrambe le transazioni erano "logicamente corrette" isolatamente
```

### Lost Update — Un Caso Speciale di Write Skew

```sql
-- Classico: counter increment senza locking
-- Transazione A: legge 10, incrementa, scrive 11
-- Transazione B (concorrente): legge 10, incrementa, scrive 11
-- Risultato: l'incremento di A è perso

-- Soluzione atomica (sempre preferibile)
UPDATE contatori SET valore = valore + 1 WHERE id = 1;
-- Un singolo UPDATE è atomico per definizione
```

---

## Livelli di Isolamento

Standard SQL definisce 4 livelli. PostgreSQL implementa i tre utili con MVCC:

| Livello | Dirty Read | Non-Repeatable | Phantom | Write Skew |
|---------|-----------|----------------|---------|------------|
| READ UNCOMMITTED | Possibile | Possibile | Possibile | Possibile |
| **READ COMMITTED** | ✓ Protetto | Possibile | Possibile | Possibile |
| **REPEATABLE READ** | ✓ | ✓ | ✓ (in PG) | Possibile |
| **SERIALIZABLE** | ✓ | ✓ | ✓ | ✓ |

!!! note "PostgreSQL e READ UNCOMMITTED"
    PostgreSQL non implementa READ UNCOMMITTED — viene trattato come READ COMMITTED. Non esiste un modo in Postgres di leggere dirty data.

### READ COMMITTED (Default PostgreSQL)

Ogni `SELECT` all'interno di una transazione vede uno snapshot aggiornato al momento dell'esecuzione della query (non al BEGIN della transazione). È il default ed è adeguato per la maggior parte delle applicazioni web.

```sql
BEGIN;  -- snapshot non fissato qui
SELECT saldo FROM conti WHERE id = 1;  -- snapshot al momento di QUESTA query
-- ... altra attività ...
SELECT saldo FROM conti WHERE id = 1;  -- snapshot NUOVO — può vedere dati cambiati
COMMIT;
```

### REPEATABLE READ

Lo snapshot è fissato al momento del `BEGIN`. Tutte le query della transazione vedono lo stesso stato del database. PostgreSQL evita anche i phantom read (lo standard SQL non lo richiede a questo livello).

```sql
BEGIN ISOLATION LEVEL REPEATABLE READ;
SELECT saldo FROM conti WHERE id = 1;  -- Snapshot fissato qui
-- Qualsiasi commit di altre transazioni è invisibile
SELECT saldo FROM conti WHERE id = 1;  -- Stesso risultato garantito
COMMIT;
```

**Quando usarlo**: report di consistenza (snapshot coerente sull'intera query), letture multiple che devono essere consistenti tra loro.

### SERIALIZABLE

Il livello più forte. PostgreSQL usa **SSI (Serializable Snapshot Isolation)** — non usa lock tradizionali ma rileva i pattern di accesso che porterebbero a risultati non serializzabili, e abortisce una delle transazioni coinvolte.

```sql
BEGIN ISOLATION LEVEL SERIALIZABLE;

-- Medico Alice: verifica on-call (legge dati)
SELECT COUNT(*) FROM medici WHERE on_call = true;  -- 2

-- Se Medico Bob fa lo stesso e entrambi tentano UPDATE,
-- SSI rileva il write skew e abortisce una delle due transazioni
-- con errore: "ERROR: could not serialize access due to read/write dependencies"

UPDATE medici SET on_call = false WHERE nome = 'Alice';
COMMIT;  -- O serializza con successo, o abortisce con retry necessario
```

**Importante**: SERIALIZABLE richiede retry dell'applicazione. Le transazioni abortite per serialization failure devono essere riprovate.

```python
import psycopg2

def aggiorna_con_serializable(conn):
    max_retries = 5
    for attempt in range(max_retries):
        try:
            with conn.transaction():
                conn.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
                # ... logica transazione ...
                return
        except psycopg2.errors.SerializationFailure:
            if attempt == max_retries - 1:
                raise
            time.sleep(0.1 * (2 ** attempt))  # exponential backoff
```

---

## MVCC — Multi-Version Concurrency Control

PostgreSQL non usa lock per le letture. Usa MVCC: ogni riga ha versioni multiple con timestamp di validità. I lettori vedono le versioni appropriate al loro snapshot senza bloccare i writer (e viceversa).

```
Riga fisica in storage:
  xmin=100, xmax=0, data={saldo: 1000}   ← versione corrente
  xmin=50,  xmax=100, data={saldo: 800}  ← versione precedente (visibile a tx < 100)
  xmin=10,  xmax=50,  data={saldo: 600}  ← vecchia versione
```

**xmin**: transaction ID che ha creato la versione
**xmax**: transaction ID che ha cancellato/aggiornato la versione (0 = ancora valida)

Ogni transazione ha un transaction snapshot che definisce quali xmin/xmax sono visibili. MVCC è il motivo per cui PostgreSQL non ha deadlock tra reader e writer — ma è anche il motivo per cui esiste il problema del bloat (le versioni obsolete non vengono rimosse automaticamente — serve VACUUM).

---

## Locking — Quando MVCC Non Basta

Per alcune operazioni, il lock esplicito è necessario.

### Row-Level Lock

```sql
-- SELECT FOR UPDATE: lock esclusivo sulla riga, blocca altri FOR UPDATE
BEGIN;
SELECT * FROM inventario WHERE prodotto_id = 1 FOR UPDATE;
-- La riga è "locked" — altri FOR UPDATE aspettano
UPDATE inventario SET quantita = quantita - 1 WHERE prodotto_id = 1;
COMMIT;

-- SELECT FOR NO KEY UPDATE: meno restrittivo (non blocca FK checks)
SELECT * FROM ordini WHERE id = 1 FOR NO KEY UPDATE;

-- SELECT FOR SHARE: lock condiviso, permette altri SHARE ma blocca UPDATE
SELECT * FROM conti WHERE id = 1 FOR SHARE;

-- SKIP LOCKED: salta righe già lockate (job queue pattern)
SELECT * FROM job_queue WHERE status = 'pending'
FOR UPDATE SKIP LOCKED
LIMIT 1;
```

### Advisory Lock — Lock Applicativo

Lock non legati a righe specifiche, usati per coordinare operazioni applicative:

```sql
-- Lock su un ID arbitrario (es. per distribuire task)
SELECT pg_try_advisory_lock(12345);  -- true = lock acquisito, false = già lockato

-- Lock con blocco (aspetta)
SELECT pg_advisory_lock(12345);

-- Rilascio
SELECT pg_advisory_unlock(12345);

-- Lock di sessione (persiste oltre la transazione)
-- vs lock transazionale (rilasciato al COMMIT/ROLLBACK)
SELECT pg_advisory_xact_lock(12345);  -- transazionale (auto-release)
```

**Uso pratico**: mutex su operazioni come "esegui questo cron job una sola volta":

```python
with conn.cursor() as cur:
    cur.execute("SELECT pg_try_advisory_lock(123456)")
    if cur.fetchone()[0]:
        # Siamo l'unica istanza che ha acquisito il lock
        run_cron_job()
        # Lock rilasciato alla fine della sessione
```

---

## Deadlock

Un deadlock si verifica quando A aspetta un lock tenuto da B, e B aspetta un lock tenuto da A.

```sql
-- Transazione A
BEGIN;
UPDATE conti SET saldo = saldo - 100 WHERE id = 1;  -- Locka riga 1
-- aspetta il lock su riga 2...

-- Transazione B (concorrente)
BEGIN;
UPDATE conti SET saldo = saldo + 100 WHERE id = 2;  -- Locka riga 2
UPDATE conti SET saldo = saldo - 50 WHERE id = 1;   -- Aspetta il lock su riga 1!

-- DEADLOCK: A aspetta B, B aspetta A
-- PostgreSQL rileva il ciclo e abortisce una delle due con:
-- ERROR:  deadlock detected
```

**Prevenzione**: accedere sempre agli oggetti nello stesso ordine (A prima poi B, mai B prima poi A). In pratica:

```sql
-- Pattern sicuro: ordina sempre per ID crescente
WITH locks AS (
  SELECT id FROM conti WHERE id IN (1, 2) ORDER BY id FOR UPDATE
)
-- Acquisisce i lock nell'ordine 1, 2 — sempre uguale indipendentemente da chi chiama
UPDATE conti SET saldo = saldo - 100 WHERE id = 1;
UPDATE conti SET saldo = saldo + 100 WHERE id = 2;
```

```sql
-- Monitoraggio deadlock in PostgreSQL
SET deadlock_timeout = '1s';  -- Quanto aspettare prima di controllare per deadlock
-- Default: 1 secondo — aumentare su sistemi sotto alto carico per ridurre falsi positivi

-- Lock correnti
SELECT pid, locktype, relation::regclass, mode, granted
FROM pg_locks
WHERE NOT granted
ORDER BY pid;
```

---

## Ottimistic vs Pessimistic Concurrency

| Approccio | Meccanismo | Quando usare |
|-----------|-----------|--------------|
| **Pessimistic** | `SELECT FOR UPDATE` — blocca subito | Conflitti frequenti, operazioni brevi |
| **Optimistic** | Versioning — rileva conflitti al commit | Conflitti rari, operazioni lunghe |

```sql
-- Optimistic locking con version column
CREATE TABLE prodotti (
    id SERIAL PRIMARY KEY,
    nome TEXT,
    versione INTEGER DEFAULT 0
);

-- Lettura: salva la versione corrente
SELECT id, nome, versione FROM prodotti WHERE id = 1;
-- → versione = 5

-- Update: include la versione nel WHERE (fallisce se qualcun altro ha già aggiornato)
UPDATE prodotti
SET nome = 'Nuovo Nome', versione = versione + 1
WHERE id = 1 AND versione = 5;
-- → 0 rows affected = conflitto, l'applicazione deve gestirlo
-- → 1 row affected = successo
```

## Troubleshooting

### Scenario 1 — Serialization failure in produzione

**Sintomo**: L'applicazione riceve intermittentemente `ERROR: could not serialize access due to read/write dependencies among transactions` con `SQLSTATE 40001`.

**Causa**: Transazioni con isolamento SERIALIZABLE in conflitto — SSI ha rilevato un pattern non serializzabile e ha abortito una delle transazioni.

**Soluzione**: Implementare retry con exponential backoff nel codice applicativo. È il comportamento atteso con SERIALIZABLE, non un bug.

```python
import psycopg2, time

def run_with_retry(conn, fn, max_retries=5):
    for attempt in range(max_retries):
        try:
            with conn.transaction():
                conn.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
                return fn(conn)
        except psycopg2.errors.SerializationFailure:
            if attempt == max_retries - 1:
                raise
            time.sleep(0.05 * (2 ** attempt))  # 50ms, 100ms, 200ms...
```

```sql
-- Verificare frequenza serialization failures
SELECT datname, xact_rollback, deadlocks
FROM pg_stat_database
WHERE datname = current_database();
```

---

### Scenario 2 — Query bloccata indefinitamente (lock wait)

**Sintomo**: Una query `UPDATE` o `SELECT FOR UPDATE` non termina — l'applicazione si blocca senza risposta.

**Causa**: Un'altra transazione detiene un row-level lock sulla stessa riga e non ha ancora fatto COMMIT o ROLLBACK (es. transazione idle in transaction, connessione staccata).

**Soluzione**: Identificare la transazione bloccante e terminarla se idle; usare `lock_timeout` per evitare blocchi indefiniti.

```sql
-- Trovare le query bloccate e chi le blocca
SELECT
    blocked.pid AS blocked_pid,
    blocked.query AS blocked_query,
    blocking.pid AS blocking_pid,
    blocking.query AS blocking_query,
    blocking.state AS blocking_state,
    now() - blocking.query_start AS blocking_duration
FROM pg_stat_activity blocked
JOIN pg_stat_activity blocking
    ON blocking.pid = ANY(pg_blocking_pids(blocked.pid))
WHERE cardinality(pg_blocking_pids(blocked.pid)) > 0;

-- Terminare la transazione bloccante (se idle/stuck)
SELECT pg_terminate_backend(<blocking_pid>);

-- Prevenire blocchi indefiniti a livello sessione
SET lock_timeout = '5s';
-- Oppure a livello query
SET LOCAL lock_timeout = '2s';
```

---

### Scenario 3 — Deadlock ricorrenti su stessa coppia di tabelle

**Sintomo**: Log PostgreSQL riporta `ERROR: deadlock detected` ripetutamente, sempre tra le stesse transazioni o tabelle.

**Causa**: Due code path dell'applicazione acquisiscono lock su righe/tabelle in ordine opposto (es. A locka ordini→pagamenti, B locka pagamenti→ordini).

**Soluzione**: Canonicalizzare l'ordine di acquisizione dei lock — sempre nello stesso ordine (es. per ID crescente). Abilitare log_lock_waits per diagnosi.

```sql
-- Abilitare log dei deadlock e dei lock wait (postgresql.conf o per sessione)
SET deadlock_timeout = '250ms';  -- Ridurre per rilevare prima in sviluppo
SET log_lock_waits = on;         -- Logga le attese di lock

-- Pattern sicuro: ordina SEMPRE per chiave primaria crescente
BEGIN;
SELECT id FROM conti WHERE id = ANY(ARRAY[5, 3, 8]) ORDER BY id FOR UPDATE;
-- Acquisisce lock su 3, 5, 8 — ordine deterministico per tutti i caller
UPDATE conti SET saldo = saldo - 100 WHERE id = 3;
UPDATE conti SET saldo = saldo + 100 WHERE id = 5;
COMMIT;
```

---

### Scenario 4 — Lost update silenzioso (dati corrotti)

**Sintomo**: Un contatore o un campo aggregato risulta inferiore al valore atteso dopo aggiornamenti concorrenti. Nessun errore nei log.

**Causa**: Pattern read-modify-write non atomico con READ COMMITTED: due transazioni leggono lo stesso valore, entrambe calcolano il nuovo valore partendo dallo stesso base, e l'ultima scrittura sovrascrive la prima.

**Soluzione**: Usare UPDATE atomico con espressione SQL invece di read-modify-write applicativo; oppure `SELECT FOR UPDATE` se il calcolo è complesso.

```sql
-- SBAGLIATO: read in applicazione + write separata (lost update possibile)
-- val = SELECT valore FROM contatori WHERE id = 1;  -- legge 10
-- UPDATE contatori SET valore = val + 1 WHERE id = 1;  -- scrive 11
-- Se due sessioni leggono 10 contemporaneamente, entrambe scrivono 11

-- CORRETTO: UPDATE atomico
UPDATE contatori SET valore = valore + 1 WHERE id = 1;
-- Un singolo UPDATE è atomico — nessun lost update possibile

-- CORRETTO: SELECT FOR UPDATE se il calcolo dipende da logica applicativa
BEGIN;
SELECT valore FROM contatori WHERE id = 1 FOR UPDATE;
-- Nessun'altra transazione può modificare questa riga fino al COMMIT
UPDATE contatori SET valore = <nuovo_valore_calcolato> WHERE id = 1;
COMMIT;
```

---

## Relazioni

??? info "MVCC e Vacuum — Dettagli interni PostgreSQL"
    Come MVCC crea versioni e perché VACUUM è necessario.

    **Approfondimento →** [MVCC e Vacuum](../postgresql/mvcc-vacuum.md)

??? info "ACID, BASE e CAP — Isolamento nel contesto distribuito"
    Come l'isolamento si applica in sistemi distribuiti.

    **Approfondimento →** [ACID, BASE e CAP](acid-base-cap.md)

## Riferimenti

- [PostgreSQL — Transaction Isolation](https://www.postgresql.org/docs/current/transaction-iso.html)
- [A Critique of ANSI SQL Isolation Levels — Berenson et al.](https://arxiv.org/abs/cs/0701157)
- [Designing Data-Intensive Applications — Cap. 7](https://dataintensive.net/)
