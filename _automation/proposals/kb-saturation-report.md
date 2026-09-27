# KB Saturation Report — 2026-09-27 (sessione #638)

## Gate meccanico

```
file_count: 314, target: 330, over_target: false, headroom: 16
category_saturated_pct: 85, allow_zero_proposals: true
```

Sotto target. Focus raccomandato dalla sessione precedente (#637): controllo
di connettività hub→figli sui sotto-hub interni di `docs/dev/**` (categoria
più popolosa e composita, mai controllata con questo criterio prima d'ora).

## Copertura stimata per categoria

| Categoria | Files | Coverage % | Depth | Note |
|-----------|-------|------------|-------|------|
| dev/** (9 sotto-hub) | 28 file totali | — | Controllati tutti e 9 i sotto-hub (`api`, `data`, `integrazioni`, `linguaggi`, `processi`, `resilienza`, `runtime`, `sicurezza`, `testing`) | 3 gap trovati (vedi sotto) su 9 sotto-hub controllati |

## Categorie vicine alla saturazione

Confermate sature nelle sessioni precedenti (invariato): **databases/**,
**dev/linguaggi/**, **messaging/rabbitmq**, **cloud/aws**, **networking/**,
**dev/testing, dev/data, dev/resilienza (contenuto), dev/sicurezza,
dev/integrazioni (contenuto)**, **monitoring/**, **iac/**, **cloud/azure/**,
**ai/**, **security/**.

## Categorie con gap reali

Trovati **3 hub orfani** in `docs/dev/**` — file figli esistenti, completi,
ma con **zero link** dall'`_index.md` del proprio sotto-hub (verificato con
grep sull'intero corpo di ciascun file, non solo il frontmatter):

- **dev/api/_index.md** — non linka `rest-openapi.md`, il suo UNICO figlio.
  → prop-080 (high).
- **dev/resilienza/_index.md** — non linka nessuno dei 3 figli
  (`circuit-breaker.md`, `health-checks.md`, `observability-code.md`;
  `health-checks` compare solo nel frontmatter `related`, non nel corpo).
  → prop-081 (high).
- **dev/integrazioni/_index.md** — non linka nessuno dei 2 figli
  (`database-patterns.md`, `rabbitmq-client.md`). → prop-082 (medium).

Sotto-hub controllati e puliti: `dev/data` (monolitico, nessun figlio
previsto), `dev/testing` (monolitico, nessun figlio previsto), `dev/linguaggi`
(6/6 figli linkati), `dev/processi` (3/3 linkati), `dev/runtime` (2/2
linkati), `dev/sicurezza` (2/2 linkati).

## Focus usato in questa sessione

Come raccomandato da #637: controllo di connettività sui sotto-hub interni
di `docs/dev/**`. Risultato: 3 gap su 9 sotto-hub (33%), la percentuale più
alta finora tra le categorie controllate con questo criterio. Aggiornando il
conteggio complessivo: 4 categorie pulite (`ai`, `security`, `cloud/aws`,
`cloud/azure`) vs 3 con gap (`ci-cd`, `containers`, `dev`) su 7 categorie
verificate finora. Il pattern "hub non aggiornato dopo la creazione di nuovi
figli" continua a manifestarsi soprattutto nelle categorie con crescita
recente più intensa — coerente con l'osservazione di #634/#637. Vale la pena
valutare, in una prossima sessione `review` o modifica a CLAUDE.md, una
checklist esplicita "aggiorna il grid del genitore" nel protocollo 1️⃣ Nuovo
Argomento: 3 categorie su 7 con gap (43%) non è più rumore statistico.

## Prossima sessione consigliata

Non prima di 2026-10-04. Restano da controllare con questo criterio:
`ci-cd/**` (gap già noto ma non riverificato dopo prop-078/prop-079),
`messaging/**`, `databases/**`. In alternativa, valutare se aprire una
proposta `review`/modifica CLAUDE.md per rendere permanente il controllo
"grid genitore aggiornata" nel protocollo di creazione nuovo argomento, dato
il tasso di ricorrenza ormai sopra il 40%.
