# KB Saturation Report — 2026-09-27 (sessione #637)

## Gate meccanico

```
file_count: 314, target: 330, over_target: false, headroom: 16
category_saturated_pct: 85, allow_zero_proposals: true
```

Sotto target. Focus raccomandato dalla sessione precedente (#634): controllo di
connettività hub→figli sui sotto-hub **interni** (secondo livello) di
`docs/cloud/aws/**` e `docs/cloud/azure/**`, mai verificati con questo criterio
specifico prima d'ora (entrambe già grandi, a rischio di figli orfani accumulati
come visto in `containers/kubernetes`, #634).

## Copertura stimata per categoria

| Categoria | Files | Coverage % | Depth | Note |
|-----------|-------|------------|-------|------|
| cloud/aws (8 sotto-hub) | tutti i figli linkati | 100% connesso | Controllati tutti e 8 i sotto-hub (`ci-cd`, `compute`, `containers`, `database`, `fondamentali`, `iam`, `messaging`, `monitoring`, `security`, `storage` — 10 in realtà) | Nessun gap — `networking` (9 figli, il sotto-hub più grande di `aws/`) e tutti gli altri hanno grid "Sezioni"/"Argomenti" complete |
| cloud/azure (9 sotto-hub) | tutti i figli linkati | 100% connesso | Controllati `ci-cd`, `compute`, `database`, `fondamentali`, `identita`, `messaging`, `monitoring`, `networking`, `security`, `storage` | Nessun gap — ogni figlio è raggiungibile dalla grid del proprio sotto-hub |

## Categorie vicine alla saturazione

Confermate sature nelle sessioni precedenti (invariato): **databases/**,
**dev/linguaggi/**, **messaging/rabbitmq**, **cloud/aws**, **networking/**,
**dev/testing, dev/data, dev/resilienza, dev/sicurezza, dev/integrazioni**,
**monitoring/**, **iac/**, **cloud/azure/**. **ai/**, **security/**,
**cloud/aws/** e **cloud/azure/** confermate pulite anche al livello dei
sotto-hub interni (nessun figlio orfano).

## Categorie con gap reali

Nessun nuovo gap trovato in questa sessione. Restano aperti (da #634, non
ancora risolti da una proposta approvata al momento di questo report):

- **containers/kubernetes/_index.md**: 4 file figli non raggiungibili dalla
  grid "Sottosezioni" — prop-078 (high), già in `_automation/proposals/approved/`.
- **containers/kubernetes/helm.md vs containers/helm/_index.md**: contenuto
  sovrapposto senza `related` incrociati — prop-079 (medium), già approvata.

Zero proposte generate in questa sessione: il check di connettività su
`cloud/aws/**` e `cloud/azure/**` non ha rivelato figli orfani in nessuno dei
17 sotto-hub controllati (8 AWS + 9 Azure), e nessun altro gap operativo ha
superato il test di utilità (reader/scenario/outcome) durante l'analisi.

## Focus usato in questa sessione

Come raccomandato da #634: controllo mirato di connettività sui sotto-hub
interni di `docs/cloud/aws/**` e `docs/cloud/azure/**`. Risultato: entrambe
completamente pulite. Aggiornando il conteggio complessivo del pattern "hub
non aggiornato dopo la creazione di nuovi figli": 4 categorie su 6 controllate
finora (`ai`, `security`, `cloud/aws`, `cloud/azure`) risultano pulite, 2
(`ci-cd`, `containers`) hanno mostrato gap. La correlazione con la frequenza
di crescita recente della categoria (osservata in #634) resta la spiegazione
più plausibile.

## Prossima sessione consigliata

Non prima di 2026-10-04. Con 6 categorie ora verificate a livello di sotto-hub
interni, il prossimo giro dovrebbe coprire i sotto-hub interni di
`docs/dev/**` (categoria più popolosa e composita, mai controllata con questo
criterio) e valutare se il pattern "hub non aggiornato" giustifica ormai una
regola strutturale permanente in CLAUDE.md (checklist "aggiorna il genitore"
nel protocollo 1️⃣ Nuovo Argomento) — 2 categorie su 6 con gap è già un segnale
non trascurabile.
