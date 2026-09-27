# KB Saturation Report — 2026-09-27 (sessione #642)

## Gate meccanico

```
file_count: 314, target: 330, over_target: false, headroom: 16
category_saturated_pct: 85, allow_zero_proposals: true
```

Sotto target. Focus raccomandato dalla sessione precedente (#638): continuare
il controllo di connettività hub→figli su `ci-cd/**`, `messaging/**`,
`databases/**` (categorie rimaste da riverificare dopo #634/#637/#638).

## Copertura stimata per categoria

| Categoria | Files | Coverage % | Depth | Note |
|-----------|-------|------------|-------|------|
| ci-cd/** (9 sotto-hub + 1 top) | 30 file totali | — | Controllati tutti i 9 sotto-hub + il grid top-level | 1 gap: `pipeline.md` orfano dal top-level `_index.md` |
| messaging/** (kafka 9 sotto-hub + rabbitmq + top) | 55 file totali | — | Controllati kafka (9 sotto-hub), rabbitmq (flat), top-level | 0 gap — categoria pulita |
| databases/** (7 sotto-hub + top) | 31 file totali | — | Controllati tutti i 7 sotto-hub + top-level | 1 gap: `schema-migrations.md` orfano da `fondamentali/_index.md` |

## Categorie vicine alla saturazione

Confermate sature nelle sessioni precedenti (invariato): **databases/**
(contenuto — la connettività aveva un gap, ora proposto fix), **dev/linguaggi/**,
**messaging/rabbitmq** (contenuto — connettività ora verificata pulita),
**cloud/aws**, **networking/**, **dev/testing, dev/data, dev/resilienza
(contenuto), dev/sicurezza, dev/integrazioni (contenuto)**, **monitoring/**,
**iac/**, **cloud/azure/**, **ai/**, **security/**.

## Categorie con gap reali

Trovati **2 hub orfani**, stesso pattern delle sessioni precedenti (figlio
completo, frontmatter `parent` corretto, ma zero link dal corpo dell'`_index.md`
del genitore):

- **ci-cd/_index.md** — non linka `pipeline.md`, unico file di secondo
  livello che vive senza sottocartella propria (tutti gli altri 8 sotto-hub
  di ci-cd sono invece linkati e connessi correttamente al 100%: github-actions,
  gitlab-ci, gitops, jenkins, platform-engineering, strategie, testing, tools).
  → prop-083 (high).
- **databases/fondamentali/_index.md** — non linka `schema-migrations.md`,
  aggiunto dopo i 5 figli originali (acid-base-cap, modelli-dati, indici,
  transazioni-concorrenza, sharding) e mai inserito nel grid "## Argomenti".
  Tutti gli altri 6 sotto-hub di databases sono puliti al 100%: kubernetes-cloud,
  nosql, postgresql, replicazione-ha, sql-avanzato, mysql. Anche il top-level
  `databases/_index.md` è pulito (mysql confermato linkato correttamente).
  → prop-084 (high).

Sotto-hub controllati e puliti (nessun gap): tutti i 9 sotto-hub Kafka
(fondamenti, kafka-connect, kafka-streams, kubernetes-cloud, operazioni,
pattern-microservizi, schema-registry, sicurezza, sviluppo), rabbitmq
(flat, 6/6 figli linkati), messaging/_index.md top-level.

## Focus usato in questa sessione

Come raccomandato da #638: completamento del controllo di connettività
hub→figli su `ci-cd/**`, `messaging/**`, `databases/**`. Risultato: 2 gap su
17 sotto-hub verificati in questa sessione (~12%), messaging risultata
categoria completamente pulita (0/9 sotto-hub Kafka + rabbitmq + top). Bilancio
cumulativo del pattern "hub non aggiornato dopo creazione nuovo figlio" su
tutte le sessioni: 5 gap totali (dev/api, dev/resilienza, dev/integrazioni,
ci-cd/pipeline, databases/schema-migrations) su circa 26 sotto-hub controllati
nelle sessioni #634/#637/#638/#642 (~19%) — sotto la soglia 40% osservata
prima in dev/**, ma comunque un pattern ricorrente e a basso costo di fix
(sempre `fix-relation` da poche righe). Conferma il valore di aggiungere una
checklist esplicita "aggiorna il grid del genitore" al protocollo 1️⃣ Nuovo
Argomento in CLAUDE.md — segnalato di nuovo, non applicato in questa sessione
perché fuori scope (agente di contenuto, non modifica-CLAUDE.md).

## Prossima sessione consigliata

Non prima di 2026-10-04. Categorie ancora da controllare con questo
criterio: `networking/**`, `iac/**`, `monitoring/**`, `security/**`, `ai/**`,
`cloud/**` (aws/azure già confermate pulite in #638, gcp/finops non ancora
verificate), `containers/**` (gap noto da sessioni precedenti — verificare se
prop-078/079 sono state applicate). In alternativa: proposta `review` per
introdurre la checklist "grid genitore" nel protocollo 1️⃣ di CLAUDE.md, dato
che il pattern è ora confermato in 3 sessioni consecutive su categorie diverse.
