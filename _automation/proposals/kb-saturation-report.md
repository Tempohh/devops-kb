# KB Saturation Report — 2026-09-27 (sessione #621)

## Gate meccanico

```
file_count: 315, target: 330, over_target: false, headroom: 15
category_saturated_pct: 85, allow_zero_proposals: true
```

Sotto target. Raccomandazione della sessione precedente (#616): niente
nuova esplorazione di contenuto su monitoring/iac (già mature), ma un
**controllo mirato** sul pattern "hub `_index.md` non aggiornato quando
nasce una nuova sottocartella/file" su altri hub — in particolare
`ci-cd/jenkins/_index.md` e gli `_index.md` di `cloud/aws/*`.

## Copertura stimata per categoria

| Categoria | Files | Coverage % | Depth | Note |
|-----------|-------|------------|-------|------|
| ci-cd/ | ~24 file (incl. 9 `_index`) | ~90% contenuto, gap di connettività hub | jenkins/_index perfetto (5/5 figli linkati); ma ci-cd/_index.md (hub di livello superiore) elenca solo 5 sottosezioni su 8 | Gap reale trovato: 3 intere sottosezioni (tools/, testing/, platform-engineering/) assenti dalla grid dell'hub |
| security/ | 26 file (incl. 8 `_index`) | ~95% contenuto | autenticazione/_index, supply-chain/_index verificati completi e ben linkati | Gap reale trovato: sottosezione network/ (2 file) assente da security/_index.md |
| networking/ | 43 file | ~95%, hub sani | kubernetes/_index e api-gateway/_index verificati: nessun figlio orfano; networking/_index.md ben strutturato con percorsi di studio coerenti | Nessun gap trovato in questa sessione |

## Analisi di questa sessione

File letti (10): `ci-cd/jenkins/_index.md`, `networking/kubernetes/_index.md`,
`networking/api-gateway/_index.md`, `security/supply-chain/_index.md`,
`security/autenticazione/_index.md`, `security/_index.md`,
`networking/_index.md`, `security/network/_index.md`, `ci-cd/_index.md`,
`ci-cd/tools/_index.md`.

**Verificato NON un gap**: `ci-cd/jenkins/_index.md` (5/5 figli linkati),
`networking/kubernetes/_index.md` (4/4), `networking/api-gateway/_index.md`
(3/3), `security/supply-chain/_index.md` (3/3), `security/autenticazione/_index.md`
(3/3), `networking/_index.md` (tutte le 7 sottosezioni presenti in grid,
percorsi di studio e tabella finale coerenti tra loro).

**Gap reale #1 — `ci-cd/_index.md` elenca 5 sottosezioni su 8**: la grid
"## Argomenti in questa Sezione" cita Jenkins, GitHub Actions, GitLab CI,
GitOps, Strategie di Deployment, ma non `ci-cd/tools/_index.md` (Tekton,
CircleCI), `ci-cd/testing/_index.md` (contract/performance testing, test
strategy) né `ci-cd/platform-engineering/_index.md` (Backstage) — tutte e
tre `status: complete` e con contenuto verificato. → prop-071
(extend-section, priority high — 3 sottosezioni intere, il gap più ampio
di questa sessione).

**Gap reale #2 — `security/_index.md` non elenca `security/network/_index.md`**
(Network Security / Zero Trust, `status: complete`): assente dalla grid
"## Sezioni" (6 card invece di 7), dai "Percorsi di Studio" e dalla tabella
"Tutti gli Argomenti". → prop-072 (extend-section, priority medium — 1
sottosezione con 1 file figlio).

Il pattern "hub padre non aggiornato quando nasce una nuova sottocartella"
(già visto in monitoring/sre, monitoring/alerting, monitoring/tools,
iac/_index — prop-067..070) si conferma **trasversale a più categorie**:
qui colpisce ci-cd/ e security/ a livello di hub di primo livello (non
solo hub di sottosezione). Nessun caso trovato invece in networking/,
che risulta l'unica categoria tra quelle controllate con navigazione
interamente coerente.

## Categorie vicine alla saturazione

- **networking/**: confermata matura per contenuto e connettività in
  questa sessione — nessun gap trovato.
- Confermate sature nelle sessioni precedenti (invariato): **databases/**,
  **dev/linguaggi/**, **messaging/rabbitmq**, **cloud/aws**,
  **ci-cd/testing** (contenuto, non connettività — vedi gap #1),
  **dev/testing, dev/data, dev/resilienza, dev/sicurezza, dev/integrazioni**,
  **monitoring/**, **iac/** (contenuto maturo, connettività già corretta
  da prop-067..070).

## Categorie con gap reali

- **ci-cd/_index.md**: 3/8 sottosezioni non raggiungibili dall'hub —
  prop-071 (high).
- **security/_index.md**: 1/7 sottosezioni non raggiungibile —
  prop-072 (medium).

## Focus usato in questa sessione

Controllo mirato (non intera sessione di analisi) sul pattern di
connettività hub→figli, come raccomandato da #616, esteso a `ci-cd/`,
`security/` e `networking/` invece che a una singola categoria di
contenuto. Scelta motivata dal fatto che il pattern trovato in #616 era
strutturale (hub desincronizzati), non specifico di monitoring/iac —
verificarlo su altre categorie era il modo più efficiente di trovare
valore reale senza riaprire un'analisi di contenuto su aree già mature.

## Prossima sessione consigliata

Non prima di 2026-10-04. Suggerito completare lo stesso controllo mirato
di connettività hub→figli su `cloud/aws/*/_index.md` (11 hub, mai
controllati con questo criterio) e su `docs/dev/**/_index.md` — se il
pattern si ripete anche lì, valutare se aggiungere un controllo
automatico (script) invece di continuare a scoprirlo manualmente file
per file. In assenza di nuovi hit, ruotare su una verifica di contenuto
(non solo connettività) di `docs/cloud/azure/` e `docs/cloud/gcp/`, mai
riverificate dal punto di vista di completezza dei singoli file.
