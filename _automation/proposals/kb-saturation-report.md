# KB Saturation Report — 2026-09-27 (sessione 5, task 571)

## Copertura stimata per categoria

| Categoria | Files | Coverage % | Depth | Note |
|-----------|-------|------------|-------|------|
| KB totale | 306 (gate) / ~309 (glob, esclusi index/tags/template) | n/a | n/a | `target_file_count` 330, `over_target: false`, headroom 24 |
| networking | 44 | ~88% | Advanced | 4 file `status: draft` scoperti in questo ciclo (network-troubleshooting, nginx-haproxy, wireguard, +1 in cloud/aws) — contenuto completo ma isolati dai rispettivi hub `_index.md`. Non più "congelata": 3 gap di connettività reali trovati. |
| cloud/aws | 44 | ~90% | Advanced | 1 file draft isolato (ipv6-dual-stack) + 1 file `needs-review` non ancora chiuso (containers-ecs-eks). Non più "congelata": 2 gap trovati. |
| messaging | 55 | ~92% | Advanced | invariata da sessione 569 (gap hub già coperto da prop-039, ancora pending) |
| containers | 38 | ~90% | Advanced/Expert | invariata da sessione 569 |
| security | 26 | ~90% | Advanced | invariata da sessione 568 |
| iac | 14 | ~90% | Advanced | invariata da sessione 568 |
| cloud (totale) | 108 | n/d | n/d | solo AWS analizzato in profondità; Azure/GCP non campionati in questo ciclo |
| ci-cd | 29 | n/d | n/d | non analizzata in profondità |
| dev | 28 | n/d | n/d | non analizzata in profondità |
| databases | 28 | n/d | n/d | non analizzata in profondità |
| ai | 27 | n/d | n/d | non analizzata in profondità |
| monitoring | 20 | n/d | n/d | non analizzata in profondità |

## Categorie vicine alla saturazione

- **networking / cloud/aws**: contenuto tecnico maturo, ma questo ciclo ha
  rivelato un problema di **processo** più che di contenuto: file creati il
  2026-09-26 (probabilmente da un task `new_topic` recente) restano in
  `status: draft` pur superando ampiamente il gate meccanico per `complete`
  (righe, code-block, Troubleshooting, keyword, related), e non sono mai
  stati agganciati agli hub `_index.md` delle rispettive sottocategorie. Non
  è un gap di saturazione ma un gap di **integrazione post-creazione** —
  vedi prop-040..043.
- **messaging / containers / security / iac**: confermate sature, nessun
  nuovo segnale in questo ciclo (non ri-analizzate).

## Categorie con gap reali

- **docs/networking/fondamentali/_index.md**: non elenca
  `network-troubleshooting.md` (completo, 540 righe). → **prop-040**.
- **docs/networking/load-balancing/_index.md**: non elenca
  `nginx-haproxy.md` (completo, 489 righe). → **prop-041**.
- **docs/networking/sicurezza/_index.md**: non elenca `wireguard.md`
  (completo, 366 righe). → **prop-042**.
- **docs/cloud/aws/networking/_index.md**: non elenca
  `ipv6-dual-stack.md` (completo, 376 righe, driver economico diretto:
  costo IPv4 pubblico AWS). → **prop-043**.
- **docs/cloud/aws/compute/containers-ecs-eks.md**: `status: needs-review`
  da una modifica precedente, mai chiuso da un task `review`. → **prop-044**.

Pattern trasversale da segnalare (non una proposta a sé, annotato nelle 4
proposte `extend-section`): i 4 file draft sopra sono probabilmente l'output
di un batch di `new_topic` che non ha eseguito il passo finale di
integrazione nell'hub né la promozione di stato. Vale la pena, in un
prossimo ciclo `audit`, controllare se altri file recenti hanno lo stesso
problema (draft + assente dagli hub) oltre ai 4 già trovati qui.

## Sessione proposal 2026-09-27 (task 571)

Gate: `file_count` 306, target 330, `over_target: false`, headroom 24.
`pending/` conteneva prop-001..039 (tutte in attesa) prima di questa
sessione; `approved/` vuota.

Letti 5 file completi (i 4 draft + containers-ecs-eks.md) più le 6 pagine
hub `_index.md` di networking/fondamentali, networking/load-balancing,
networking/sicurezza, networking (root), cloud/aws/networking — per
verificare l'assenza di riferimenti. Confermato con grep che nessun file
della KB (eccetto i 2 `related` incrociati già esistenti: cni.md e
vpn-ipsec.md) referenzia i 4 file draft.

**Proposte generate: 5** (prop-040..044), tutte a priorità
high/medium, effort small, nel focus tematico richiesto (networking +
cloud/aws). Nessuna proposta `new-file`: il freno di saturazione (headroom
24) l'avrebbe ammessa, ma non è emerso alcun gap di contenuto mancante con
`score: high` in queste due categorie — solo gap di connettività e di
status/processo, già coperti.

## Prossima sessione consigliata

**Data**: 2026-10-04 (prossimo ciclo settimanale). **Focus**: verificare se
il pattern "draft + assente dall'hub" si ripete su altri file creati di
recente (grep `status: draft` su tutta la KB, non solo networking/cloud-aws);
se prop-040..044 sono state approvate ed eseguite, ri-analizzare
containers/security/iac per un nuovo gap dato che networking/cloud-aws
restano temi ricorrenti da 5 cicli.
