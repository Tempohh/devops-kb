# KB Saturation Report — 2026-09-27 (sessione #609)

## Gate meccanico

```
file_count: 314, target: 330, over_target: false, headroom: 16
category_saturated_pct: 85, allow_zero_proposals: true
```

Sotto target. Focus ruotato su `docs/security/` e `docs/messaging/` (raccomandazione
del report #607: "security/ mai stato in focus esplicito" / "messaging/ solo
kafka+rabbitmq, coverage da verificare").

## Copertura stimata per categoria

| Categoria | Files | Coverage % | Depth | Note |
|-----------|-------|------------|-------|------|
| security | 25 (+8 `_index`) | ~90% | Molto alta: autenticazione (OAuth2/OIDC, JWT, mTLS/SPIFFE), autorizzazione (RBAC/ABAC/ReBAC, OPA), secret-management (Vault + K8s Secrets con Sealed Secrets/ESO/Reloader trattati nello stesso file), PKI, supply-chain (4 file), compliance/audit (SIEM, Falco, cloud audit log, framework compliance) | Nessun gap operativo trovato |
| messaging/rabbitmq | 7 (+1 `_index`) | ~90% | Alta: architettura AMQP, affidabilità/Quorum Queues, Streams, DLX/retry, Federation/Shovel, clustering, deployment K8s (Cluster+Topology Operator, TLS, Prometheus/Grafana, Amazon MQ) | Asimmetria con Kafka (44 file) è per design — RabbitMQ non necessita pari profondità, i topic esistenti sono trattati a fondo |

## Analisi di questa sessione

File analizzati (9): `messaging/rabbitmq/_index.md`, `messaging/rabbitmq/features-avanzate.md`,
`messaging/rabbitmq/deployment.md`, `security/_index.md`, `security/network/_index.md`,
`security/compliance/_index.md`, `security/compliance/audit-logging.md`,
`security/secret-management/_index.md`, `security/secret-management/kubernetes-secrets.md`.

**Verificato NON un gap — RabbitMQ**: ipotizzato che il subcat fosse sottodimensionato
(7 file vs 44 di Kafka). Verifica mostra che i temi esistenti (Streams, DLX+retry con
backoff, Federation, Shovel, Single Active Consumer, Lazy Queues, Cluster/Topology
Operator, TLS, Prometheus alerting, Amazon MQ) sono trattati con lo stesso livello di
profondità di Kafka — mancano solo topic che *non esistono* in RabbitMQ (partitioning
stile Kafka, schema registry). Nessun gap reale.

**Verificato NON un gap — Secret Management**: `security/_index.md` promette "Sealed
Secrets, External Secrets Operator" nella sezione Secret Management, ma esiste solo
`kubernetes-secrets.md` (oltre a `vault.md`) — sembrava un file mancante. Lettura del
contenuto mostra che Sealed Secrets ed ESO sono trattati per intero dentro
`kubernetes-secrets.md` (setup, confronto Sealed Secrets vs ESO vs Vault Agent,
troubleshooting dedicato). Non serve uno split — l'informazione esiste ed è profonda.

**Verificato NON un gap — Compliance/Audit**: un solo file (`audit-logging.md`) per
l'intero subcat sembrava sottile, ma copre application audit strutturato, K8s audit
log, Falco (regole, sidekick, troubleshooting), cloud audit log (CloudTrail), SIEM
(OpenSearch/Fluentbit con regole di correlazione), tabella framework compliance
(SOC2/ISO27001/PCI-DSS/GDPR/HIPAA) e CIS Benchmark. Copertura completa in un file
coerente — split forzerebbe una divisione artificiale.

**Verificato NON un gap — Network Security**: `security/network/` ha un solo file
(`zero-trust.md`). Possibili estensioni (WAF, DDoS, firewall, VPN) sono già coperte
in profondità in `networking/sicurezza/` (confermato saturo nelle sessioni #591-596).
Il file esistente tratta lo zero trust a livello di identità workload (SPIFFE, OPA,
NIST 800-207) — argomento distinto e non duplicato.

## Categorie vicine alla saturazione

- **security/**, **messaging/rabbitmq**: confermato saturo in questa sessione dopo
  verifica approfondita (9 file letti, zero gap reali trovati).
- **networking**, **cloud/aws**, **ci-cd/testing**: confermato saturo nelle sessioni
  precedenti (#591-596, #607).

## Categorie con gap reali

Nessuno identificato in questa sessione.

## Focus usato in questa sessione

`docs/security/` (rotazione da report #607: "mai stato in focus esplicito") +
`docs/messaging/` (rotazione da report #607: "solo kafka+rabbitmq, coverage da
verificare"). Entrambi risultati saturi dopo verifica mirata.

## Decisione: 0 proposte

Nessuna proposta generata. I due gap ipotizzati dal report precedente (asimmetria
RabbitMQ/Kafka, presunto file mancante su Sealed Secrets/ESO) sono stati verificati e
scartati come non reali — l'informazione esiste già con profondità adeguata. Generare
proposte qui avrebbe prodotto lavoro a basso valore (contenuto duplicato o split
artificiale di file già coerenti).

## Prossima sessione consigliata

2026-09-28 o successiva. Aree non ancora esplorate in focus esplicito: `docs/dev/`
(coverage da verificare, categoria ampia e potenzialmente eterogenea) e
`docs/databases/` (menzionato come coverage più bassa nel report #603, non ancora
verificato con lettura approfondita). Se anche queste risultano sature, considerare
`consolidate`/`review` sui file con `last_verified` più vecchio invece di nuova
generazione — la KB con 314/330 file e gap reali sempre più rari sta approcciando un
punto di rendimento decrescente per i task `new_topic`.
