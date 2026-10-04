---
title: "Docker Storage"
slug: storage
category: containers
tags: [docker, storage, volumes, bind-mounts, overlay2, storage-drivers, tmpfs, csi]
search_keywords: [docker volumes, docker bind mount, docker tmpfs, overlay2 storage driver, docker volume driver, docker persistent storage, docker storage performance, docker volume backup, named volumes docker, anonymous volumes docker, docker storage plugin]
parent: containers/docker/_index
related: [containers/docker/architettura-interna, containers/kubernetes/storage]
official_docs: https://docs.docker.com/engine/storage/
status: needs-review
difficulty: advanced
last_updated: 2026-10-04
last_verified: 2026-10-04
---

# Docker Storage

## Le Tre Opzioni di Storage

```
Docker Storage — Dove Vivono i Dati

  +------------ Container Filesystem (overlay2) ---------------+
  |  Layer RW del container — PERSO quando il container muore   |
  |  /app/data  ← scritture CoW dall'image layer               |
  +------------------------------------------------------------+

  +--- Volume ---+  +--- Bind Mount ---+  +--- tmpfs ---+
  | /var/lib/    |  | /host/path →     |  | RAM only    |
  | docker/      |  | /container/path  |  | mai su disco|
  | volumes/vol  |  |                  |  |             |
  | Managed by   |  | Managed by user  |  | Ephemeral   |
  | Docker       |  | (filesystem host)|  | secrets     |
  +--------------+  +------------------+  +-------------+
  | Persiste     |  | Persiste         |  | Non persiste|
  | Portabile    |  | Host-dipendente  |  | Velocissimo |
  | Backup tool  |  | Dev workflow     |  |             |
  +--------------+  +------------------+  +-------------+
```

---

## Named Volumes — Lo Standard per la Persistenza

I **named volumes** sono gestiti interamente da Docker e sono il metodo raccomandato per i dati persistenti in produzione.

!!! note "Volume vs bind mount: il perché"
    Un named volume vive in `/var/lib/docker/volumes/` ed è gestito dal daemon: non dipende dalla struttura di directory dell'host, eredita ownership/contenuto dalla directory dell'immagine alla **prima** creazione (copy-up) e funziona uguale su Linux, Windows e Docker Desktop (dove i bind mount attraversano la VM e sono più lenti). Con `--mount` un source bind inesistente è un errore; con `-v` Docker lo crea (come root) — fonte comune di permission problem.

```bash
# Crea un volume named che punta a una directory esistente dell'host
# (type=none + o=bind: il local driver fa un bind mount di device)
docker volume create \
    --driver local \
    --opt type=none \
    --opt device=/mnt/data \
    --opt o=bind \
    app-data

# Usa il volume nel container
docker run -d \
    --name postgres \
    --volume postgres-data:/var/lib/postgresql/data \
    --volume postgres-config:/etc/postgresql:ro \
    postgres:16

# Ispezione
docker volume inspect postgres-data
# {
#   "Driver": "local",
#   "Mountpoint": "/var/lib/docker/volumes/postgres-data/_data",
#   "Name": "postgres-data",
#   "Scope": "local"
# }

# Backup di un volume (esportazione tar)
docker run --rm \
    -v postgres-data:/data:ro \
    -v $(pwd)/backup:/backup \
    alpine \
    tar czf /backup/postgres-data-$(date +%Y%m%d).tar.gz -C /data .

# Restore
docker run --rm \
    -v postgres-data:/data \
    -v $(pwd)/backup:/backup:ro \
    alpine \
    tar xzf /backup/postgres-data-20260225.tar.gz -C /data

# Lista e cleanup volumi
docker volume ls
docker volume ls -f dangling=true  # volumi non usati da container
docker volume prune                # elimina i volumi ANONIMI non usati (Docker 23+)
docker volume prune -a             # elimina anche i named volume non usati — DATI PERSI
```

!!! warning "Cambio di comportamento di `prune` (Docker Engine 23+)"
    Dalla 23.0 `docker volume prune` (e `docker system prune --volumes`) rimuove solo i volumi **anonimi**. I named volume non usati richiedono `-a`/`--all`. Su host con engine precedenti, `prune` cancellava anche i named volume non collegati a un container: verificare la versione prima di fidarsi di vecchi runbook.

---

## Bind Mounts — Development Workflow

I **bind mount** montano direttamente una directory dell'host nel container. Utili per lo sviluppo (hot reload) ma da evitare in produzione (accoppiamento con il filesystem host).

