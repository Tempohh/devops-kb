---
title: "Pulumi — Policy as Code (CrossGuard)"
slug: policy-as-code
category: iac
tags: [pulumi, iac, policy-as-code, crossguard, compliance, security, governance, ci-cd]
search_keywords: [crossguard, pulumi crossguard, policy as code, policy pack, pulumi policy, policy pack new, enforcement level, advisory, mandatory, remediate, pulumi cloud policy groups, organization policy, compliance as code, guardrail iac, governance pulumi, pulumi opa, opa vs crossguard, sentinel vs crossguard, checkov vs crossguard, pulumi convert, resource validation policy, stack policy pack, pac pulumi, policy enforcement pulumi]
parent: iac/pulumi/_index
related: [iac/pulumi/fondamentali, iac/pulumi/stacks-ambienti, iac/terraform/testing]
official_docs: https://www.pulumi.com/docs/using-pulumi/crossguard/
status: reviewed
difficulty: intermediate
last_updated: 2026-10-04
last_verified: 2026-10-04
---

# Pulumi — Policy as Code (CrossGuard)

## Panoramica

**CrossGuard** è il framework di Policy as Code nativo di Pulumi: permette di scrivere regole di governance (sicurezza, costi, naming, compliance) come codice, nello stesso linguaggio usato per l'infrastruttura, e di farle valutare **durante** `pulumi preview`/`pulumi up` — prima che qualsiasi risorsa venga creata o modificata. A differenza di uno scan statico post-hoc (checkov, tfsec), CrossGuard intercetta il piano di esecuzione in tempo reale e può bloccare il deploy nello stesso momento in cui viene proposto.

Le policy sono raggruppate in **Policy Pack**: progetti a sé stanti (con proprio `PulumiPolicy.yaml`) che contengono una o più regole, ciascuna con un **enforcement level** che determina cosa succede in caso di violazione.

**Quando usare CrossGuard:**
- Bloccare deploy che violano regole di sicurezza (bucket pubblici, security group aperti, encryption disabilitata) prima che la risorsa esista nel cloud
- Applicare policy centralizzate multi-team via Pulumi Cloud, senza duplicare codice in ogni progetto
- Scrivere regole complesse con logica arbitraria (loop, chiamate a API esterne, aggregazioni cross-resource) nello stesso linguaggio dell'infrastruttura

**Quando NON usare CrossGuard (o usarlo in combinazione con altro):**
- Audit di infrastruttura **già esistente** e non gestita da Pulumi → serve uno scanner statico (checkov, Prowler, cloud-native CSPM), CrossGuard valuta solo risorse nel piano di uno stack Pulumi
- Team multi-tool (Terraform + Pulumi) che vogliono un unico motore di policy condiviso → OPA/Sentinel restano scelte più neutre rispetto al provider IaC
- Governance "read-only" senza necessità di bloccare il deploy → uno scan CI post-apply può bastare ed è più semplice da introdurre in un repo esistente

## Concetti Chiave

### Policy Pack

Un **Policy Pack** è un progetto Pulumi dedicato, generato con `pulumi policy new`, che contiene una funzione `validateResource` (o `validateStack`) per ogni regola:

```bash
# Creare un policy pack TypeScript per AWS
pulumi policy new aws-typescript --name my-org-security

# Creare un policy pack Python
pulumi policy new aws-python --name my-org-security
```

Struttura generata:

```
my-org-security/
├── PulumiPolicy.yaml     # Nome e runtime del policy pack
├── index.ts              # Definizione delle policy
├── package.json
└── tsconfig.json
```

```yaml
# PulumiPolicy.yaml
runtime: nodejs
name: my-org-security
description: Policy di sicurezza baseline per tutti gli stack AWS
```

### Enforcement Level

Ogni policy dichiara uno dei tre livelli, indipendentemente dalle altre regole nello stesso pack:

| Livello | Comportamento | Uso tipico |
|---|---|---|
| `advisory` | Stampa un warning, il deploy **prosegue** | Rollout iniziale di una nuova regola, raccolta dati senza impatto |
| `mandatory` | Blocca `pulumi up`/`pulumi preview` con exit code ≠ 0 se violata | Regole di sicurezza consolidate, gate di produzione |
| `remediate` | **Modifica automaticamente** la risorsa nel piano prima dell'apply | Correzioni sicure e non ambigue (es. forzare un tag mancante) |

!!! warning "`remediate` modifica risorse a runtime senza intervento umano"
    `remediate` altera il piano d'esecuzione — non solo lo segnala. Su risorse già esistenti gestite da Pulumi, una regola `remediate` mal scritta può cambiare configurazioni in produzione senza che nessuno abbia approvato esplicitamente quel singolo cambiamento nel diff. Riservalo a correzioni ovvie e reversibili (aggiungere un tag), mai a modifiche strutturali (cambiare CIDR, instance type, IAM policy).

### Policy Pack vs Scanning Statico

CrossGuard valuta il piano **durante** `preview`/`up`, con accesso allo stato completo delle risorse (inclusi valori calcolati a runtime). Uno scanner come checkov/tfsec legge solo il codice sorgente staticamente, prima di qualunque `plan`. I due approcci sono complementari: uno scanner esterno resta utile come ulteriore livello difensivo o per riusare policy già scritte in Rego altrove, ma checkov/tfsec non leggono nativamente programmi Pulumi.

!!! note "`pulumi convert` non è un export verso Terraform"
    `pulumi convert` converte programmi **verso** Pulumi (da Terraform HCL, YAML, o tra linguaggi Pulumi): non produce HCL scansionabile da checkov/tfsec.

!!! note "Audit di risorse esistenti: audit policy group (Pulumi Cloud)"
    Pulumi Cloud offre anche gli **audit policy group**, che valutano le risorse trovate da **Discovery** (scansione schedulata degli account cloud) — incluse quelle create con CloudFormation, Terraform o console, non solo con Pulumi. Disponibili nei tier Essentials, Pro ed Enterprise. Il criterio sopra resta valido per CrossGuard in senso stretto (gate su `preview`/`up`); per l'audit di infrastruttura esistente valutare gli audit policy group o uno scanner esterno. Vedi [Pulumi Policies](https://www.pulumi.com/docs/insights/policy/).


## Architettura / Come Funziona

```
pulumi preview / pulumi up
        │
        ▼
┌────────────────────────────────────────────┐
│  Pulumi Engine costruisce il resource graph │
│  (desired state, come da fondamentali.md)   │
└──────────────────┬───────────────────────────┘
                   │
                   ▼
┌────────────────────────────────────────────┐
│  CrossGuard valuta ogni risorsa del piano   │
│  contro tutte le policy attive nel pack     │
│                                              │
│  advisory   → warning, continua             │
│  mandatory  → violazione = STOP (exit ≠ 0)  │
│  remediate  → risorsa nel piano modificata  │
└──────────────────┬───────────────────────────┘
                   │ tutte le mandatory passate
                   ▼
              pulumi apply
```

Le policy possono essere applicate in due modalità:

1. **Locale/esplicita**: passando `--policy-pack` al comando, valido solo per quella singola esecuzione.
2. **Centralizzata via Pulumi Cloud**: un **organization policy group** assegna automaticamente uno o più policy pack a tutti gli stack di un'organizzazione (o a un sottoinsieme), senza che ogni team debba ricordarsi di passare il flag. Questo è il pattern consigliato per garantire che **nessun deploy** possa saltare la valutazione.

```bash
# Pubblicare un policy pack sull'organizzazione (richiede Pulumi Cloud)
pulumi policy publish my-org

# Applicare il pack a un policy group esistente
pulumi policy enable my-org/my-org-security latest --policy-group default

# Elencare i policy pack pubblicati e le versioni
pulumi policy ls
```

## Configurazione & Pratica

### Esempio 1 — Vietare bucket S3 pubblici (TypeScript)

