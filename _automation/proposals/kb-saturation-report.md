# KB Saturation Report — 2026-09-27

## Gate meccanico

```
file_count: 307 (manage-state.py saturation-gate)
target: 330
over_target: false
headroom: 23
category_saturated_pct: 85
```

Non satura (`allow_zero_proposals: true` ma non necessario). Ciclo precedente
(2026-09-27, prop-047/048/049) aveva chiuso i gap di navigazione/contenuto
trovati allora (Gateway API non linkato, ELB/API GW/VPC Lattice non linkati,
Global Accelerator mancante) — verificati oggi tutti risolti negli `_index.md`
e il file `global-accelerator.md` esiste. Nessun nuovo gap di contenuto o
navigazione emerso in `networking/` e `cloud/aws/networking/` in questo giro.

## Copertura stimata per categoria (focus sessione)

| Categoria | Files (Glob) | Coverage % | Depth | Note |
|-----------|-------|------------|-------|------|
| networking/ | 44 | ~90% | alta | Contenuto e navigazione ok; 4 file "draft" di alta qualità mai promossi |
| cloud/aws/networking/ | 10 | ~90% | alta | Gap ciclo precedente chiusi; 1 file "draft" di alta qualità (ipv6-dual-stack) |
| cloud/aws/ (totale) | ~46 | alta | alta | Copertura ampia, invariata |

## Categorie vicine alla saturazione

- **cloud/aws/networking/** e **networking/**: contenuto tecnico già molto
  profondo. Nuovi `new-file` ammessi solo con gap operativo esplicito
  (nessuno trovato in questo ciclo). Il valore residuo sta nella qualità/
  affidabilità del contenuto esistente, non in nuovi argomenti.

## Categorie con gap reali

- **Nessun gap di contenuto o navigazione nuovo** trovato in `networking/`
  e `cloud/aws/networking/` in questo ciclo (i 3 gap del ciclo precedente
  risultano chiusi).
- **Gap trasversale identificato**: 4 file sostanziali (297–541 righe,
  troubleshooting completo, `related` ricchi) sono fermi a `status: draft`
  da `last_updated: 2026-09-26` pur superando il gate meccanico —
  `network-troubleshooting.md`, `nginx-haproxy.md`, `wireguard.md`
  (networking/) e `ipv6-dual-stack.md` (cloud/aws/networking/). Senza un
  passaggio esplicito restano "draft" a tempo indeterminato, invisibili
  alla percezione di affidabilità del lettore e potenzialmente al ciclo di
  `last_verified` (mai impostato). Generate 4 proposte `review` mirate.

## Proposte generate questo ciclo

- prop-050 (review, medium): docs/networking/fondamentali/network-troubleshooting.md
- prop-051 (review, medium): docs/networking/load-balancing/nginx-haproxy.md
- prop-052 (review, medium): docs/networking/sicurezza/wireguard.md
- prop-053 (review, high): docs/cloud/aws/networking/ipv6-dual-stack.md

## Prossima sessione consigliata

Data: 2026-10-04 (o al prossimo ciclo `proposal` schedulato).
Focus tematico suggerito: verificare se lo stesso pattern di "draft
sostanziale mai promosso" esiste in altre categorie profonde (es.
`docs/security/`, `docs/ci-cd/jenkins/`) e se `_automation/config.yaml`
debba includere `status: draft` con `last_updated` vecchio tra i criteri di
selezione per i task `review` (oggi basati solo su `last_verified`).
