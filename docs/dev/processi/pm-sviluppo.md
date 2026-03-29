---
title: "Project Management Tecnico per Microservizi"
slug: pm-sviluppo
category: dev
tags: [project-management, team-topologies, dora-metrics, tech-debt, engineering-metrics, roadmap, capacity-planning, flow-metrics]
search_keywords: [project manager tecnico, engineering manager, PM sviluppo, EM, team topologies, skelton pais, stream-aligned team, enabling team, platform team, complicated subsystem team, interaction modes, collaboration mode, x-as-a-service, facilitating, DORA metrics, dora, lead time for changes, deployment frequency, change failure rate, MTTR, mean time to restore, flow metrics, velocity, story points, cycle time, throughput, work in progress, WIP, PR size, pull request size, code review turnaround, engineering metrics, tech debt register, tech debt register, technical debt tracking, capacity allocation, 20 percent rule, roadmap tecnica, product roadmap, roadmap alignment, API governance, breaking changes, internal API contract, dipendenze tra team, dependency management teams, accoppiamento tra servizi, engineering KPI, vanity metrics, non-vanity metrics, SPACE framework, developer productivity, ingegneria del software enterprise, software engineering management, CTO, VP engineering, team lead]
parent: dev/processi/_index
related: [dev/processi/enterprise-sdlc, monitoring/sre/incident-management, monitoring/sre/slo-sla-sli, monitoring/sre/capacity-planning]
official_docs: https://itrevolution.com/product/accelerate/
status: complete
difficulty: advanced
last_updated: 2026-03-29
---

# Project Management Tecnico per Microservizi

## Panoramica

Il Project Manager tecnico (o Engineering Manager, o CTO di una business unit) che governa un sistema a microservizi enterprise non gestisce un progetto software: gestisce un sistema sociotecnico. Le decisioni sul come organizzare i team, su quale metrica guardare per sapere se il sistema sta accelerando o rallentando, e su come fare in modo che i servizi di team diversi evolvano senza bloccarsi a vicenda — queste sono le leve che determinano la velocità di delivery a lungo termine.

Questo documento copre i modelli operativi fondamentali per questa figura: il framework **Team Topologies** per l'organizzazione dei team, le **DORA metrics** e le **flow metrics** come KPI tecnici non-vanity, la gestione del **tech debt** come processo (non come eccezione), la **governance delle dipendenze** tra team e servizi, e l'allineamento tra **roadmap tecnica e product roadmap**.

**A chi è rivolto:** PM tecnico, Engineering Manager, CTO/VP Engineering che governa 3+ team su un sistema a microservizi. Per team singoli o <= 3 microservizi, la maggior parte di questi modelli introduce overhead che supera il beneficio.

!!! warning "Processo senza cultura è solo burocrazia"
    Nessuno dei framework descritti qui funziona se applicato come procedura top-down. Team Topologies funziona se i team capiscono *perché* i confini esistono. DORA funziona se i team misurano per migliorare, non per essere giudicati. Il PM tecnico è un abilitatore di autonomia, non un controllore di metriche.

---

## Team Topologies

Il framework **Team Topologies** (Skelton & Pais, 2019) fornisce un vocabolario preciso per descrivere come organizzare i team intorno al flusso di valore, minimizzando il carico cognitivo e i colli di bottiglia da dipendenze.

### Quattro Tipi di Team

```
┌─────────────────────────────────────────────────────────────────┐
│  STREAM-ALIGNED TEAM                                            │
│  Allineato a un flusso di valore (prodotto, dominio, cliente)   │
│  → Ha tutto ciò che serve per portare feature in produzione     │
│  → Minimal external dependencies                               │
│  Esempio: "Team Pagamenti", "Team Catalogo", "Team Mobile"      │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  ENABLING TEAM                                                  │
│  Aiuta i stream-aligned team ad acquisire nuove capacità        │
│  → Non produce software direttamente                            │
│  → Temporaneo: esiste finché il team target è autonomo          │
│  Esempio: "Team DevOps Enablement", "Team SRE Advisory"         │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  PLATFORM TEAM                                                  │
│  Fornisce una piattaforma interna come prodotto (self-service)  │
│  → Riduce il carico cognitivo degli stream-aligned team         │
│  → Ha un "product owner" della piattaforma interna             │
│  Esempio: "Team Platform/IDP", "Team Observability", "Team CI"  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  COMPLICATED-SUBSYSTEM TEAM                                     │
│  Gestisce un sottosistema ad alta complessità specialistica     │
│  → Richiede expertise che non ha senso distribuire              │
│  → Interfaccia API pulita verso gli altri team                  │
│  Esempio: "Team ML/Recommandation Engine", "Team Cryptography"  │
└─────────────────────────────────────────────────────────────────┘
```

