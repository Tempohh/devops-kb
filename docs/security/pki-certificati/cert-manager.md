---
title: "cert-manager — Automazione Certificati su Kubernetes"
slug: cert-manager
category: security
tags: [cert-manager, kubernetes, let-encrypt, tls, certificati, automazione]
search_keywords: [cert-manager kubernetes, let's encrypt kubernetes, tls automatic kubernetes, cert-manager issuer, cert-manager clusterissuer, acme challenge, http01 challenge, dns01 challenge, cert-manager vault pki, cert-manager internal ca, cert-manager certificate crd, cert-manager certificaterequest, cert-manager order challenge, wildcard certificate kubernetes, cert-manager prometheus metrics, cert-manager trust bundle, cert-manager webhook, cert-manager approver policy, cert-manager egress, cert-manager renewal, certficiate expiry monitoring, cert-manager istio, cert-manager annotations ingress, tls in transit kubernetes]
parent: security/pki-certificati/_index
related: [security/pki-certificati/pki-interna, security/secret-management/vault, networking/kubernetes/ingress]
official_docs: https://cert-manager.io/docs/
status: complete
difficulty: intermediate
last_updated: 2026-02-24
---

# cert-manager — Automazione Certificati su Kubernetes

## Panoramica

**cert-manager** è il controller Kubernetes standard per l'automazione del ciclo di vita dei certificati TLS. Risolve il problema operativo più comune con i certificati: le persone dimenticano di rinnovarli e il sito va down.

cert-manager monitora continuamente i certificati, li rinnova automaticamente prima della scadenza (default: 30 giorni prima), e archivia il risultato in Kubernetes Secrets. Supporta molteplici fonti di certificati: Let's Encrypt, HashiCorp Vault, CA interna, AWS PCA.

```
cert-manager controller
      │
      │ osserva Certificate CRD
      │
      ├── Certificate "orders-tls" → scade in 25 giorni → rinnova
      │         │
      │         │ crea CertificateRequest
      │         ▼
      │    Issuer/ClusterIssuer ──► Let's Encrypt / Vault / CA interna
      │         │
      │         │ certificato emesso
      │         ▼
      │    Kubernetes Secret "orders-tls-secret"
      │         │
      │         └── montato in Ingress / pod
      │
      └── Certificate "payment-tls" → scade in 80 giorni → nessuna azione
```

---

## Installazione

```bash
# Helm (raccomandato)
helm repo add jetstack https://charts.jetstack.io
helm repo update

helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --set installCRDs=true \
  --set prometheus.enabled=true \  # Metriche Prometheus
  --set webhook.timeoutSeconds=10
```

---

## Issuer e ClusterIssuer

Un **Issuer** è namespace-scoped; un **ClusterIssuer** è cluster-wide. La scelta dipende dal caso: ClusterIssuer per Let's Encrypt (condiviso tra tutti i namespace), Issuer per CA interna namespace-specifica.

### Let's Encrypt

```yaml
# ClusterIssuer per Let's Encrypt (produzione)
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: security@example.com
    privateKeySecretRef:
      name: letsencrypt-prod-account-key   # Chiave account ACME (auto-generata)
    solvers:
    # Solver HTTP-01: Let's Encrypt chiede un file HTTP su porta 80
    # Funziona se il dominio è raggiungibile da Internet
    - http01:
        ingress:
          ingressClassName: nginx

    # Solver DNS-01: Let's Encrypt chiede un record TXT nel DNS
    # Unico modo per wildcard e domini non raggiungibili da Internet
    - dns01:
        route53:
          region: us-east-1
          role: arn:aws:iam::123456789:role/cert-manager-route53
      selector:
        dnsZones:
        - "*.example.com"   # Usa DNS-01 solo per wildcard

---
# Staging per test (nessun rate limiting, ma non trusted dai browser)
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-staging
spec:
  acme:
    server: https://acme-staging-v02.api.letsencrypt.org/directory
    email: security@example.com
    privateKeySecretRef:
      name: letsencrypt-staging-account-key
    solvers:
    - http01:
        ingress:
          ingressClassName: nginx
```

### HashiCorp Vault Issuer

```yaml
# Issuer che usa Vault PKI Engine come backend
apiVersion: cert-manager.io/v1
kind: Issuer
metadata:
  name: vault-pki-issuer
  namespace: production
spec:
  vault:
    server: https://vault.vault.svc.cluster.local:8200
    path: pki_int/sign/services-role
    caBundle: <base64 del Vault CA certificate>
    auth:
      kubernetes:
        mountPath: /v1/auth/kubernetes
        role: cert-manager
        secretRef:
          name: cert-manager-vault-token
          key: token
```

### CA Interna (Self-Signed o Con Root CA)

```yaml
# Issuer con CA interna (certificato+chiave come Kubernetes Secret)
apiVersion: cert-manager.io/v1
kind: Issuer
metadata:
  name: internal-ca
  namespace: production
spec:
  ca:
    secretName: services-ca-key-pair   # Secret contenente tls.crt e tls.key della CA

---
# Crea il secret con la CA interna (da CFSSL/step-ca)
kubectl create secret tls services-ca-key-pair \
  --cert=services-ca.pem \
  --key=services-ca-key.pem \
  -n production
```

---

## Certificate CRD

Il CRD `Certificate` descrive il certificato desiderato — cert-manager lo mantiene aggiornato automaticamente:

```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: orders-service-cert
  namespace: production
spec:
  # Il Secret dove cert-manager archivia il certificato emesso
  secretName: orders-service-tls

  # Rinnova 30 giorni prima della scadenza
  renewBefore: 720h    # 30 giorni

  # Durata del certificato
  duration: 2160h       # 90 giorni (Let's Encrypt max)
  # Per certificati interni a breve durata:
  # duration: 24h
  # renewBefore: 8h

  # Subject
  commonName: orders.production.svc.cluster.local
  dnsNames:
  - orders.production.svc.cluster.local
  - orders-service                           # Short name nel cluster
  - orders-service.production               # FQDN parziale
  uriSANs:
  - "spiffe://example.com/ns/production/sa/orders-service-account"  # SPIFFE per mTLS

  privateKey:
    algorithm: ECDSA
    size: 256
    rotationPolicy: Always    # Genera sempre una nuova chiave al rinnovo

  issuerRef:
    name: vault-pki-issuer
    kind: Issuer
```

```bash
# Monitora lo stato del certificato
kubectl describe certificate orders-service-cert -n production

# Forza rinnovo immediato (utile per test o dopo compromissione)
kubectl cert-manager renew orders-service-cert -n production
```

---

## Annotazioni Ingress — Il Modo Più Semplice

Per i certificati degli Ingress pubblici, cert-manager supporta annotazioni dirette — non serve creare manualmente il CRD Certificate:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api-ingress
  namespace: production
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"    # Quale issuer usare
    cert-manager.io/duration: "2160h"
    cert-manager.io/renew-before: "720h"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - api.example.com
    secretName: api-example-com-tls    # cert-manager crea questo Secret automaticamente
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: api-service
            port:
              number: 80
```

---

## Trust Manager — Distribuzione del CA Bundle

**cert-manager Trust Manager** è il componente che distribuisce i CA bundle (per la validazione dei certificati interni) in tutti i namespace:

```yaml
# Installa Trust Manager
helm install trust-manager jetstack/trust-manager \
  -n cert-manager \
  --set app.trust.namespace=cert-manager

---
# Bundle CRD: distribuisce il CA bundle in tutti i namespace
apiVersion: trust.cert-manager.io/v1alpha1
kind: Bundle
metadata:
  name: internal-ca-bundle
spec:
  sources:
  - configMap:
      name: internal-ca-cert         # ConfigMap con il root CA cert
      key: root-ca.pem
  - inLine: |
      -----BEGIN CERTIFICATE-----
      ...
      -----END CERTIFICATE-----     # CA aggiuntiva inline
  target:
    configMap:
      key: ca-bundle.crt
    namespaceSelector:
      matchLabels:
        trust-bundle: "true"    # Solo nei namespace con questo label
```

---

## Monitoring Certificati

```yaml
# Alerte per certificati in scadenza (Prometheus + cert-manager metrics)
groups:
- name: cert-manager
  rules:
  - alert: CertificateExpiringIn30Days
    expr: |
      certmanager_certificate_expiration_timestamp_seconds - time() < 30 * 24 * 3600
    for: 1h
    labels:
      severity: warning
    annotations:
      summary: "Certificato {{ $labels.name }} in namespace {{ $labels.namespace }} scade in meno di 30 giorni"

  - alert: CertificateExpiringIn7Days
    expr: |
      certmanager_certificate_expiration_timestamp_seconds - time() < 7 * 24 * 3600
    for: 1h
    labels:
      severity: critical
    annotations:
      summary: "Certificato {{ $labels.name }} scade in meno di 7 giorni — rinnovo fallito?"

  - alert: CertificateNotReady
    expr: certmanager_certificate_ready_status{condition="False"} == 1
    for: 10m
    annotations:
      summary: "Certificato {{ $labels.name }} non in stato Ready da 10 minuti"
```

```bash
# Verifica manuale di tutti i certificati del cluster
kubectl get certificates -A

# Stato dettagliato
kubectl cert-manager status certificate orders-service-cert -n production

# Log del controller per troubleshooting
kubectl logs -n cert-manager -l app=cert-manager --follow
```

---

## DNS-01 Challenge con Route53 (per Wildcard e Interno)

Il DNS-01 challenge è l'unico modo per ottenere certificati wildcard (`*.example.com`) e per domini interni non raggiungibili da Internet.

```yaml
# IAM Policy per cert-manager (AWS IRSA)
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "route53:GetChange",
      "route53:ChangeResourceRecordSets",
      "route53:ListResourceRecordSets"
    ],
    "Resource": [
      "arn:aws:route53:::change/*",
      "arn:aws:route53:::hostedzone/ZONE_ID"
    ]
  }, {
    "Effect": "Allow",
    "Action": ["route53:ListHostedZonesByName"],
    "Resource": "*"
  }]
}
```

```yaml
# ClusterIssuer con DNS-01 via Route53 + IRSA
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-dns
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: security@example.com
    privateKeySecretRef:
      name: letsencrypt-dns-key
    solvers:
    - dns01:
        route53:
          region: us-east-1
          # Usa IRSA: il SA cert-manager ha il ruolo IAM con la policy sopra
          # nessuna access key hardcodata

