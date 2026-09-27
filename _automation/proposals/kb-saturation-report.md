# KB Saturation Report — 2026-09-27 (sessione #613)

## Gate meccanico

```
file_count: 315, target: 330, over_target: false, headroom: 15
category_saturated_pct: 85, allow_zero_proposals: true
```

Sotto target. Focus da report #610: `docs/databases/` (file di dettaglio non
ancora letti: `postgresql/extensions.md`, `nosql/cassandra.md`,
`kubernetes-cloud/db-su-kubernetes.md`) e completamento `docs/dev/` (`runtime`,
`processi`, dettagli `linguaggi`: `go.md`, `python.md`, `java-quarkus.md`,
`dotnet.md`).

## Copertura stimata per categoria

| Categoria | Files | Coverage % | Depth | Note |
|-----------|-------|------------|-------|------|
| databases/ (dettaglio) | 3 letti (extensions, cassandra, db-su-kubernetes) | ~95% | Molto alta: ognuno 300-500 righe, 4-5 scenari di troubleshooting con comandi reali, best practice specifiche, nessuna sezione mancante rispetto al proprio official_docs | Nessun gap reale — confermano la valutazione "alta coverage" di #609/#610 |
| dev/linguaggi/ (dettaglio) | 4 letti (go, python, dotnet, java-quarkus) + _index | ~95% | Molto alta: Panoramica con quando-usare/quando-non-usare, tabella comparativa coerente nell'_index, tutti i 6 linguaggi (incl. Node.js, verificato integrato da sessione #611/#612) ora presenti | Gap #2 di #610 (Node.js mancante) risulta chiuso: file esiste e _index lo referenzia |
| dev/runtime/, dev/processi/ | 2 _index letti | Alta come hub, ma **isolati nel grafo `related`** | Struttura a schede coerente con pattern hub validato altrove | Gap di connettività trovato (non di contenuto) — vedi sotto |

## Analisi di questa sessione

File analizzati (10): `databases/postgresql/extensions.md`,
`databases/nosql/cassandra.md`, `databases/kubernetes-cloud/db-su-kubernetes.md`,
`dev/runtime/_index.md`, `dev/processi/_index.md`, `dev/linguaggi/go.md`,
`dev/linguaggi/python.md`, `dev/linguaggi/_index.md`, `dev/linguaggi/dotnet.md`,
`dev/linguaggi/java-quarkus.md`. Verificati inoltre via `grep` i campi `related`
di `dev/api/_index`, `dev/resilienza/_index`, `dev/integrazioni/_index`,
`ci-cd/_index`, `dev/_index` per la coerenza bidirezionale.

**Verificato NON un gap — contenuto databases/ e dev/linguaggi/**: tutti i file
letti sono completi, con troubleshooting operativo reale (comandi `nodetool`,
`kubectl cnpg`, query SQL diagnostiche) e nessuna sezione promessa-e-assente.
Il gap Node.js segnalato in #610 è chiuso (nodejs.md esiste, `_index.md`
aggiornato `last_updated: 2026-09-27`).

**Gap reale #1 — `dev/linguaggi/_index.md` isola nel grafo `related`**:
`related: []` nonostante sia citato da `dev/api/_index` e (per due file figli)
da `dev/runtime/_index`. Nessun link di ritorno. → prop-065 (fix-relation).

**Gap reale #2 — `dev/processi/_index.md` completamente irraggiungibile via
`related`**: campo assente dal frontmatter, e `grep -rn "dev/processi" docs/`
non trova nessun riferimento da altri file. Tema (branching strategy, quality
gate, DORA metrics) fortemente sovrapposto a `ci-cd/`, che non lo referenzia.
→ prop-066 (fix-relation, tocca anche `ci-cd/_index.md` per la reciprocità).

## Categorie vicine alla saturazione

- **databases/** (incl. dettagli postgresql/nosql/kubernetes-cloud): confermata
  satura — coverage alta, nessun gap di contenuto in questa sessione.
- **dev/linguaggi/**: confermata satura per contenuto (6/6 linguaggi coperti,
  simmetria tra file completa); gap residuo solo di connettività (prop-065).
- **security/**, **messaging/rabbitmq**, **networking**, **cloud/aws**,
  **ci-cd/testing**, **dev/testing, dev/data, dev/resilienza, dev/sicurezza,
  dev/integrazioni**: confermati saturi nelle sessioni precedenti (#591-596,
  #607, #609, #610).

## Categorie con gap reali

- **dev/linguaggi/_index.md**: nessun gap di contenuto, gap di connettività
  (`related` vuoto) — prop-065.
- **dev/processi/_index.md**: nessun gap di contenuto, isola completa nel
  grafo `related` — prop-066.

## Focus usato in questa sessione

`docs/databases/` (dettaglio) + `docs/dev/` (runtime, processi, linguaggi
dettaglio), come raccomandato dal report #610. Entrambe le aree risultano
mature sul piano del contenuto: non emergono gap che superino il test di
utilità per proposte `new-file`/`extend-section`. Le uniche proposte generate
sono di connettività (`fix-relation`), categoria di proposta sempre ammessa
indipendentemente dal freno di saturazione.

## Prossima sessione consigliata

2026-09-28 o successiva. Nessuna area di `docs/dev/` o `docs/databases/`
richiede ulteriore esplorazione di contenuto a breve termine (entrambe verificate
mature su più sessioni). Ruotare il focus su un'area non ancora esplorata in
profondità nelle ultime 4 sessioni: `docs/monitoring/` (mai stata in focus
esplicito secondo i report #607-#613) e/o `docs/iac/` (terraform/opentofu/
pulumi/ansible — coverage non verificata di recente).