### Tre Modalità di Interazione

I team non si relazionano sempre allo stesso modo. Team Topologies definisce tre modalità esplicite — e la scelta di quale usare ha impatto diretto sul throughput:

```yaml
# interaction_modes.yaml — documentazione esplicita delle interazioni tra team
interaction_modes:

  collaboration:
    descrizione: |
      Due team lavorano insieme attivamente per un periodo limitato,
      condividendo ownership e conoscenza. Alta bandwidth, alta friczione.
    quando_usare:
      - Discovery di un dominio nuovo
      - Integrazione tra due sistemi non ancora definita
      - Onboarding di un team su una piattaforma nuova
    durata_tipica: "2-4 sprint (max ~2 mesi)"
    segnale_di_abuso: "Due team che collaborano da > 6 mesi senza riduzione"
    esempio: "Team Pagamenti + Team Platform → definiscono l'API di autenticazione"

  x_as_a_service:
    descrizione: |
      Un team consuma un servizio/piattaforma dell'altro con minimal interaction.
      Bassa bandwidth, bassa friczione, alta scalabilità.
    quando_usare:
      - Piattaforme mature con API stabili
      - Tooling DevOps/CI/CD fornito dal Platform Team
      - Librerie condivise con versioning semantico
    segnale_di_salute: "Ticket di supporto < 2/settimana tra i team"
    esempio: "Team Ordini usa il servizio di notifiche email tramite API REST pubblica"

  facilitating:
    descrizione: |
      Un enabling team facilita temporaneamente l'adozione di una pratica/tecnologia.
      L'obiettivo è rendere il team target autonomo.
    quando_usare:
      - Introduzione di osservabilità distribuita
      - Adozione di Kubernetes in un team che non lo conosce
      - Security review process
    segnale_di_completamento: "Il team target non chiede più supporto attivo"
    esempio: "Team SRE Advisory facilita l'adozione di SLO nel Team Catalogo"
```

### Carico Cognitivo come Metrica di Design

Il confine di un team dovrebbe essere tracciato in modo che il suo **carico cognitivo** sia gestibile. Skelton & Pais identificano tre tipi:

| Tipo | Descrizione | Obiettivo |
|------|-------------|-----------|
| **Intrinseco** | Complessità del dominio applicativo | Minimizzare tramite buoni astrazioni |
| **Estraneo** | Overhead non legato al dominio (infra, proc) | Delegare al Platform Team |
| **Germanivo** | Sforzo per acquisire nuova expertise | Lasciare spazio per questo |

!!! tip "Come misurare il carico cognitivo in pratica"
    Chiedi al team: "Quante cose devi tenere in testa contemporaneamente per fare una deploy?" Se la risposta è una lista > 10 item, il confine del team è troppo ampio o la piattaforma interna non sta facendo abbastanza.

---

## DORA Metrics e Flow Metrics

### DORA Metrics — I Quattro Indicatori di Elite Performance

Il programma **DORA** (DevOps Research and Assessment) ha identificato quattro metriche che separano i team ad alte performance dagli altri, basate su studi empirici su migliaia di organizzazioni.

```
┌──────────────────────┬────────────────────────────────────────────────┐
│ METRICA              │ DEFINIZIONE                                     │
├──────────────────────┼────────────────────────────────────────────────┤
│ Lead Time for Changes│ Tempo dal commit al deployment in produzione    │
│                      │ Elite: < 1 ora | Low: > 1 mese                 │
├──────────────────────┼────────────────────────────────────────────────┤
│ Deployment Frequency │ Quante volte si fa deploy in produzione         │
│                      │ Elite: multipli/giorno | Low: < 1/mese         │
├──────────────────────┼────────────────────────────────────────────────┤
│ Change Failure Rate  │ % deploy che causano incident/rollback          │
│                      │ Elite: 0-15% | Low: 46-60%                     │
├──────────────────────┼────────────────────────────────────────────────┤
│ Mean Time to Restore │ Tempo medio per ripristinare il servizio        │
│                      │ Elite: < 1 ora | Low: > 1 settimana            │
└──────────────────────┴────────────────────────────────────────────────┘
```

