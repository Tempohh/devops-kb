---
title: "Schema Migrations — Flyway, Liquibase, Atlas, golang-migrate"
slug: schema-migrations
category: databases
tags: [database, migrations, schema, flyway, liquibase, atlas, golang-migrate, ci-cd, versioning]
search_keywords: [schema migration, database migration, versioned migration, declarative migration, state-based migration, flyway, liquibase, atlas, ariga atlas, golang-migrate, sqlx migrate, rollback migration, migration idempotente, drift detection, schema drift, migration locking, migration lock, up down migration, changelog, changeset, ddl migration, database versioning, expand and contract, zero downtime migration]
parent: databases/fondamentali/_index
related: [databases/fondamentali/transazioni-concorrenza, dev/integrazioni/database-patterns, ci-cd/gitops/argocd]
official_docs: https://atlasgo.io/docs
status: needs-review
difficulty: intermediate
last_updated: 2026-10-04
last_verified: 2026-10-04
---

# Schema Migrations — Flyway, Liquibase, Atlas, golang-migrate

## Panoramica

Uno schema migration tool applica in modo controllato e ripetibile i cambi di struttura a un database (nuove tabelle, colonne, indici, vincoli), tenendo traccia di cosa è già stato applicato. Serve ovunque lo schema evolva insieme al codice: senza di esso, l'allineamento tra ambienti (dev/staging/prod) degrada in fretta e il rollout diventa un'operazione manuale rischiosa. Esistono due filosofie opposte — **versioned/imperative** (una sequenza di script SQL numerati, applicati in ordine) e **declarative/state-based** (si descrive lo stato finale desiderato, il tool calcola il diff) — e la scelta tra le due ha conseguenze dirette su rollback, drift detection e revisione in code review. Non serve per migrazioni di dati massive tra database diversi (ETL) né per replica continua — quello è terreno di strumenti diversi (es. Debezium, AWS DMS).

## Concetti Chiave

!!! note "Versioned vs Declarative"
    **Versioned (imperative)**: ogni cambio è uno script SQL esplicito (`V1__create_users.sql`, `V2__add_email.sql`). Il tool applica solo gli script non ancora eseguiti, in ordine, tracciandoli in una tabella di controllo. Flyway e golang-migrate lavorano così.

    **Declarative (state-based)**: si mantiene un file che descrive lo schema finale desiderato (HCL, SQL "target", o un modello ORM). Il tool confronta lo stato desiderato con lo stato reale del database e genera automaticamente il diff da applicare. Atlas lavora così nativamente; Liquibase lo supporta in una modalità aggiuntiva (`diff`) ma il suo modello primario resta versioned via changelog.

- **Migration idempotente**: può essere eseguita più volte senza produrre errori o doppi effetti (es. `CREATE TABLE IF NOT EXISTS`). Fondamentale quando le migration girano da init container Kubernetes che può ripartire dopo un crash parziale — vedi [Database Patterns — Init Container](../../dev/integrazioni/database-patterns.md).
- **Locking**: meccanismo che impedisce a due processi di applicare la stessa migration in parallelo (es. due pod che partono contemporaneamente). Senza locking, una migration `ADD COLUMN` può essere tentata due volte in race e fallire con errori inconsistenti tra i pod.
- **Drift detection**: rilevare che lo schema reale del database si è discostato da quello atteso (es. una modifica manuale fatta a mano da un DBA in produzione, non passata dal tool). Atlas lo fa nativamente (introspection + diff semantico); Liquibase lo copre manualmente via `diff`; con Flyway Community/golang-migrate serve tooling esterno o disciplina operativa.
- **Rollback (migration "down")**: la capacità di annullare una migration applicata. È il punto di maggiore trade-off tra i tool, approfondito sotto.

## Architettura / Come Funziona

Tutti i tool versioned condividono lo stesso schema concettuale:

