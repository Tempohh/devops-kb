# KB Saturation Report — 2026-10-02 (sessione #714)

## Gate meccanico

```
file_count: 323, target: 330, over_target: false, headroom: 7, category_saturated_pct: 85, allow_zero_proposals: true
```

Sotto target (headroom 7). Verificato che prop-131 e prop-132 sono implementate
(`cis-benchmarks-compliance-scanning.md`, `saml-ldap-enterprise-sso.md` presenti
in `docs/security/`). `pending/` vuota a inizio sessione.

## Copertura stimata per categoria

File esclusi `_index.md`: cloud 78, messaging 45, networking 36, containers 29,
databases 25, ci-cd 21, ai 19, dev 19, security 19, monitoring 18, iac 12.

| Categoria | Files | Coverage % | Depth | Note |
|-----------|-------|------------|-------|------|
| cloud | 78 | alta | alta | provider simmetrici, nessun gap reale |
| messaging | 45 | alta | alta | satura dopo Pulsar |
| networking | 36 | alta | alta | matura (sessione #711) |
| containers | 29 | alta | media | gap: backup/DR del cluster |
| databases | 25 | media-alta | alta | mysql/postgres/nosql coperti |
| ci-cd | 21 | media | media | testing saturo |
| ai | 19 | media | media | |
| dev | 19 | alta | media | satura |
| security | 19 | media-alta | alta | compliance/autenticazione colmate da prop-131/132 |
| monitoring | 18 | media | alta | |
| iac | 12 | media | media | terraform/pulumi/ansible/crossplane |

## Categorie vicine alla saturazione

`docs/dev/`, `docs/ci-cd/testing/`, `docs/messaging/`, `docs/networking/`,
`docs/cloud/` (provider): nessun gap con score alto.

## Categorie con gap reali

`docs/containers/kubernetes/`: Velero ha 0 file dedicati (1 sola riga in una
config di audit) ed etcd backup è solo accennato. Proposta prop-133.
`docs/security/` resta con margine su `secret-management/` (External Secrets
Operator/SOPS hanno 6-8 file di menzioni, da verificare se bastano) e
`autorizzazione/`; non emerso un gap con score alto in questo ciclo.

## Metodo e limiti di questa sessione

Analisi basata su censimento strutturale (Glob/conteggi), gate meccanico e grep
mirati di 20 termini (external-secrets, sops, kyverno, velero, karpenter, thanos,
terragrunt, cilium, ecc.) su tutta la KB. Non sono stati letti 10 file per intero
come richiesto dal PASSO 2: la copertura dei gap è stimata da grep, non da lettura
del contenuto. Karpenter è già coperto in due file AWS (scartato).

## Focus usato in questa sessione

Rotazione dal report #711 (che indicava `security/autorizzazione` e
`secret-management`), allargata a containers/iac/monitoring/databases perché
security è ora ben coperta. Il gap con score alto è emerso in containers.

## Prossima sessione consigliata

Non prima di 2026-10-09. Verificare prima l'implementazione di prop-133. Focus:
leggere per intero `security/secret-management/` e `iac/` (drift detection,
Terragrunt: 3 file di menzioni) prima di aprire nuove categorie.
