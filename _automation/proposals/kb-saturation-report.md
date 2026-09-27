# KB Saturation Report — 2026-09-27 (sessione #627)

## Gate meccanico

```
file_count: 315, target: 330, over_target: false, headroom: 15
category_saturated_pct: 85, allow_zero_proposals: true
```

Sotto target. Raccomandazione della sessione precedente (#624): completare il
controllo mirato di connettività hub→figli su `docs/dev/**/_index.md` (mai
controllato con questo criterio) e su `docs/cloud/azure/*/_index.md` /
`docs/cloud/gcp/*/_index.md`.

## Copertura stimata per categoria

| Categoria | Files | Coverage % | Depth | Note |
|-----------|-------|------------|-------|------|
| dev/ | 9 sotto-hub (`_index.md`) + contenuti | contenuto maturo, gap di connettività | Hub padre `dev/_index.md` controllato: 7/9 sotto-hub raggiungibili dalla grid "Macro-Aree" | Gap reale: `runtime/_index.md` e `processi/_index.md` orfani (contenuto completo, non linkati) — prop-074 |
| cloud/azure/ | 11 sotto-hub | 100% connesso | Hub padre `cloud/azure/_index.md` controllato: 10/10 sotto-hub (escl. sé stesso) presenti nella grid "Mappa Servizi" | Nessun gap — coerente |
| cloud/gcp/ | 8 sotto-hub | gap di connettività | Hub padre `cloud/gcp/_index.md` controllato: 5/7 sotto-hub (escl. sé stesso) presenti nella grid "Mappa dei Servizi" | Gap reale: `iam/_index.md` e `messaging/_index.md` orfani (contenuto completo, non linkati) — prop-075, gap più rilevante perché IAM è cross-cutting e presente come card precoce sia su AWS che Azure |

## Categorie vicine alla saturazione

Confermate sature nelle sessioni precedenti (invariato): **databases/**,
**dev/linguaggi/**, **messaging/rabbitmq**, **cloud/aws** (contenuto e
connettività, corretto in #624), **ci-cd/** (prop-071), **security/**
(prop-072), **networking/** (verificato #621), **dev/testing, dev/data,
dev/resilienza, dev/sicurezza, dev/integrazioni**, **monitoring/**, **iac/**
(prop-067..070), **cloud/azure/** (100% connesso, confermato in questa
sessione).

## Categorie con gap reali

- **dev/_index.md**: 2/9 sotto-hub (`runtime`, `processi`) non raggiungibili
  dall'hub — prop-074 (high).
- **cloud/gcp/_index.md**: 2/7 sotto-hub (`iam`, `messaging`) non
  raggiungibili dall'hub — prop-075 (high).

## Focus usato in questa sessione

Controllo mirato di connettività hub→figli su `docs/dev/_index.md`,
`docs/cloud/azure/_index.md` e `docs/cloud/gcp/_index.md`, come raccomandato
da #624. Diversamente dall'ipotesi della sessione precedente ("il pattern sta
diventando raro"), qui il pattern è tornato **sistemico**: 2 categorie su 3
controllate avevano hub padre non aggiornato (dev, gcp), solo azure era
pulito. Il pattern "nuova sottocartella figlia nata dopo l'ultima modifica
della grid del genitore" resta la criticità strutturale dominante della KB.

## Prossima sessione consigliata

Non prima di 2026-10-04. Dato che il pattern hub→figli è riemerso con forza,
vale la pena un ultimo giro sistematico sui livelli **secondari** non ancora
controllati con questo criterio specifico: i sotto-hub di secondo livello
dentro `docs/cloud/aws/**/_index.md` erano già verificati (#624), ma
`docs/ai/**/_index.md` e `docs/ci-cd/**/_index.md` (sotto-hub interni, non
solo l'hub di categoria) non sono mai stati controllati con questo criterio.
Se anche lì il pattern è sistemico, valutare una regola strutturale
permanente (es. checklist nel protocollo "nuovo argomento" di CLAUDE.md che
imponga l'aggiornamento del genitore alla creazione di un nuovo `_index.md`)
invece di continuare a correggerlo caso per caso.
