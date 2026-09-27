# KB Saturation Report — 2026-09-27 (sessione #616)

## Gate meccanico

```
file_count: 315, target: 330, over_target: false, headroom: 15
category_saturated_pct: 85, allow_zero_proposals: true
```

Sotto target. Focus di questa sessione (da raccomandazione #613): `docs/monitoring/`
e `docs/iac/` — categorie mai state in focus esplicito nelle sessioni #591-#615.

## Copertura stimata per categoria

| Categoria | Files | Coverage % | Depth | Note |
|-----------|-------|------------|-------|------|
| monitoring/ | 20 file (incl. 5 `_index`) | ~95% contenuto | Alta: ogni file letto (sre/_index, alerting/_index, tools/_index, tools/_index dettaglio) ha troubleshooting reale e best practice specifiche | Nessun gap di contenuto — gap solo di connettività hub→figli |
| iac/ | 17 file (incl. 4 `_index`) | ~95% contenuto | Molto alta: terraform (5 sotto-argomenti + testing + ci-cd), ansible (2), pulumi (3), crossplane (1, molto dettagliato: 500+ righe, 4 scenari troubleshooting) | Nessun gap di contenuto reale — solo incoerenza narrativa minore nell'_index |

## Analisi di questa sessione

File analizzati (10): `monitoring/_index.md`, `monitoring/tools/_index.md`,
`monitoring/sre/_index.md`, `monitoring/alerting/_index.md`,
`iac/_index.md`, `iac/crossplane/_index.md`, `iac/crossplane/fondamentali.md`,
`iac/ansible/_index.md`, `iac/pulumi/_index.md`, `iac/terraform/_index.md`.

**Verificato NON un gap — contenuto monitoring/ e iac/**: tutti i file di
dettaglio ispezionati (specialmente `crossplane/fondamentali.md`, 520 righe,
4 scenari di troubleshooting con comandi `kubectl` reali) sono completi,
con esempi concreti, best practice e anti-pattern. Nessuna sezione
promessa-e-assente.

**Gap reale #1 — `monitoring/sre/_index.md` elenca 1 argomento su 5**:
la cartella contiene `slo-sla-sli.md`, `error-budget.md`,
`capacity-planning.md`, `chaos-engineering.md`, `incident-management.md`
(tutti `status: complete`), ma l'hub ("## Argomenti") linka solo
`slo-sla-sli.md`. 4 file completi sono irraggiungibili dalla navigazione
del sito. → prop-067 (extend-section, priority high — gap più ampio
trovato in questa sessione).

**Gap reale #2 — `monitoring/alerting/_index.md` non elenca
`prometheus-rules.md`**: la cartella ha 2 file, l'hub ne linka 1
(`alertmanager.md`). → prop-068 (extend-section, priority medium).

**Gap reale #3 — `monitoring/tools/_index.md` non elenca
`continuous-profiling.md`**: 6 file nella cartella, 5 nell'elenco
puntato dell'hub. → prop-069 (extend-section, priority medium).

**Gap minore #4 — `iac/_index.md`**: la tabella "Strumenti Coperti" lista
Terraform/Ansible/Pulumi/Crossplane come pari livello, ma "## Percorso di
Apprendimento" si ferma al punto 4 (Ansible) senza mai citare Pulumi o
Crossplane, entrambi sezioni sviluppate. → prop-070 (extend-section,
priority low — incoerenza narrativa, non un vero blocco di scoperta
perché la tabella sopra li cita comunque).

Pattern ricorrente rilevato: **hub `_index.md` che invecchia peggio dei
file figli** — quando si aggiunge un file di dettaglio a una sezione, la
lista "## Argomenti" dell'_index non viene sempre aggiornata in parallelo.
Stesso pattern già visto in #613 (dev/linguaggi, dev/processi) ma lì era
il campo `related` a mancare, qui è la lista di navigazione interna alla
sezione stessa — variante più subdola perché il file esiste ed è pure
linkato da `related` altrove, solo non dall'hub della propria categoria.

## Categorie vicine alla saturazione

- **monitoring/** e **iac/**: confermate mature per contenuto in questa
  sessione — nessun gap di `new-file`/`extend-section` sostanziale oltre
  ai 4 fix di connettività sopra.
- Confermate sature nelle sessioni precedenti (invariato): **databases/**,
  **dev/linguaggi/**, **security/**, **messaging/rabbitmq**, **networking**,
  **cloud/aws**, **ci-cd/testing**, **dev/testing, dev/data, dev/resilienza,
  dev/sicurezza, dev/integrazioni**.

## Categorie con gap reali

- **monitoring/sre/_index.md**: 4/5 argomenti non raggiungibili dall'hub —
  prop-067 (high).
- **monitoring/alerting/_index.md**: 1/2 argomenti non raggiungibile —
  prop-068 (medium).
- **monitoring/tools/_index.md**: 1/6 argomenti non raggiungibile —
  prop-069 (medium).
- **iac/_index.md**: percorso di apprendimento incompleto rispetto alla
  tabella strumenti — prop-070 (low).

## Focus usato in questa sessione

`docs/monitoring/` e `docs/iac/`, come raccomandato dal report #613 (aree
mai esplorate in focus esplicito nelle sessioni #591-#615). Entrambe
risultano mature sul contenuto; il valore emerso è interamente di
connettività hub→figli (pattern "_index non aggiornato quando si aggiunge
un file"), coerente con `allow_zero_proposals` ma non azzerato perché
i gap di navigazione superano il test di utilità (contenuto reale
invisibile, non ridondanza).

## Prossima sessione consigliata

Non prima di 2026-10-04. Nessuna delle due aree richiede ulteriore
esplorazione di contenuto a breve termine. Suggerito un controllo
mirato — non un'intera sessione di analisi — su altri hub `_index.md`
della KB per verificare se il pattern "elenco argomenti disperso rispetto
ai file reali della cartella" si ripete altrove (es. `ci-cd/jenkins/_index.md`,
che ha 5 file figli, o `cloud/aws/*/​_index.md`, mai controllati con
questo criterio specifico). In assenza di quel controllo, ruotare il
focus su `docs/security/` (ultima verifica di contenuto risalente a
#591-#596, non ancora ri-controllata con il criterio di connettività
hub) o su `docs/networking/` (stesso discorso).
