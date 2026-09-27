# KB Saturation Report — 2026-09-27 (sessione #624)

## Gate meccanico

```
file_count: 315, target: 330, over_target: false, headroom: 15
category_saturated_pct: 85, allow_zero_proposals: true
```

Sotto target. Raccomandazione della sessione precedente (#621): completare il
controllo mirato di connettività hub→figli su `cloud/aws/*/_index.md` (11 hub,
mai controllati con questo criterio) e su `docs/dev/**/_index.md`.

## Copertura stimata per categoria

| Categoria | Files | Coverage % | Depth | Note |
|-----------|-------|------------|-------|------|
| cloud/aws/ | ~50 file (incl. 11 `_index`) | ~95% contenuto, gap di connettività hub | 11 hub controllati: iam (2/2), networking (9/9), monitoring (2/2), database (3/3), messaging (2/2), ci-cd (2/2), fondamentali (4/4), security (3/3), compute (4/4), storage (3/3) tutti coerenti | Gap reale trovato: hub di livello superiore `cloud/aws/_index.md` non elenca la sottosezione `containers/` (EKS, status complete) nella sua grid "Mappa dei Servizi" — 10 card su 11 |

## Categorie vicine alla saturazione

- **cloud/aws/**: contenuto e struttura interna dei sotto-hub confermati
  maturi e coerenti in questa sessione (10 hub su 11 già perfettamente
  connessi). Unico gap: hub di primo livello.
- Confermate sature nelle sessioni precedenti (invariato): **databases/**,
  **dev/linguaggi/**, **messaging/rabbitmq**, **cloud/aws** (contenuto, non
  connettività — vedi gap sopra), **ci-cd/** (connettività già corretta da
  prop-071), **security/** (connettività già corretta da prop-072),
  **networking/** (nessun gap, verificato in #621), **dev/testing, dev/data,
  dev/resilienza, dev/sicurezza, dev/integrazioni**, **monitoring/**, **iac/**
  (connettività già corretta da prop-067..070).

## Categorie con gap reali

- **cloud/aws/_index.md**: 1/11 sottosezioni (`containers/`) non raggiungibile
  dall'hub principale — prop-073 (medium).

## Focus usato in questa sessione

Controllo mirato di connettività hub→figli su tutti gli 11 hub di
`docs/cloud/aws/`, come raccomandato da #621. Pattern "hub padre non
aggiornato quando nasce una nuova sottocartella" confermato anche qui, ma
questa volta isolato: solo l'hub di primo livello (`cloud/aws/_index.md`) ha
un gap, mentre tutti gli 11 sotto-hub controllati sono internamente coerenti
(nessun figlio orfano). A differenza delle sessioni precedenti (monitoring,
iac, ci-cd, security dove il pattern era diffuso), qui il pattern è meno
sistemico — probabile segnale che il pattern stia diventando raro nella KB
man mano che viene corretto categoria per categoria.

## Prossima sessione consigliata

Non prima di 2026-10-04. Suggerito completare lo stesso controllo mirato di
connettività hub→figli su `docs/dev/**/_index.md` (mai controllato con questo
criterio, come indicato da #621) e su `docs/cloud/azure/*/_index.md` e
`docs/cloud/gcp/*/_index.md` (11 e 8 hub, mai controllati). Se anche lì il
pattern risulta ormai raro (come qui, 1 gap su 11 hub), valutare di chiudere
questo filone di controllo strutturale e tornare a una verifica di
completezza di contenuto (non solo connettività) su `docs/cloud/azure/` e
`docs/cloud/gcp/`, mai riverificate da questo punto di vista.
