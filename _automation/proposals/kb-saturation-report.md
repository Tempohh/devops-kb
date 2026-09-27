# KB Saturation Report — 2026-09-27 (sessione #597)

## Gate meccanico

```
file_count: 307, target: 330, over_target: false, headroom: 23
category_saturated_pct: 85, allow_zero_proposals: true
```

Sotto target. Focus ruotato via da `networking`/`cloud/aws` (saturi da 3+
sessioni consecutive, vedi report #596) verso `iac` e `monitoring`, come
raccomandato dalla sessione precedente.

## Copertura stimata per categoria

| Categoria | Files | Coverage % | Depth | Note |
|-----------|-------|------------|-------|------|
| iac | 14 | ~70% | Alta (pochi file, ma molto profondi) | Terraform (6 file) e Ansible (3 file) enciclopedici; Pulumi (3 file) profondo su fondamentali/stack ma privo di Policy as Code |
| monitoring | 20 | ~65% | Alta sui 3 pilastri classici | Metriche/log/tracce e SRE (SLO, error budget, chaos, incident, capacity) molto completi; nessun contenuto sul "quarto pilastro" (profiling) |
| databases | 28 | ~70% | Media | Non analizzata in profondità in questa sessione (focus su iac/monitoring) |
| networking | 44 | ~90% | Alta | Confermato saturo (sessioni #591-596) |
| cloud/aws | 45 | ~90% | Alta | Confermato saturo (sessioni #594-596) |

## Analisi di questa sessione

File letti (7, mirati sul focus iac/monitoring invece del campione generico da
10, per concentrare il budget sulle aree indicate come gap reale dal report
precedente): `iac/ansible/roles-collections.md`, `iac/pulumi/stacks-ambienti.md`,
`iac/terraform/testing.md`, `iac/_index.md`, `iac/pulumi/_index.md`,
`iac/ansible/_index.md`, `iac/terraform/_index.md`. Più censimento strutturale
completo di `docs/iac/**` (14 file) e `docs/monitoring/**` (20 file), e grep
mirato su "profiling/eBPF/CrossGuard/PolicyPack" per verificare l'assenza di
contenuto prima di proporre.

**Sorpresa**: `iac` ha pochi file ma sono già molto estesi e maturi (es.
`ansible/roles-collections.md` copre Molecule, Vault multi-ambiente, dynamic
inventory AWS, CI — quasi 1000 righe). Il conteggio file basso non riflette un
gap di qualità, ma due gap puntuali reali:
1. **Pulumi non ha alcun contenuto su Policy as Code** (CrossGuard), mentre
   Terraform ha un intero file (`testing.md`) dedicato a policy/compliance
   (OPA, Sentinel, checkov). Asimmetria non simmetrica-formale ma di
   funzionalità reale mancante lato Pulumi.
2. **Monitoring non copre il continuous profiling** (Pyroscope/Parca/eBPF),
   il "quarto pilastro" dell'osservabilità ormai mainstream e con supporto
   OTel stabilizzato nel 2025. I tre pilastri classici sono coperti in modo
   enciclopedico ma il documento fondamentali si ferma esplicitamente a tre.

Entrambi i gap superano il test di utilità (PASSO 3): non sono reperibili in
2 click nella documentazione ufficiale di un singolo prodotto, richiedono
sintesi cross-fonte, e risolvono un problema operativo concreto e non banale.

## Categorie vicine alla saturazione

- **networking**, **cloud/aws**: confermato saturo, nessuna nuova analisi in
  questa sessione (fuori focus).
- **iac/terraform**, **iac/ansible**: profondità già alta, nessun gap
  operativo residuo individuato in questa sessione.

## Categorie con gap reali

- **iac/pulumi**: manca Policy as Code (CrossGuard) — proposta generata.
- **monitoring**: manca continuous profiling (quarto pilastro) — proposta
  generata.
- **databases**: coverage media (~70%), non ancora esplorata in profondità
  in nessuna sessione recente — candidata per il prossimo focus.

## Focus usato in questa sessione

`docs/iac/` e `docs/monitoring/`, per rotazione esplicita raccomandata dal
report della sessione #596 (3 sessioni consecutive sature su networking/
cloud-aws senza nuove proposte). Entrambe le aree hanno prodotto un gap reale
di score `high`, confermando che la rotazione era la scelta corretta.

## Decisione: 2 proposte

- `prop-056`: Pulumi — Policy as Code (CrossGuard), `iac/pulumi`, priority high.
- `prop-057`: Continuous Profiling (Pyroscope/Parca/eBPF), `monitoring/tools`,
  priority high.

Zero proposte aggiuntive: `databases` non è stata analizzata in profondità in
questa sessione (budget concentrato sul focus iac/monitoring) e non generare
proposte "a simmetria" per Terraform/Ansible, già maturi.

## Prossima sessione consigliata

2026-09-28 o successiva, focus tematico `docs/databases/` (gap reale mai
esplorato in profondità nelle ultime sessioni, coverage ~70%) oppure
completamento del giro su `docs/monitoring/` (tools/alerting non ancora
riletti in dettaglio in questa sessione).
