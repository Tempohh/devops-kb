# KB Saturation Report — 2026-09-27 (sessione #645)

## Gate meccanico

```
file_count: 314, target: 330, over_target: false, headroom: 16
category_saturated_pct: 85, allow_zero_proposals: true
```

Sotto target. Focus raccomandato dalla sessione precedente (#642): completare
il controllo di connettività hub→figli su `networking/**`, `iac/**`,
`monitoring/**`, `security/**`, `ai/**`, `cloud/gcp` (fondi/finops), `containers/**`.

## Copertura stimata per categoria

| Categoria | Sotto-hub controllati | Gap trovati | Note |
|-----------|------------------------|-------------|------|
| networking/** (7 sotto-hub + top) | 8/8 | 0 | Tutti i grid del genitore linkano correttamente i figli |
| iac/** (4 strumenti + top) | 5/5 | 0 | terraform, ansible, pulumi, crossplane tutti agganciati |
| monitoring/** (4 sotto-hub + top) | 5/5 | 0 | fondamentali, tools, alerting, sre puliti |
| security/** (7 sotto-hub + top) | 8/8 | 0 | autenticazione, autorizzazione, secret-management, pki, supply-chain, compliance, network tutti puliti |
| cloud/gcp/** (7 sotto-hub + top) | 7/8 | 1 | **compute/_index.md manca del tutto** — unico hub GCP assente (vedi sotto) |
| cloud/finops (2 file) | 1/1 | 0 | Pulito |
| containers/** (6 sotto-hub + top + kubernetes 11 figli) | 7/7 | 0 | docker, openshift, helm, kustomize, registry, container-runtime, kubernetes tutti puliti |
| ai/** (7 sotto-hub + top) | 8/8 | 0 (connettività) — 1 gap di **currency** e 1 di **refuso path** | Vedi sotto |

## Categorie vicine alla saturazione

Confermate sature (invariato dalle sessioni precedenti): **databases/**,
**dev/linguaggi/**, **messaging/rabbitmq**, **cloud/aws**, **networking/**,
**dev/testing, dev/data, dev/resilienza, dev/sicurezza, dev/integrazioni**,
**monitoring/**, **iac/**, **cloud/azure/**, **ai/**, **security/**,
**containers/**. Con questa sessione si aggiungono a "verificate pulite sotto
il profilo connettività hub→figli": networking, iac, monitoring, security,
containers, cloud/gcp (a parte 1 gap), cloud/finops.

## Categorie con gap reali

Trovati **3 gap concreti**, nessuno di tipo "hub non linkato dal grid" puro
(il pattern ricorrente delle sessioni precedenti) tranne il primo, che è
un caso più severo (hub interamente mancante):

- **cloud/gcp/compute/_index.md — file mancante** (non solo link mancante):
  `cloud-run.md` esiste, completo, con `parent: cloud/gcp/compute/_index`,
  ma quel file `_index.md` non esiste in tutta la sezione GCP (unico caso
  su 7 sotto-sezioni). Il grid "Mappa dei Servizi" in `cloud/gcp/_index.md`
  non menziona nemmeno "Compute". → prop-085 (high).
- **ai/sviluppo/_index.md — currency**: tutti gli esempi di codice usano
  model ID Claude 3.5 datati (`claude-3-5-sonnet-20241022`), disallineati
  da `ai/modelli/claude.md` (già `reviewed`, model ID famiglia 5 correnti)
  nella stessa KB. Stesso pattern della criticità #3 (CLAUDE.md), sanato
  altrove ma non qui. → prop-086 (medium, currency).
- **ai/agents/_index.md — refuso path**: campo `related` punta a
  `ai/agenti/...` (italiano) invece di `ai/agents/...` (inglese, cartella
  reale) — innocuo per il rendering ma inquina i dati di connettività per
  audit futuri. → prop-087 (low, fix-relation).

Sotto-hub controllati e puliti in questa sessione (nessun gap di
connettività): tutti i 7 sotto-hub networking + top, tutti i 4 strumenti
IaC + top, tutti i 4 sotto-hub monitoring + top, tutti i 7 sotto-hub
security + top, tutti i 6 sotto-hub containers + kubernetes (11 figli via
grid + nota cross-reference) + top, 6/7 sotto-hub GCP + finops + top.

## Focus usato in questa sessione

Come raccomandato da #642: completamento del controllo di connettività
hub→figli su `networking/**`, `iac/**`, `monitoring/**`, `security/**`,
`cloud/gcp/**`, `cloud/finops/**`, `containers/**`, più un giro di lettura
approfondita su `ai/**` (mai stato nel focus di rotazione finora, come da
default del PASSO 3). Risultato: il pattern "hub non linkato dal grid"
osservato nelle 4 sessioni precedenti (5 casi su ~26 sotto-hub, ~19%) qui
sale a 1 caso su ~35 sotto-hub controllati (~3%) — la KB risulta molto più
pulita sotto questo profilo nelle categorie appena verificate rispetto a
`dev/**` (dove il pattern era più marcato). Il gap trovato in `cloud/gcp`
è però più severo del solito: non manca un link, manca il file hub stesso.
In `ai/**`, primo giro di lettura approfondita per questa sessione, sono
emersi due problemi di natura diversa dalla connettività pura (currency e
refuso di frontmatter) — segnale che vale la pena, nelle prossime sessioni,
alternare il controllo "hub→figli" con una lettura di contenuto mirata
anche nelle categorie già dichiarate "pulite" strutturalmente.

## Prossima sessione consigliata

Non prima di 2026-10-04. Il ciclo di controllo "hub→figli" avviato in
#634 può considerarsi concluso su tutte le categorie principali (solo
containers/openshift e kustomize erano da riconfermare dopo prop-078/079,
ora verificati puliti in questa sessione). Prossimo focus suggerito:
lettura di contenuto (non solo connettività) su `dev/**` e `messaging/**`
per cercare pattern analoghi a quelli trovati in `ai/sviluppo/` (currency,
refusi di frontmatter) — la connettività strutturale della KB è ormai
in buono stato diffuso, il valore marginale maggiore ora sta nel controllo
di freschezza dei contenuti e nell'accuratezza dei metadati.