1. Una tabella di controllo nel database stesso (es. `flyway_schema_history`, `schema_migrations`, `atlas_schema_revisions`) registra quali migration sono state applicate, con checksum e timestamp.
2. All'avvio, il tool confronta i file di migration presenti con le righe della tabella di controllo.
3. Applica solo le migration mancanti, in ordine di versione, ciascuna dentro una transazione (dove il DB lo supporta — DDL transazionale è nativo in PostgreSQL, non in MySQL).
4. Se una migration fallisce a metà, su PostgreSQL la transazione viene rollbackata e lo schema resta pulito — MySQL invece può lasciare uno stato parziale perché molte DDL fanno commit implicito. In quel caso Flyway registra la riga come `failed` (da sistemare con `flyway repair` dopo aver ripulito a mano lo schema) e golang-migrate marca il database **dirty**, rifiutando ulteriori `up` finché non si corregge lo schema e si usa `migrate force <versione>`.

Atlas inverte il flusso: non parte dai file storici ma calcola sempre il diff tra **stato desiderato** (schema HCL/SQL dichiarato) e **stato reale** (introspezione live del database), poi genera il piano di migrazione al volo. Questo elimina la deriva tra "quello che pensiamo sia lo schema" e "quello che è davvero" — ma richiede più fiducia nel motore di diffing per DDL complesse (rename ambigui, split di colonne).

```
Versioned (Flyway / golang-migrate)
  file V1, V2, V3... ──► tabella controllo ──► applica i mancanti in ordine

Declarative (Atlas)
  schema desiderato (HCL) ──┐
                             ├──► diff engine ──► piano DDL ──► applica
  schema reale (introspect)─┘
```

!!! warning "Locking non è garantito ovunque"
    Flyway usa un lock a livello di tabella di controllo (advisory lock su PostgreSQL) di default. golang-migrate implementa il lock per driver (es. advisory lock su PostgreSQL, `GET_LOCK` su MySQL) ma non in modo uniforme su tutti i backend — dove manca, due processi paralleli possono correre in race. Se le migration girano da più pod contemporaneamente (rolling deploy con più repliche che partono insieme), verificare esplicitamente il comportamento di lock del tool scelto o serializzare l'esecuzione con un init container unico / Kubernetes Job con `parallelism: 1`.

## Configurazione & Pratica

Stessa modifica — **aggiungere una colonna NOT NULL con default** su una tabella `users` — espressa nei tre tool.

### Flyway (versioned, community edition)

```sql
-- V4__add_status_to_users.sql
-- Flyway Community non supporta rollback automatico: se serve annullare,
-- va scritta a mano una migration "forward" che inverte l'effetto (V5).
ALTER TABLE users
  ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active';
```

```bash
# Applica tutte le migration pendenti
flyway -url=jdbc:postgresql://localhost:5432/app -user=app -password=*** migrate

# Verifica stato senza applicare
flyway -url=jdbc:postgresql://localhost:5432/app info

# Rollback: SOLO in Flyway Teams (a pagamento) con `flyway undo`
# In Community: si scrive una nuova migration V5 che fa DROP COLUMN o inverte
```

```ini
# flyway.conf
flyway.url=jdbc:postgresql://localhost:5432/app
flyway.locations=filesystem:./sql/migrations
# baselineOnMigrate: serve SOLO per adottare Flyway su un DB già popolato
# (crea la baseline alla prima esecuzione). Su DB nuovi lasciarlo false:
# con true, un DB non vuoto senza history verrebbe "adottato" senza errori.
flyway.baselineOnMigrate=true
```

### Liquibase (changelog, con modalità diff opzionale)

```yaml
# changelog/004-add-status-to-users.yaml
databaseChangeLog:
  - changeSet:
      id: 004-add-status
      author: andrea
      changes:
        - addColumn:
            tableName: users
            columns:
              - column:
                  name: status
                  type: varchar(20)
                  defaultValue: active
                  constraints:
                    nullable: false
      # rollback esplicito dichiarato nello stesso changeset
      rollback:
        - dropColumn:
            tableName: users
            columnName: status
```