```bash
# Bind mount per development (hot reload)
docker run -d \
    --name dev-server \
    --mount type=bind,source="$(pwd)"/src,target=/app/src \
    --mount type=bind,source="$(pwd)"/config.yaml,target=/app/config.yaml,readonly \
    -p 8080:8080 \
    myapp:dev

# Sintassi -v equivalente (più breve ma meno esplicita)
docker run -d \
    -v $(pwd)/src:/app/src \
    -v $(pwd)/config.yaml:/app/config.yaml:ro \
    myapp:dev

# Pattern: override file di config in produzione
docker run -d \
    --name nginx \
    -v /etc/nginx/sites-available/:/etc/nginx/sites-available/:ro \
    -v /var/log/nginx/:/var/log/nginx/ \
    nginx:stable

# Attenzione alle permission:
# I file del bind mount hanno i permessi del filesystem host.
# Se il container gira come UID 1001, il file host deve essere
# leggibile da UID 1001 (o usare :z/:Z per SELinux relabeling)
docker run -v $(pwd)/data:/data:z myapp    # SELinux: shared label
docker run -v $(pwd)/data:/data:Z myapp    # SELinux: private label
```

---

## tmpfs Mounts — Storage in Memoria

I **tmpfs** mount vivono in RAM (page cache del kernel) e non toccano il filesystem del container. Ideali per dati temporanei sensibili (token, certificati temporanei). Nota: se l'host ha swap, le pagine tmpfs possono finire su disco; per dati davvero sensibili usare swap cifrato o disabilitato. tmpfs è solo Linux e conta nel limite di memoria del cgroup del container.

```bash
# tmpfs mount
docker run -d \
    --mount type=tmpfs,target=/tmp,tmpfs-size=128m,tmpfs-mode=1777 \
    --mount type=tmpfs,target=/run/secrets,tmpfs-size=10m \
    myapp

# Dimensione limitata (evita OOM se un processo scrive troppo)
# mode=1777 = sticky bit per tmp (come /tmp di Linux)

# Caso d'uso: sessioni applicazione in memoria
docker run -d \
    -e SESSION_DIR=/run/sessions \
    --mount type=tmpfs,target=/run/sessions,tmpfs-size=256m \
    web-app

# Dati in /run/sessions:
# ✓ Sub-millisecondo per lettura/scrittura
# ✓ Mai persistiti su disco (sicurezza)
# ✗ Persi se il container si riavvia
```

---

## Storage Drivers — overlay2 in Profondità

Lo **storage driver** gestisce i layer dell'immagine e il layer RW del container. `overlay2` è il driver raccomandato su Linux moderno.

```
overlay2 — Struttura sul Disco

  /var/lib/docker/overlay2/
  ├── <layer-sha256-1>/
  │   ├── diff/          ← contenuto del layer (tar estratto)
  │   ├── link           ← ID breve del layer (symlink ottimizzazione)
  │   └── lower          ← lista dei layer inferiori (lower:lower:lower)
  ├── <layer-sha256-2>/
  │   ├── diff/
  │   ├── link
  │   ├── lower
  │   └── work/          ← directory di lavoro overlay (solo layer superiori)
  └── <container-rw-layer>/
      ├── diff/          ← scritture del container (upper layer)
      ├── work/          ← overlay working dir (richiesto dal kernel)
      ├── lower          ← punta a tutti i layer dell'immagine
      └── merged/        ← mount point (vista unificata al container)

  Mount overlay2 effettivo (kernel):
  mount -t overlay overlay \
      -o lowerdir=/l/AAAA:/l/BBBB:/l/CCCC,  \
         upperdir=/var/lib/docker/overlay2/<rw>/diff, \
         workdir=/var/lib/docker/overlay2/<rw>/work \
      /var/lib/docker/overlay2/<rw>/merged
```

**Performance overlay2:**

overlay2 opera a livello di **file**: alla prima scrittura su un file presente in un layer inferiore esegue un *copy-up* dell'intero file nel layer RW (costoso per file grandi, es. un DB nell'immagine). La scrittura di file nuovi o già copiati ha overhead basso; restano però il costo dello stacking dei lookup su molti layer e l'assenza di un filesystem dedicato (stesso disco dei layer, nessun tuning per DB).

```bash
# Benchmark indicativo (i numeri dipendono da disco e filesystem: misurare sul proprio host)
# Volume
docker run --rm -v bench-vol:/data ubuntu \
    dd if=/dev/zero of=/data/test bs=1M count=1000 conv=fdatasync

# Layer RW del container
docker run --rm ubuntu \
    dd if=/dev/zero of=/test bs=1M count=1000 conv=fdatasync
```

Regola pratica: per I/O intensivo e dati persistenti (DB, log) usare volumi — non tanto per il throughput sequenziale quanto per persistenza, copy-up evitato e possibilità di montare un disco dedicato.

