---
title: "PKI Interna — Progettazione e Implementazione"
slug: pki-interna
category: security
tags: [pki, ca-interna, certificate-authority, cfssl, step-ca, x509, hsm]
search_keywords: [pki interna enterprise, certificate authority interna, root ca design, ca intermedia, cfssl cloudflare, step-ca smallstep, hsm hardware security module, online ca offline ca, certificate revocation crl ocsp, pki gerarchia, cross-certificate, ca bundle, trust store, certificate pinning, cert lifecycle management, automated certificate issuance, acme protocol internal, ca rotation, root ca renewal, subordinate ca, issuing ca, policy ca, private ca aws, google private ca, azure certificate authority, private pki microservices]
parent: security/pki-certificati/_index
related: [security/pki-certificati/cert-manager, security/autenticazione/mtls-spiffe, security/secret-management/vault]
official_docs: https://smallstep.com/docs/
status: complete
difficulty: advanced
last_updated: 2026-02-24
---

# PKI Interna — Progettazione e Implementazione

## Panoramica

Una **PKI interna** è necessaria quando i certificati pubblici (Let's Encrypt) non sono sufficienti: comunicazioni interne tra microservizi, mTLS con identità SPIFFE, certificati per sistemi on-premise non raggiungibili da Internet, o quando si richiede un controllo totale sulla CA.

Il design della PKI è una decisione architetturale con impatti a lungo termine: una PKI progettata male è difficile e costosa da correggere — ogni sistema che si fida di quella CA deve essere aggiornato.

**Principi del design:**
- La Root CA non deve mai emettere certificati direttamente ai servizi
- La Root CA deve essere mantenuta offline (o HSM-protetta) — più è offline, meglio è
- Ogni CA intermedia ha un scope limitato (per servizio, per ambiente, per scopo)
- I certificati leaf devono avere lifetime breve — automatizzare il rinnovo

---

## Gerarchia Raccomandata per un'Azienda

```
┌─────────────────────────────────────────────────────────────────────┐
│                    ROOT CA (OFFLINE / HSM)                          │
│                                                                     │
│  Chiave: RSA 4096 o EC P-384 (HSM)                                 │
│  Lifetime: 20 anni                                                  │
│  CRL: pubblicata ogni 6 mesi, valida 1 anno                        │
│  Uso: firma SOLO CA intermedie, mai certificati leaf               │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ firma
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  CA INTERMEDIA   │  │  CA INTERMEDIA   │  │  CA INTERMEDIA   │
│  "Services"      │  │  "Infrastructure"│  │  "External"      │
│  (online)        │  │  (online)        │  │  (online)        │
│                  │  │                  │  │                  │
│  Lifetime: 5y    │  │  Lifetime: 5y    │  │  Lifetime: 5y    │
│  Emette: cert    │  │  Emette: cert    │  │  Emette: cert    │
│  microservizi    │  │  per infra/VPN   │  │  *.example.com   │
│  (lifetime 24h)  │  │  (lifetime 90d)  │  │  (lifetime 90d)  │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

---

## CFSSL — CA con API REST (Cloudflare)

[CFSSL](https://github.com/cloudflare/cfssl) è un toolkit PKI sviluppato da Cloudflare, orientato all'automazione. Espone una API REST per l'emissione di certificati.

```bash
# Installa
go install github.com/cloudflare/cfssl/cmd/cfssl@latest
go install github.com/cloudflare/cfssl/cmd/cfssljson@latest

# Genera la Root CA
cat > ca-config.json << 'EOF'
{
  "signing": {
    "default": {
      "expiry": "87600h"
    },
    "profiles": {
      "intermediate": {
        "usages": ["cert sign", "crl sign"],
        "expiry": "43800h",
        "ca_constraint": {"is_ca": true, "max_path_len": 0}
      },
      "server": {
        "usages": ["digital signature", "key encipherment", "server auth"],
        "expiry": "8760h"
      },
      "client": {
        "usages": ["digital signature", "key encipherment", "client auth"],
        "expiry": "8760h"
      },
      "peer": {
        "usages": ["digital signature", "key encipherment", "server auth", "client auth"],
        "expiry": "8760h"
      }
    }
  }
}
EOF

cat > root-csr.json << 'EOF'
{
  "CN": "My Corp Root CA",
  "key": {"algo": "ecdsa", "size": 384},
  "ca": {"expiry": "175200h"},
  "names": [{"O": "My Corp", "OU": "Security", "C": "IT"}]
}
EOF

# Genera root CA (chiave + certificato autofirmato)
cfssl gencert -initca root-csr.json | cfssljson -bare root-ca
# Output: root-ca.pem (cert), root-ca-key.pem (chiave) ← tieni offline!

# Genera CA intermedia per i servizi
cat > services-ca-csr.json << 'EOF'
{
  "CN": "My Corp Services CA",
  "key": {"algo": "ecdsa", "size": 256},
  "names": [{"O": "My Corp", "OU": "Services PKI"}]
}
EOF

cfssl gencert -ca=root-ca.pem -ca-key=root-ca-key.pem \
  -config=ca-config.json -profile=intermediate \
  services-ca-csr.json | cfssljson -bare services-ca

# Avvia l'API server CFSSL (CA intermedia online)
cfssl serve \
  -ca=services-ca.pem \
  -ca-key=services-ca-key.pem \
  -config=ca-config.json \
  -address=0.0.0.0 \
  -port=8888 \
  -db-config=db-config.json  # PostgreSQL per il tracking dei certificati emessi
```

```bash
# Emetti un certificato per un servizio via API
curl -s -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "request": {
      "CN": "orders-service",
      "hosts": ["orders.production.svc.cluster.local", "orders-service"],
      "key": {"algo": "ecdsa", "size": 256}
    },
    "profile": "peer"
  }' \
  http://cfssl-server:8888/api/v1/cfssl/newcert | \
  cfssljson -bare orders-service
