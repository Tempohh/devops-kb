---
title: "Container Registry"
slug: registry
category: containers
tags: [registry, harbor, ecr, oci, distribution, image-signing, cosign, proxy-cache, air-gap]
search_keywords: [container registry, OCI distribution spec, Harbor registry, AWS ECR, proxy cache registry, air-gap registry, image replication, registry authentication, cosign image signing, container image mirroring, pull-through cache, registry garbage collection]
parent: containers/_index
related: [containers/docker/dockerfile-avanzato, security/supply-chain/image-scanning, security/supply-chain/sbom-cosign]
official_docs: https://distribution.github.io/distribution/
status: complete
difficulty: advanced
last_updated: 2026-02-25
---

# Container Registry

## OCI Distribution Specification

La **OCI Distribution Specification** definisce il protocollo HTTP per pull/push di immagini container tra client e registry.

```
OCI Distribution — Operazioni Fondamentali

  docker pull registry.company.com/myapp:1.0.0

  1. GET /v2/  (check auth)
     → 401 Unauthorized + WWW-Authenticate: Bearer realm=...

  2. GET https://auth.registry.company.com/token?scope=repository:myapp:pull
     → 200 {"token": "eyJ..."}

  3. GET /v2/myapp/manifests/1.0.0
     Accept: application/vnd.oci.image.manifest.v1+json
     Authorization: Bearer eyJ...
     → 200 {manifest JSON}

  4. Per ogni layer nel manifest:
     GET /v2/myapp/blobs/sha256:<digest>
     → 200 (layer tar.gz)

  5. Verifica digest di ogni layer

  docker push registry.company.com/myapp:1.0.0

  1. Auth (come sopra, scope=push)
  2. Per ogni layer non presente nel registry:
     POST /v2/myapp/blobs/uploads/  → 202 con Location header
     PATCH <location> (body: layer content, chunked)
     PUT <location>?digest=sha256:<digest>  → 201
  3. PUT /v2/myapp/manifests/1.0.0
     Content-Type: application/vnd.oci.image.manifest.v1+json
     → 201
```

**Registry importanti nell'ecosistema:**

| Registry | Provider | Caratteristiche |
|----------|----------|-----------------|
| Harbor | CNCF / VMware | Self-hosted, proxy cache, Trivy integrato, RBAC, replication |
| ECR | AWS | Managed, integrato con IAM, scan con Inspector, lifecycle policies |
| GCR/GAR | Google | Managed, Artifact Registry è il successore |
| ACR | Azure | Managed, geo-replication, tasks per build |
| Quay | Red Hat | Self-hosted o managed, robot accounts, clair scanning |
| Docker Hub | Docker | Pubblico di default, rate limiting severo (pull: 200/6h) |
| GHCR | GitHub | Integrato con GitHub Actions, free per open source |

---

## Harbor — Enterprise Self-Hosted Registry

**Harbor** è il registry enterprise open-source CNCF con funzionalità avanzate per ambienti enterprise e air-gap.

Vedi [Harbor in Dettaglio](harbor.md) per la configurazione completa.

```
Harbor Feature Set

  Registry Core:
  ✓ OCI-compliant (images, Helm charts, WASM, OPA bundles)
  ✓ RBAC (users, robot accounts, groups via LDAP/OIDC)
  ✓ Multiple projects con access policies

  Security:
  ✓ Vulnerability scanning (Trivy integrato)
  ✓ Content Trust / Cosign image signing
  ✓ Policy: block pull di immagini con CVE critical
  ✓ Immutable tags

  Replication:
  ✓ Push/pull replication tra registry diversi
  ✓ Multi-cloud: Harbor ↔ ECR ↔ ACR ↔ GCR
  ✓ Scheduling replication jobs

  Proxy Cache:
  ✓ Pull-through cache per Docker Hub, Quay, GCR
  ✓ Riduce dipendenza da registri esterni
  ✓ Critico per air-gap e high availability

  Garbage Collection:
  ✓ Pulizia automatica di blobs non referenziati
  ✓ Tag retention policies
```

