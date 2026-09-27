# KB Saturation Report — 2026-09-27 (sessione #634)

## Gate meccanico

```
file_count: 315, target: 330, over_target: false, headroom: 15
category_saturated_pct: 85, allow_zero_proposals: true
```

Sotto target. Focus raccomandato dalla sessione precedente (#630): controllo
di connettività hub→figli sui sotto-hub **interni** (secondo livello) di
`docs/containers/**` e `docs/security/**`, mai verificati con questo
criterio specifico prima d'ora.

## Copertura stimata per categoria

| Categoria | Files | Coverage % | Depth | Note |
|-----------|-------|------------|-------|------|
| security/ (7 sotto-hub) | tutti i figli linkati | 100% connesso | Controllati tutti e 7 i sotto-hub (`autenticazione`, `autorizzazione`, `compliance`, `network`, `pki-certificati`, `runtime`, `secret-management`): ogni figlio è raggiungibile dalla grid del proprio sotto-hub | Nessun gap — quarta categoria a passare il controllo di connettività interna senza problemi (dopo `ai/`) |
| containers/ (7 sotto-hub) | 1 sotto-hub con 4 figli orfani | gap reale, il più grande trovato finora | Controllati `container-runtime`, `docker`, `helm`, `kustomize`, `openshift`, `registry` (puliti, 100% figli linkati) e `kubernetes` (12 file: grid ne linka solo 7, la nota Networking ne linka 1, **4 restano orfani**: `autoscaling.md`, `ingress.md`, `multi-cluster.md`, `resource-management.md`) | prop-078 (high, fix-relation) per i 4 orfani; scoperta secondaria: `kubernetes/helm.md` (anch'esso orfano, coperto da prop-078) si sovrappone concettualmente a `helm/_index.md` senza `related` incrociati — prop-079 (medium, consolidate) |

## Categorie vicine alla saturazione

Confermate sature nelle sessioni precedenti (invariato): **databases/**,
**dev/linguaggi/**, **messaging/rabbitmq**, **cloud/aws**, **networking/**,
**dev/testing, dev/data, dev/resilienza, dev/sicurezza, dev/integrazioni**,
**monitoring/**, **iac/**, **cloud/azure/**. **ai/** e **security/**
confermate pulite anche al livello dei sotto-hub interni.

## Categorie con gap reali

- **containers/kubernetes/_index.md**: 4 file figli completi
  (`autoscaling`, `ingress`, `multi-cluster`, `resource-management`) non
  raggiungibili dalla grid "Sottosezioni" dell'hub — prop-078 (high).
- **containers/kubernetes/helm.md vs containers/helm/_index.md**: contenuto
  sovrapposto su Helm-per-Kubernetes, nessun `related` incrociato —
  prop-079 (medium).

## Focus usato in questa sessione

Come raccomandato da #630: controllo mirato di connettività sui sotto-hub
**interni** (secondo livello) di `docs/containers/**` e `docs/security/**`.
Risultato: `security/` è risultata completamente pulita (seconda categoria,
dopo `ai/`, a passare senza alcun gap in quattro sessioni consecutive),
mentre `containers/` ha rivelato il gap di connettività più grande trovato
finora nella KB — 4 file orfani in un solo sotto-hub, contro il massimo di
2 osservato in `ci-cd/strategie` (#630). Il pattern "hub non aggiornato
dopo la creazione di nuovi figli" resta sistemico ma non uniforme: due
categorie su quattro controllate finora (`ci-cd`, `containers`) lo mostrano,
due (`ai`, `security`) no — la correlazione sembra con la frequenza di
crescita della categoria più che con la sua dimensione.

## Prossima sessione consigliata

Non prima di 2026-10-04. Con `ai/`, `ci-cd/`, `containers/` e `security/`
ora verificate a livello di sotto-hub interni (2 su 4 con gap reali), il
prossimo giro dovrebbe coprire i sotto-hub interni di `docs/cloud/**`
(aws/azure, entrambi già grandi e a rischio di figli orfani accumulati) e
valutare se aprire una proposta di follow-up per una regola strutturale
permanente in CLAUDE.md (checklist obbligatoria "aggiorna il genitore" nel
protocollo 1️⃣ Nuovo Argomento) — il pattern è ora confermato in 2 categorie
su 4, con containers/kubernetes come caso peggiore finora.
