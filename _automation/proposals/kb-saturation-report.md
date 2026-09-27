# KB Saturation Report — 2026-09-27

## Gate meccanico

```
file_count: 306 (conteggio manage-state.py)
target: 330
over_target: false
headroom: 24
category_saturated_pct: 85
```

Non satura. `allow_zero_proposals: true` ma non necessario in questo ciclo:
trovati 2 gap di connettività reali (costo quasi zero, impatto alto) + 1 gap
di contenuto (AWS Global Accelerator) nel focus tematico richiesto.

## Copertura stimata per categoria (focus sessione)

| Categoria | Files (Glob) | Coverage % | Depth | Note |
|-----------|-------|------------|-------|------|
| networking/ | 44 | ~90% | alta | Contenuto completo; gap solo di navigazione (Gateway API non linkato dagli _index) |
| cloud/aws/networking/ | 9 | ~85% | alta | Contenuto completo (VPC, VPC avanzato, IPv6, Route53, CloudFront, ELB, API GW, VPC Lattice); gap di navigazione (3/8 file non in _index) + 1 gap di contenuto (Global Accelerator) |
| cloud/aws/ (totale) | ~46 | alta | alta | Copertura ampia su compute, storage, database, iam, security, monitoring, messaging |

## Categorie vicine alla saturazione

- **cloud/aws/networking/**: contenuto tecnico già molto profondo (VPC,
  routing, DNS, CDN, load balancing, application networking). Nuovi
  `new-file` qui ammessi solo con gap operativo esplicito e non banale
  (vedi Global Accelerator, unico caso trovato).
- **networking/** (generale): tutte le 7 sotto-aree del percorso di
  studio hanno già file `status: complete` multipli. Ulteriore
  espansione con `new-file` va giustificata con score `high` esplicito.

## Categorie con gap reali

- **Navigazione/connettività** (trasversale, non categoria specifica):
  2 casi confermati di file `status: complete` e sostanziali (297–457
  righe) esistenti ma non raggiungibili dagli `_index.md` della propria
  categoria — gateway-api.md (networking/kubernetes) e 3 file in
  cloud/aws/networking (ELB, API Gateway, VPC Lattice). Pattern da
  tenere d'occhio in futuri audit: un file "complete" isolato dalla
  navigazione vale meno di uno collegato.
- **AWS Global Accelerator**: servizio distinto senza file proprio,
  oggi solo citato di sfuggita in elastic-load-balancing.md.

## Proposte generate questo ciclo

- prop-047 (extend-section, high): Gateway API → docs/networking/_index.md
  + kubernetes/_index.md
- prop-048 (extend-section, high): ELB/API Gateway/VPC Lattice →
  docs/cloud/aws/networking/_index.md
- prop-049 (new-file, medium): docs/cloud/aws/networking/global-accelerator.md

## Prossima sessione consigliata

Data: 2026-10-04 (o al prossimo ciclo `proposal` schedulato).
Focus tematico suggerito: verificare se lo stesso pattern di "file
completo ma non linkato dall'_index" esiste in altre categorie ad alta
profondità (es. `docs/security/`, `docs/ci-cd/jenkins/`) prima di
generare nuovi `new-file`. Il focus tematico corrente (networking +
aws) resta valido finché non emergono gap `score: high` altrove.
