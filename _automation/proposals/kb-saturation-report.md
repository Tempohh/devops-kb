# KB Saturation Report — 2026-09-28 (sessione #683)

## Gate meccanico

```
file_count: 314, target: 330, over_target: false, headroom: 16, category_saturated_pct: 85
```

Invariato dalle sessioni precedenti (#649...#679). Sotto target, ma nessuna
proposta `new-file` in questa sessione (vedi sotto).

## Copertura stimata per categoria

Nessuna variazione rispetto a #679: tutte le macro-categorie sono state
verificate a livello di contenuto diretto nelle sessioni precedenti e
confermano qualità alta (`status: complete` giustificato, Troubleshooting
presente, esempi reali).

## Focus usato in questa sessione

Come raccomandato dal report di #679: **secondo giro mirato su
connettività**, campionando file con `related` ricco (5+ voci, individuati
via grep su tutto `docs/`, 73 file candidati) per verificarne la reciprocità.
Campione analizzato in questa sessione (12 file, escludendo `_index.md` e i
casi già coperti da prop-110/111/112): `dev/resilienza/circuit-breaker.md`,
`dev/resilienza/health-checks.md`, `dev/sicurezza/secrets-config.md`,
`dev/sicurezza/tls-da-codice.md`, `dev/integrazioni/database-patterns.md`,
`dev/integrazioni/rabbitmq-client.md`, `networking/sicurezza/wireguard.md`,
`networking/sicurezza/zero-trust.md`, `security/network/zero-trust.md`,
`cloud/gcp/containers/gke.md`, `ai/agents/agent-patterns.md`,
`monitoring/sre/chaos-engineering.md` — più i rispettivi target citati
(`dev/linguaggi/java-spring-boot.md`, `dotnet.md`, `go.md`,
`cloud/gcp/fondamentali/panoramica.md`, `containers/kubernetes/architettura.md`,
`workloads.md`, `ai/sviluppo/api-integration.md`).

## Risultato

Confermata l'ipotesi del report precedente: **ogni sessione che ha
verificato reciprocità ha trovato almeno un'asimmetria**. Trovato questa
volta un pattern sistemico più ampio dei singoli casi isolati precedenti:

- **`dev/linguaggi/{java-spring-boot,dotnet,go}.md`** sono citati come
  esempio linguistico da **6 file** ciascuno
  (`dev/resilienza/circuit-breaker.md`, `dev/resilienza/health-checks.md`,
  `dev/sicurezza/secrets-config.md`, `dev/sicurezza/tls-da-codice.md`,
  `dev/integrazioni/database-patterns.md`,
  `dev/integrazioni/rabbitmq-client.md`), ma nessuno dei tre file
  "linguaggio" reciproca verso nessuno dei sei. Pattern sistemico: i file
  hub per linguaggio non linkano indietro ai pattern applicativi che li
  usano come esempio. → prop-113, prop-114, prop-115 (fix-relation, high,
  una per file linguaggio, 6 link ciascuna).
- **`networking/sicurezza/zero-trust.md`** non reciproca
  `networking/sicurezza/wireguard.md` (che lo cita). → prop-116
  (fix-relation, medium).
- **`cloud/gcp/fondamentali/panoramica.md`** non reciproca
  `cloud/gcp/containers/gke.md` (che lo cita) e più in generale non ha
  nessun link verso contenuti GCP concreti della sezione. → prop-117
  (fix-relation, medium).

Casi verificati **reciproci** (nessuna azione): `networking/sicurezza/zero-trust.md`
↔ `security/network/zero-trust.md`; `ai/agents/agent-patterns.md` ↔
`ai/sviluppo/api-integration.md`. Non tutte le asimmetrie rilevate sono
state proposte: `monitoring/sre/chaos-engineering.md` →
`containers/kubernetes/architettura.md`/`workloads.md` è scartata perché
questi ultimi sono hub generici di Kubernetes che citerebbero decine di
consumer se reciprocassero ogni citazione in ingresso — non è un gap reale
ma normale asimmetria hub↔consumer.

Nessuna proposta `new-file` in questa sessione — **8a sessione consecutiva**
(#653, #656, #659, #662, #668, #674, #679, #683) senza gap di copertura.

## Categorie vicine alla saturazione

Invariato rispetto a #679.

## Categorie con gap reali

Nessun gap di contenuto. Gap di connettività confermato come pattern
ricorrente e ora parzialmente sistemico (hub per linguaggio in dev/linguaggi/
non reciprocano i consumer applicativi).

## Prossima sessione consigliata

Non prima di 2026-10-04. Continuare il giro connettività sul resto dei 73
file con `related` ricco non ancora campionati (candidati prioritari:
`monitoring/tools/prometheus.md`, `monitoring/tools/grafana.md`,
`ci-cd/jenkins/*`, `ai/training/*` — non ancora verificati in questo giro).
Evitare di riproporre hub↔consumer generici (kubernetes/architettura,
kubernetes/workloads) come gap: l'asimmetria lì è strutturale, non un
difetto.