```bash
# Applica il changelog
liquibase --changelog-file=changelog/db.changelog-master.yaml update

# Rollback dell'ultimo changeset applicato — supportato nativamente
# SE il rollback è stato dichiarato esplicitamente nel changeset (come sopra)
liquibase --changelog-file=changelog/db.changelog-master.yaml rollback-count 1
# (rollback-one-changeset esiste solo in edizione Pro; in Community usare
#  rollback-count N, rollback --tag=X oppure rollback-to-date)

# Modalità diff (stato-based, opzionale): genera un changelog dal confronto
# tra due database o tra un database e uno schema di riferimento
liquibase diff-changelog \
  --reference-url=jdbc:postgresql://localhost/app_target \
  --url=jdbc:postgresql://localhost/app_current \
  --changelog-file=changelog/005-generated-diff.yaml
```

### Atlas (declarative, drift detection nativo)

```hcl
# schema.hcl — stato DESIDERATO, non uno script incrementale
schema "public" {}

table "users" {
  schema = schema.public
  column "id" {
    type = int
    identity {}
  }
  column "status" {
    type    = varchar(20)
    null    = false
    default = "active"
  }
  primary_key {
    columns = [column.id]
  }
}
```

```bash
# Atlas calcola il diff tra schema.hcl e lo stato reale del DB, genera il piano
atlas schema apply \
  --url "postgres://app:***@localhost:5432/app?sslmode=disable" \
  --to "file://schema.hcl" \
  --dry-run   # mostra il piano DDL senza applicarlo

# Applica dopo revisione
atlas schema apply \
  --url "postgres://app:***@localhost:5432/app?sslmode=disable" \
  --to "file://schema.hcl"

# Drift detection: diff semantico tra stato reale e schema dichiarato
# (output vuoto / "Schemas are synced" = nessun drift)
atlas schema diff \
  --from "postgres://app:***@localhost:5432/app?sslmode=disable" \
  --to "file://schema.hcl"

# "Rollback" in Atlas = riapplicare uno schema.hcl precedente (versionato in git)
git checkout HEAD~1 -- schema.hcl
atlas schema apply --url "postgres://..." --to "file://schema.hcl"
```

### golang-migrate (versioned, minimale, multi-driver)

```sql
-- migrations/000004_add_status_to_users.up.sql
ALTER TABLE users ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active';

-- migrations/000004_add_status_to_users.down.sql
-- Rollback manuale: la migration "down" va scritta esplicitamente,
-- il tool si limita a eseguirla — nessuna generazione automatica
ALTER TABLE users DROP COLUMN status;
```

```bash
# Applica tutte le migration pendenti
migrate -path ./migrations -database "postgres://app:***@localhost:5432/app?sslmode=disable" up

# Rollback dell'ultima migration applicata (esegue lo script .down.sql)
migrate -path ./migrations -database "postgres://..." down 1

# golang-migrate non ha locking robusto su tutti i driver: in Kubernetes
# usare un Job con parallelism:1, non un initContainer replicato per ogni pod
```

## Best Practices

