# KB Saturation Report — 2026-09-27 (sessione #653)

## Gate meccanico

```
file_count: 314, target: 330, over_target: false, headroom: 16, category_saturated_pct: 85
```

Invariato dalle sessioni precedenti (#649, #651). Sotto target, espansione ammessa
ma solo con gap reali (vedi PASSO 0/3 del prompt).

## Focus usato in questa sessione

Come raccomandato dal report di #651: continuazione del giro di lettura
**content-focused** (non solo connettività) su `cloud/aws/` e `databases/`,
questa volta sulle sottocategorie non ancora coperte: `cloud/aws/{networking,
security,storage,messaging,monitoring}` e `databases/{fondamentali,
replicazione-ha,nosql}`. 10 file letti in profondità:

- `cloud/aws/networking/vpc-lattice.md`, `cloud/aws/networking/global-accelerator.md`
- `cloud/aws/security/network-security.md`, `cloud/aws/security/kms-secrets.md`
- `cloud/aws/storage/s3-avanzato.md`
- `cloud/aws/messaging/eventbridge-kinesis.md`
- `cloud/aws/monitoring/observability.md`
- `databases/fondamentali/sharding.md`
- `databases/replicazione-ha/failover-recovery.md`
- `databases/nosql/cassandra.md`

## Risultato

Tutti e 10 i file sono risultati **maturi e solidi**: contenuto denso, esempi
pratici realistici (CLI, Terraform, Python), sezioni Troubleshooting con
scenari multipli, nessun comando/flag palesemente deprecato, nessuna
incoerenza di contenuto tra file collegati.

Due gap reali trovati, entrambi di tipo **connettività** (non contenuto),
sullo stesso pattern già riscontrato in #651 con prop-089:

- **`cloud/aws/networking/vpc-lattice.md`** (creato/aggiornato in questa
  sessione, `last_updated: 2026-09-27`) confronta in prosa Transit
  Gateway/PrivateLink (`vpc-avanzato.md`), NLB/ALB come target
  (`elastic-load-balancing.md`) e la sintassi auth policy
  (`iam/policies-avanzate.md`), ma nessuno dei tre lo referenzia nel proprio
  `related`. → prop-090 (low, fix-relation).
- **`cloud/aws/networking/global-accelerator.md`** (stesso `last_updated`)
  confronta esplicitamente il proprio failover-in-secondi con Route 53
  failover routing, si posiziona vs CloudFront per traffico non cacheable, e
  usa ALB/NLB/VPC come endpoint — ma `route53.md`, `cloudfront.md`,
  `elastic-load-balancing.md` e `vpc.md` non lo referenziano indietro. →
  prop-091 (low, fix-relation).

Nessun gap di tipo `new-file` o `extend-section`: le sezioni esaminate sono
mature. Da notare che `vpc-lattice.md` e `global-accelerator.md` sono file
recenti (stesso `last_updated` di questa sessione) — probabile causa del gap:
aggiunti senza aggiornare i `related` inversi nei file più vecchi che
confrontano.

## Categorie vicine alla saturazione

Invariato: **databases/**, **dev/linguaggi/**, **messaging/rabbitmq**,
**cloud/aws**, **networking/**, **dev/testing, dev/data, dev/resilienza,
dev/sicurezza, dev/integrazioni**, **monitoring/**, **iac/**, **cloud/azure/**,
**ai/**, **security/**, **containers/**, **messaging/kafka/**. Con questa
sessione si confermano di alta qualità (content-read) anche
`cloud/aws/{networking,security,storage,messaging,monitoring}` e
`databases/{fondamentali,replicazione-ha,nosql}` (parzialmente — vedi sotto).

## Categorie con gap reali

Due gap di connettività isolati (vedi sopra, prop-090/091). Nessun gap di
contenuto in questa sessione.

## Prossima sessione consigliata

Non prima di 2026-10-03. Il giro content-focused su `cloud/aws/` copre ora
tutte le sottocategorie principali (compute, containers, database, iam,
networking, security, storage, messaging, monitoring) su un campione denso.
Per `databases/` restano da coprire in profondità: `postgresql/` (solo
`replicazione.md` letto finora, mancano `connection-pooling`, `extensions`,
`mvcc-vacuum`), `mysql/`, `sql-avanzato/` (parziale), `kubernetes-cloud/`. Per
`cloud/aws/`, prossimo giro utile: applicare prop-090/091 (fix-relation, se
approvate) e poi passare a un primo giro content-focused su `cloud/azure/`
(mai stato oggetto di lettura mirata finora) o completare `databases/`
elencato sopra.