!!! note "DORA misura il sistema, non i team"
    Le DORA metrics sono indicatori della capacità dell'intero sistema di delivery — pipeline CI/CD, architettura, processo, cultura. Un basso deployment frequency può dipendere da una pipeline lenta, da deployment manuali, da test instabili, o da processi di approvazione. Non usarle per confrontare team individuali in modo isolato.

```yaml
# Esempio: configurazione raccolta DORA metrics con dati da GitHub/GitLab + PagerDuty
dora_data_sources:
  lead_time:
    source: "git log — tempo tra primo commit di una PR e merge + deploy timestamp"
    query: |
      SELECT
        AVG(TIMESTAMPDIFF(HOUR, pr_first_commit, deploy_timestamp)) as lead_time_hours
      FROM deployments
      WHERE environment = 'production'
        AND DATE_TRUNC('week', deploy_timestamp) = CURRENT_WEEK

  deployment_frequency:
    source: "CD pipeline — eventi di deploy su production environment"
    query: |
      SELECT
        COUNT(*) / 7.0 as deploys_per_day
      FROM deployments
      WHERE environment = 'production'
        AND deploy_timestamp >= NOW() - INTERVAL '30 days'

  change_failure_rate:
    source: "PagerDuty incidents + deploy events correlati"
    query: |
      SELECT
        COUNT(DISTINCT incident_id) * 1.0 / COUNT(DISTINCT deploy_id) as cfr
      FROM deployments d
      LEFT JOIN incidents i
        ON i.triggered_at BETWEEN d.deploy_timestamp AND d.deploy_timestamp + INTERVAL '1 hour'
      WHERE d.environment = 'production'

  mttr:
    source: "PagerDuty — tempo da incident_triggered a incident_resolved"
    query: |
      SELECT AVG(TIMESTAMPDIFF(MINUTE, triggered_at, resolved_at)) as mttr_minutes
      FROM incidents
      WHERE severity IN ('P1', 'P2')
        AND triggered_at >= NOW() - INTERVAL '90 days'
```

### Flow Metrics — Visibilità sul Flusso di Lavoro

Le **flow metrics** (Mik Kersten, *Project to Product*) misurano il flusso di valore attraverso il sistema di delivery. Complementano le DORA metrics e sono più utili per il PM tecnico nel quotidiano.

```python
# Flow metrics — definizioni operative per un team che usa Jira/Linear

FLOW_METRICS = {
    "flow_velocity": {
        "definizione": "Numero di item completati per sprint/settimana",
        "differenza_da_story_points": """
            Story points misurano l'effort stimato (input).
            Flow velocity misura gli item completati (output).

            Un team che completa 3 feature/settimana con 0 bug è più produttivo
            di uno che completa 30 story points ma con 5 bug e 2 rollback.
        """,
        "come_misurare": "COUNT(issues WHERE status=Done AND closed_at IN periodo)",
        "livello": "team",
    },

    "flow_time": {
        "definizione": "Tempo dall'inizio del lavoro su un item al suo completamento",
        "include": "attesa, sviluppo, review, QA, staging, deploy",
        "differenza_da_lead_time_dora": """
            Lead time DORA: primo commit → deploy production
            Flow time: item moved to 'In Progress' → item moved to 'Done'
            Flow time è più ampio e cattura il tempo in attesa pre-sviluppo.
        """,
        "target_tipico": "< 5 giorni per story, < 2 settimane per epic",
    },

    "flow_efficiency": {
        "definizione": "Percentuale del flow time in cui c'è lavoro attivo",
        "formula": "active_time / total_flow_time * 100",
        "benchmark_industria": "10-25% (la maggior parte del tempo è attesa)",
        "come_migliorare": "Ridurre WIP, eliminare bottleneck nel processo di review/approval",
    },

    "flow_load": {
        "definizione": "Work In Progress (WIP) attuale del team",
        "legge_di_little": "Lead Time = WIP / Throughput",
        "implicazione": "Aumentare il WIP aumenta il lead time, non la velocità",
        "limite_consigliato": "WIP <= capacità_team * 1.5",
    },
}
```

### Story Points vs Flow Metrics — Quando Usare Cosa