---

## ECR — AWS Elastic Container Registry

```bash
# Login a ECR
aws ecr get-login-password --region eu-west-1 | \
    docker login --username AWS --password-stdin \
    123456789.dkr.ecr.eu-west-1.amazonaws.com

# Crea repository
aws ecr create-repository \
    --repository-name myapp/api \
    --region eu-west-1 \
    --image-scanning-configuration scanOnPush=true \
    --encryption-configuration encryptionType=KMS,kmsKey=arn:aws:kms:eu-west-1:xxx \
    --tags Key=Project,Value=myapp

# Push immagine
docker tag myapp/api:1.0.0 123456789.dkr.ecr.eu-west-1.amazonaws.com/myapp/api:1.0.0
docker push 123456789.dkr.ecr.eu-west-1.amazonaws.com/myapp/api:1.0.0

# Lifecycle policy (mantieni solo ultime 30 immagini tagged)
aws ecr put-lifecycle-policy \
    --repository-name myapp/api \
    --lifecycle-policy-text file://lifecycle-policy.json

# lifecycle-policy.json:
# {
#   "rules": [
#     {
#       "rulePriority": 1,
#       "description": "Keep last 30 tagged images",
#       "selection": {
#         "tagStatus": "tagged",
#         "tagPrefixList": ["v"],
#         "countType": "imageCountMoreThan",
#         "countNumber": 30
#       },
#       "action": {"type": "expire"}
#     },
#     {
#       "rulePriority": 2,
#       "description": "Remove untagged after 7 days",
#       "selection": {
#         "tagStatus": "untagged",
#         "countType": "sinceImagePushed",
#         "countUnit": "days",
#         "countNumber": 7
#       },
#       "action": {"type": "expire"}
#     }
#   ]
# }

# ECR Pull Through Cache (proxy per Docker Hub)
aws ecr create-pull-through-cache-rule \
    --ecr-repository-prefix docker-hub \
    --upstream-registry-url registry-1.docker.io \
    --credential-arn arn:aws:secretsmanager:eu-west-1:xxx:secret:dockerhub-creds

# Poi: docker pull 123456789.dkr.ecr.eu-west-1.amazonaws.com/docker-hub/nginx:latest
# → ECR scarica da Docker Hub e cachea localmente
```

---

## Registry Mirror in Kubernetes

```yaml
# containerd mirror configuration (tutti i nodi)
# /etc/containerd/config.toml

[plugins."io.containerd.grpc.v1.cri".registry]
  [plugins."io.containerd.grpc.v1.cri".registry.mirrors]
    [plugins."io.containerd.grpc.v1.cri".registry.mirrors."docker.io"]
      endpoint = [
        "https://registry.company.com/docker-hub",  # proxy cache
        "https://registry-1.docker.io"              # fallback
      ]
    [plugins."io.containerd.grpc.v1.cri".registry.mirrors."quay.io"]
      endpoint = ["https://registry.company.com/quay-io"]
    [plugins."io.containerd.grpc.v1.cri".registry.mirrors."registry.k8s.io"]
      endpoint = ["https://registry.company.com/k8s"]
  [plugins."io.containerd.grpc.v1.cri".registry.configs]
    [plugins."io.containerd.grpc.v1.cri".registry.configs."registry.company.com".tls]
      ca_file   = "/etc/ssl/certs/company-ca.crt"
    [plugins."io.containerd.grpc.v1.cri".registry.configs."registry.company.com".auth]
      username = "k8s-puller"
      password = "token-xxx"
```

---

## Riferimenti

- [OCI Distribution Spec](https://github.com/opencontainers/distribution-spec)
- [Harbor](https://goharbor.io/docs/)
- [AWS ECR](https://docs.aws.amazon.com/ecr/)
- [containerd registry config](https://github.com/containerd/containerd/blob/main/docs/cri/config.md#registry-configuration)