- **Migration additive prima, distruttive dopo (expand & contract)**: per zero-downtime, separare "aggiungi colonna nullable" (deploy 1) da "rendi NOT NULL e rimuovi la vecchia colonna" (deploy successivo, dopo che tutto il traffico usa la nuova colonna). Questo evita che un vecchio pod, ancora in rolling update, scriva contro uno schema che non conosce.
- **Mai modificare una migration già applicata in produzione**: se un file versioned cambia dopo essere stato eseguito, il checksum non corrisponde più e Flyway/golang-migrate falliscono (comportamento corretto, non un bug da bypassare con `repair` senza capire perché).
- **Serializzare l'esecuzione in Kubernetes**: eseguire le migration in un singolo `Job` (`completions: 1`, `parallelism: 1`) prima del rollout, oppure usare un lock applicativo esplicito (advisory lock PostgreSQL) se più pod potrebbero partire in parallelo — vedi [Database Patterns](../../dev/integrazioni/database-patterns.md).
- **DDL a basso impatto di lock (PostgreSQL)**: `ALTER TABLE` richiede `ACCESS EXCLUSIVE` e si accoda dietro query lunghe, bloccando tutte le successive. Impostare `SET lock_timeout = '5s'` nella migration per fallire in fretta invece di bloccare il traffico. `SET NOT NULL` su tabelle grandi fa una scansione completa sotto lock: da PG 12 aggiungere prima `CHECK (col IS NOT NULL) NOT VALID`, poi `VALIDATE CONSTRAINT` (lock leggero), poi `SET NOT NULL` (che riusa il check). Un `ADD COLUMN ... DEFAULT <costante>` è invece solo metadata da PG 11.
- **Committare `schema.hcl` (Atlas) o le directory `migrations/` in git insieme al codice applicativo**: la versione dello schema deve essere tracciabile allo stesso commit del codice che la richiede.

!!! tip "Scegliere in base al rollback che serve davvero"
    Se il rollback automatico è un requisito hard (compliance, cambio frequente di piani), Liquibase con rollback dichiarati esplicitamente o Flyway Teams sono le uniche opzioni pronte all'uso senza scrivere script "down" a mano. Se il team è disciplinato nello scrivere `.down.sql` per ogni migration, golang-migrate è la scelta più leggera. Se serve drift detection continuo su ambienti dove qualcuno potrebbe intervenire manualmente sul DB, solo Atlas lo copre nativamente.

!!! warning "Flyway Community non fa rollback automatico"
    <!-- REVIEW: verificare edizioni Flyway attuali (Redgate ha riorganizzato le edizioni; "Teams" potrebbe non esistere più con questo nome) e quale edizione include `flyway undo` -->
    È il trade-off più sottovalutato: un team che sceglie Flyway (community, gratuito) assumendo di poter fare `flyway undo` come con Liquibase scopre solo in un incidente che quel comando è a pagamento (Teams edition). Il piano di rollback per Flyway Community è sempre "scrivi e applica una nuova migration forward che inverte l'effetto" — va progettato PRIMA, non improvvisato durante un incidente.

## Troubleshooting

### Scenario 1 — Due pod applicano la stessa migration in parallelo (race condition)

**Sintomo**: errore `duplicate column` o `relation already exists` durante un rolling deploy con più repliche, migration falliscono in modo intermittente.

**Causa**: più init container/pod partono nella stessa finestra temporale e tentano di applicare le migration pendenti senza lock effettivo (tipico con golang-migrate su driver senza lock, o con tool/script custom che non ne usano).

**Soluzione**: spostare l'esecuzione della migration in un `Job` Kubernetes dedicato con `completions: 1`, eseguito come step separato prima del rollout del Deployment, invece che in ogni init container di ogni pod.

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: db-migrate-v4
spec:
  backoffLimit: 2
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: migrate
          image: migrate/migrate
          args: ["-path", "/migrations", "-database", "$(DB_URL)", "up"]
