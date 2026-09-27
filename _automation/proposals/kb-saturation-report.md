# KB Saturation Report — 2026-09-27 (sessione #659)

## Gate meccanico

```
file_count: 314, target: 330, over_target: false, headroom: 16, category_saturated_pct: 85
```

Invariato dalle sessioni precedenti (#649, #651, #653, #656). Sotto target,
espansione ammessa ma solo con gap reali (vedi PASSO 0/3 del prompt).

## Focus usato in questa sessione

Come raccomandato dal report di #656: primo giro content-focused su `docs/iac/`,
mai stato oggetto di lettura mirata prima d'ora. 10 file letti in profondità,
coprendo tutte le sottocategorie principali:

- `iac/ansible/fondamentali.md`, `iac/ansible/roles-collections.md`
- `iac/pulumi/fondamentali.md`, `iac/pulumi/stacks-ambienti.md`,
  `iac/pulumi/policy-as-code.md`
- `iac/terraform/fondamentali.md`, `iac/terraform/moduli.md`,
  `iac/terraform/state-management.md`, `iac/terraform/testing.md`
- `iac/crossplane/fondamentali.md`

## Risultato

Tutti e 10 i file sono risultati **maturi e solidi**: contenuto denso, esempi
CLI realistici (`ansible-playbook`, `pulumi`, `terraform`, `kubectl`), snippet
completi (playbook YAML, HCL, Python/TypeScript/Go), sezioni Troubleshooting
con scenari multipli concreti, confronti espliciti tra i tool (Terraform vs
Pulumi vs Crossplane vs Ansible) coerenti tra i vari file. Nessun gap di
contenuto (`new-file` / `extend-section`) trovato — `iac/` è coperta a un
livello di maturità paragonabile a `cloud/aws/` (#653) e `cloud/azure/` (#656).

Due gap individuati, stesso pattern ricorrente delle sessioni precedenti:

- **Connettività** — `iac/terraform/fondamentali.md` è referenziato in
  dettaglio (related + sezione Relazioni) sia da `iac/pulumi/fondamentali.md`
  sia da `iac/crossplane/fondamentali.md`, ma il proprio `related` (5 voci:
  state-management, moduli, ansible/fondamentali, cloud/aws EC2, cloud/aws VPC)
  non include nessuno dei due. → prop-094 (low, fix-relation).
- **Correttezza** — `iac/ansible/fondamentali.md` ha nel `related` il path
  `ci-cd/pipeline/github-actions`, che non esiste (verificato con Glob); il
  path corretto è `ci-cd/github-actions/_index`, già usato correttamente nel
  file gemello `iac/ansible/roles-collections.md`. → prop-095 (low, fix-relation).

Nessuna proposta `new-file` in questa sessione.

## Categorie vicine alla saturazione

Invariato: **databases/**, **dev/linguaggi/**, **messaging/rabbitmq**,
**cloud/aws**, **networking/**, **dev/testing, dev/data, dev/resilienza,
dev/sicurezza, dev/integrazioni**, **monitoring/**, **ai/**, **security/**,
**containers/**, **messaging/kafka/**, **cloud/azure/**. Con questa sessione
si conferma di alta qualità (content-read) anche `iac/` (campione di 10 file
su 4 sottocategorie: ansible, pulumi, terraform, crossplane).

## Categorie con gap reali

Due gap isolati (vedi sopra, prop-094/095). Nessun gap di contenuto in questa
sessione.

## Prossima sessione consigliata

Non prima di 2026-10-04. Il giro content-focused ha ora coperto un campione
denso di `cloud/aws/` (#653), `cloud/azure/` (#656) e `iac/` (questa sessione).
In alternativa, applicare prop-094/095 (fix-relation, se approvate) e passare
a un primo giro content-focused su `databases/postgresql/` (file esistenti ma
non ancora letti per contenuto: `connection-pooling.md`, `extensions.md`,
`mvcc-vacuum.md`, `replicazione.md`) — mai stata in focus finora nonostante
sia segnalata "vicina alla saturazione" da diverse sessioni consecutive senza
mai essere stata verificata a livello di contenuto.