```markdown
## Confronto: Story Points vs Flow Metrics

| Aspetto | Story Points | Flow Metrics |
|---------|-------------|--------------|
| Cosa misurano | Effort relativo stimato | Throughput/tempo reale |
| Utilità | Planning sprint, comunicare complessità relativa | Previsioni, identificare colli di bottiglia |
| Limite principale | Soggettivi, non confrontabili tra team | Richiedono dati storici consistenti |
| Vanity risk | Alto (velocity gonfiata, "velocity washing") | Basso se usate correttamente |
| Consigliato per | Negoziazione backlog con PO | KPI engineering a lungo termine |

**Raccomandazione pratica:**
- Usa story points per il dialogo PO ↔ team (stima relativa)
- Usa flow metrics per misurare il miglioramento del processo nel tempo
- Non usare story points come KPI di produttività — sono uno strumento di conversazione
```

---

## Tech Debt Register

Il **tech debt register** è il documento/backlog che rende visibile il debito tecnico accumulato con una struttura che permette al PM di priorizarlo accanto alle feature funzionali.

### Struttura del Tech Debt Register

```yaml
# tech-debt-register.yaml — artefatto mantenuto aggiornato dal team
tech_debt_register:
  servizio: "order-service"
  ultimo_aggiornamento: "2026-03-29"
  debit_ratio_attuale: "23%"  # ore stimate debito / ore totali backlog

  items:
    - id: "TD-042"
      titolo: "Rimozione accoppiamento diretto order-service → inventory-service"
      categoria: "deliberate-prudent"  # quadrante Fowler
      data_creazione: "2025-11-15"
      stimato_giorni: 3
      impatto_se_non_risolto: |
        Ogni modifica al modello Stock richiede una modifica coordinata in order-service.
        Attualmente 2-3 deploy coordinati/mese → bottleneck sulla delivery indipendente.
      dipendenze_bloccate:
        - "Migrazione a event-driven architecture (Q3)"
      priorita: "alta"
      sprint_target: "Sprint 24"

    - id: "TD-039"
      titolo: "Upgrade Spring Boot 3.2 → 3.4"
      categoria: "accidental-prudent"
      data_creazione: "2025-10-01"
      stimato_giorni: 1
      impatto_se_non_risolto: |
        Spring Boot 3.2 EOL a Novembre 2026. Dipendenze di sicurezza non più patchate.
        CVE potenziali non risolti nelle transitive dependencies.
      priorita: "media"
      sprint_target: "Sprint 26"

    - id: "TD-031"
      titolo: "Refactoring PaymentService: God Class da 2000 LOC"
      categoria: "accidental-imprudent"
      data_creazione: "2025-07-20"
      stimato_giorni: 8
      impatto_se_non_risolto: |
        Ogni nuova feature richiede 30-40% più tempo del previsto a causa della complessità.
        Onboarding nuovi developer: > 2 settimane per capire il flusso di pagamento.
        Test coverage impossibile al di sopra del 45% senza refactoring strutturale.
      priorita: "alta"
      sprint_target: "Q2-2026 (richiede spike dedicato)"
```

### Capacity Allocation — La Regola del 20%

```markdown
## Policy: Capacity Allocation per Tech Debt

### Accordo Standard

Il team riserva il **20% della capacità sprint** per lavoro tecnico non funzionale.

Questa percentuale NON è negoziabile sprint-per-sprint: è un accordo strutturale.
Variazioni ammesse: 15% (codebase sana, < 2 anni) — 30% (legacy con debito critico).

### Come Gestire la Pressione del Product Manager

Quando il PM chiede "perché non possiamo usare quel 20% per feature?":

1. **Mostrare il Tech Debt Ratio**: se > 25%, il team sta già spendendo più del 25%
   del suo tempo su rallentamenti invisibili causati dal debito esistente.

2. **Proiettare la tendenza**: un team che non ripaga il debito vede il proprio
   throughput scendere del 5-10% ogni trimestre (misurabile dal flow time).

3. **L'analogia finanziaria**: il debito tecnico ha "interessi". Non pagarlo ora
   significa pagare di più domani — con il tasso che cresce nel tempo.

### Segnali che il 20% non è sufficiente

| Segnale | Soglia di Allarme |
|---------|------------------|
| Tech Debt Ratio | > 30% del backlog |
| Flow Time medio in aumento | +20% QoQ |
| Bug production rate | +30% MoM |
| Nuovi sviluppatori non produttivi dopo 3 settimane | → complexity tax |
```

---

