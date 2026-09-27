# KB Saturation Report — 2026-09-27 (sessione #674)

## Gate meccanico

```
file_count: 314, target: 330, over_target: false, headroom: 16, category_saturated_pct: 85
```

Invariato dalle sessioni precedenti (#649...#668). Sotto target, espansione
ammessa ma solo con gap reali (vedi PASSO 0/3 del prompt).

## Focus usato in questa sessione

Il report di #668 raccomandava un primo giro content-focused su `containers/`
o `networking/` (mai stati in focus finora). Letti in questa sessione:
`ci-cd/_index.md` (unico `needs-review` residuo insieme ai due sotto),
`monitoring/_index.md` e `monitoring/fondamentali/opentelemetry.md` (appena
modificati oggi da #669/#670), `containers/kubernetes/multi-cluster.md`,
`networking/kubernetes/gateway-api.md`, `networking/fondamentali/ebpf.md`,
`containers/registry/harbor.md` e `containers/openshift/gitops-pipelines.md`
(lettura parziale, frontmatter + prime sezioni).

## Risultato

`containers/` e `networking/` confermano lo stesso pattern di maturità già
osservato in tutte le altre categorie lette finora (postgresql, iac, cloud/aws,
cloud/azure, monitoring, security): contenuto denso, comandi/YAML reali,
Troubleshooting con scenari multipli, `status: complete` giustificato.
**Nessun gap di contenuto** (`new-file`/`extend-section` maggiore) nei file
letti.

Gap reali trovati, di tre tipi — connettività, currency, e per la prima volta
in questa serie di sessioni un **dato tecnico sbagliato non ancora corretto**:

- `ci-cd/_index.md` contiene un commento HTML `<!-- REVIEW: ... -->` (riga 66)
  che segnala una tabella DORA Change Failure Rate con lo stesso intervallo
  "16-30%" ripetuto identico per High, Medium e Low — palese copia-incolla.
  Il commento è sopravvissuto a **due** passaggi di automazione recenti
  (review auto #672, currency auto #673) senza essere risolto: il file resta
  `needs-review`. → prop-106 (high, extend-section mirato, non un ennesimo
  review generico).
- `monitoring/_index.md` e `monitoring/fondamentali/opentelemetry.md`
  (modificati oggi, #669/#670): a lettura diretta il contenuto è già coerente
  e corretto — l'asimmetria "quarto pilastro" segnalata da #668 risulta
  risolta in entrambi. Restano solo `needs-review` senza `last_verified`:
  contesto fresco, certificazione economica. → prop-107 (review).
- `networking/fondamentali/ebpf.md` cita `networking/kubernetes/cni` come
  `related` (e nel testo spiega che Cilium implementa il CNI via eBPF), ma
  `cni.md` non reciproca — stesso pattern di relazione asimmetrica già
  rilevato ripetutamente nella KB (postgresql #662, opa/zero-trust #668).
  → prop-108 (fix-relation).
- `networking/kubernetes/gateway-api.md` cita `networking/service-mesh/
  linkerd` in un admonition dedicato, ma `linkerd.md` non ha alcun
  riferimento a Gateway API (verificato via grep, nessun match). → prop-109
  (fix-relation).

Nessuna proposta `new-file` in questa sessione — 6a sessione consecutiva
(#653, #656, #659, #662, #668, #674) senza gap di copertura. Il pattern dei
gap residui si conferma: connettività e certificazione di freschezza, con
l'aggiunta — nuova in questa sessione — di un dato numerico errato rimasto
irrisolto attraverso due cicli di automazione, segnale che i task `review`/
`currency` generici possono non intercettare un problema puntuale già
segnalato inline nel testo.

## Categorie vicine alla saturazione

Invariato: **databases/**, **dev/linguaggi/**, **messaging/rabbitmq**,
**cloud/aws**, **networking/**, **dev/testing, dev/data, dev/resilienza,
dev/sicurezza, dev/integrazioni**, **monitoring/**, **ai/**, **security/**,
**containers/**, **messaging/kafka/**, **cloud/azure/**, **iac/**. Con questa
sessione si confermano di alta qualità (content-read) anche `containers/`
(3 file) e `networking/` (2 file), le ultime due aree mai verificate a livello
di contenuto.

## Categorie con gap reali

Nessun gap di contenuto in tutte le aree lette fino ad oggi (postgresql, iac,
cloud/aws, cloud/azure, monitoring, security, containers, networking). Gap
residui: connettività interna/incrociata, certificazione di freschezza
(`review`), e — caso isolato ma da tenere d'occhio — dati tecnici segnalati
inline ma non corretti da automazione generica (ci-cd DORA table).

## Prossima sessione consigliata

Non prima di 2026-10-04. Suggerito: applicare prop-106/107/108/109 (se
approvate) e, se prop-106 viene applicata, verificare che il pattern "commento
REVIEW inline sopravvissuto a più cicli" non si ripeta altrove nella KB (un
`grep -r "REVIEW:" docs/` a basso costo potrebbe rivelare altri casi simili
mai chiusi). In assenza di nuovi `needs-review` freschi dal normale flusso,
aprire un primo giro content-focused su `iac/` (opentofu/pulumi/ansible, mai
esplorato in dettaglio nonostante il focus di default originale) o `dev/`
(mai stata in focus, area con più sottocategorie "vicine alla saturazione"
mai verificate a contenuto).
