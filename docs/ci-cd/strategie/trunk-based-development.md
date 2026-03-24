---
title: "Trunk-Based Development"
slug: trunk-based-development
category: ci-cd
tags: [branching, git, continuous-integration, feature-flags, devops]
search_keywords: [TBD, trunk based development, GitFlow, short-lived branches, main branch, feature branches, branching strategy, continuous integration, release branch, pair programming, branch management, monorepo, merge conflict, development workflow]
parent: ci-cd/strategie/_index
related: [ci-cd/strategie/deployment-strategies, ci-cd/strategie/feature-flags, ci-cd/testing/contract-testing, ci-cd/gitops/argocd]
official_docs: https://trunkbaseddevelopment.com/
status: complete
difficulty: intermediate
last_updated: 2026-03-24
---

# Trunk-Based Development

## Panoramica

Trunk-Based Development (TBD) è una strategia di branching Git in cui tutti gli sviluppatori integrano le proprie modifiche direttamente sul branch principale (`main`/`trunk`) — o tramite feature branch di brevissima durata (< 2 giorni). L'obiettivo primario è eliminare il costo di integrazione e ridurre il batch size dei commit, abilitando una vera Continuous Integration.

Al contrario di GitFlow (con branch `develop`, `release`, `hotfix`, `feature` che vivono settimane o mesi), TBD tratta l'integrazione come un processo continuo e non come un evento periodico. È il modello adottato da Google, Facebook, e dalla maggior parte delle organizzazioni tech ad alto ritmo di delivery.

TBD **non** significa deployare ogni commit in produzione: il disaccoppiamento tra integrazione e rilascio si ottiene tramite feature flags e release branches di breve durata.

## Concetti Chiave

!!! note "Trunk (Main Branch)"
    Il branch principale condiviso da tutti gli sviluppatori. Deve essere **sempre** in uno stato deployable. Nessun lavoro incompiuto arriva qui senza essere nascosto da un feature flag.

!!! note "Short-Lived Feature Branch"
    Branch opzionale, creato per un singolo sviluppatore o una coppia, con durata massima di 1-2 giorni. Viene integrato nel trunk tramite PR con CI obbligatoria. Non è il branch `feature/` di GitFlow.

!!! warning "Regola dei 2 giorni"
    Se un branch supera i 2 giorni senza essere integrato nel trunk, è un segnale che il task è troppo grande. Il corretto rimedio è scomporre il lavoro, non ritardare l'integrazione.

!!! tip "Branch by Abstraction"
    Tecnica che permette di fare refactoring massicci senza un long-lived branch: si introduce un livello di astrazione intorno al codice da modificare, si migra incrementalmente, poi si rimuove l'astrazione.

### Confronto con GitFlow

| Aspetto | GitFlow | Trunk-Based Development |
|---|---|---|
| Branch principali | `main`, `develop`, `release/*`, `hotfix/*`, `feature/*` | Solo `main` (+ short-lived) |
| Durata feature branch | Settimane/mesi | 0-2 giorni |
| Merge conflict | Frequenti e complessi | Rari e piccoli |
| Ciclo di release | Schedulato (sprint, milestone) | Continuo o on-demand |
| CI efficace | Difficile (branch longevi) | Naturale |
| Curva apprendimento | Alta per coordinare branch | Alta per discipline TBD |
| Adatto a | Team poco frequenti, open source | Team high-frequency, prodotti SaaS |

### Quando usare GitFlow invece di TBD

GitFlow resta valido in questi scenari:
- **Release schedulati** con ciclo lungo (es. librerie, firmware, app mobile con store review)
- **Team distribuiti con bassa sincronia** e poca comunicazione
- **Open source con molti contributor esterni** non fidati
- **Compliance** che richiede approvazione manuale per ogni release

## Architettura / Come Funziona

### Flusso di lavoro base

```
Developer A                 Developer B
    │                           │
    ├─ git pull main            ├─ git pull main
    ├─ [modifica piccola]       ├─ [modifica piccola]
    ├─ git push main ─────────► │   (fast-forward o merge pulito)
    │                           ├─ git push main
    │ ◄─────────────────────────┤
    │
    [CI: test, lint, build] × ogni commit
```

### Flusso con Short-Lived Branch + PR

```
main ──────┬──────────────────┬────────►
           │                  │
           └─ feature/xxx ────┘
              (max 2 giorni)
              (1 developer)
              (CI obbligatoria)
              (code review snella)
```

### Release Branches

Quando serve una release stabile (es. per testing QA o app store), si crea un branch **a partire dal trunk** solo al momento del rilascio:

```
main ──●──●──●──●──●──●──●──►  (continua lo sviluppo)
             │
             └─ release/1.4 ──[cherry-pick hotfix]──► v1.4.1
```

