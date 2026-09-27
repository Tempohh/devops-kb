# KB Saturation Report — 2026-09-28 (sessione #679)

## Gate meccanico

```
file_count: 314, target: 330, over_target: false, headroom: 16, category_saturated_pct: 85
```

Invariato dalle sessioni precedenti (#649...#674). Sotto target, espansione ammessa ma solo con gap reali (vedi PASSO 0/3 del prompt).

## Focus usato in questa sessione

Il report di #674 raccomandava di aprire un primo giro content-focused su
`iac/` (mai esplorato in dettaglio) o `dev/` (mai in focus). Letti in questa
sessione, a contenuto completo: `docs/dev/data/_index.md`,
`docs/dev/testing/_index.md`, `docs/iac/crossplane/_index.md`,
`docs/iac/crossplane/fondamentali.md`, `docs/iac/_index.md`; letti a
frontmatter + prime sezioni: `docs/iac/ansible/roles-collections.md`,
`docs/iac/pulumi/policy-as-code.md`, `docs/iac/terraform/testing.md`,
`docs/dev/runtime/jvm-tuning.md`, `docs/dev/resilienza/observability-code.md`.

## Risultato

`iac/` e `dev/` — le ultime due macro-categorie mai verificate a livello di
contenuto — confermano lo stesso pattern di maturità di tutte le altre
(postgresql, cloud/aws, cloud/azure, monitoring, security, containers,
networking): contenuto denso, esempi reali (YAML Crossplane, SQL, Go/Java/
Python), sezioni Troubleshooting con scenari multipli, `status: complete`
giustificato. **Nessun gap di contenuto** (`new-file`/`extend-section`
maggiore) nei 10 file letti. Con questa sessione **tutte** le macro-categorie
della KB sono state verificate almeno una volta a livello di contenuto diretto
(non solo frontmatter).

Gap reali trovati, stessi due tipi già osservati nelle sessioni precedenti —
connettività e commenti di currency non risolti:

- **`docs/cloud/aws/ci-cd/code-services.md`** (riga 24) contiene un commento
  HTML `<!-- REVIEW: verificare lo stato corrente di CodeCommit ... -->`
  ancora irrisolto — **secondo caso indipendente** di questo pattern dopo
  `ci-cd/_index.md` (prop-106, sessione #674). Conferma che task `review`/
  `currency` generici non intercettano sistematicamente commenti REVIEW
  inline residui. → prop-110 (high, currency mirato).
- **`docs/iac/crossplane/fondamentali.md`** cita `containers/kubernetes/
  operators-crd.md` come fondamento tecnico (admonition dedicato), ma
  `operators-crd.md` non reciproca (verificato via grep, nessun match
  "crossplane"). → prop-111 (fix-relation).
- **`docs/dev/resilienza/observability-code.md`** ha
  `monitoring/tools/jaeger-tempo` in `related`, ma `jaeger-tempo.md` non
  reciproca (verificato via grep, nessun match). → prop-112 (fix-relation).

Nessuna proposta `new-file` in questa sessione — **7a sessione consecutiva**
(#653, #656, #659, #662, #668, #674, #679) senza gap di copertura. Il grep
mirato `REVIEW:` su tutto `docs/` ha trovato **una sola** occorrenza residua
(quella risolta da prop-110); nessun'altra istanza del pattern nel resto della
KB al momento di questa sessione.

## Categorie vicine alla saturazione

Invariato: **databases/**, **dev/linguaggi/**, **messaging/rabbitmq**,
**cloud/aws**, **networking/**, **dev/testing, dev/data, dev/resilienza,
dev/sicurezza, dev/integrazioni, dev/runtime**, **monitoring/**, **ai/**,
**security/**, **containers/**, **messaging/kafka/**, **cloud/azure/**,
**iac/** (tutte e tre le sottocategorie campionate: crossplane, ansible,
pulumi, terraform confermano qualità alta).

## Categorie con gap reali

Nessun gap di contenuto rilevato in nessuna macro-categoria esplorata finora
(l'intera KB è stata ora campionata a livello di contenuto diretto). Gap
residui, confermati stabili su 7 sessioni: connettività interna/incrociata
(relazioni asimmetriche) e certificazione di freschezza (`review`/
`last_verified`), con occasionali commenti REVIEW inline non risolti (2 casi
noti su tutta la KB, entrambi ora coperti da proposte).

## Prossima sessione consigliata

Non prima di 2026-10-04. Con tutte le macro-categorie ormai verificate a
contenuto, il ciclo "primo giro esplorativo per categoria" è concluso.
Suggerito per la prossima sessione: passare da esplorazione per categoria a
un **secondo giro mirato su connettività** — campionare file con `related`
molto ricchi (5+ voci) per verificare sistematicamente la reciprocità delle
relazioni citate, dato che finora ogni sessione che ha controllato reciprocità
ha trovato almeno un'asimmetria. In alternativa, se emergono nuovi
`needs-review` dal normale flusso di automazione, dare priorità a quelli.