```typescript
// index.ts — Policy Pack TypeScript
import * as aws from "@pulumi/aws";
import { PolicyPack, validateResourceOfType } from "@pulumi/policy";

new PolicyPack("my-org-security", {
    policies: [
        {
            name: "s3-no-public-read",
            description: "I bucket S3 non devono avere ACL public-read o public-read-write.",
            enforcementLevel: "mandatory",
            validateResource: validateResourceOfType(aws.s3.Bucket, (bucket, args, reportViolation) => {
                if (bucket.acl === "public-read" || bucket.acl === "public-read-write") {
                    reportViolation(
                        `Il bucket '${args.name}' ha ACL '${bucket.acl}': i bucket S3 non possono essere pubblici.`
                    );
                }
            }),
        },
    ],
});
```

### Esempio 2 — Tag obbligatori e instance type in produzione (Python)

```python
# __main__.py — Policy Pack Python
from pulumi_policy import (
    EnforcementLevel,
    PolicyPack,
    ResourceValidationPolicy,
    ResourceValidationArgs,
    ReportViolation,
)

def required_tags_validator(args: ResourceValidationArgs, report_violation: ReportViolation):
    required = ["Environment", "Owner", "CostCenter"]
    tags = args.props.get("tags", {})
    for tag in required:
        if tag not in tags:
            report_violation(f"Risorsa '{args.resource_name}' manca del tag obbligatorio '{tag}'.")

required_tags_policy = ResourceValidationPolicy(
    name="required-tags",
    description="Ogni risorsa deve avere i tag Environment, Owner e CostCenter.",
    validate=required_tags_validator,
    enforcement_level=EnforcementLevel.MANDATORY,
)

def prod_instance_type_validator(args: ResourceValidationArgs, report_violation: ReportViolation):
    if args.resource_type != "aws:ec2/instance:Instance":
        return
    stack_tag = args.props.get("tags", {}).get("Stack", "")
    instance_type = args.props.get("instanceType", "")
    forbidden_types = ["t2.micro", "t2.nano", "t3.nano"]
    if stack_tag == "prod" and instance_type in forbidden_types:
        report_violation(
            f"Instance type '{instance_type}' non ammesso in produzione (risorse sotto-dimensionate)."
        )

prod_instance_type_policy = ResourceValidationPolicy(
    name="prod-instance-type-minimum",
    description="In produzione non sono ammessi instance type di fascia t2/t3-nano.",
    validate=prod_instance_type_validator,
    enforcement_level=EnforcementLevel.MANDATORY,
)

PolicyPack(
    name="my-org-security",
    enforcement_level=EnforcementLevel.ADVISORY,
    policies=[required_tags_policy, prod_instance_type_policy],
)
```

### Esecuzione locale

```bash
# Validare un singolo stack con un policy pack locale
pulumi up --policy-pack ./my-org-security

# Solo preview (dry-run) con policy
pulumi preview --policy-pack ./my-org-security

# Passare configurazione al policy pack (es. lista tag richiesti parametrica)
pulumi up --policy-pack ./my-org-security --policy-pack-config ./policy-config.json
```

La policy deve dichiarare uno `config` schema (campo `config` della policy, es. `requiredTags: { type: "array" }`) e leggerlo con `getConfig()`; gli esempi sopra usano valori fissi, quindi il file seguente è uno schema illustrativo.

```json
// policy-config.json — override runtime dei parametri di una policy
{
    "required-tags": {
        "requiredTags": ["Environment", "Owner", "CostCenter", "Team"]
    }
}
```

### CI/CD — Fallire la pipeline su violazione mandatory

`pulumi up` termina con **exit code diverso da 0** se una policy `mandatory` viene violata: nessuna logica extra serve in CI, basta non silenziare l'exit code dello step.

