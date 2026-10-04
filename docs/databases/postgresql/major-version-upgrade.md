---
title: "PostgreSQL Major Version Upgrade"
slug: major-version-upgrade
category: databases
tags: [postgresql, upgrade, pg-upgrade, logical-replication, blue-green, migration, downtime]
search_keywords: [postgresql major upgrade, pg_upgrade, pg_upgrade --link, pg_upgrade --clone, pg_upgrade --check, pg_dump pg_restore upgrade, logical replication upgrade, blue green deployment, RDS blue/green, Aurora blue/green, Cloud SQL major version upgrade, Database Migration Service, DMS, vacuumdb analyze-in-stages, REINDEX collation, glibc collation change, ICU collation, update_extensions, ALTER EXTENSION UPDATE, sequences sync, setval, publication subscription, pg_createsubscriber, zero downtime upgrade, near-zero downtime, rollback plan, cutover, LSN lag, pg_current_wal_lsn, CloudNativePG import, in-place major upgrade, upgrade PostgreSQL 15 to 17, password_encryption scram, prepared transactions, replication slot, data checksums]
parent: databases/postgresql/_index
related: [databases/postgresql/replicazione, databases/postgresql/extensions, databases/postgresql/mvcc-vacuum, databases/kubernetes-cloud/db-su-kubernetes, databases/kubernetes-cloud/managed-databases, databases/replicazione-ha/backup-pitr]
official_docs: https://www.postgresql.org/docs/current/pgupgrade.html
status: needs-review
difficulty: advanced
last_updated: 2026-10-03
last_verified: 2026-10-04
---

# PostgreSQL Major Version Upgrade

## Panoramica

Una **major version** di PostgreSQL (es. 15 → 17) cambia il formato interno del catalogo di sistema, quindi la data directory di una versione **non** è leggibile dal binario di un'altra: non basta sostituire i binari come per una minor release (16.3 → 16.4). Serve migrare i dati con una delle strategie descritte qui. La scelta si riduce a un trade-off tra **downtime**, **complessità** e **reversibilità**.

Si fa un major upgrade perché ogni versione ha un ciclo di supporto di 5 anni: dopo l'EOL non arrivano più fix di sicurezza. Ogni major porta anche miglioramenti concreti di performance (vacuum, parallel query, `MERGE`, logical replication da standby, ecc.).

Questa guida copre le strategie, la checklist pre-upgrade, i passi post-upgrade (spesso dimenticati e causa di regressioni di performance), il rollback e l'upgrade su Kubernetes. Il caso base di logical replication è già introdotto in [Replicazione](replicazione.md); qui si entra nei dettagli operativi (sequenze, DDL, large object, cutover).

!!! warning "Non si salta nulla"
    Si può passare direttamente da 12 a 17 con `pg_upgrade` (non serve toccare le versioni intermedie), ma bisogna leggere le **release notes di ogni versione attraversata**, sezione *Migration to Version X*: elencano le incompatibilità cumulative.

## Concetti Chiave

| Strategia | Downtime tipico | Rollback | Complessità | Quando usarla |
|---|---|---|---|---|
| `pg_dump` / `pg_restore` | proporzionale alla dimensione (ore) | facile (vecchio cluster intatto) | bassa | DB piccoli (< ~50 GB), cambio di encoding/locale/checksum |
| `pg_upgrade` copy | proporzionale alla dimensione (copia file) | facile | bassa | spazio disco abbondante, nessuna fretta |
| `pg_upgrade --link` | secondi–minuti, indipendente dalla dimensione | **difficile** dopo l'avvio del nuovo cluster | media | DB grandi, finestra di manutenzione breve |
| `pg_upgrade --clone` | secondi–minuti | facile (i file originali restano) | media | filesystem con reflink (XFS, Btrfs, APFS, ZFS recente) |
| Logical replication blue/green | secondi (solo cutover) | facile fino al cutover, poi richiede replica inversa | alta | downtime quasi zero, DB critici |
| Managed blue/green (RDS/Aurora) | tipicamente ~1 min di switchover | possibile (ambiente blue conservato) | media | servizi gestiti AWS |

!!! note "Definizioni"
    - **Downtime**: intervallo in cui l'applicazione non può scrivere (o leggere).
    - **Cutover**: il momento in cui il traffico passa dal vecchio al nuovo cluster.
    - **LSN** (Log Sequence Number): posizione nel WAL; confrontare gli LSN permette di misurare il lag di replica.