```

---

## step-ca — CA Moderna con ACME

[step-ca](https://smallstep.com/docs/step-ca/) è la CA più moderna per ambienti DevOps: supporta il protocollo **ACME** (lo stesso di Let's Encrypt), JWK Provisioner, SSH certificates, e ha una UX migliore di CFSSL.

```bash
# Inizializza la PKI
step ca init \
  --name "My Corp Internal CA" \
  --dns "ca.corp.internal" \
  --address ":443" \
  --provisioner "admin@corp.internal"

# Struttura generata:
# ~/.step/
#   certs/root_ca.crt    ← root certificate (da distribuire nei trust store)
#   certs/intermediate_ca.crt
#   secrets/root_ca_key  ← chiave root (protetta con password)
#   secrets/intermediate_ca_key
#   config/ca.json
#   config/defaults.json

# Avvia il server CA
step-ca ~/.step/config/ca.json
```

### ACME Provider — Let's Encrypt interno

```bash
# Aggiungi un provisioner ACME (compatibile con certbot, cert-manager)
step ca provisioner add acme --type ACME

# Da un servizio/server che usa certbot:
certbot certonly \
  --server https://ca.corp.internal/acme/acme/directory \
  --no-verify-ssl \   # se il CA non ha un cert pubblico
  -d orders.production.svc.cluster.local \
  --standalone
```

### SSH Certificates con step-ca

```bash
# step-ca supporta anche certificati SSH — alternativa alle SSH key statiche
step ca provisioner add sshpop --type SSHPOP

# Emetti un certificato SSH per un utente (valido 8h)
step ssh certificate mario.rossi@corp.internal ~/.ssh/id_ecdsa.pub \
  --provisioner admin@corp.internal \
  --principal mario.rossi \
  --not-after 8h

# Il server SSH accetta solo certificati firmati dalla CA (no chiavi statiche)
```

---

## Managed Private CA — Cloud

### AWS Private CA (ACM PCA)

```bash
# Crea una Root CA in AWS
aws acm-pca create-certificate-authority \
  --certificate-authority-configuration '{
    "KeyAlgorithm": "EC_PRIME256V1",
    "SigningAlgorithm": "SHA256WITHECDSA",
    "Subject": {
      "Organization": "My Corp",
      "CommonName": "My Corp Root CA"
    }
  }' \
  --certificate-authority-type ROOT \
  --revocation-configuration '{
    "CrlConfiguration": {"Enabled": true, "S3BucketName": "my-crl-bucket", "ExpirationInDays": 365}
  }'