```yaml
# .github/workflows/pulumi-deploy.yml
name: Pulumi Deploy

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  preview-with-policy:
    if: github.event_name == 'pull_request'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: pulumi/actions@v7
        with:
          command: preview
          stack-name: prod
          # Input dedicato `policyPacks` (non esiste `extra-args`); se una policy
          # mandatory è violata lo step fallisce (exit ≠ 0) e il job termina in errore
          policyPacks: ./my-org-security
        env:
          PULUMI_ACCESS_TOKEN: ${{ secrets.PULUMI_ACCESS_TOKEN }}

  deploy:
    # L'apply gira solo dopo il merge su main, non sulle PR
    if: github.event_name == 'push'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: pulumi/actions@v7
        with:
          command: up
          stack-name: prod
          policyPacks: ./my-org-security
        env:
          PULUMI_ACCESS_TOKEN: ${{ secrets.PULUMI_ACCESS_TOKEN }}
```

Credenziali cloud e install delle dipendenze sono omesse per brevità. Per la config del pack c'è l'input `policyPackConfigs` (path al JSON).

```bash
# Verifica manuale dell'exit code (utile fuori da action dedicate)
pulumi up --policy-pack ./my-org-security --yes
echo "Exit code: $?"   # 0 = ok, diverso da 0 = almeno una mandatory violata
```

### Policy Group organization-wide (Pulumi Cloud)

La creazione di un policy group e l'assegnazione degli stack si fanno dalla console Pulumi Cloud (o via REST API): il gruppo `default` copre tutti gli stack dell'org, i gruppi aggiuntivi un sottoinsieme. Funzionalità di governance org-wide legata al tier di Pulumi Cloud.

La CLI ha il comando `pulumi policy group` con sottocomandi `new`, `edit`, `get`, `list`, `remove` (i primi quattro marcati **EXPERIMENTAL** nella reference); non esistono `create`/`update --add-stack`. L'assegnazione degli stack resta più affidabile da console o REST API.

```bash
# Pubblicare e abilitare la versione più recente sul gruppo
pulumi policy publish my-org
pulumi policy enable my-org/my-org-security latest --policy-group security-baseline
```

## Best Practices

!!! tip "Rollout graduale: advisory → mandatory"
    Introdurre una policy nuova direttamente come `mandatory` su uno stack esistente spesso blocca deploy legittimi per violazioni pregresse mai corrette. Pattern consigliato: pubblicare la regola come `advisory`, misurare quante risorse esistenti la violerebbero, sanare quelle risorse, **poi** promuovere a `mandatory`.

- **Un policy pack per dominio, non uno monolitico**: separare `security-baseline`, `cost-controls`, `naming-conventions` in pack distinti permette di assegnarli a policy group diversi e di versionarli in modo indipendente.
- **Versionare i policy pack come codice**: repo Git dedicato, PR review sulle regole stesse — una policy troppo permissiva è un rischio quanto l'infrastruttura che dovrebbe proteggere.
- **Testare le policy con dati sintetici** prima di pubblicarle: Pulumi supporta l'esecuzione di policy pack contro stack di test isolati per validare che la regola catturi i casi attesi e non generi falsi positivi massivi.
- **Preferire `mandatory` a `remediate` per default**: `remediate` va riservato a un piccolo set di correzioni ovvie (tag mancanti, naming); qualunque cosa tocchi networking, IAM o dimensionamento va bloccata e corretta manualmente, mai auto-modificata.

## Troubleshooting

### Errore: "policy pack not found" durante `pulumi up --policy-pack`

**Sintomo:** `pulumi up --policy-pack ./my-org-security` fallisce con `error: could not find policy pack`.

**Causa:** Il path passato non punta a una directory con `PulumiPolicy.yaml` valido, oppure le dipendenze del policy pack (`npm install`/`pip install -r requirements.txt`) non sono state installate.

**Soluzione:**
```bash
# Verifica che il file esista e sia leggibile
cat ./my-org-security/PulumiPolicy.yaml

# Installa le dipendenze del policy pack (separate da quelle dello stack)
cd my-org-security && npm install
# oppure per Python
cd my-org-security && pip install -r requirements.txt
```

### Conflitto tra policy locali e organization policy

**Sintomo:** Un deploy viene bloccato da una regola che non è presente nel repo locale del progetto.

