---
title: "Kubernetes Secrets — Native e Avanzati"
slug: kubernetes-secrets
category: security
tags: [kubernetes, secrets, sealed-secrets, external-secrets-operator, encryption-at-rest]
search_keywords: [kubernetes secrets, kubernetes secret base64, kubernetes encrypt secrets at rest, sealed secrets bitnami, external secrets operator eso, aws secrets manager kubernetes, azure keyvault kubernetes, gcp secret manager kubernetes, secret store csi driver, kubernetes secret best practices, secret rotation kubernetes, kubernetes secret encryption provider, vault agent injector vs eso, kubernetes secret gitops, sealed secrets vs eso, bitnami sealed secrets, reflector kubernetes, reloader kubernetes secret, kubernetes imagepullsecret, kubernetes tls secret, kubernetes opaque secret, kubernetes service account token]
parent: security/secret-management/_index
related: [security/secret-management/vault, security/supply-chain/admission-control, databases/postgresql/connection-pooling]
official_docs: https://kubernetes.io/docs/concepts/configuration/secret/
status: complete
difficulty: intermediate
last_updated: 2026-03-29
---

# Kubernetes Secrets — Native e Avanzati

## Panoramica

I **Kubernetes Secrets** sono l'oggetto nativo per archiviare informazioni sensibili (password, token, certificati) in Kubernetes. La comprensione delle loro limitazioni è fondamentale prima di scegliere una strategia.

**La limitazione critica**: i Kubernetes Secrets non sono cifrati per default — sono codificati in Base64, che è reversibile senza chiave. Chiunque possa fare `kubectl get secret -o yaml` legge il valore. L'API server li archivia in etcd, anch'esso non cifrato per default.

```bash
# Quanto "segreto" è un Kubernetes Secret di default
kubectl get secret my-secret -o jsonpath='{.data.password}' | base64 -d
# → la password in chiaro
```

Questo non significa che Kubernetes Secrets siano inutili — significa che richiedono configurazione aggiuntiva e, per sistemi ad alta sicurezza, integrazioni esterne.

---

## Tipi di Kubernetes Secret

```yaml
# Opaque (generico) — tipo più comune
apiVersion: v1
kind: Secret
metadata:
  name: app-credentials
type: Opaque
data:
  username: YWRtaW4=         # base64("admin")
  password: c3VwZXJzZWNyZXQ=  # base64("supersecret")
stringData:                   # alternativa: stringData accetta valori in chiaro
  api-key: "sk-prod-abc123"   # Kubernetes lo converte in base64 automaticamente

---
# TLS — per certificati TLS
apiVersion: v1
kind: Secret
metadata:
  name: service-tls
type: kubernetes.io/tls
data:
  tls.crt: <base64 del certificato>
  tls.key: <base64 della chiave privata>

---
# Docker registry credentials
apiVersion: v1
kind: Secret
metadata:
  name: registry-credentials
type: kubernetes.io/dockerconfigjson
data:
  .dockerconfigjson: <base64 del config.json>
```

---

## Encryption at Rest — Cifrare etcd

Per cifrare i secret in etcd, configurare un **EncryptionConfiguration**:

```yaml
# encryption-config.yaml (passato a kube-apiserver)
apiVersion: apiserver.config.k8s.io/v1
kind: EncryptionConfiguration
resources:
- resources:
  - secrets
  providers:
  # KMS v2 (raccomandato) — delega la cifratura a un KMS esterno
  - kms:
      apiVersion: v2
      name: aws-kms-provider
      endpoint: unix:///var/run/kmsplugin/socket.sock
      timeout: 3s

  # AES-GCM con chiave locale (meno sicuro — la chiave è nel file)
  - aesgcm:
      keys:
      - name: key1
        secret: <base64 di una chiave AES-256>

  # Identity = no cifratura (fallback per i secret pre-esistenti)
  - identity: {}
```

```bash
# Applica la configurazione (kube-apiserver deve essere riavviato)
# Poi ricrifa i secret esistenti (erano in chiaro)
kubectl get secrets --all-namespaces -o json | kubectl replace -f -
```

**Per cluster managed (EKS, GKE, AKS):**
```bash
# AWS EKS — abilita envelope encryption con KMS
aws eks create-cluster \
  --name prod \
  --encryption-config '[{
    "resources": ["secrets"],
    "provider": {"keyArn": "arn:aws:kms:us-east-1:123:key/abc-123"}
  }]'

# GKE — Application-layer secrets encryption
gcloud container clusters create prod \
  --database-encryption-key projects/my-project/locations/us-central1/keyRings/my-ring/cryptoKeys/my-key
```