## Governance delle Dipendenze tra Team

In un sistema a microservizi enterprise, le dipendenze tra team sono il principale moltiplicatore (o distruttore) di velocità. La governance delle API interne è un processo, non solo un accordo tecnico.

### API Contract tra Team

```yaml
# Esempio: internal-api-contract.yaml — artefatto in repo del servizio provider
api_contract:
  servizio_provider: "inventory-service"
  team_owner: "Team Warehouse"
  versione: "2.1.0"

  stability_guarantee:
    livello: "stable"  # stable | beta | experimental
    backwards_compatibility: true
    deprecation_policy: "Minimo 3 mesi di notice prima di breaking change"

  consumer_teams:
    - team: "Team Ordini"
      endpoints_usati: ["/api/v2/stock/check", "/api/v2/stock/reserve"]
      notifica_breaking_change: "team-ordini@company.slack"

    - team: "Team Reportistica"
      endpoints_usati: ["/api/v2/stock/history"]
      notifica_breaking_change: "team-reportistica@company.slack"

  breaking_changes_policy:
    processo:
      1: "RFC pubblicato nel team channel almeno 3 mesi prima"
      2: "Review con tutti i consumer team (meeting dedicato)"
      3: "Periodo di dual-versioning: v1 + v2 coesistono"
      4: "Migration guide scritta e validata con almeno un consumer team"
      5: "Deprecation notice nel changelog e negli header HTTP (Deprecation: date)"
      6: "Sunset della versione precedente con avviso 1 mese prima"

  versioning:
    schema: "semantic versioning (semver)"
    major_bump: "breaking change (cambia il contratto)"
    minor_bump: "additive change (backward compatible)"
    patch_bump: "bug fix senza cambio contratto"
```

### Dependency Matrix

```markdown
## Service Dependency Matrix — Aggiornamento Trimestrale

Il PM tecnico dovrebbe mantenere una dependency matrix visibile a tutti i team:

| Consumer ↓ / Provider → | auth-svc | inventory-svc | order-svc | notification-svc |
|--------------------------|----------|---------------|-----------|-----------------|
| **order-service**        | sync/HTTP | sync/HTTP    | —         | async/Kafka     |
| **checkout-service**     | sync/HTTP | sync/HTTP    | sync/HTTP | —               |
| **reporting-service**    | —         | async/Kafka  | async/Kafka| —              |
| **mobile-bff**           | sync/HTTP | —            | sync/HTTP | —               |

**Segnali di allarme nella matrix:**
- Un servizio ha > 5 consumer sync → collo di bottiglia strutturale
- Due team in coupling reciproco (A → B e B → A) → candidate per merger o event-driven
- Servizio critico senza async fallback → single point of failure
```

!!! warning "Coupling sincronno tra team è debt architetturale"
    Ogni chiamata HTTP sincrona tra servizi di team diversi crea una dipendenza di availability (se A chiama B, il downtime di B impatta A). Il PM tecnico dovrebbe monitorare il crescere di coupling sincrono come segnale di design fragile e promuovere pattern event-driven dove appropriato.

---

## Roadmap Tecnica vs Product Roadmap

### Il Problema dell'Allineamento

La product roadmap dice *cosa* costruire per gli utenti. La roadmap tecnica dice *come* rendere sostenibile la costruzione. Quando le due non sono sincronizzate, si accumula debito tecnico invisibile o si rallenta la delivery di feature per "ragioni misteriose".

```markdown
## Framework: Roadmap Duale Allineata

### Product Roadmap (esempio Q2-2026)
| Priorità | Feature | Team | Sprint Target |
|----------|---------|------|---------------|
| P0 | Pagamenti con PayPal | Team Pagamenti | Sprint 21 |
| P1 | Raccomandazioni AI v2 | Team ML | Sprint 23 |
| P2 | Notifiche push iOS | Team Mobile | Sprint 25 |

### Tech Roadmap Parallela (Q2-2026)
| Priorità | Investimento Tecnico | Abilitazione | Team | Sprint Target |
|----------|---------------------|--------------|------|---------------|
| P0 | Refactoring PaymentGateway (anticipa PayPal) | Sprint 21 | Team Pagamenti | Sprint 20 |
| P0 | Upgrade infra ML: GPU autoscaling | Abilita AI v2 | Team Platform | Sprint 22 |
| P1 | Migrazione push notification provider | Sostituisce provider deprecato | Team Mobile | Sprint 24 |
| P1 | Riduzione Tech Debt Ratio order-service | Sostenibilità Q3 | Team Ordini | continuo |

### Regola di Allineamento
Per ogni feature P0/P1 nella product roadmap, verificare:
1. Esiste debito tecnico bloccante nel servizio target? → schedulare 1 sprint prima
2. La piattaforma supporta i requisiti non funzionali? → coinvolgere Platform Team nello sprint di preparazione
3. Ci sono dipendenze tra team? → avviare interaction mode "collaboration" in anticipo
```