```

### Scenario 2 — Checksum mismatch su migration già applicata

**Sintomo**: Flyway fallisce all'avvio con `Migration checksum mismatch for migration version X`.

**Causa**: un file di migration già eseguito in produzione è stato modificato dopo il fatto (es. correzione di un typo in uno script SQL già applicato in staging).

**Soluzione**: non modificare mai un file versionato applicato — creare una nuova migration correttiva. Se il mismatch è dovuto a un fix legittimo già concordato, allineare i checksum con `flyway repair` solo dopo aver verificato manualmente che lo schema reale è coerente.

```bash
flyway repair -url=jdbc:postgresql://localhost/app
flyway info -url=jdbc:postgresql://localhost/app   # verificare stato dopo il repair
```

### Scenario 3 — Drift non rilevato: modifica manuale in produzione ignorata dal tool

**Sintomo**: un DBA ha eseguito manualmente un `ALTER TABLE` in produzione per un fix urgente; la prossima migration applicata da golang-migrate o Flyway non fallisce, ma lo schema risultante è inconsistente con gli altri ambienti.

**Causa**: i tool versioned non fanno introspection dello stato reale — si fidano ciecamente della tabella di controllo, non verificano che lo schema corrisponda a quanto atteso.

**Soluzione**: con Atlas, eseguire `atlas schema inspect` periodicamente (o in CI) e confrontare con lo schema dichiarato per rilevare drift; con Flyway/golang-migrate, introdurre un controllo esterno (script di introspection schedulato) perché il drift detection non è nativo.

Il `diff` testuale tra output di `inspect` e `schema.hcl` genera falsi positivi (ordine/formattazione): usare il diff semantico di Atlas.

```bash
atlas schema diff \
  --from "postgres://app:***@prod-host:5432/app?sslmode=disable" \
  --to "file://schema.hcl"
```

### Scenario 4 — Migration NOT NULL fallisce su tabella con dati esistenti

**Sintomo**: `ALTER TABLE users ADD COLUMN status VARCHAR(20) NOT NULL` fallisce con `column "status" contains null values` (o equivalente) su una tabella già popolata, indipendentemente dal tool usato.

**Causa**: aggiungere una colonna NOT NULL senza `DEFAULT` su una tabella con righe esistenti lascia quelle righe senza un valore da assegnare — il vincolo NOT NULL rifiuta l'operazione.

**Soluzione**: fornire sempre un `DEFAULT` nella stessa DDL (come negli esempi sopra), oppure — se il default non è accettabile a lungo termine — dividere in tre migration: aggiungi colonna nullable, backfill dei dati esistenti, poi aggiungi il vincolo NOT NULL in una migration successiva (pattern expand & contract).

```sql
-- Migration 1: colonna nullable
ALTER TABLE users ADD COLUMN status VARCHAR(20);

-- Migration 2: backfill (fuori transazione DDL se la tabella è grande, in batch)
UPDATE users SET status = 'active' WHERE status IS NULL;

-- Migration 3: vincolo, solo dopo che il backfill è confermato completo
ALTER TABLE users ALTER COLUMN status SET NOT NULL;
```

## Relazioni

??? info "Init Container Pattern — Dove girano le migration in Kubernetes"
    Come eseguire le migration prima che il pod applicativo si avvii, e perché serve idempotenza quando l'init container può ripartire.

    **Approfondimento completo →** [Database Patterns](../../dev/integrazioni/database-patterns.md)

??? info "Transazioni e Concorrenza — Perché il locking conta"
    DDL transazionale, advisory lock e perché MySQL si comporta diversamente da PostgreSQL durante una migration fallita a metà.

    **Approfondimento completo →** [Transazioni e Concorrenza](transazioni-concorrenza.md)

??? info "GitOps — Migration come parte del deployment dichiarativo"
    Come integrare l'esecuzione delle migration in una pipeline GitOps (Argo CD) senza rompere la sincronizzazione dichiarativa.

    **Approfondimento completo →** [Argo CD](../../ci-cd/gitops/argocd.md)

## Riferimenti

- [Atlas — Documentazione ufficiale](https://atlasgo.io/docs)
- [Flyway — Documentazione ufficiale](https://documentation.red-gate.com/fd)
- [Liquibase — Documentazione ufficiale](https://docs.liquibase.com/)
- [golang-migrate — GitHub](https://github.com/golang-migrate/migrate)
- [Evolutionary Database Design — Martin Fowler](https://martinfowler.com/articles/evodb.html)
