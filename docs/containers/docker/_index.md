---
title: "Docker"
slug: docker
category: containers
tags: [docker, container, oci, runtime, image, dockerfile, compose]
search_keywords: [docker overview, docker engine, docker daemon, container runtime, OCI spec, docker image, docker compose, docker swarm, moby project, containerd docker]
parent: containers/_index
related: [containers/container-runtime/_index, containers/kubernetes/_index, containers/registry/_index]
official_docs: https://docs.docker.com/
status: complete
difficulty: intermediate
last_updated: 2026-02-25
---

# Docker

Docker è la piattaforma che ha reso i container accessibili agli sviluppatori. Comprendere Docker in profondità significa capire i meccanismi del kernel Linux su cui si basa.

## Sottosezioni

<div class="grid cards" markdown>

-   **Architettura Interna**

    Namespaces, cgroups, UnionFS, OCI spec, containerd integration.

    → [Architettura Interna](architettura-interna.md)

-   **Dockerfile Avanzato**

    Multi-stage builds, BuildKit, layer caching, distroless, best practices.

    → [Dockerfile Avanzato](dockerfile-avanzato.md)

-   **Networking**

    Bridge, host, overlay, macvlan, DNS, iptables rules, troubleshooting.

    → [Networking](networking.md)

-   **Storage**

    Volumes, bind mounts, tmpfs, storage drivers (overlay2), volume plugins.

    → [Storage](storage.md)

-   **Docker Compose**

    Dev e production patterns, health checks, depends_on, secrets, networks.

    → [Compose](compose.md)

-   **Sicurezza**

    Rootless Docker, capabilities, seccomp, AppArmor, namespace escaping, supply chain.

    → [Sicurezza](sicurezza.md)

</div>