### Come Presentare la Roadmap Tecnica al Business

```markdown
## Template: Tech Investment Proposal per C-Suite

### Investimento: Migrazione da Monolite a Microservizi — Order Processing

**Perché ora:**
Il modulo order processing ha un deployment frequency di 2/mese (benchmark elite: multipli/giorno).
Ogni deploy richiede 4 ore di test regression. Con la crescita del catalogo prevista per Q3,
questo bottleneck impedirà di rispettare i SLA.

**Impatto misurabile:**
- Deployment frequency: da 2/mese → 15/mese (8x)
- Lead time per changes: da 3 settimane → 3 giorni
- Team autonomia: 3 team che ora si bloccano → lavoro indipendente

**Costo:**
- 3 sprint di 4 developer (= ~12 settimane/developer)
- Zero funzionalità nuove in questo periodo per il Team Ordini

**ROI proiettato:**
- Break-even: sprint successivi (recupero velocità immediato)
- Anno 1: +30% feature throughput per il dominio ordini
```

---

## Engineering Metrics Non-Vanity

Le **vanity metrics** sembrano buone ma non aiutano a prendere decisioni. Le **engineering metrics** rilevanti guidano interventi concreti.

### Metriche da Monitorare

```python
# engineering_metrics_dashboard.py — definizione metriche rilevanti

ENGINEERING_METRICS = {

    # DELIVERY SPEED
    "cycle_time": {
        "definizione": "Tempo da quando uno sviluppatore inizia a lavorare su un ticket a quando è in production",
        "misura": "PR first commit → deploy production",
        "target": "< 2 giorni per story normale",
        "perché_importa": "Cicli corti = feedback rapido = meno waste",
        "come_raccogliere": "GitHub/GitLab API → join con deploy log",
    },

    "pr_size": {
        "definizione": "Numero medio di linee cambiate per PR",
        "target_linee_cambiate": "< 400 linee (ideale < 200)",
        "perché_importa": "PR grandi rallentano il review, aumentano il rischio, difficili da rollback",
        "segnale_allarme": "Mediana > 800 linee/PR → decomposizione scadente",
        "sql": "SELECT AVG(additions + deletions) FROM pull_requests WHERE merged_at > NOW() - '30 days'::interval",
    },

    "code_review_turnaround": {
        "definizione": "Tempo medio tra PR aperta e primo review significativo",
        "target": "< 4 ore in orario lavorativo",
        "perché_importa": "Attesa review è la principale causa di alto flow time",
        "segnale_allarme": "> 24 ore → processo di review da ottimizzare o team sotto-dimensionato",
    },

    # QUALITÀ
    "defect_escape_rate": {
        "definizione": "Bug trovati in produzione / bug totali trovati (prod + staging + test)",
        "target": "< 10%",
        "perché_importa": "Bug in produzione costano 10-100x più che in sviluppo",
    },

    "test_coverage_trend": {
        "definizione": "Andamento della coverage nel tempo (non il valore assoluto)",
        "target": "Non deve scendere sprint-su-sprint",
        "perché_importa": "La coverage assoluta è meno importante del trend: una coverage che scende segnala che si aggiunge codice senza test",
    },

    # TEAM HEALTH
    "deployment_frequency_per_service": {
        "definizione": "Quante volte ogni servizio viene deployato in produzione a settimana",
        "target": "> 2/settimana per servizi attivi",
        "segnale_allarme": "< 1/settimana → possibile fear of deployment, pipeline lenta, test instabili",
    },

    "incident_recurrence_rate": {
        "definizione": "% di incident causati dallo stesso root cause di un incident precedente",
        "target": "< 5%",
        "perché_importa": "Incidenti ricorrenti indicano che i postmortem non portano a fix strutturali",
    },
}
```

### Metriche da Evitare (Vanity Metrics)

