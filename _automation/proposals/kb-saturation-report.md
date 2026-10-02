# KB Saturation Report — 2026-10-02 (sessione #709)

## Gate meccanico

```
file_count: 320, target: 330, over_target: false, headroom: 10, category_saturated_pct: 85, allow_zero_proposals: true
```

Sotto target (headroom 10): proposte di espansione ammesse se superano il test
di utilità. Nota di cadenza: ancora un arrivo rapido dopo #706/#707 (stessa
settimana) — pattern già segnalato in report precedenti, non bloccante per
questa sessione.

Verificato lo stato delle proposte della sessione precedente (#706): prop-128
(`cloud/gcp/security/kms-secret-manager.md`) risulta committata (commit
1416785f, auto #707). prop-129 (`cloud/gcp/security/network-perimeter-detection.md`)
risulta creata ma non ancora committata (file untracked in working tree) —
nessuna azione richiesta in questa sessione, nessuna duplicazione.

## Focus usato in questa sessione

Il report #706 raccomandava, in caso di arrivo anticipato, di spostare il
focus su `docs/messaging/` o `docs/containers/` (non esplorate di recente nelle
sessioni `proposal`). Applicato: entrambe analizzate.

File letti/ispezionati (10): `docs/messaging/_index.md`, `docs/messaging/kafka/*`
(elenco strutturale, non letture complete), `docs/messaging/rabbitmq/vs-kafka.md`
(grep), `docs/messaging/rabbitmq/features-avanzate.md`, `docs/containers/container-runtime/_index.md`
(completo), `docs/containers/*` (elenco strutturale), `docs/iac/ansible/_index.md`,
`docs/iac/crossplane/_index.md` + `fondamentali.md` (grep su "function"),
`docs/databases/*` (elenco strutturale), `docs/ai/sviluppo/rag.md` +
`docs/databases/postgresql/extensions.md` (grep su "vector/pgvector/qdrant").

## Risultato

**`docs/containers/`**: maturo. `container-runtime/_index.md` copre già CRI,
containerd, CRI-O, runc, RuntimeClass, gVisor/Kata in profondità (expert).
Nessun gap trovato.

**`docs/iac/`**: Ansible (`roles-collections.md`) copre già Vault multi-ambiente,
dynamic inventory, Molecule testing — ipotesi di gap iniziale (secrets/testing)
smentita a lettura. Crossplane `fondamentali.md` copre già Composition Functions
(v1.14+, pipeline, `crossplane render`) — expand recente (sessione #705) ha
già colmato quello che sembrava un gap.

**Vector database / pgvector**: ipotesi di gap smentita — `docs/ai/sviluppo/rag.md`
(Qdrant, Pinecone, Weaviate, pgvector, hybrid search, tabella comparativa) e
`docs/databases/postgresql/extensions.md` (pgvector, HNSW/IVFFlat, troubleshooting)
coprono il tema da entrambe le angolazioni, cross-referenziati.

**Gap reale trovato — `docs/messaging/pulsar/`**: la categoria messaging
documenta solo Kafka (56 file) e RabbitMQ (8 file). Apache Pulsar — terzo
sistema di event-streaming più diffuso in produzione, spesso termine di
confronto diretto con Kafka per multi-tenancy nativa e tiered storage — non
è menzionato in **nessun** file della KB (verificato via grep ricorsivo,
zero risultati). Non è simmetria formale: l'architettura compute/storage
separata (broker stateless + BookKeeper) di Pulsar è concettualmente diversa
da Kafka e genera domande operative specifiche (bookie sizing, tiered storage
offload, subscription model key_shared) non risolvibili per analogia con i
contenuti Kafka/RabbitMQ esistenti.

## Proposte generate

- **prop-130** (high, new-file) — `messaging/pulsar/fondamentali.md` (+ creazione
  `messaging/pulsar/_index.md`, + card nella grid di `messaging/_index.md`,
  + `pulsar` in `taxonomy.yml:messaging.subcategories`)

## Categorie vicine alla saturazione

`docs/dev/`, `docs/ci-cd/testing/` (confermate sature, sessioni precedenti).
`docs/containers/` e `docs/iac/` risultano mature dopo l'analisi di questa
sessione (nessun gap reale, vedi sopra) — non formalmente sature per conteggio
file ma senza ulteriori gap operativi individuati.
`docs/messaging/kafka/` e `docs/messaging/rabbitmq/` maturi (56+8 file,
coverage profonda su sicurezza, pattern, operazioni).

## Categorie con gap reali

`docs/messaging/pulsar/` (intera sottocategoria mancante) — vedi proposta sopra.

## Prossima sessione consigliata

Non prima di 2026-10-09. Verificare prima l'implementazione di prop-130 e il
commit di prop-129 (sessione #706, ancora untracked). Se arriva comunque in
anticipo, spostare il focus su `docs/networking/` o `docs/security/` (non
esplorate in profondità da più sessioni `proposal` consecutive).
