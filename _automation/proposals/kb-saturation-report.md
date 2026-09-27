# KB Saturation Report — 2026-09-27

## Gate meccanico

```
file_count: 307, target: 330, over_target: false, headroom: 23
category_saturated_pct: 85, allow_zero_proposals: true
```

Sotto target a livello globale, ma il **focus tematico corrente** (`docs/networking/`,
`docs/cloud/aws/`) risulta saturo nei fatti — vedi sotto.

## Copertura stimata per categoria

| Categoria | Files | Coverage % | Depth | Note |
|-----------|-------|------------|-------|------|
| networking | 44 | ~90% | Alta | 8 sottocategorie, hub `_index` ricchi, `related` densi |
| cloud/aws | 43 | ~90% | Alta | 8 sottocategorie, review recenti (#590-593), `vpc-avanzato`/`vpc-lattice` copre già Transit Gateway/PrivateLink/Direct Connect |
| messaging | 55 | ~95% | Molto alta | Kafka quasi enciclopedico (7 sottosezioni), RabbitMQ completo |
| cloud (totale) | 109 | ~75% | Media-alta | AWS saturo, Azure/GCP meno profondi ma fuori focus |
| containers | 38 | ~80% | Alta | — |
| databases | 28 | ~70% | Media | — |
| security | 26 | ~70% | Media | — |
| ci-cd | 29 | ~75% | Media-alta | — |
| ai | 27 | ~75% | Media-alta | — |
| dev | 28 | ~65% | Media | — |
| monitoring | 20 | ~60% | Media | — |
| iac | 14 | ~55% | Bassa-media | Sottodimensionata rispetto al resto |

## Categorie vicine alla saturazione

- **networking**: ogni sottocategoria (fondamentali, protocolli, load-balancing,
  service-mesh, sicurezza, api-gateway, kubernetes) ha hub `_index` con card
  complete e cross-link ricchi. Nessun file `draft`/`needs-review` residuo.
- **cloud/aws/networking**: 9 file, tutti `complete` o `reviewed`, `last_updated`
  concentrati nelle ultime settimane. Transit Gateway, PrivateLink, Direct Connect,
  VPC Flow Logs, Reachability Analyzer sono già trattati (in `vpc-avanzato.md`,
  `vpc.md`, `network-security.md`) — non isole scoperte, gap simmetrici scartati
  per regola PASSO 3.
- **messaging/kafka**: 7 sottosezioni, quasi ogni pattern enterprise già coperto
  (CQRS, Saga, Outbox, exactly-once, schema registry, sicurezza SASL/TLS/ACL).

## Categorie con gap reali

- **iac**: solo 14 file per 3 tecnologie (terraform+opentofu, pulumi, ansible) —
  sottodimensionata rispetto a containers/networking, ma **fuori focus tematico**
  di questo ciclo (`networking`/`cloud/aws`). Da considerare nella prossima sessione
  senza focus ristretto.
- **monitoring** e **databases**: coverage media, ma anch'esse fuori focus corrente.

Nessun gap reale trovato dentro il focus richiesto (`networking/`, `cloud/aws/`)
che superi il test di utilità (PASSO 3): tutti i candidati esaminati sono già
coperti con profondità operativa (comandi reali, tabelle di confronto, sezioni
Troubleshooting) e connettività (`related` con 3-5 voci ciascuno).

## Decisione: 0 proposte

10 file analizzati in profondità (`vpc-avanzato.md`, `protocolli/_index.md`,
`gateway-api.md`, `containers-ecs-eks.md`, `zero-trust.md`, `vpc-lattice.md`,
`global-accelerator.md`, `ha-e-failover.md`, `network-policies.md`,
`cloud/aws/networking/_index.md`). Nessuno supera il test di utilità per una
nuova proposta: o il contenuto è già completo e reviewed, o il gap ipotizzato
(es. file dedicato a Transit Gateway/PrivateLink) è già assorbito in un file
esistente con profondità sufficiente — creare un file gemello sarebbe
simmetria formale, non gap operativo (regola di scarto esplicita PASSO 3).

Il backlog `draft`/`needs-review` residuo (`containers-ecs-eks.md`,
`cloud/finops/fondamentali.md`, `containers/kubernetes/networking.md`) è già
gestito dai task `review`/`expand` esistenti in coda, non richiede proposte.

## Prossima sessione consigliata

2026-10-04+ — spostare il focus tematico fuori da `networking`/`cloud/aws`
(entrambi saturi) verso **`iac/`** (sottodimensionata, 14 file) o
**`monitoring/`** e **`databases/`** (coverage media), dove il gate di
saturazione ha più margine reale per proposte `new-file` ad alto score.