---

## RBAC per i Secrets — Limitare l'Accesso

Il principio del least privilege applicato ai Secrets:

```yaml
# Role che permette SOLO la lettura del secret specifico dell'applicazione
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: orders-secret-reader
  namespace: production
rules:
- apiGroups: [""]
  resources: ["secrets"]
  resourceNames: ["orders-db-credentials", "orders-api-keys"]  # Solo questi secret!
  verbs: ["get"]   # Solo get, non list/watch (list espone i nomi di tutti i secret)

---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: orders-secret-binding
  namespace: production
subjects:
- kind: ServiceAccount
  name: orders-service-account
  namespace: production
roleRef:
  kind: Role
  name: orders-secret-reader
  apiGroup: rbac.authorization.k8s.io
```

!!! warning "Evitare `list` e `watch` sui secrets"
    Il verbo `list` espone i metadata di tutti i secret nel namespace (inclusi i nomi). Il verbo `watch` permette di vedere i cambiamenti in tempo reale. In produzione, usare solo `get` con `resourceNames` espliciti.

---

## Sealed Secrets — GitOps-Friendly

**Il problema GitOps**: vuoi archiviare tutta la configurazione Kubernetes in Git, ma i Secrets non possono essere committati in chiaro.

**[Sealed Secrets](https://github.com/bitnami-labs/sealed-secrets)** (Bitnami) risolve questo con crittografia asimmetrica: un controller nel cluster ha la chiave privata; `kubeseal` cifra il secret con la chiave pubblica; il file cifrato (SealedSecret) è sicuro da committare in Git.

```bash
# Installa il controller (Helm)
helm install sealed-secrets sealed-secrets/sealed-secrets \
  -n kube-system \
  --set fullnameOverride=sealed-secrets-controller

# Ottieni la chiave pubblica del controller
kubeseal --fetch-cert > pub-sealed-secrets.pem

# Crea un Secret normale e cifralo con kubeseal
kubectl create secret generic orders-credentials \
  --from-literal=db-password="supersecret" \
  --dry-run=client -o yaml | \
kubeseal --cert pub-sealed-secrets.pem \
         --format yaml > sealed-orders-credentials.yaml

# Il file .yaml risultante può essere committato in Git
cat sealed-orders-credentials.yaml
# apiVersion: bitnami.com/v1alpha1
# kind: SealedSecret
# metadata:
#   name: orders-credentials
# spec:
#   encryptedData:
#     db-password: AgB1K9z...  ← cifrato, inutile senza la chiave privata del controller

# Deploy
kubectl apply -f sealed-orders-credentials.yaml
# Il controller decifra e crea il Kubernetes Secret corrispondente
```

**Limitazioni Sealed Secrets:**
- La chiave privata del controller è nel cluster — backup obbligatorio
- Se il controller viene ricreato con una nuova chiave, tutti i SealedSecret devono essere rigenerati
- Non supporta rotazione automatica del secret — solo cifratura per GitOps

---

## External Secrets Operator (ESO) — Secret Sincroni da Store Esterni

**[External Secrets Operator](https://external-secrets.io/)** sincronizza i secret da store esterni (Vault, AWS Secrets Manager, GCP Secret Manager, Azure Key Vault) in Kubernetes Secrets nativi.

```
Store Esterno (AWS SM, Vault, ecc.) ◄── read ── ESO Controller
                                                      │
                                                      │ crea/aggiorna
                                                      ▼
                                           Kubernetes Secret
                                                      │
                                                      │ montato in
                                                      ▼
                                                   Pod
```

```yaml
# SecretStore — configura la connessione all'AWS Secrets Manager
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: aws-secrets-manager
spec:
  provider:
    aws:
      service: SecretsManager
      region: us-east-1
      auth:
        jwt:
          serviceAccountRef:
            name: external-secrets-sa   # SA con IRSA (IAM role)
            namespace: external-secrets

---
# ExternalSecret — definisce quale secret importare e come
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: orders-db-credentials
  namespace: production
spec:
  refreshInterval: 1h               # Sincronizza ogni ora
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  target:
    name: orders-db-secret          # Kubernetes Secret risultante
    creationPolicy: Owner           # ESO è il proprietario → cleanup automatico
    template:
      type: Opaque
      data:
        DB_HOST: "{{ .host }}"
        DB_PORT: "{{ .port }}"
        DB_USER: "{{ .username }}"
        DB_PASS: "{{ .password }}"
  data:
  - secretKey: host
    remoteRef:
      key: production/orders/database   # Path in AWS Secrets Manager
      property: host
  - secretKey: username
    remoteRef:
      key: production/orders/database
      property: username
  - secretKey: password
    remoteRef:
      key: production/orders/database
      property: password
```

```yaml
# ESO con HashiCorp Vault
apiVersion: external-secrets.io/v1beta1
kind: ClusterSecretStore
metadata:
  name: vault-backend
spec:
  provider:
    vault:
      server: "https://vault.vault.svc.cluster.local:8200"
      path: "kv"
      version: "v2"
      auth:
        kubernetes:
          mountPath: "kubernetes"
          role: "external-secrets"
          serviceAccountRef:
            name: external-secrets-sa
```

**Confronto ESO vs Sealed Secrets vs Vault Agent:**

| | Sealed Secrets | ESO | Vault Agent |
|---|---|---|---|
| Source of truth | Git (cifrato) | Store esterno | Vault |
| GitOps-friendly | ✅ Sì | ✅ Con sync | ❌ No (file locali) |
| Dynamic secrets | ❌ No | Limitato | ✅ Sì |
| Rotation automatica | ❌ No | ✅ Sì | ✅ Sì |
| Complessità | Bassa | Media | Alta |
| Formato K8s Secret | ✅ Nativo | ✅ Nativo | File in /vault/secrets/ |

---

## Reloader — Restart Automatico dopo Secret Update

Quando un Kubernetes Secret viene aggiornato, i pod esistenti non vedono il cambiamento (i secret montati come volume vengono aggiornati, ma le env var no — richiedono restart del pod).

**[Reloader](https://github.com/stakater/Reloader)** monitora i cambiamenti ai Secret e riavvia automaticamente i deployment:

```yaml
# Annotazione sul Deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  annotations:
    reloader.stakater.com/auto: "true"   # Riavvia se qualsiasi secret referenziato cambia
    # oppure:
    secret.reloader.stakater.com/reload: "orders-db-secret,orders-api-keys"  # Solo questi
spec:
  ...
```

---

## Best Practices

- **Encryption at rest sempre**: configurare KMS encryption per etcd — un dump di etcd non deve esporre secret in chiaro
- **RBAC granulare sui secret**: nessun pod/SA deve avere `list` o accesso wildcard ai secret — solo `get` sui secret specifici necessari
- **Non usare env var per secret critici**: le env var sono visibili in `kubectl describe pod`, in `/proc/PID/environ`, e nei log. Preferire file montati come volume (aggiornabili senza restart)
- **ESO per managed cloud**: se usi AWS/GCP/Azure, ESO + Secrets Manager è la soluzione più semplice e sicura — centralizza la gestione con rotazione
- **Sealed Secrets per GitOps on-premise**: quando non hai un cloud secret store ma vuoi tutto in Git

## Troubleshooting

### Scenario 1 — Secret non montato nel pod / pod rimane in `Pending`

**Sintomo:** Il pod non parte e `kubectl describe pod` mostra `MountVolume.SetUp failed: secret "my-secret" not found` oppure il pod è bloccato in `Pending`.

**Causa:** Il Secret referenziato nel volume o nell'`envFrom` non esiste nel namespace del pod, oppure è stato creato nel namespace sbagliato.

**Soluzione:** Verificare che il Secret esista nello stesso namespace del pod e che il nome corrisponda esattamente.

```bash
# Verifica esistenza del secret nel namespace corretto
kubectl get secret my-secret -n production

# Lista tutti i secret nel namespace
kubectl get secrets -n production

# Dettaglio del pod per leggere il messaggio di errore completo
kubectl describe pod <pod-name> -n production

# Se il secret manca, crearlo
kubectl create secret generic my-secret \
  --from-literal=password="mypassword" \
  -n production
```

---

### Scenario 2 — ExternalSecret rimane in `SecretSyncedError` o `NotReady`

**Sintomo:** `kubectl get externalsecret -n production` mostra `STATUS: SecretSyncedError` o `READY: False`. Il Kubernetes Secret target non viene creato o aggiornato.

**Causa:** Problema di autenticazione/autorizzazione tra ESO e lo store esterno (permessi IAM mancanti, IRSA non configurato, path errato nel secret store).

**Soluzione:** Ispezionare gli eventi dell'ExternalSecret e i log del controller ESO.

```bash
# Controlla lo status e gli eventi dell'ExternalSecret
kubectl describe externalsecret orders-db-credentials -n production

# Controlla i log del controller ESO
kubectl logs -n external-secrets \
  -l app.kubernetes.io/name=external-secrets \
  --tail=50

# Verifica che il SecretStore sia Ready
kubectl get clustersecretstore aws-secrets-manager
kubectl describe clustersecretstore aws-secrets-manager

# Test manuale: verifica che la SA abbia accesso al secret AWS
kubectl exec -it -n external-secrets \
  $(kubectl get pod -n external-secrets -l app.kubernetes.io/name=external-secrets -o jsonpath='{.items[0].metadata.name}') \
  -- env | grep AWS
```

---

### Scenario 3 — Sealed Secret non viene decifrato (`controller not found` o `decryption error`)

**Sintomo:** Dopo `kubectl apply` di un SealedSecret, il Kubernetes Secret non viene creato. `kubectl get sealedsecret` mostra `STATUS: SyncError`.

**Causa 1:** Il controller Sealed Secrets è stato ricreato con una nuova chiave — i SealedSecret cifrati con la vecchia chiave non sono più decifrabili.
**Causa 2:** Il SealedSecret è stato cifrato per un namespace diverso (scope `strict` = namespace-locked).

**Soluzione:**

```bash
# Verifica stato del controller
kubectl get pods -n kube-system -l app.kubernetes.io/name=sealed-secrets

# Controlla gli eventi del SealedSecret
kubectl describe sealedsecret orders-credentials -n production

# Log del controller per vedere errori di decifratura
kubectl logs -n kube-system \
  -l app.kubernetes.io/name=sealed-secrets \
  --tail=30

# Se la chiave è stata persa, ripristinare il backup della chiave privata
kubectl apply -f sealed-secrets-key-backup.yaml -n kube-system
kubectl rollout restart deployment/sealed-secrets-controller -n kube-system

# Rigenerare il SealedSecret con la chiave pubblica attuale
kubeseal --fetch-cert --controller-namespace kube-system > pub-cert.pem
kubectl create secret generic orders-credentials \
  --from-literal=password="newvalue" \
  --dry-run=client -o yaml | \
kubeseal --cert pub-cert.pem --format yaml > sealed-orders-credentials.yaml
```

---

### Scenario 4 — Le variabili d'ambiente dai Secret non si aggiornano dopo una modifica

**Sintomo:** Aggiornato un Kubernetes Secret con `kubectl apply` o tramite ESO, ma il pod continua a leggere il valore vecchio. I secret montati come volume si aggiornano, ma le env var restano stantie.

**Causa:** Le env var (`env`/`envFrom`) vengono iniettate al momento del lancio del pod e non vengono aggiornate dynamicamente. Solo i secret montati come volume (`volumeMounts`) vengono sincronizzati dal kubelet.

**Soluzione:** Forzare il rolling restart del deployment. Se il problema è ricorrente, usare Reloader.

```bash
# Forza il rolling restart del deployment per ricaricare le env var
kubectl rollout restart deployment/orders-service -n production

# Verifica che il restart sia completato
kubectl rollout status deployment/orders-service -n production

# Verifica il valore attuale dell'env var nel pod aggiornato
kubectl exec -it \
  $(kubectl get pod -n production -l app=orders-service -o jsonpath='{.items[0].metadata.name}') \
  -n production -- env | grep DB_PASS

# Soluzione permanente: installare Reloader e annotare il deployment
helm install reloader stakater/reloader -n kube-system
kubectl annotate deployment orders-service \
  reloader.stakater.com/auto="true" \
  -n production
```

---

## Riferimenti

- [Kubernetes Secrets Documentation](https://kubernetes.io/docs/concepts/configuration/secret/)
- [Kubernetes Encryption at Rest](https://kubernetes.io/docs/tasks/administer-cluster/encrypt-data/)
- [Bitnami Sealed Secrets](https://github.com/bitnami-labs/sealed-secrets)
- [External Secrets Operator](https://external-secrets.io/latest/)
- [Stakater Reloader](https://github.com/stakater/Reloader)