# Emetti un certificato da ACM PCA
aws acm-pca issue-certificate \
  --certificate-authority-arn "arn:aws:acm-pca:us-east-1:123456789:certificate-authority/abc-123" \
  --csr fileb://orders-service.csr \
  --signing-algorithm "SHA256WITHECDSA" \
  --validity '{"Value": 365, "Type": "DAYS"}' \
  --template-arn "arn:aws:acm-pca:::template/EndEntityCertificate/V1"
```

---

## Distribuzione del Trust Store

Tutti i sistemi che devono verificare i certificati emessi dalla PKI interna devono avere il **root certificate** nel loro trust store:

```bash
# Linux (Debian/Ubuntu)
cp root-ca.pem /usr/local/share/ca-certificates/mycorp-root.crt
update-ca-certificates

# Linux (RHEL/CentOS)
cp root-ca.pem /etc/pki/ca-trust/source/anchors/mycorp-root.crt
update-ca-trust

# Kubernetes — ConfigMap con il CA bundle, montato nei pod
kubectl create configmap internal-ca-bundle \
  --from-file=ca-bundle.crt=root-ca.pem \
  -n production

# Poi montato nel pod:
# volumeMounts:
# - name: ca-bundle
#   mountPath: /etc/ssl/certs/internal-ca.crt
#   subPath: ca-bundle.crt
# volumes:
# - name: ca-bundle
#   configMap:
#     name: internal-ca-bundle
```

---

## Revoca — CRL e OCSP

```
CRL (Certificate Revocation List):
  La CA pubblica periodicamente un file firmato con i serial dei certificati revocati.
  Il client scarica il CRL (può essere vecchio di ore/giorni) → latenza di revoca alta.
  Esempio: CA pubblica CRL ogni 24h, valida 7 giorni.

OCSP (Online Certificate Status Protocol):
  Il client interroga l'OCSP responder in tempo reale per un certificato specifico.
  Risposta fresca → revoca più rapida (secondi/minuti).
  Problema: OCSP responder deve essere disponibile → SPOF.

OCSP Stapling:
  Il server TLS ottiene la risposta OCSP dalla CA e la "staples" nell'handshake TLS.
  Il client ottiene la risposta OCSP senza fare una richiesta separata alla CA.
  → Migliore performance + privacy (la CA non sa quale cert il client sta verificando).
```

```bash
# Verifica revoca con openssl (OCSP)
openssl ocsp \
  -url "http://ocsp.corp.internal" \
  -issuer services-ca.pem \
  -cert orders-service.pem \
  -text

# Revoca un certificato (con cfssl)
cfssl revoke -db-config=db-config.json \
  -serial="12345678" \
  -aki="aa:bb:cc:dd..." \
  -reason=superseded
```

---

## Best Practices

- **Root CA offline sempre**: la root CA non deve mai essere connessa alla rete. Usare un HSM per la chiave privata in produzione; usare una VM air-gapped per ambienti interni più semplici
- **Lifetime brevi per certificati leaf**: 24h per certificati servizio-a-servizio, 90d max per certificati server. Con cert-manager o step-ca, il rinnovo automatico rende il lifetime breve un non-problema
- **CA intermedia per ogni ambiente**: prod, staging e dev devono avere CA intermedie separate — un certificato staging non funziona in prod
- **Backup sicuro della chiave root**: la chiave root è irrecuperabile se persa — cifrarla con più copie in posizioni fisiche separate (HSM + backup offline cifrato + notaio)
- **Monitorare la scadenza delle CA stesse**: le CA intermedie scadono in anni, non giorni. Un alert a 180 giorni dalla scadenza dà tempo sufficiente per la rotazione

## Riferimenti

- [CFSSL — Cloudflare PKI Toolkit](https://github.com/cloudflare/cfssl)
- [step-ca — Smallstep](https://smallstep.com/docs/step-ca/)
- [AWS Private CA](https://docs.aws.amazon.com/privateca/)
- [RFC 5280 — X.509 PKI Certificate](https://www.rfc-editor.org/rfc/rfc5280)
- [NIST SP 800-57 — Key Management](https://csrc.nist.gov/publications/detail/sp/800-57-part-1/rev-5/final)
