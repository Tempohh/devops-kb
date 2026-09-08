# Istruzioni: Passaggio di Review Critica

Stai eseguendo una **review critica** di un file esistente della Knowledge Base.
Questo NON è l'audit meccanico (righe/code-block/troubleshooting): qui giudichi
**correttezza, attualità e valore reale**. Modello atteso: alto ragionamento.

## Task corrente

Leggi `_automation/current-task.json` per `path` e `reason`.

## Processo

### Fase 1 — Lettura completa
Leggi il file per intero. Leggi 1–2 file `related` per contesto.

### Fase 2 — Giudizio su 3 assi

| Asse | Domanda | Se fallisce |
|---|---|---|
| **Correttezza** | Ci sono affermazioni tecnicamente sbagliate, comandi che non funzionano, API/flag inesistenti, versioni citate come correnti ma superate? | Correggi in loco le imprecisioni evidenti e sicure. Per quelle che richiedono verifica esterna, annota `<!-- REVIEW: verificare X -->` e abbassa `status`. |
| **Attualità** | Il contenuto riflette lo stato del 2026? Tool deprecati presentati come vivi? Manca una novità rilevante e stabile? | Aggiorna i punti sicuri. Apri una proposta `currency` (vedi Fase 4) se serve un intervento ampio. |
| **Valore** | Un DevOps che legge SOLO questo file risolve un problema reale, o è contenuto generico/di riempimento? C'è overlap forte con un altro file? | Se è debole ma recuperabile: nota cosa manca. Se è ridondante: proponi `consolidate`. |

### Fase 3 — Aggiornamento frontmatter

- Se il file è **corretto, attuale e utile**: imposta `status: reviewed` e `last_verified: <oggi>`.
- Se resta lavoro non banale: `status: needs-review`, `last_verified: <oggi>`, e lascia i marker `<!-- REVIEW: ... -->`.
- Non toccare `last_updated` se non hai modificato il contenuto in modo sostanziale.

### Fase 4 — Proposta di follow-up (solo se necessaria)

Se serve un intervento oltre i ritocchi sicuri, crea `_automation/proposals/pending/prop-NNN.yaml`
(numero progressivo dopo l'ultimo in `pending/` e `approved/`) con `type` fra
`extend-section`, `consolidate`, `currency`. Massimo 1 proposta per review.

### Fase 5 — NON toccare `_automation/state.yaml`

Il sistema aggiorna lo stato da solo.

## Output finale (max 10 righe)

```
REVIEW: [path]
Correttezza: [ok | corretti N punti | N da verificare]
Attualità:   [ok | aggiornati N punti | proposta currency aperta]
Valore:      [ok | debole: ... | ridondante con ...: proposta consolidate]
status -> [reviewed | needs-review]
```