## Architettura / Come Funziona

### pg_upgrade

`pg_upgrade` non riscrive i dati utente: crea un nuovo cluster (`initdb`) con la versione target, **ricrea il catalogo di sistema** facendo un dump dello schema (`pg_dump --schema-only`) dal vecchio e ripristinandolo nel nuovo, poi **riusa i file dei dati** delle tabelle. Cambia solo il modo in cui i file vengono trasferiti:

```
modalità          cosa fa con i file di dati                      vecchio cluster dopo l'upgrade
--copy (default)  copia ogni file                                 utilizzabile
--link            hard link ai file del vecchio cluster           NON utilizzabile dopo l'avvio del nuovo
--clone           reflink (copy-on-write) dove il FS lo supporta  utilizzabile
--copy-file-range usa copy_file_range() (PG 17+)                  utilizzabile
--swap            scambia le directory (PG 18+, più veloce)       NON utilizzabile
```

Cosa **non** porta con sé `pg_upgrade` (rilevante nel post-upgrade):

- le **statistiche del planner** fino a PG 17 incluso (da PG 18 le statistiche vengono preservate): senza `ANALYZE` i piani sono pessimi;
- i file di configurazione (`postgresql.conf`, `pg_hba.conf`): vanno riportati a mano, rivedendo i parametri rimossi o rinominati;
- gli **slot di replica logica** e lo stato delle subscription: preservati solo se il vecchio cluster è PG 17+ (altrimenti vanno ricreati);
- le librerie delle estensioni: i `.so` della nuova versione devono essere installati sul sistema prima dell'upgrade.

### Logical replication blue/green

Si costruisce un secondo cluster (green) con la versione nuova, lo si popola con uno snapshot iniziale e poi lo si tiene allineato via logical replication dal cluster esistente (blue). Al cutover si ferma la scrittura su blue, si attende che green sia allineato, si sposta il traffico.

```
  App ──> PG15 (blue, primary)  ── publication ──>  PG17 (green, subscriber)
                │                                         │
        scritture continuano                     schema pre-creato (pg_dump -s)
                                                  sequenze sincronizzate al cutover
```

Limiti noti della logical replication, da affrontare **prima** di sceglierla:

| Limite | Conseguenza | Mitigazione |
|---|---|---|
| Le **sequenze** non vengono replicate (fino a PG 18; da PG 19 sono previste) <!-- REVIEW: verificare se PG 19 (autunno 2026) ha rilasciato la replica delle sequenze e se pg_upgrade/stato corrente delle versioni supportate è cambiato --> | Dopo il cutover gli `INSERT` falliscono con duplicate key | Sincronizzare con `setval()` al cutover |
| Il **DDL non viene replicato** | Una `ALTER TABLE` su blue rompe la subscription | Congelare gli schema change durante la migrazione |
| I **large object** (`pg_largeobject`) non vengono replicati | Dati mancanti su green | Migrarli con `pg_dump --large-objects` o convertirli in `bytea` |
| Tabelle senza `PRIMARY KEY` | `UPDATE`/`DELETE` falliscono se non c'è `REPLICA IDENTITY` | `ALTER TABLE ... REPLICA IDENTITY FULL` (costoso) o aggiungere una PK |
| Ruoli, tablespace, `pg_authid` | Non replicati | `pg_dumpall --globals-only` |
| Viste materializzate, `TRUNCATE` su alcune versioni | Comportamento diverso | Verificare il supporto per la versione di origine |

### Managed blue/green

I servizi gestiti automatizzano lo stesso schema:

- **RDS for PostgreSQL / Aurora PostgreSQL — Blue/Green Deployments**: creano un ambiente green clone di production, con la versione nuova, mantenuto allineato via logical replication. Lo *switchover* rinomina gli endpoint ed è tipicamente un minuto di interruzione. L'ambiente blue originale viene conservato finché non lo si elimina.
- **Cloud SQL**: offre l'upgrade in-place della major version (con downtime e backup automatico pre-upgrade) oppure la migrazione verso una nuova istanza con **Database Migration Service (DMS)**, basata su logical replication, per ridurre il downtime.

Dettagli sui servizi: [Managed Databases](../kubernetes-cloud/managed-databases.md).

## Configurazione & Pratica

### Checklist pre-upgrade

Prima di toccare qualsiasi cosa:

1. **Backup verificato** e restore testato: vedi [Backup e PITR](../replicazione-ha/backup-pitr.md).
2. **Rehearsal** su una copia (snapshot/restore del cluster di produzione) con misurazione dei tempi reali.
3. **Release notes** di tutte le versioni attraversate.
4. **Estensioni**: stessa versione supportata dalla nuova major?
5. **Prepared transactions** chiuse e **slot** gestiti.
6. **Cambi di default** rilevanti.

```bash
# Estensioni installate e versione (nel DB di produzione)
psql -d mydb -c "SELECT extname, extversion FROM pg_extension ORDER BY 1;"

# Versioni disponibili con i pacchetti già installati sul nuovo host
psql -d mydb -c "SELECT name, default_version, installed_version FROM pg_available_extensions WHERE installed_version IS NOT NULL;"

# Prepared transactions pendenti: pg_upgrade si rifiuta di procedere
psql -c "SELECT gid, prepared, owner, database FROM pg_prepared_xacts;"

# Slot di replica: logical slot (non preservati prima di PG 17) e slot inattivi
psql -c "SELECT slot_name, slot_type, active, restart_lsn FROM pg_replication_slots;"
```

#### Compatibilità estensioni

| Estensione | Punti di attenzione |
|---|---|
| **PostGIS** | Versione di PostGIS compatibile con la nuova major *e* con GEOS/PROJ/GDAL di sistema; dopo l'upgrade `SELECT postgis_extensions_upgrade();` |
| **pgvector** | Installare la stessa (o più recente) versione per la nuova major; gli indici HNSW/IVFFlat sono file normali e vengono preservati |
| **TimescaleDB** | Ogni versione di Timescale supporta solo alcune major di PG: upgrade prima Timescale a una versione che supporta sia la vecchia sia la nuova, poi `pg_upgrade`, poi `ALTER EXTENSION timescaledb UPDATE` in una sessione con `-X` |
| **pg_stat_statements, pg_cron, pgaudit** | Pacchetto per la nuova major; `shared_preload_libraries` da riportare nella nuova configurazione |

Vedi [Extensions](extensions.md) per il quadro generale.

#### Cambi di default e incompatibilità frequenti

| Versione | Cambio | Impatto |
|---|---|---|
| PG 14 | `password_encryption` default = `scram-sha-256` | Client/driver o pooler vecchi che supportano solo `md5` non si autenticano; gli hash `md5` esistenti restano validi |
| PG 15 | `CREATE` sullo schema `public` revocato a `PUBLIC` (solo per DB nuovi, non per quelli migrati con `pg_upgrade`) | Cambia il comportamento tra cluster migrato e cluster nuovo: verificare i grant |
| PG 15+ | ICU come locale provider disponibile; PG 17 aggiunge il provider `builtin` | Occasione per sganciarsi dalla `glibc` (vedi sotto) |
| PG 16 | Rimosse alcune opzioni legacy (`promote_trigger_file`, `vacuum_defer_cleanup_age` in PG 16) | La configurazione con parametri rimossi impedisce l'avvio |
| PG 17 | Rimosso `old_snapshot_threshold`; `MAINTAIN` come privilegio | Rimuovere il parametro dal `postgresql.conf` |