---
# Certificate wildcard
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: wildcard-example-com
  namespace: production
spec:
  secretName: wildcard-example-com-tls
  dnsNames:
  - "*.example.com"
  - "example.com"
  issuerRef:
    name: letsencrypt-dns
    kind: ClusterIssuer
```

---

## Best Practices

- **staging prima di prod**: testare sempre con `letsencrypt-staging` prima di passare a prod — Let's Encrypt ha rate limit (5 cert falliti per dominio per ora)
- **`renewBefore` = 1/3 della durata**: per cert da 90d, rinnova a 30d; per cert da 24h, rinnova a 8h. Dà tempo per debug se il rinnovo fallisce
- **`rotationPolicy: Always`**: genera sempre una nuova chiave privata ad ogni rinnovo — evita che una chiave compromessa rimanga in uso a lungo
- **Monitoring obbligatorio**: le alert Prometheus sui certificati in scadenza sono l'ultima rete di sicurezza se il rinnovo automatico fallisce silenziosamente
- **IRSA/Workload Identity per DNS-01**: mai hardcodare credenziali AWS/GCP nel ClusterIssuer — usare IRSA (AWS), Workload Identity (GCP) o AzureAD Workload Identity

## Riferimenti

- [cert-manager Documentation](https://cert-manager.io/docs/)
- [cert-manager Trust Manager](https://cert-manager.io/docs/projects/trust-manager/)
- [Let's Encrypt Rate Limits](https://letsencrypt.org/docs/rate-limits/)
- [cert-manager + HashiCorp Vault](https://cert-manager.io/docs/configuration/vault/)