**Causa:** Un policy group Pulumi Cloud applica policy org-wide **in aggiunta** a quelle passate con `--policy-pack` in locale — non le sostituisce. Entrambe vengono valutate.

**Soluzione:**
```bash
# Elencare le policy attualmente assegnate all'organizzazione/stack
pulumi policy group list
# dettaglio di un gruppo e dei pack assegnati (EXPERIMENTAL): pulumi policy group get <nome>, oppure console Pulumi Cloud

# Se la regola org-wide è quella che blocca, va gestita centralmente
# (richiedere eccezione al team platform, non aggirarla in locale)
```

### Falsi positivi `mandatory` su risorse già esistenti (import)

**Sintomo:** Dopo un `pulumi import`, una policy `mandatory` blocca ogni successivo `pulumi up` sullo stesso stack, anche senza modifiche a quella risorsa.

**Causa:** CrossGuard valuta lo stato **desiderato** ad ogni run, non solo il diff: una risorsa importata che non rispettava la policy al momento della creazione continua a violarla finché non viene corretta nel codice.

**Soluzione:**
```bash
# Opzione 1: correggere la risorsa nel codice per farla rientrare nella policy
# (es. aggiungere il tag mancante, poi pulumi up)

# Opzione 2 (temporanea): abbassare la policy a advisory per il tempo
# necessario a pianificare la remediation, senza sbloccarla in modo permanente
```

### `remediate` modifica una risorsa in modo inatteso durante `preview`

**Sintomo:** `pulumi preview` mostra un `update` non richiesto su una risorsa che nessuno ha toccato nel codice.

**Causa:** Una policy `remediate` sta iniettando un cambiamento (es. normalizzando un tag o un valore) ad ogni valutazione del piano.

**Soluzione:**
```bash
# Identificare quale policy sta rimediando: l'output di preview lista
# il nome della policy accanto alla riga "remediated by policy"

# Disabilitare temporaneamente il pack per confermare la causa
pulumi preview   # senza --policy-pack

# Se confermato, restringere la condizione della regola remediate
# (es. applicarla solo a risorse create ex-novo, non a update esistenti)
```

## Relazioni

??? info "Terraform Testing — Confronto con OPA/Sentinel/Checkov"
    Terraform non ha un motore di policy nativo equivalente a CrossGuard: si appoggia a conftest/OPA (policy in Rego), Sentinel (solo Terraform Cloud/Enterprise) o scanner esterni come checkov. CrossGuard invece è integrato nell'engine Pulumi e scritto nello stesso linguaggio dell'infrastruttura — nessun DSL separato da imparare.

    **Approfondimento completo →** [Terraform — Testing e Quality Gate](../terraform/testing.md)

??? info "Pulumi Fondamentali — Prerequisito"
    Capire il ciclo `preview`/`up` e il resource graph è necessario per capire *quando* CrossGuard interviene nel flusso.

    **Approfondimento completo →** [Pulumi Fondamentali](fondamentali.md)

??? info "Pulumi Stack e Ambienti — Dove assegnare le policy"
    I policy group si assegnano a stack specifici (es. solo `prod`) o all'intera organizzazione. La strategia di stack-per-ambiente descritta in questo file determina la granularità con cui applicare policy diverse (più permissive in dev, `mandatory` strette in prod).

    **Approfondimento completo →** [Pulumi — Stack e Ambienti](stacks-ambienti.md)

## Riferimenti

- [CrossGuard — Documentazione ufficiale](https://www.pulumi.com/docs/using-pulumi/crossguard/)
- [Policy as Code — Guida ai Policy Pack](https://www.pulumi.com/docs/using-pulumi/crossguard/get-started/)
- [Pulumi Cloud — Organization Policy Groups](https://www.pulumi.com/docs/pulumi-cloud/organizations/policy-groups/)
- [pulumi policy CLI reference](https://www.pulumi.com/docs/cli/commands/pulumi_policy/)
- [pulumi convert — Conversione di programmi verso Pulumi](https://www.pulumi.com/docs/using-pulumi/pulumi-converter/)
