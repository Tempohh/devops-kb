# DevOps Knowledge Base

Documentazione DevOps scalabile, organizzata e moderna.

## Setup (Windows)

### Prerequisiti
- Python 3.10+ installato e nel PATH
- Git installato
- Node.js 18+ (per Claude Code)

### Installazione

```powershell
# Clonare il repository (o inizializzare)
git init
git add .
git commit -m "Initial project structure"

# Installare le dipendenze Python
pip install -r requirements.txt

# Preview locale
mkdocs serve
```

Il sito sarà disponibile su `http://127.0.0.1:8000`

### Deploy su GitHub Pages

```powershell
# Collegare il repository a GitHub
git remote add origin https://github.com/USERNAME/devops-kb.git
git push -u origin main

# Deploy
mkdocs gh-deploy
```

## Struttura del Progetto

```
devops-kb/
├── CLAUDE.md           # Istruzioni per Claude Code + criticità
├── mkdocs.yml          # Configurazione MkDocs
├── requirements.txt    # Dipendenze Python
├── docs/               # Contenuto della knowledge base
│   ├── index.md        # Homepage
│   ├── _metadata/      # Tassonomia e metadati globali
│   ├── _templates/     # Template per nuovi argomenti
│   ├── cloud/          # Cloud providers
│   ├── networking/     # Networking e protocolli
│   ├── messaging/      # Message broker e streaming
│   ├── databases/      # Database
│   ├── security/       # Security e autenticazione
│   ├── ci-cd/          # CI/CD e automazione
│   ├── containers/     # Container e orchestration
│   └── ai/             # AI e ML services
└── assets/             # Risorse statiche
    ├── diagrams/       # Diagrammi Draw.io
    ├── images/         # Immagini
    └── styles/         # CSS personalizzato
```

## Workflow con Claude Code

Vedi `CLAUDE.md` per i protocolli operativi completi.