```markdown
## Anti-pattern: Metriche Vanity

| Metrica | Perché è Vanity | Metrica Migliore |
|---------|----------------|-----------------|
| Story points completati/sprint | Gonfiabili, non confrontabili tra team | Flow velocity (item completati) |
| Lines of code scritte | Più codice ≠ più valore | Cycle time, PR size |
| Numero di commit | Facile da manipolare | Deployment frequency |
| % test coverage (valore assoluto) | Un test inutile conta come copertura | Test coverage trend + defect escape rate |
| Uptime 99.9% (senza context) | Non distingue severity | MTTR per P1/P2, error budget |
| Numero di PR aperte | Non distingue PR tiny da PR enormi | PR size + code review turnaround |
| Velocity sprint trend (se usato come KPI) | I team gonfiano i punti se giudicati sulla velocity | DORA metrics |

**Principio:** una metrica è utile solo se, quando peggiora, sai esattamente su cosa intervenire.
```

---

## Best Practices

!!! tip "Start with Team Topologies, not with tools"
    La prima domanda non è "quale strumento CI/CD usiamo?" ma "come sono organizzati i team intorno al flusso di valore?". L'architettura del software tende a rispecchiare la struttura di comunicazione dell'organizzazione (Legge di Conway). Progettare prima i team, poi i servizi.

!!! tip "Le DORA metrics migliorano insieme"
    Non cercare di ottimizzare una sola DORA metric isolatamente. I team elite hanno tutte e quattro le metriche alte. Se il deployment frequency sale ma il change failure rate sale anche lui, stai deploying garbage più spesso. Monitora tutte e quattro.

!!! tip "Il Tech Debt Register è un artefatto di business"
    Presenta il tech debt register al PM/PO in termini di impatto sul delivery, non di qualità del codice. "Questo item ci costa 2 sprint extra di rallentamento ogni trimestre" è più convincente di "il codice è disordinato".

!!! warning "Non usare le metriche per valutare i singoli developer"
    Le DORA metrics e le engineering metrics misurano il **sistema**, non le persone. Usarle per review individuali incentiva comportamenti disfunzionali: PR piccole artificialmente, PR rush prima della fine sprint, paura di assegnare ticket complessi. Misura i team e i processi, non le persone.

!!! warning "Team Topologies non è un org chart permanente"
    Le team topology cambiano con la maturità del prodotto. Un enabling team diventa superfluo quando il team target è autonomo. Un complicated-subsystem team può essere assorbito da uno stream-aligned team quando la tecnologia matura. Rivedere le interaction modes ogni 6 mesi.

---

## Troubleshooting

### Deployment frequency bassa nonostante il team sia veloce

**Sintomo:** il team finisce story in 2-3 giorni ma i deploy in produzione avvengono solo 1-2/mese.

**Cause possibili:**
1. Pipeline CI/CD troppo lenta (> 30 minuti) → developer rimanda i push
2. Processo di approvazione manuale prima del deploy → collo di bottiglia umano
3. Fear of deployment per incidenti passati → blocco culturale, non tecnico
4. Deploy batch ("accumulo di feature") come policy → anti-pattern da eliminare

**Soluzione:**
```bash
# Misurare dove si perde il tempo nel pipeline
# Esempio con GitHub Actions
gh run list --workflow=deploy.yml --limit=20 --json=startedAt,completedAt,status | \
  jq '[.[] | {
    duration_min: ((.completedAt | fromdateiso8601) - (.startedAt | fromdateiso8601)) / 60,
    status: .status
  }] | group_by(.status) | map({status: .[0].status, avg_duration: ([.[].duration_min] | add / length)})'
```

### Lead time alto nonostante deployment frequency ok

**Sintomo:** si deploya spesso ma il tempo dal commit al deploy è > 1 settimana.

**Causa tipica:** il codice entra nel pipeline ma ci sono fasi di attesa (staging freeze, manual QA, approval gates) che non sono deployment ma bloccano il flow.

**Soluzione:** mappare ogni fase del pipeline con timestamp reali e identificare dove il tempo è "attesa" vs "lavoro attivo". Target: flow efficiency > 40%.

### Tech debt ratio superiore al 35% e in crescita

**Sintomo:** il team spende > 35% del tempo su lavoro tecnico non pianificato, e la percentuale cresce.

**Causa:** debito non pagato accumula "interesse" — ogni feature aggiunta su codice problematico aumenta il debito.