Il branch di release è **read-only** salvo cherry-pick di hotfix critici. Non si sviluppa su di esso.

### Feature Flags come abilitatore

Il codice incompleto arriva nel trunk ma rimane inattivo. I feature flags separano il momento dell'**integrazione** da quello del **rilascio**:

```python
# Prima dell'attivazione del flag — codice nel trunk ma invisibile agli utenti
if feature_flags.is_enabled("new-checkout-flow", user):
    return new_checkout_handler(request)
else:
    return legacy_checkout_handler(request)
```

Quando il team è pronto, si attiva il flag — senza alcun deploy.

## Configurazione & Pratica

### Repository Setup

```bash
# Proteggere il trunk con regole di branch
# GitHub — via UI o GitHub CLI
gh api repos/{owner}/{repo}/branches/main/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["ci/tests","ci/lint"]}' \
  --field enforce_admins=false \
  --field required_pull_request_reviews='{"required_approving_review_count":1}' \
  --field restrictions=null
```

### Pre-commit hooks per qualità locale

```bash
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-merge-conflict   # blocca commit con marker di conflict

  - repo: https://github.com/psf/black
    rev: 23.12.1
    hooks:
      - id: black

  - repo: https://github.com/PyCQA/flake8
    rev: 7.0.0
    hooks:
      - id: flake8
```

### CI Pipeline per TBD

```yaml
# .github/workflows/ci.yml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Lint
        run: flake8 .

      - name: Test
        run: pytest --cov=app --cov-report=xml

      - name: Coverage gate
        run: |
          coverage=$(python -c "import xml.etree.ElementTree as ET; t=ET.parse('coverage.xml').getroot(); print(float(t.attrib['line-rate'])*100)")
          echo "Coverage: $coverage%"
          python -c "assert float('$coverage') >= 80, f'Coverage {$coverage}% < 80%'"
```

### Branch by Abstraction — Esempio pratico

Scenario: sostituire un client HTTP legacy con uno nuovo.

```python
# Step 1 — Introduce l'astrazione (merge in trunk)
from abc import ABC, abstractmethod

class HttpClient(ABC):
    @abstractmethod
    def get(self, url: str) -> Response: ...

    @abstractmethod
    def post(self, url: str, data: dict) -> Response: ...

class LegacyHttpClient(HttpClient):
    """Wrapper del client esistente — invariato"""
    def get(self, url): return legacy_lib.get(url)
    def post(self, url, data): return legacy_lib.post(url, data)
```

```python
# Step 2 — Implementa il nuovo client (merge incrementale in trunk)
class ModernHttpClient(HttpClient):
    def get(self, url): return httpx.get(url)
    def post(self, url, data): return httpx.post(url, json=data)
```

```python
# Step 3 — Switcha tramite feature flag (merge in trunk)
def get_http_client() -> HttpClient:
    if feature_flags.is_enabled("modern-http-client"):
        return ModernHttpClient()
    return LegacyHttpClient()
```

```python
# Step 4 — Rimuovi l'abstraction quando la migrazione è completa
# (solo dopo disattivazione del flag + cleanup)
```

### Commit atomici e messaggi

TBD richiede disciplina sul size dei commit. Ogni commit deve essere:

```bash
# ✅ Corretto — piccolo, atomico, sempre verde
git commit -m "feat(auth): add OAuth2 PKCE flow for SPA clients

Implements RFC 7636 code challenge/verifier. Feature flag 'oauth2-pkce'
controls activation. Unit tests cover happy path and error cases."

# ❌ Sbagliato — batch enorme, mescolate feature e refactor
git commit -m "fix stuff and add new feature and refactor auth"
```

### Strategia di merge

```bash
# Preferire squash merge per PR piccole
git merge --squash feature/xxx

# O rebase per preservare storia lineare
git rebase main
git push origin main

# Evitare merge commit "noiosi" su PR a singolo commit
```

## Best Practices

### Do

- **Commit frequente sul trunk** — almeno 1 volta al giorno per sviluppatore
- **Test suite veloce** — la CI deve completare in < 10 minuti per non bloccare il flusso
- **Feature flags per work-in-progress** — mai codice a metà senza protezione
- **Branch by abstraction per refactoring** — evita long-lived branch anche per grandi refactoring
- **Code review asincrona ma rapida** — target < 4 ore per la review di una PR
- **Scomporre i task** se non riesci a integrare entro 2 giorni
- **Monitoring del cycle time** — dal primo commit alla produzione, target < 1 giorno

### Non fare

