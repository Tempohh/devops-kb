---
title: "Docker Storage"
slug: storage
category: containers
tags: [docker, storage, volumes, bind-mounts, overlay2, storage-drivers, tmpfs, csi]
search_keywords: [docker volumes, docker bind mount, docker tmpfs, overlay2 storage driver, docker volume driver, docker persistent storage, docker storage performance, docker volume backup, named volumes docker, anonymous volumes docker, docker storage plugin]
parent: containers/docker/_index
related: [containers/docker/architettura-interna, containers/kubernetes/storage]
official_docs: https://docs.docker.com/engine/storage/
status: complete
difficulty: advanced
last_updated: 2026-02-25
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

```bash
# Crea un volume named
docker volume create \
    --driver local \
    --opt type=none \          # tipo filesystem
    --opt device=/mnt/data \   # path fisico (local driver)
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
docker volume prune                # elimina tutti i dangling volumes
```

---

## Bind Mounts — Development Workflow

I **bind mount** montano direttamente una directory dell'host nel container. Utili per lo sviluppo (hot reload) ma da evitare in produzione (accoppiamento con il filesystem host).

```bash
# Bind mount per development (hot reload)
docker run -d \
    --name dev-server \
    --mount type=bind,source=$(pwd)/src,target=/app/src,readonly=false \
    --mount type=bind,source=$(pwd)/config.yaml,target=/app/config.yaml,readonly=true \
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
    nginx:1.25

# Attenzione alle permission:
# I file del bind mount hanno i permessi del filesystem host.
# Se il container gira come UID 1001, il file host deve essere
# leggibile da UID 1001 (o usare :z/:Z per SELinux relabeling)
docker run -v $(pwd)/data:/data:z myapp    # SELinux: shared label
docker run -v $(pwd)/data:/data:Z myapp    # SELinux: private label
```

---

## tmpfs Mounts — Storage in Memoria

I **tmpfs** mount vivono solo in RAM, mai scritti su disco. Ideali per dati temporanei sensibili (token, certificati temporanei).

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

```bash
# Benchmark: confronta volume vs container filesystem
# Test scrittura sequenziale
docker run --rm \
    -v /tmp/vol-test:/data \                          # volume (ext4 diretto)
    ubuntu dd if=/dev/zero of=/data/test bs=1M count=1000 conv=fdatasync
# Tipico: ~500-1000 MB/s

docker run --rm ubuntu \
    dd if=/dev/zero of=/data/test bs=1M count=1000 conv=fdatasync
# Container RW layer: ~100-300 MB/s (overhead CoW)

# Conclusione: per I/O intensivo (DB, log), usare SEMPRE volumi
```

**Scegliere il giusto driver:**

| Driver | Filesystem host richiesto | Note |
|--------|--------------------------|------|
| `overlay2` | ext4, xfs (d_type=true) | **Raccomandato** — tutti i sistemi moderni |
| `btrfs` | btrfs | Snapshots nativi, buono per build |
| `zfs` | ZFS | Snapshots, compressione, storage avanzato |
| `fuse-overlayfs` | qualsiasi | Per rootless Docker su sistemi non supportati |
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

I **volume driver** (plugin) permettono di montare storage remoto (NFS, Ceph, AWS EBS, Azure File) come volumi Docker.

```bash
# NFS volume driver
docker volume create \
    --driver local \
    --opt type=nfs \
    --opt o=addr=nfs-server.internal,rw,nfsvers=4 \
    --opt device=:/exports/data \
    nfs-data

# Plugin REX-Ray per storage cloud
docker plugin install rexray/ebs \
    EBS_ACCESSKEY=xxx EBS_SECRETKEY=yyy EBS_REGION=eu-west-1

docker volume create \
    --driver rexray/ebs \
    --opt size=100 \
    --opt type=gp3 \
    ebs-volume

docker run -v ebs-volume:/data myapp

# Verificare i plugin installati
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
    driver_opts:                                   # NFS per HA
      type: nfs
      o: "addr=nfs.internal,rw,nfsvers=4"
      device: ":/mnt/postgres"
  redis-data:
  app-logs:
  postgres-backup:
    external: true                                 # creato fuori da compose
```

---

## Riferimenti

- [Docker Storage Overview](https://docs.docker.com/engine/storage/)
- [Volumes](https://docs.docker.com/engine/storage/volumes/)
- [Bind Mounts](https://docs.docker.com/engine/storage/bind-mounts/)
- [overlay2 Storage Driver](https://docs.docker.com/storage/storagedriver/overlayfs-driver/)
- [Volume Drivers](https://docs.docker.com/engine/extend/plugins_volume/)