!!! note "containerd image store (Docker Engine 29+)"
    Le installazioni nuove di Docker Engine 29 usano di default il **containerd image store** (snapshotter `overlayfs`) al posto del classico graph driver `overlay2`; i layer stanno in `/var/lib/containerd` e `docker info` mostra `driver-type: io.containerd.snapshotter.v1`. Le installazioni aggiornate mantengono il driver precedente. I concetti (union FS, copy-up, volumi) restano identici, ma i path e i comandi di ispezione di questa sezione valgono per il graph driver `overlay2`. <!-- REVIEW: verificare default e versione esatta (Engine 29) su docs.docker.com/engine/storage/containerd/ -->


**Scegliere il giusto driver:**

| Driver | Filesystem host richiesto | Note |
|--------|--------------------------|------|
| `overlay2` | ext4, xfs (d_type=true) | **Raccomandato** — tutti i sistemi moderni |
| `btrfs` | btrfs | Snapshots nativi, buono per build |
| `zfs` | ZFS | Snapshots, compressione, storage avanzato |
| `fuse-overlayfs` | qualsiasi | Fallback per rootless Docker su kernel < 5.11 (con kernel ≥ 5.11 il rootless usa `overlay2` nativo) |
| `vfs` | qualsiasi | Nessuna condivisione layer, lento — solo testing |

```bash
# Verifica il driver in uso
docker info | grep "Storage Driver"
# Storage Driver: overlay2

# Verifica che d_type sia true (richiesto per overlay2 su XFS)
xfs_info /var/lib/docker | grep "ftype"
# ftype=1 ← corretto
# ftype=0 ← overlay2 NON funzionerà, usare vfs o ricreare il filesystem

# Configurazione in /etc/docker/daemon.json
# {
#   "storage-driver": "overlay2",
#   "storage-opts": [
#     "overlay2.size=20G"          ← quota per container (richiede projectquota su XFS)
#   ]
# }
```

---

## Volume Drivers — Storage Remoto e Cloud

I **volume driver** permettono di montare storage remoto (NFS, Ceph, cloud block/file storage) come volumi Docker. Il driver `local` supporta NFS/CIFS direttamente; per il resto servono plugin di terze parti.

!!! warning "Ecosistema plugin in gran parte abbandonato"
    Il plugin REX-Ray (usato in vecchi esempi per EBS) non è più mantenuto. I plugin Docker managed sono un'API legacy: su cloud, per storage dinamico si usa oggi Kubernetes + CSI (vedi [Kubernetes Storage](../kubernetes/storage.md)); su Docker standalone, preferire NFS via driver `local` o i volume driver ufficiali del provider (es. Azure File, Cloud Stor) dopo aver verificato che siano ancora supportati.

```bash
# NFS volume (driver local)
docker volume create \
    --driver local \
    --opt type=nfs \
    --opt o=addr=nfs-server.internal,rw,nfsvers=4 \
    --opt device=:/exports/data \
    nfs-data

docker run -v nfs-data:/data myapp

# Verificare i plugin installati (volume driver di terze parti)
docker plugin ls
```

---

## Docker Compose Storage Patterns

```yaml
# docker-compose.yml — pattern storage produzione
services:
  postgres:
    image: postgres:16-alpine
    volumes:
      - postgres-data:/var/lib/postgresql/data     # named volume (persistente)
      - ./config/postgresql.conf:/etc/postgresql/postgresql.conf:ro  # bind mount config
      - postgres-backup:/backup                    # backup volume
    tmpfs:
      - /tmp                                       # tmp in RAM

  redis:
    image: redis:7-alpine
    volumes:
      - redis-data:/data
    command: redis-server --appendonly yes --appendfsync everysec

  app:
    build: .
    volumes:
      - app-logs:/app/logs                         # log separati dal container
      - /run/secrets/api-key:/run/secrets/api-key:ro  # secret via bind mount
    tmpfs:
      - /tmp:size=128m                             # tmpfs con dimensione limitata

volumes:
  postgres-data:
    driver: local
    driver_opts:                                   # NFS: storage condiviso (attenzione: PostgreSQL su NFS è sconsigliato, fsync/locking inaffidabili; preferire disco locale/block storage)
      type: nfs
      o: "addr=nfs.internal,rw,nfsvers=4"
      device: ":/mnt/postgres"
  redis-data:
  app-logs:
  postgres-backup:
    external: true                                 # creato fuori da compose
```

---

## Troubleshooting

### Scenario 1 — Volume non persiste i dati tra riavvii

**Sintomo:** I dati scritti nel container scompaiono dopo un `docker rm` / ricreazione del container (con `docker stop`/`start` il layer RW sopravvive; si perde solo con `rm`, `compose down` o `up --force-recreate`).

**Causa:** Il container usa il layer RW di overlay2 invece di un named volume. Oppure il path montato nel container non corrisponde a dove l'applicazione scrive i dati.

