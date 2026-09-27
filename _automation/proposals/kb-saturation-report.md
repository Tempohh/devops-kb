# KB Saturation Report — 2026-09-27 (sessione #668)

## Gate meccanico

```
file_count: 314, target: 330, over_target: false, headroom: 16, category_saturated_pct: 85
```

Invariato dalle sessioni precedenti (#649...#665). Sotto target, espansione
ammessa ma solo con gap reali (vedi PASSO 0/3 del prompt).

## Focus usato in questa sessione

Il report di #662 raccomandava di aprire un primo giro content-focused su
`monitoring/` o `security/` — mai stati in focus fino ad ora nonostante
segnalati "vicini alla saturazione" da diverse sessioni consecutive senza
verifica di contenuto. Letti in questa sessione: `ci-cd/_index.md` (unico
file `needs-review` residuo, trovato con Grep su tutto `docs/**/*.md`),
`monitoring/sre/chaos-engineering.md`, `monitoring/tools/continuous-profiling.md`,
`monitoring/alerting/prometheus-rules.md`, `monitoring/fondamentali/opentelemetry.md`,
`monitoring/_index.md` (hub), `security/runtime/falco.md`,
`security/supply-chain/sbom-cosign.md`, `security/network/zero-trust.md`,
`security/autorizzazione/opa.md`.

## Risultato

I file `monitoring/` e `security/` letti sono **maturi e completi**: stesso
pattern osservato in `postgresql/` (#662), `iac/` (#659), `cloud/aws` (#653),
`cloud/azure` (#656) — sezioni Troubleshooting con scenari multipli reali,
comandi/YAML concreti, `status: complete` giustificato. Nessun gap di
contenuto (`new-file`/`extend-section` maggiore).

Gap reali trovati, tutti di **connettività/currency**, non di copertura:

- `monitoring/fondamentali/opentelemetry.md` (last_updated 2026-03-24) descrive
  solo "I Tre Pilastri" (metriche/log/tracce) mentre il file fratello
  `monitoring/tools/continuous-profiling.md` (last_updated 2026-09-27) afferma
  che OTel ha stabilizzato il profiling come **quarto signal dal 2025** —
  relazione asimmetrica (continuous-profiling → opentelemetry sì, il
  contrario no) e modello concettuale disallineato tra due file della stessa
  cartella. → prop-101 (medium, extend-section).
- `monitoring/_index.md`, lo stesso schema "Tre Pilastri" si propaga
  all'indice di categoria, che non menziona affatto il profiling nella
  tabella Tools. → prop-102 (low, extend-section).
- `security/autorizzazione/opa.md` non reciproca il `related` verso
  `security/network/zero-trust.md`, che invece cita OPA esplicitamente come
  componente del Policy Decision Point — stesso pattern di relazione
  asimmetrica già rilevato in #662 su `postgresql/`. → prop-103 (low,
  fix-relation).
- `ci-cd/_index.md`: **unico file `needs-review` residuo** nell'intera KB
  (verificato via Grep, dopo che #663/#664/#665 hanno chiuso i tre precedenti),
  modificato oggi stesso (2026-09-27) — review economica perché il contesto
  è fresco. → prop-104 (high, review).

Nessuna proposta `new-file` in questa sessione — 5° sessione consecutiva
(#653, #656, #659, #662, #668) senza gap di copertura: il pattern è ormai
consolidato, i gap residui sono sistematicamente di connettività e
certificazione di freschezza.

## Categorie vicine alla saturazione

Invariato: **databases/**, **dev/linguaggi/**, **messaging/rabbitmq**,
**cloud/aws**, **networking/**, **dev/testing, dev/data, dev/resilienza,
dev/sicurezza, dev/integrazioni**, **monitoring/**, **ai/**, **security/**,
**containers/**, **messaging/kafka/**, **cloud/azure/**, **iac/**. Con
questa sessione si confermano di alta qualità (content-read) anche
`monitoring/` (5 file + indice) e `security/` (4 file), aree mai verificate
a livello di contenuto prima di ora.

## Categorie con gap reali

Nessun gap di contenuto in tutte le aree lette fino ad oggi (postgresql,
iac, cloud/aws, cloud/azure, monitoring, security). Gap residui: solo
connettività interna/incrociata e certificazione di freschezza (`review`)
sui pochi file rimasti `needs-review`.

## Prossima sessione consigliata

Non prima di 2026-10-04. Suggerito: applicare prop-101/102/103/104 (se
approvate) e aprire un primo giro content-focused su `containers/` o
`networking/` (mai stati in focus finora, segnalati "vicini alla saturazione"
da molte sessioni senza verifica di contenuto) — oppure, se emergono nuovi
`needs-review` dal normale flusso di modifica della KB, ripetere il pattern
"review su needs-review appena segnalato" che in questa e nella sessione
precedente si è rivelato l'unico gap realmente produttivo trovato in aree
mature.
