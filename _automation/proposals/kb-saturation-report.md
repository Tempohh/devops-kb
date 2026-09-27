# KB Saturation Report — 2026-09-27 (sessione 4, task 569)

## Copertura stimata per categoria

| Categoria | Files | Coverage % | Depth | Note |
|-----------|-------|------------|-------|------|
| KB totale | 306 (gate) / 420 (glob, incl. `_index`/template) | n/a | n/a | `target_file_count` 330, `over_target: false`, headroom 24 |
| messaging | 55 | ~92% | Advanced | analizzata in profondità in questo ciclo (Kafka hub, RabbitMQ, confronto) — 1 gap di connettività (hub) |
| containers | 38 | ~90% | Advanced/Expert | analizzata in profondità in questo ciclo (registry, runtime, sandboxing, openshift) — nessun gap di contenuto |
| networking | 44 | ~88% | Advanced | invariata da sessioni 566/567/568 — congelata come focus, nessun nuovo segnale |
| cloud/aws | 44 | ~90% | Advanced | invariata da sessioni 566/567/568 — congelata come focus, nessun nuovo segnale |
| security | 26 | ~90% | Advanced | invariata da sessione 568 |
| iac | 14 | ~90% | Advanced | invariata da sessione 568 |
| cloud (totale) | 108 | n/d | n/d | solo AWS analizzato in profondità finora; Azure/GCP non campionati |
| ci-cd | 29 | n/d | n/d | non analizzata in profondità |
| dev | 28 | n/d | n/d | non analizzata in profondità |
| databases | 28 | n/d | n/d | non analizzata in profondità |
| ai | 27 | n/d | n/d | non analizzata in profondità |
| monitoring | 20 | n/d | n/d | non analizzata in profondità |

## Categorie vicine alla saturazione

- **messaging**: Kafka (48 file) e RabbitMQ (7 file) sono entrambi trattati con
  profondità expert, `related` ricchi, Troubleshooting multi-scenario. L'unico
  problema non è di contenuto ma di connettività dell'hub (vedi gap sotto).
- **containers**: registry (Harbor + ECR + mirror), container-runtime (CRI,
  containerd, CRI-O, runc, sandboxing gVisor/Kata/Firecracker) e openshift
  sono hub completi con percorsi di studio, decision matrix e troubleshooting
  reale. Nessun gap con `score: high`.
- **networking / cloud/aws**: 4 cicli di analisi consecutivi (566, 567, 568,
  non ri-analizzati in questo 569) a zero gap. Restano congelati.

## Categorie con gap reali

- **messaging/_index.md**: la grid card "Strumenti e Piattaforme" elenca solo
  Kafka; RabbitMQ (sezione completa, 7 file `status: complete`) non compare.
  Gap di connettività puro — contenuto esiste già, manca solo la porta
  d'ingresso dall'hub. → **prop-039** (extend-section, score high).

## Sessione proposal 2026-09-27 (task 569)

Gate: `file_count` 306, target 330, `over_target: false`, headroom 24.
`pending/` vuota prima di questa sessione; `approved/` invariata a prop-001..038.

Cambiato focus rispetto a 566/567/568 (che avevano esaurito networking/aws e
poi security/iac): letti 10 file tra `messaging/_index`, `messaging/rabbitmq/*`
(hub + confronto Kafka), `messaging/kafka/kubernetes-cloud/_index`,
`containers/_index`, `containers/registry/_index` + `harbor.md`,
`containers/container-runtime/_index` + `sandboxing-avanzato.md`,
`containers/openshift/_index`. Contenuto denso e maturo ovunque; un solo gap
reale trovato, di connettività (hub messaging), non di profondità.

Generata 1 proposta (prop-039). Scartati come non-gap: "RabbitMQ non ha una
pagina di troubleshooting dedicata" (già coperta come sezione dentro
`vs-kafka.md`, 4 scenari reali), "containers manca file su Docker Compose
production" (già `docker/compose.md` esistente, non campionato ma presente
nel glob), "openshift manca confronto costi ROSA/ARO vs self-managed" (score
medio, reperibile in 2 click nella doc ufficiale AWS/Azure — scartato per
regola PASSO 3).

## Prossima sessione consigliata

Cambiare focus su categorie mai campionate in profondità in questo ciclo di 4
sessioni: `cloud/azure` e `cloud/gcp` (parte dei 108 file cloud, solo AWS
analizzato finora), `ci-cd/` (29 file), `dev/` (28 file) o `databases/` (28
file). Continuare a congelare networking/aws/security/iac finché non arriva
nuovo segnale (file nuovi, modifiche, o completamento dei task `review`
pendenti sugli 8 file draft/needs-review già noti — tra cui
`containers/kubernetes/networking.md`, `cloud/aws/compute/containers-ecs-eks.md`,
`cloud/finops/fondamentali.md`, `networking/sicurezza/wireguard.md`,
`networking/load-balancing/nginx-haproxy.md`,
`networking/fondamentali/network-troubleshooting.md`,
`cloud/aws/networking/ipv6-dual-stack.md`).
