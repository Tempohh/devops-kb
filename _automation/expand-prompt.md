# Istruzioni: Sessione di Espansione

Stai eseguendo un'**espansione significativa** di un file esistente della Knowledge Base.

## Task corrente

Leggi `_automation/current-task.json` per conoscere il `path` del file da espandere e il `reason` che descrive cosa espandere.

## Processo

### Fase 1 — Orientamento
1. Leggi il file indicato in `path`
2. Leggi 1-2 file `related` dal frontmatter per mantenere coerenza terminologica e non duplicare contenuto

### Fase 2 — Pianificazione
Identifica le sezioni da espandere guidandoti dal `reason` nel task. Tipicamente:
- Sezioni con meno di 20 righe
- Troubleshooting con meno di 4 scenari
- Sezioni "Configurazione & Pratica" con pochi o nessun esempio reale

### Fase 3 — Espansione

Obiettivi minimi per questa run:
- **+100-200 righe** di contenuto nuovo rispetto al file attuale
- **Almeno 3 nuovi code block** con esempi concreti e reali (non placeholder)
- **Troubleshooting**: porta a minimo 5 scenari totali con sintomo/causa/soluzione/comandi
- **Casi d'uso avanzati**: aggiungi pattern enterprise o edge case se rilevanti per il tema

**Non fare:**
- Non ripetere contenuto già presente
- Non modificare il frontmatter tranne `last_updated` (oggi) e `status: complete`
- Non riscrivere sezioni già buone

### Fase 4 — NON aggiornare state.yaml

**Non leggere né modificare `_automation/state.yaml`.**
Il sistema PS1 aggiorna lo stato automaticamente. Concentrati solo sul file di contenuto.

## Output finale (obbligatorio)

```
EXPAND: [path]
Sezioni espanse: [lista]
Righe aggiunte: ~[numero]
Code block nuovi: [numero]
Troubleshooting totale: [numero scenari]
```