**Soluzione:**
```markdown
1. Freeze temporaneo di feature nuove per 1-2 sprint (debt reduction sprint)
2. Prioritizzare i TD item con impatto su flow time (TD che rallentano ogni task)
3. Applicare la "regola dello scout": ogni PR deve lasciare il codice meglio di come lo ha trovato
4. Monitorare il Tech Debt Ratio settimanalmente nel team meeting
```

### Due team bloccati in collaboration mode da > 3 mesi

**Sintomo:** Team A e Team B hanno un integration point non definito e continuano a lavorare insieme senza arrivare ad una API stabile.

**Causa:** l'API boundary non è stato progettato prima di iniziare il lavoro. La collaboration mode ha iniziato senza un deliverable chiaro.

**Soluzione:**
```markdown
1. Meeting dedicato: definire l'API contract (provider e consumer) in modo formale
2. Assegnare ownership: chi è il provider? Chi ha l'ultima parola sul design?
3. Pubblicare il contract come OpenAPI spec in un repo condiviso
4. Passare a X-as-a-Service mode una volta che il contract è stabile
5. Impostare una data di fine della collaboration mode (es. fine sprint corrente)
```

### Impossibile presentare la tech roadmap al business

**Sintomo:** il management non approva investimenti tecnici perché "non producono valore agli utenti".

**Causa:** la tech roadmap viene presentata in termini tecnici, non in termini di impatto al business.

**Soluzione:**
```markdown
Template di presentazione:
- NON: "Dobbiamo migrare da PostgreSQL 12 a 15"
- SÌ: "Il nostro database è su una versione che raggiunge l'EOL tra 6 mesi.
       Il rischio: nessuna patch di sicurezza. L'intervento richiede 1 sprint.
       Il non-intervento: rischio compliance + potenziale vulnerabilità CVE."

- NON: "Dobbiamo rifattorizzare PaymentService"
- SÌ: "Ogni nuova feature nel processo di pagamento richiede 40% più tempo del previsto.
       Abbiamo perso 3 sprint di delivery nei ultimi 6 mesi su questo servizio.
       Un refactoring di 2 sprint recupera quella velocità entro Q3."
```

---

## Relazioni

??? info "Enterprise SDLC — Approfondimento"
    Il PM tecnico opera dentro un SDLC definito. Le cerimonie di sprint planning, la Definition of Done, e la gestione del feature backlog sono coperte in dettaglio nell'SDLC enterprise.

    **Approfondimento completo →** [Enterprise SDLC per Microservizi](enterprise-sdlc.md)

??? info "Incident Management — Approfondimento"
    MTTR e Change Failure Rate (DORA) dipendono direttamente dalla qualità del processo di incident management. Runbook, on-call rotation e postmortem blameless impattano le DORA metrics.

    **Approfondimento completo →** [Incident Management](../../monitoring/sre/incident-management.md)

??? info "SLO/SLA/SLI — Approfondimento"
    Gli error budget e gli SLO collegano le DORA metrics agli obiettivi di affidabilità del servizio. Il PM tecnico usa gli error budget come meccanismo di negoziazione tra velocity e reliability.

    **Approfondimento completo →** [SLO, SLA, SLI](../../monitoring/sre/slo-sla-sli.md)

??? info "Capacity Planning — Approfondimento"
    Il capacity planning infrastrutturale è il complemento del capacity planning tecnico. Un team che cresce in deployment frequency deve fare in modo che l'infrastruttura scala di conseguenza.

    **Approfondimento completo →** [Capacity Planning](../../monitoring/sre/capacity-planning.md)

---

## Riferimenti

- [Accelerate — Forsgren, Humble, Kim (2018)](https://itrevolution.com/product/accelerate/) — La ricerca empirica alla base delle DORA metrics
- [Team Topologies — Skelton & Pais (2019)](https://teamtopologies.com/book) — Framework per l'organizzazione dei team
- [Project to Product — Mik Kersten (2018)](https://projecttoproduct.org/) — Flow metrics e Value Stream Management
- [Martin Fowler — Technical Debt](https://martinfowler.com/bliki/TechnicalDebt.html) — Il quadrante di Fowler
- [DORA State of DevOps Report](https://dora.dev/research/) — Report annuale con benchmark aggiornati
- [SPACE Framework — Microsoft Research](https://queue.acm.org/detail.cfm?id=3454124) — Framework olistico per la produttività degli sviluppatori
