# KB Saturation Report — 2026-09-27 (sessione #630)

## Gate meccanico

```
file_count: 315, target: 330, over_target: false, headroom: 15
category_saturated_pct: 85, allow_zero_proposals: true
```

Sotto target. Focus raccomandato dalla sessione precedente (#627): controllo
di connettività hub→figli sui sotto-hub **interni** (secondo livello) di
`docs/ai/**/_index.md` e `docs/ci-cd/**/_index.md`, mai verificati con questo
criterio specifico (solo l'hub di categoria era stato controllato finora).

## Copertura stimata per categoria

| Categoria | Files | Coverage % | Depth | Note |
|-----------|-------|------------|-------|------|
| ai/ (7 sotto-hub) | tutti i figli linkati | 100% connesso | Controllati tutti e 7 i sotto-hub (`agents`, `fondamentali`, `mlops`, `modelli`, `sviluppo`, `tokens-context`, `training`): ogni figlio è raggiungibile dalla grid del proprio sotto-hub | Nessun gap — categoria pulita a questo livello |
| ci-cd/ (8 sotto-hub) | 2 sotto-hub con figli orfani | gap di connettività | Controllati tutti e 8 i sotto-hub. `github-actions`, `gitlab-ci`, `gitops`, `jenkins`, `platform-engineering`, `tools` sono puliti (100% figli linkati). `strategie` e `testing` hanno figli completi non linkati | Gap reale: `strategie/trunk-based-development.md` + `strategie/feature-flags.md` orfani — prop-076 (high); `testing/performance-testing.md` orfano — prop-077 (medium) |

## Categorie vicine alla saturazione

Confermate sature nelle sessioni precedenti (invariato): **databases/**,
**dev/linguaggi/**, **messaging/rabbitmq**, **cloud/aws**, **security/**,
**networking/**, **dev/testing, dev/data, dev/resilienza, dev/sicurezza,
dev/integrazioni**, **monitoring/**, **iac/**, **cloud/azure/** (100%
connesso). **ai/** confermata pulita anche al livello dei sotto-hub interni
in questa sessione.

## Categorie con gap reali

- **ci-cd/strategie/_index.md**: 2 file figli (`trunk-based-development`,
  `feature-flags`) non raggiungibili dalla sezione Relazioni dell'hub —
  prop-076 (high).
- **ci-cd/testing/_index.md**: 1 file figlio (`performance-testing`) non
  raggiungibile dalla lista argomenti dell'hub — prop-077 (medium).

## Focus usato in questa sessione

Come raccomandato da #627: controllo mirato di connettività sui sotto-hub
**interni** (secondo livello, non l'hub di categoria) di `docs/ai/**` e
`docs/ci-cd/**`. Risultato misto: `ai/` è risultata completamente pulita a
questo livello (prima categoria a passare il controllo senza alcun gap in
tre sessioni), mentre `ci-cd/` ha confermato il pattern sistemico — 2 dei
suoi 8 sotto-hub avevano figli orfani. Il pattern "nuovo file nato dopo
l'ultimo aggiornamento della grid/lista del genitore" resta la criticità
strutturale dominante, ma non è universale: dipende da quanto spesso la
categoria riceve nuovi file rispetto a quanto viene toccato l'hub.

## Prossima sessione consigliata

Non prima di 2026-10-04. Con `ai/` e `ci-cd/` ora verificate a livello di
sotto-hub interni, il prossimo giro dovrebbe coprire i sotto-hub interni di
`docs/containers/**` e `docs/security/**` — mai controllati con questo
criterio specifico e tra le categorie più grandi della KB, quindi a rischio
più alto di figli orfani accumulati nel tempo. Se anche lì il pattern è
sistemico (3 categorie su 4 controllate), vale la pena aprire una proposta
di follow-up per una regola strutturale permanente in CLAUDE.md (checklist
obbligatoria "aggiorna il genitore" nel protocollo 1️⃣ Nuovo Argomento).
