# KB Saturation Report — 2026-09-27 (sessione #662)

## Gate meccanico

```
file_count: 314, target: 330, over_target: false, headroom: 16, category_saturated_pct: 85
```

Invariato dalle sessioni precedenti (#649, #651, #653, #656, #659). Sotto
target, espansione ammessa ma solo con gap reali (vedi PASSO 0/3 del prompt).

## Focus usato in questa sessione

Il report di #659 raccomandava un primo giro content-focused su
`databases/postgresql/` (file esistenti ma mai letti per contenuto). Letti
tutti e 4 i file (`connection-pooling.md`, `extensions.md`, `mvcc-vacuum.md`,
`replicazione.md`) più `_index.md`, e per contesto comparativo
`databases/replicazione-ha/strategie-replica.md` e
`databases/mysql/architettura-replicazione.md`. In più, 3 file `needs-review`
individuati con Grep: `containers/kubernetes/networking.md`,
`cloud/aws/compute/containers-ecs-eks.md`, `cloud/finops/fondamentali.md`.

Nota: la raccomandazione indicava "non prima di 2026-10-04" per il prossimo
giro content-focused pieno, ma questo task era già in coda (P2, dispatch
automatico) al 2026-09-27 — la sessione ha proceduto comunque, dando priorità
comunque alla qualità sopra la quantità (vedi risultato sotto).

## Risultato

I 4 file `postgresql/` sono **maturi e completi**: contenuto denso e
tecnicamente corretto (MVCC/vacuum/XID wraparound, streaming e logical
replication, PgBouncer pool mode, pgvector/TimescaleDB/PostGIS/pg_cron),
sezioni Troubleshooting con scenari multipli, `status: complete` giustificato.
Nessun gap di contenuto (`new-file` / `extend-section`) — stesso pattern di
maturità già osservato in `iac/` (#659), `cloud/aws/` (#653), `cloud/azure/`
(#656).

Due gap di **connettività** interna alla cartella `postgresql/`, verificati
leggendo direttamente i 4 file (non solo l'indice):
- `extensions.md` non è linkato da/verso nessuno dei tre fratelli
  (`connection-pooling`, `mvcc-vacuum`, `replicazione`) — isolato salvo il
  collegamento tramite `_index.md`. → prop-099 (low, fix-relation).
- `connection-pooling.md` linka `mvcc-vacuum.md` in un'admonition, ma
  `mvcc-vacuum.md` non reciproca nel proprio `related` — relazione
  asimmetrica. → prop-100 (low, fix-relation).

Tre gap di **freschezza/certificazione** sui file `needs-review` trovati con
Grep (non erano nel focus tematico ma segnalati dal gate meccanico
`status: needs-review`):
- `cloud/finops/fondamentali.md`: `needs-review` da **6 mesi**
  (`last_updated: 2026-03-29`), mai passato a `reviewed`, nessun
  `last_verified` mai impostato — il gap di freschezza più vecchio trovato
  finora. → prop-096 (**high**, review).
- `containers/kubernetes/networking.md`: espanso oggi stesso (>800 righe,
  molte tabelle comparative nuove) — merita la revisione che il gate
  richiede prima di tornare stabile. → prop-097 (medium, review).
- `cloud/aws/compute/containers-ecs-eks.md`: contiene un commento
  `<!-- REVIEW: ... -->` esplicito e non risolto sullo stato di App Runner.
  → prop-098 (medium, review).

Nessuna proposta `new-file` in questa sessione — pattern ormai consistente
da 4 sessioni consecutive (#653, #656, #659, #662): il contenuto esistente è
maturo, i gap reali sono di connettività e di certificazione (`review`), non
di copertura.

## Categorie vicine alla saturazione

Invariato: **databases/**, **dev/linguaggi/**, **messaging/rabbitmq**,
**cloud/aws**, **networking/**, **dev/testing, dev/data, dev/resilienza,
dev/sicurezza, dev/integrazioni**, **monitoring/**, **ai/**, **security/**,
**containers/**, **messaging/kafka/**, **cloud/azure/**, **iac/**. Con
questa sessione si conferma di alta qualità (content-read) anche
`databases/postgresql/` (4/4 file letti).

## Categorie con gap reali

Nessun gap di contenuto. Gap residui: connettività isolata (2, in
`postgresql/`) e certificazione di freschezza mancante/scaduta su 3 file
`needs-review` (uno dei quali fermo da 6 mesi — priorità alta).

## Prossima sessione consigliata

Non prima di 2026-10-04, come da raccomandazione precedente. Suggerito:
applicare prop-096/097/098/099/100 (se approvate) e passare a un primo giro
content-focused su `monitoring/` o `security/` — mai state in focus finora
nonostante siano segnalate "vicine alla saturazione" da diverse sessioni
consecutive senza mai essere state verificate a livello di contenuto. In
alternativa, dato che il pattern "review su needs-review vecchi" si è
rivelato produttivo in questa sessione, un giro dedicato a un Grep di tutti
i `status: needs-review` residui nella KB (oltre ai 3 trovati qui) potrebbe
chiudere debito di qualità accumulato prima di aprire nuovi fronti di
contenuto.
