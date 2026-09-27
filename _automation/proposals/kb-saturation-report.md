# KB Saturation Report — 2026-09-27 (ciclo #591)

## Gate meccanico

```
file_count: 307 (manage-state.py saturation-gate)
target: 330
over_target: false
headroom: 23
category_saturated_pct: 85
```

Non satura. Ciclo precedente (auto #586, prop-050/051/052/053) ha già chiuso
i 4 file "draft" sostanziali (network-troubleshooting, nginx-haproxy,
wireguard, ipv6-dual-stack) — verificati oggi tutti promossi a `reviewed`
nei commit #587-590. `grep status: draft` su `docs/` restituisce **zero**
risultati in tutta la KB.

## Copertura stimata per categoria (focus sessione)

| Categoria | Files (Glob) | Coverage % | Depth | Note |
|-----------|-------|------------|-------|------|
| networking/ | 44 | ~90% | alta | Nessun draft residuo; 1 hub `needs-review` (kubernetes/_index) |
| cloud/aws/networking/ | 10 | ~90% | alta | Nessun draft residuo; hub `_index` `needs-review` |
| cloud/aws/ (totale) | ~46 | alta | alta | Copertura ampia, invariata |

## Categorie vicine alla saturazione

- **cloud/aws/networking/** e **networking/**: contenuto tecnico profondo,
  nessun draft residuo. Nuovi `new-file` ammessi solo con gap operativo
  esplicito (nessuno trovato in questo ciclo).

## Categorie con gap reali

- **Nessun gap di contenuto o navigazione nuovo** in `networking/` e
  `cloud/aws/networking/` in questo ciclo.
- **Pattern residuo, non un gap di contenuto**: 5 file in tutta la KB
  restano `status: needs-review` (nessuno `draft`). Due sono hub `_index`
  nel focus tematico corrente, mai certificati dopo l'ultima estensione:
  `docs/cloud/aws/networking/_index.md` (link Global Accelerator/API
  Gateway/VPC Lattice aggiunti dal ciclo precedente) e
  `docs/networking/kubernetes/_index.md` (sezione Gateway API aggiunta).
  Generate 2 proposte `review` mirate su questi due hub. Gli altri 3
  `needs-review` (`cloud/aws/compute/containers-ecs-eks.md`,
  `cloud/finops/fondamentali.md`, `containers/kubernetes/networking.md`)
  sono fuori dal focus tematico corrente e restano candidati per il
  prossimo ciclo con focus diverso.

## Proposte generate questo ciclo

- prop-054 (review, medium): docs/cloud/aws/networking/_index.md
- prop-055 (review, medium): docs/networking/kubernetes/_index.md

## Prossima sessione consigliata

Data: 2026-10-04 (o al prossimo ciclo `proposal` schedulato).
Focus tematico suggerito: chiudere i restanti 3 `needs-review` fuori focus
(`cloud/aws/compute/containers-ecs-eks.md`, `cloud/finops/fondamentali.md`,
`containers/kubernetes/networking.md`); verificare se `_automation/config.yaml`
debba includere `status: needs-review` tra i criteri di selezione automatica
per i task `review` (oggi basati solo su `last_verified`), dato che questi
file non hanno mai `last_verified` impostato e quindi non emergono nel ciclo
standard.
