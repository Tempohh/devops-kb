# KB Saturation Report — 2026-09-27 (sessione #607)

## Gate meccanico

```
file_count: 313, target: 330, over_target: false, headroom: 17
category_saturated_pct: 85, allow_zero_proposals: true
```

Sotto target. Focus ruotato su `docs/iac/` (raccomandato dal report #603:
"non riletto da tempo, coverage ~75%") e verifica mirata su `docs/ci-cd/testing/`
(secondo suggerimento del report #603).

## Copertura stimata per categoria

| Categoria | Files | Coverage % | Depth | Note |
|-----------|-------|------------|-------|------|
| iac | 14 (+3 `_index`) | ~75% | Alta su Terraform (7 file), Ansible (2, con Vault/Molecule/CI), Pulumi (3, con CrossGuard) | Manca paradigma K8s-native (Crossplane) — gap confermato |
| ci-cd/testing | 4 (incl. `_index`) | ~85% | Alta: test pyramid, mutation testing, contract testing, k6/Gatling già coperti in profondità | Flaky test management già coperto (troubleshooting test-strategy.md) — nessun gap |

## Analisi di questa sessione

File analizzati (10): `iac/_index.md`, `iac/ansible/_index.md`,
`iac/ansible/fondamentali.md`, `iac/ansible/roles-collections.md`,
`iac/pulumi/_index.md`, `iac/pulumi/policy-as-code.md`,
`iac/terraform/testing.md`, `ci-cd/testing/_index.md`,
`ci-cd/testing/test-strategy.md`, `ci-cd/testing/performance-testing.md`.

**Verificato NON un gap**: test parallelization/flaky test management in
ci-cd/testing (ipotesi del report #603). `test-strategy.md` copre già test
splitting/shard, ordine random per rilevare flaky, pytest-randomly,
rerunFailingTestsCount, cause comuni (stato condiviso, sleep fissi). Non serve
un file dedicato — l'informazione esiste già ed è collegata.

**Gap reale confermato**: **Crossplane assente come argomento**. La sezione
iac/ tratta solo Terraform/Ansible/Pulumi — tutti CLI-driven con ciclo
plan/apply o playbook on-demand. Crossplane introduce un paradigma diverso
(control loop Kubernetes, CRD come interfaccia, riconciliazione continua) che
non ha equivalente diretto negli altri tre. Citato solo di striscio in
`containers/kubernetes/multi-cluster.md` (provisioning multi-cluster), senza
spiegare Provider/Managed Resource/Composition/XRD. Non è simmetria formale:
il modello è concettualmente distinto da plan/apply e merita trattazione
propria — score high.

## Categorie vicine alla saturazione

- **networking**, **cloud/aws**: confermato saturo nelle sessioni precedenti
  (#591-596), fuori focus in questa sessione.
- **ci-cd**, **ci-cd/testing**: alta profondità confermata anche in questa
  sessione, nessun gap aggiuntivo trovato.

## Categorie con gap reali

- **iac/**: manca Crossplane (paradigma K8s-native) — proposta generata
  (prop-062, priority high).

## Focus usato in questa sessione

`docs/iac/` (rotazione da report #603: "coverage più bassa, non riletto da
tempo") + verifica mirata su `docs/ci-cd/testing/` (secondo suggerimento del
report #603, risultata in nessun gap).

## Decisione: 1 proposta

- `prop-062`: Crossplane — Provisioning Kubernetes-native,
  `iac/crossplane/fondamentali.md`, priority high.

Zero proposte aggiuntive: `ci-cd/testing` confermato ben coperto anche su
flaky test management (verifica esplicita sopra); networking/cloud/aws
restano fuori focus e già confermati saturi.

## Prossima sessione consigliata

2026-09-28 o successiva. Se `prop-062` viene eseguita, valutare se
`iac/_index.md` necessita di un aggiornamento della tabella "Strumenti
Coperti" (task `expand`, non `new_topic`) per includere Crossplane. Se non
emergono nuovi gap in iac/, ruotare focus su `security/` (verificare
coverage supply-chain/runtime, mai stati in focus esplicito nelle ultime
sessioni tracciate) o su `messaging/` (solo kafka+rabbitmq, coverage da
verificare).