!!! warning "Collation e glibc: il rischio silenzioso"
    Se il nuovo host ha una versione di `glibc` diversa (tipico quando si cambia OS insieme al DB; il salto 2.27 → 2.28 ha cambiato l'ordinamento di molte lingue), l'ordine di sort cambia **senza errori**. Gli indici B-tree su colonne testuali diventano corrotti rispetto al nuovo ordinamento: query che non trovano righe esistenti e violazioni di unicità non rilevate. Con `pg_upgrade` su stesso host e stessa glibc il problema non si pone; con restore/replica su un host diverso sì.

```bash
# Verifica la versione di glibc e il collation provider usato dal database
ldd --version | head -1
psql -c "SELECT datname, datcollate, datctype, datlocprovider FROM pg_database;"

# Rileva indici testuali corrotti dopo un cambio di collation (richiede l'estensione amcheck)
psql -d mydb -c "CREATE EXTENSION IF NOT EXISTS amcheck;"
psql -d mydb -c "SELECT bt_index_check(c.oid) FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid JOIN pg_am a ON a.oid = c.relam WHERE a.amname = 'btree';"
```

### Strategia 1 — pg_dump / pg_restore

La più semplice e l'unica che permette di cambiare encoding, locale o abilitare i data checksums nel passaggio.

```bash
# Globals (ruoli, tablespace) dal vecchio cluster
pg_dumpall -h old-host --globals-only > globals.sql

# Dump in formato directory, parallelo, usando i binari della NUOVA versione (best practice)
/usr/lib/postgresql/17/bin/pg_dump -h old-host -Fd -j 8 -f /backup/mydb.dump mydb

# Sul nuovo cluster
psql -h new-host -f globals.sql
createdb -h new-host mydb
/usr/lib/postgresql/17/bin/pg_restore -h new-host -d mydb -j 8 --no-owner --exit-on-error /backup/mydb.dump
```

!!! tip "Usa i binari nuovi per il dump"
    `pg_dump` della versione target sa leggere i server più vecchi ed emette SQL adatto alla destinazione. L'opposto non vale.

### Strategia 2 — pg_upgrade

```bash
# 1. Installa i binari 17 accanto ai 15 e crea il nuovo cluster vuoto.
#    Encoding, locale e locale provider DEVONO coincidere con il vecchio cluster
#    (verifica con: SELECT datname, datcollate, datctype, datlocprovider FROM pg_database;),
#    altrimenti pg_upgrade --check fallisce. Idem per i data checksums: stessa impostazione.
sudo -u postgres /usr/lib/postgresql/17/bin/initdb -D /var/lib/postgresql/17/main \
    --encoding=UTF8 --locale=it_IT.UTF-8

# 2. Controllo di compatibilità: NON modifica nulla, si può ripetere a cluster in produzione
sudo -u postgres /usr/lib/postgresql/17/bin/pg_upgrade \
    --old-bindir=/usr/lib/postgresql/15/bin \
    --new-bindir=/usr/lib/postgresql/17/bin \
    --old-datadir=/var/lib/postgresql/15/main \
    --new-datadir=/var/lib/postgresql/17/main \
    --link --jobs=8 --check
```

Output atteso: `*Clusters are compatible*`. Con `--check` si scoprono i blocchi tipici: prepared transactions, tipi `reg*` nelle tabelle utente, estensioni mancanti, `data checksums` diversi tra i due cluster (devono coincidere), encoding/locale/locale provider diversi. Attenzione: da PG 18 `initdb` abilita i checksum **di default**; se il vecchio cluster non li ha, creare il nuovo con `initdb --no-data-checksums` (oppure abilitarli prima sul vecchio con `pg_checksums --enable`, a cluster fermo).

```bash
# 3. Finestra di manutenzione: ferma l'applicazione e il vecchio cluster
sudo systemctl stop postgresql@15-main

# 4. Upgrade vero (stessi parametri, senza --check). --link: secondi anche per 5 TB
sudo -u postgres /usr/lib/postgresql/17/bin/pg_upgrade \
    --old-bindir=/usr/lib/postgresql/15/bin --new-bindir=/usr/lib/postgresql/17/bin \
    --old-datadir=/var/lib/postgresql/15/main --new-datadir=/var/lib/postgresql/17/main \
    --link --jobs=8

# 5. Riporta la configurazione, avvia il nuovo cluster, poi esegui il post-upgrade
sudo systemctl start postgresql@17-main
```

!!! warning "Il punto di non ritorno di --link"
    Con `--link` il nuovo cluster **condivide** i file con il vecchio. Dopo la prima scrittura sul nuovo cluster, il vecchio non è più utilizzabile. Il rollback richiede il restore da backup. Se la dimensione del dato lo permette, preferire `--clone` (reflink) che mantiene intatto il vecchio cluster in modo istantaneo.

Per le standby fisiche **non** si rifà l'upgrade: si usa `rsync --archive --hard-links --size-only` come descritto nella documentazione ufficiale `pg_upgrade` ("Upgrade Streaming Replication and Log-Shipping standby servers"), oppure si ricostruiscono con `pg_basebackup` dal nuovo primary.

### Strategia 3 — Logical replication blue/green

```bash
# --- BLUE (PG15, sorgente): configurazione ---
# postgresql.conf: wal_level = logical  (richiede riavvio, pianificarlo prima!)
psql -h blue -c "SHOW wal_level;"

# Schema + ruoli sul nuovo cluster (schema-only: niente dati)
pg_dumpall -h blue --globals-only | psql -h green
pg_dump -h blue -s -Fc mydb -f schema.dump
createdb -h green mydb
pg_restore -h green -d mydb --no-owner schema.dump
```

```sql
-- BLUE: pubblica tutte le tabelle
CREATE PUBLICATION upgrade_pub FOR ALL TABLES;

-- GREEN: sottoscrivi (copia i dati iniziali, poi segue il WAL)
CREATE SUBSCRIPTION upgrade_sub
  CONNECTION 'host=blue port=5432 dbname=mydb user=replicator password=***'
  PUBLICATION upgrade_pub
  WITH (copy_data = true, create_slot = true);

-- GREEN: stato della sincronizzazione iniziale (r = ready)
SELECT srrelid::regclass, srsubstate FROM pg_subscription_rel;
```

!!! tip "Alternativa fisica → logica: pg_createsubscriber"
    Da PG 17, `pg_createsubscriber` converte una **standby fisica** (stessa major del primary) in un subscriber logico, evitando la copia iniziale dei dati (molto più veloce per DB grandi). Da solo **non** cambia versione: la standby ha la stessa major del primary. Per arrivare a una major superiore, dopo la conversione si esegue `pg_upgrade` sul subscriber, che da un cluster PG 17+ preserva slot e stato della subscription; quindi il percorso vale per partenze da PG 17 in su.

#### Script di cutover con verifica del lag LSN

```bash
#!/usr/bin/env bash
# cutover.sh — switchover blue (PG15) -> green (PG17). Eseguire con set -e: si ferma al primo errore.
set -euo pipefail
BLUE="host=blue dbname=mydb user=postgres"
GREEN="host=green dbname=mydb user=postgres"

echo "1) Blocca le scritture su blue"
psql "$BLUE" -c "ALTER DATABASE mydb SET default_transaction_read_only = on;"
# Chiude le sessioni esistenti per applicare subito il read-only
psql "$BLUE" -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='mydb' AND pid <> pg_backend_pid() AND backend_type='client backend';"

echo "2) Cattura la posizione WAL finale di blue"
TARGET_LSN=$(psql "$BLUE" -Atc "SELECT pg_current_wal_lsn();")

echo "3) Attendi che green abbia applicato fino a TARGET_LSN ($TARGET_LSN)"
for i in $(seq 1 120); do
  # Differenza in byte tra la posizione finale di blue e quella applicata da green
  LAG=$(psql "$GREEN" -Atc "SELECT pg_wal_lsn_diff('$TARGET_LSN', latest_end_lsn) FROM pg_stat_subscription WHERE subname='upgrade_sub' AND relid IS NULL;")
  echo "   lag = ${LAG} byte"
  [ "${LAG%.*}" -le 0 ] && break
  sleep 1
done
[ "${LAG%.*}" -le 0 ] || { echo "Lag non azzerato: ROLLBACK (riabilita le scritture su blue)"; \
  psql "$BLUE" -c "ALTER DATABASE mydb RESET default_transaction_read_only;"; exit 1; }

echo "4) Sincronizza le sequenze (non replicate)"
psql "$BLUE" -Atc "SELECT format('SELECT setval(%L, %s, true);', quote_ident(schemaname)||'.'||quote_ident(sequencename), last_value) FROM pg_sequences WHERE last_value IS NOT NULL;" \
  | psql "$GREEN"

echo "5) Rimuovi la subscription (blue resta intatto per il rollback; lo slot su blue NON viene droppato: eliminarlo a mano quando non serve più, altrimenti trattiene WAL)"
psql "$GREEN" -c "ALTER SUBSCRIPTION upgrade_sub DISABLE;"
psql "$GREEN" -c "ALTER SUBSCRIPTION upgrade_sub SET (slot_name = NONE);"
psql "$GREEN" -c "DROP SUBSCRIPTION upgrade_sub;"

echo "6) Ora puoi spostare il traffico (DNS / pooler / connection string) su green"
```

!!! note "Margine di sicurezza sulle sequenze"
    Il valore letto da blue è l'ultimo allocato al momento della lettura. Per sicurezza molti team aggiungono un margine (`last_value + 1000`) per tollerare valori `nextval` già prenotati dalle cache delle sessioni.

### Post-upgrade (obbligatorio)

#### 1. Statistiche — `vacuumdb --analyze-in-stages`

`pg_upgrade` (fino a PG 17) non porta le statistiche del planner. Con tabelle senza statistiche il planner usa default arbitrari: query che prima erano rapide possono diventare lentissime. `--analyze-in-stages` costruisce prima statistiche grossolane (veloci, con `default_statistics_target` bassissimo) per rendere il DB usabile subito, poi quelle complete.

```bash
# Subito dopo l'avvio del nuovo cluster (può girare mentre l'app è già online)
/usr/lib/postgresql/17/bin/vacuumdb --all --analyze-in-stages --jobs=8

# Da PG 18: solo le tabelle prive di statistiche
/usr/lib/postgresql/18/bin/vacuumdb --all --analyze-in-stages --missing-stats-only --jobs=8
```

#### 2. Estensioni

```sql
-- Elenca le estensioni con una versione più nuova disponibile
SELECT name, installed_version, default_version
FROM pg_available_extensions
WHERE installed_version IS NOT NULL AND installed_version <> default_version;

-- Aggiorna una per una (le estensioni NON si aggiornano da sole)
ALTER EXTENSION pg_stat_statements UPDATE;
ALTER EXTENSION postgis UPDATE;
```

Alla fine `pg_upgrade` segnala gli eventuali script generati nella directory corrente (`update_extensions.sql` nelle versioni che lo producono, `delete_old_cluster.sh`): eseguire `update_extensions.sql` con `psql -f` se presente, altrimenti usare `ALTER EXTENSION ... UPDATE` come sopra.

#### 3. REINDEX per cambio di collation

Necessario quando la libreria di collation del nuovo ambiente ordina diversamente dal vecchio.

```bash
# Ricostruzione degli indici senza lock esclusivo lungo (PG 12+)
reindexdb --all --concurrently --jobs=4

# Poi, se il DB ha una collation versionata, aggiorna la versione registrata
psql -d mydb -c "ALTER DATABASE mydb REFRESH COLLATION VERSION;"
```

#### 4. Pulizia

```bash
# Solo dopo una finestra di osservazione adeguata (giorni): rimuove il vecchio cluster
./delete_old_cluster.sh      # generato da pg_upgrade (rm del vecchio cluster: irreversibile)
```

## Rollback plan e downtime attesi

| Strategia | Rollback prima del go-live | Rollback dopo che il nuovo cluster ha scritto | Downtime tipico |
|---|---|---|---|
| dump/restore | Il vecchio cluster non è mai stato toccato: basta non fare il cutover | Dati scritti sul nuovo persi, salvo replica inversa | Dimensione / throughput del restore (ordine: ~100–300 GB/h con `-j` alto, dipende da indici) |
| `pg_upgrade --link` | Possibile **solo prima di avviare il nuovo cluster**: ripristinare `global/pg_control` da `pg_control.old` e riavviare il vecchio | **Impossibile**: restore da backup | Secondi–minuti (+ analyze in background) |
| `pg_upgrade --clone` / copy | Vecchio cluster intatto: riavviare il vecchio | Dati scritti sul nuovo persi | Minuti (clone) / ore (copy) |
| Logical replication | Basta non fare il cutover; riabilitare le scritture su blue | Possibile **solo** se si è predisposta una **replica inversa** green → blue prima del cutover | Secondi (solo cutover + setval) |
| RDS/Aurora blue/green | Eliminare l'ambiente green | Ambiente blue conservato ma non più aggiornato: eventuali scritture su green vanno riportate a mano | ~1 min (switchover) |

Il rollback va deciso **prima** dell'upgrade, con una soglia esplicita (es. "se entro 30 minuti dal cutover il p95 delle query supera X, torniamo indietro"). Il caso peggiore è sempre "nuovo cluster con scritture e nessuna via di ritorno": per questo la replica inversa o un backup consistente subito prima del cutover valgono il costo.

```bash
# Rollback di pg_upgrade --link PRIMA di avviare il nuovo cluster
mv /var/lib/postgresql/15/main/global/pg_control.old /var/lib/postgresql/15/main/global/pg_control
sudo systemctl start postgresql@15-main
```

## Upgrade su Kubernetes (CloudNativePG)

Con l'operator **CloudNativePG** (CNPG) i pod sono effimeri e il cluster è dichiarativo: non si lancia `pg_upgrade` a mano ma si usa una delle due modalità, descritte in [DB su Kubernetes](../kubernetes-cloud/db-su-kubernetes.md):

**A. Import in un nuovo Cluster (logico, universale).** Si crea un *nuovo* `Cluster` con l'immagine nuova che importa i dati dal vecchio con `pg_dump`/`pg_restore` (`microservice` per un singolo DB, `monolith` per tutti). Il vecchio cluster resta intatto (rollback = tornare a puntarlo). Downtime = durata dell'import, a meno di usare l'opzione di replica logica.

```yaml
apiVersion: postgresql.cnpg.io/v1
kind: Cluster
metadata:
  name: app-pg17
spec:
  instances: 3
  imageName: ghcr.io/cloudnative-pg/postgresql:17
  storage:
    size: 100Gi
  bootstrap:
    initdb:
      import:
        type: microservice          # un database; "monolith" per importarli tutti
        databases: [app]
        source:
          externalCluster: app-pg15
  externalClusters:
    - name: app-pg15
      connectionParameters:
        host: app-pg15-rw.prod.svc
        user: postgres
        dbname: postgres
      password:
        name: app-pg15-superuser
        key: password
```

**B. Upgrade in-place offline.** Nelle versioni recenti dell'operator (1.26+) basta cambiare `imageName` verso un'immagine con major superiore: l'operator esegue `pg_upgrade` in un job, con downtime del cluster per tutta la durata. Verificare nella documentazione della propria versione che la funzione sia disponibile e supportata.

```bash
# Verifica prima dell'upgrade dello stato e dell'immagine corrente
kubectl cnpg status app-pg15 -n prod

# Upgrade in-place: patch dell'immagine (solo se la propria versione dell'operator lo supporta)
kubectl patch cluster app-pg15 -n prod --type merge \
  -p '{"spec":{"imageName":"ghcr.io/cloudnative-pg/postgresql:17"}}'

# Segui il job di upgrade e lo stato del cluster
kubectl get pods -n prod -l cnpg.io/cluster=app-pg15 -w
```

!!! warning "Snapshot prima di tutto"
    Prima di un upgrade in-place, fare un backup completo (Barman/volume snapshot) e verificarne il restore. Un upgrade in-place fallito a metà su un PVC condiviso non è reversibile senza backup.

## Best Practices

- **Prova sempre** l'intera procedura su una copia di produzione e cronometra ogni fase; il tempo di rehearsal è il tuo SLA.
- Usa i **binari della versione target** per `pg_dump`, `pg_upgrade`, `vacuumdb`.
- Esegui `pg_upgrade --check` giorni prima, non il giorno dell'upgrade.
- Prepara la **configurazione** della nuova versione partendo dal file della nuova versione e riportando i soli parametri custom (non copiare il vecchio `postgresql.conf`).
- I **data checksums** rilevano la corruzione silenziosa dei blocchi su disco. Con `pg_upgrade` i due cluster devono avere la stessa impostazione: per abilitarli nel passaggio usare dump/restore o logical replication (`initdb --data-checksums` sul nuovo), oppure `pg_checksums --enable` sul vecchio cluster fermo prima dell'upgrade.
- Congela **deploy e migrazioni di schema** durante una migrazione logica.
- Monitora il lag, il numero di connessioni, `pg_stat_statements` e i tempi p95/p99 per 24–72 h dopo l'upgrade.
- **Anti-pattern**: upgrade e cambio di OS/glibc nello stesso passo senza REINDEX; omettere `ANALYZE`; spegnere il vecchio cluster il giorno stesso.

## Troubleshooting

### Scenario 1 — `pg_upgrade --check`: "Your installation contains tables declared WITH OIDS" / "contains the data type reg*"

**Sintomo**: `pg_upgrade` si ferma con `Checking for incompatible "...": fatal` e crea un file `tables_using_*.txt`.
**Causa**: oggetti non supportati dalla nuova major (`WITH OIDS` rimosso in PG 12, colonne `regproc`/`regclass` non migrabili).
**Soluzione**: leggere il file indicato e correggere nel vecchio cluster: `ALTER TABLE t SET WITHOUT OIDS;` oppure `ALTER TABLE t ALTER COLUMN c TYPE oid;`.

### Scenario 2 — `pg_upgrade`: "could not load library ... $libdir/xxx"

**Sintomo**: errore nella fase di restore dello schema, `ERROR: could not access file "$libdir/postgis-3"`.
**Causa**: il pacchetto dell'estensione per la **nuova** major non è installato.
**Soluzione**: installare il pacchetto (`apt install postgresql-17-postgis-3 postgresql-17-pgvector`), pulire il nuovo cluster (`rm -rf` della data dir e nuovo `initdb`) e rilanciare.

### Scenario 3 — "Your installation contains prepared transactions"

**Sintomo**: `--check` fallisce.
**Causa**: transazioni two-phase non committate (`pg_prepared_xacts`).
**Soluzione**: `COMMIT PREPARED 'gid';` o `ROLLBACK PREPARED 'gid';` per ogni riga, poi ripetere il check.

### Scenario 4 — Query lentissime subito dopo l'upgrade

**Sintomo**: CPU al 100%, seq scan al posto di index scan, query che passano da ms a secondi.
**Causa**: statistiche del planner assenti (non migrate da `pg_upgrade` fino a PG 17).
**Soluzione**: `vacuumdb --all --analyze-in-stages --jobs=8` (anche con l'app online); verifica con `SELECT relname, last_analyze, last_autoanalyze FROM pg_stat_user_tables ORDER BY 2 NULLS FIRST LIMIT 20;`.

### Scenario 5 — Logical replication: subscription ferma con "duplicate key value violates unique constraint" o "logical replication target relation ... is missing"

**Sintomo**: `pg_stat_subscription` mostra `latest_end_lsn` fermo; nei log del subscriber compare l'errore ripetuto.
**Causa**: una tabella è stata creata/modificata su blue dopo la creazione dello schema su green (DDL non replicato), oppure dati preesistenti su green.
**Soluzione**: applicare il DDL mancante su green, poi `ALTER SUBSCRIPTION upgrade_sub REFRESH PUBLICATION;`. Per saltare una transazione problematica (ultima risorsa): `ALTER SUBSCRIPTION upgrade_sub SKIP (lsn = '0/1234567');`.

### Scenario 6 — Dopo il cutover: "duplicate key value violates unique constraint ..._pkey" sugli INSERT

**Sintomo**: errori applicativi subito dopo lo spostamento del traffico.
**Causa**: le sequenze su green non sono state allineate (non replicate).
**Soluzione**: rieseguire il passo 4 dello script di cutover (`setval` per ogni sequenza, con margine) leggendo i valori dal vecchio cluster o da `MAX(id)` delle tabelle.

### Scenario 7 — Slot su blue che accumula WAL e riempie il disco

**Sintomo**: `pg_wal` cresce senza controllo durante la migrazione; `pg_replication_slots.active = f`.
**Causa**: la subscription è ferma o lenta; lo slot trattiene il WAL.
**Soluzione**: sistemare la subscription; se la migrazione è abbandonata, `SELECT pg_drop_replication_slot('upgrade_sub');`. Prevenzione: impostare `max_slot_wal_keep_size` e monitorare il lag.

## Relazioni

??? info "Replicazione PostgreSQL — Approfondimento"
    Streaming e logical replication, slot e Patroni: sono le fondamenta della strategia blue/green. Il caso base dell'upgrade a zero-downtime è già introdotto lì.

    **Approfondimento completo →** [Replicazione](replicazione.md)

??? info "Extensions — Approfondimento"
    PostGIS, pgvector e TimescaleDB sono i principali blocchi alla compatibilità tra major version.

    **Approfondimento completo →** [Extensions](extensions.md)

??? info "MVCC e Vacuum — Approfondimento"
    Spiega perché le statistiche e `ANALYZE`/`VACUUM` post-upgrade contano per le performance.

    **Approfondimento completo →** [MVCC e Vacuum](mvcc-vacuum.md)

??? info "DB su Kubernetes — Approfondimento"
    Operator CloudNativePG, storage e backup: contesto per l'upgrade su Kubernetes.

    **Approfondimento completo →** [DB su Kubernetes](../kubernetes-cloud/db-su-kubernetes.md)

## Riferimenti

- [pg_upgrade — documentazione ufficiale](https://www.postgresql.org/docs/current/pgupgrade.html)
- [Upgrading a PostgreSQL Cluster](https://www.postgresql.org/docs/current/upgrading.html)
- [Logical Replication — restrizioni](https://www.postgresql.org/docs/current/logical-replication-restrictions.html)
- [pg_createsubscriber](https://www.postgresql.org/docs/current/app-pgcreatesubscriber.html)
- [vacuumdb](https://www.postgresql.org/docs/current/app-vacuumdb.html)
- [AWS — Blue/Green Deployments per RDS e Aurora](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/blue-green-deployments.html)
- [CloudNativePG — PostgreSQL Upgrade](https://cloudnative-pg.io/documentation/current/postgres_upgrades/)
- [PostgreSQL Release Notes](https://www.postgresql.org/docs/release/)