**Soluzione:** Verificare che il volume sia correttamente dichiarato e montato sul path giusto.

```bash
# Verifica i mount attivi del container
docker inspect <container> --format '{{ json .Mounts }}' | jq .

# Controlla dove l'applicazione scrive realmente
docker exec <container> df -h
docker exec <container> ls -la /var/lib/app/data  # path specifico dell'app

# Se il volume è dichiarato ma non montato correttamente, ricreare il container
docker stop <container> && docker rm <container>
docker run -d --name <container> -v my-data:/var/lib/app/data myapp:latest

# Verifica che il volume contenga i dati
docker run --rm -v my-data:/data alpine ls -la /data
```

---

### Scenario 2 — Permission denied accedendo ai file di un bind mount

**Sintomo:** Il container produce errori `Permission denied` su file o directory montati via bind mount.

**Causa:** L'UID/GID del processo nel container non corrisponde al proprietario del file sull'host. Comune quando il container gira come utente non-root.

**Soluzione:** Allineare i permessi host o usare `--user` per eseguire il container con l'UID host.

```bash
# Verifica l'UID del processo nel container
docker exec <container> id
docker exec <container> ps aux

# Verifica il proprietario del file sull'host
ls -lan /host/path/data  # mostra UID numerici

# Opzione 1: cambia il proprietario del file sull'host
sudo chown -R 1001:1001 /host/path/data

# Opzione 2: esegui il container con l'UID dell'utente host
docker run --user $(id -u):$(id -g) -v $(pwd)/data:/app/data myapp

# Opzione 3: SELinux — aggiungere :z (shared) o :Z (private)
docker run -v $(pwd)/data:/app/data:z myapp
```

---

### Scenario 3 — Disco esaurito in /var/lib/docker (overlay2 che cresce)

**Sintomo:** L'host esaurisce lo spazio disco. `df -h` mostra `/var/lib/docker` molto grande. `docker system df` mostra immagini o container che occupano molto spazio.

**Causa:** Accumulo di immagini non usate, layer dangling, container fermati non rimossi, o volumi orfani.

**Soluzione:** Analizzare l'uso disco e fare pruning selettivo.

```bash
# Analisi spazio Docker
docker system df
docker system df -v  # dettaglio per immagine/container/volume

# Pulizia selettiva
docker container prune     # rimuove container fermati
docker image prune         # rimuove immagini dangling (senza tag)
docker image prune -a      # rimuove TUTTE le immagini non usate da container attivi
docker volume prune        # rimuove volumi anonimi non usati (Docker 23+; -a include i named)
docker builder prune       # rimuove build cache

# Pulizia totale (attenzione: rimuove tutto il non usato; --volumes = solo anonimi dalla 23+, aggiungere -a per i named)
docker system prune --volumes

# Se il problema è un container che scrive molto nel RW layer (log, tmp)
docker exec <container> du -sh /* 2>/dev/null | sort -rh | head -20
# Considerare di spostare il path incriminato su un volume
```

---

### Scenario 4 — overlay2 non funziona su XFS (d_type error)

**Sintomo:** Docker non parte o lancia errori come `layer does not exist` o `failed to create overlay mount`. In `journalctl -u docker` compare un warning su `d_type`.

**Causa:** Il filesystem XFS è stato formattato con `ftype=0`, che disabilita i directory entry type necessari a overlay2.

**Soluzione:** Verificare `ftype` e, se necessario, ricreare il filesystem o usare un driver alternativo.

```bash
# Verifica ftype del filesystem che ospita /var/lib/docker
xfs_info /var/lib/docker | grep ftype
# ftype=1 → OK per overlay2
# ftype=0 → overlay2 non supportato

# Verifica il driver attuale
docker info | grep -E "Storage Driver|Backing Filesystem"

# Soluzione A: ricrea il filesystem con ftype=1 (richiede backup e downtime)
# mkfs.xfs -n ftype=1 /dev/sdX

# Soluzione B (dev/test only): driver vfs (lento, nessuna condivisione layer)
# Attenzione: cambiare driver rende invisibili immagini e container esistenti
# (restano in /var/lib/docker/<driver>) — esportare con docker save prima.
sudo tee /etc/docker/daemon.json > /dev/null <<'EOF'
{
  "storage-driver": "vfs"
}
EOF
sudo systemctl restart docker
```

---

## Riferimenti

- [Docker Storage Overview](https://docs.docker.com/engine/storage/)
- [Volumes](https://docs.docker.com/engine/storage/volumes/)
- [Bind Mounts](https://docs.docker.com/engine/storage/bind-mounts/)
- [overlay2 Storage Driver](https://docs.docker.com/storage/storagedriver/overlayfs-driver/)
- [Volume Drivers](https://docs.docker.com/engine/extend/plugins_volume/)