| Anti-pattern | Problema | Alternativa |
|---|---|---|
| Feature branch di 2+ settimane | Merge conflict esplosivo | Scomponi + feature flags |
| Merge su `develop` invece di `main` | Ri-introduce un layer GitFlow | Mergia sempre su trunk |
| Lock del trunk per QA manuale | Blocca tutti gli altri | Quality gate automatici |
| "Stash" del lavoro in WIP commit | Storia sporca, CI non valida | Short-lived branch con PR |
| Skip CI "per velocità" | Rompe il trunk | Mai — fix la CI lenta |
| Deploy di ogni commit senza controllo | Rischio produzione | Feature flags + deployment gates |

### Discipline tecniche necessarie

TBD funziona bene solo se il team adotta queste pratiche complementari:

1. **Test automatici affidabili** — senza di essi, ogni merge è rischioso
2. **Feature flags** — per nascondere il codice incompleto
3. **Pair/mob programming** — riduce la necessità di code review lunghe
4. **Continuous Deployment** (o almeno Continuous Delivery) — per sfruttare i benefici del ciclo breve
5. **Observability** — per rilevare regressioni post-deploy rapidamente

## Troubleshooting

### "Il trunk si rompe spesso dopo le merge"

**Cause comuni:**
- Test suite insufficiente o lenta
- CI non obbligatoria prima del merge
- Commit troppo grandi con troppe modifiche contemporanee

**Soluzioni:**
```bash
# Verifica che la CI sia bloccante
gh api repos/{owner}/{repo}/branches/main/protection | jq '.required_status_checks'

# Aggiungi test di regressione per ogni bug trovato
# Riduci il scope dei commit
```

### "I feature flags si accumulano e diventano debito tecnico"

**Problema:** Feature flags non vengono mai rimossi dopo l'attivazione.

**Soluzione — Lifecycle dei flag:**
```python
# Flag con data di scadenza esplicita
@feature_flag(name="new-checkout-flow", expires="2026-06-01")
def new_checkout_handler(request):
    ...
```

```yaml
# Ticket di cleanup automatico — es. con GitHub Actions
- name: Check expired feature flags
  run: python scripts/check_flag_expiry.py --warn-days 30
```

### "Il team resiste perché abituato a GitFlow"

**Approccio di migrazione graduale:**

1. **Fase 1:** Ridurre la durata dei feature branch (target: < 1 settimana)
2. **Fase 2:** Introdurre feature flags per i branch long-lived rimanenti
3. **Fase 3:** Ridurre a < 2 giorni
4. **Fase 4:** TBD completo

Non è necessario fare il cambio in un giorno.

### "Come gestire hotfix in TBD?"

```bash
# Hotfix direttamente su trunk (se hai CD o deploy rapido)
git checkout main
git pull
# fix the bug
git push origin main
# deploy immediato tramite pipeline

# Hotfix su release branch (se serve per una versione specifica)
git checkout release/2.3
git cherry-pick <commit-hash-from-main>
git tag v2.3.1
git push origin release/2.3 --tags
```

## Relazioni

??? info "Deployment Strategies — Collegamento con TBD"
    TBD controlla **quando il codice arriva nel trunk**; le deployment strategies (blue/green, canary, rolling) controllano **come il codice va in produzione**. I due pattern si combinano: TBD fornisce un flusso continuo di commit, le strategie di deployment gestiscono il rischio del rilascio.

    **Approfondimento completo →** [Deployment Strategies](./deployment-strategies.md)

??? info "Feature Flags — L'abilitatore chiave di TBD"
    Senza feature flags, TBD è applicabile solo per modifiche complete e non rischiose. Con i feature flags, è possibile integrare qualsiasi lavoro in corso senza rischio per la produzione. Feature flags e TBD sono quasi inseparabili a scala.

    **Approfondimento completo →** [Deployment Strategies — Feature Flags](./deployment-strategies.md#feature-flags)

??? info "GitOps — TBD come fondamento"
    I sistemi GitOps (ArgoCD, Flux) si basano sul trunk come source of truth. TBD è il modello di branching naturale per GitOps: ogni commit sul trunk scatena riconciliazione nel cluster.

    **Approfondimento completo →** [ArgoCD](../gitops/argocd.md)

## Riferimenti

- [trunkbaseddevelopment.com](https://trunkbaseddevelopment.com/) — riferimento ufficiale e community site
- [Google Engineering Practices](https://google.github.io/eng-practices/) — pratiche di review di Google
- [Accelerate (book)](https://itrevolution.com/accelerate-book/) — Nicole Forsgren et al. — evidenza statistica che TBD correla con alta performance DevOps (DORA research)
- [Branch by Abstraction](https://martinfowler.com/bliki/BranchByAbstraction.html) — Martin Fowler
- [Feature Toggles](https://martinfowler.com/articles/feature-toggles.html) — Pete Hodgson / Martin Fowler
- [Ship / Show / Ask](https://martinfowler.com/articles/ship-show-ask.html) — strategia di PR per TBD
