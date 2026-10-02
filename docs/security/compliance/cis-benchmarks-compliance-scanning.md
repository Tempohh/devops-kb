---
title: "CIS Benchmarks e Compliance Scanning"
slug: cis-benchmarks-compliance-scanning
category: security
tags: [cis-benchmarks, hardening, kube-bench, openscap, inspec, compliance-as-code, stig]
search_keywords: [CIS benchmark, CIS Kubernetes Benchmark, kube-bench, OpenSCAP, oscap, SCAP, XCCDF, OVAL, SCAP Security Guide, SSG, DISA STIG, Chef InSpec, Cinc Auditor, compliance as code, hardening, security baseline, configuration scanning, configuration audit, node hardening, EKS benchmark, GKE benchmark, AKS benchmark, OpenShift hardening, oscap-docker, oscap-podman, dev-sec baseline, linux-baseline, benchmark CIS, conformità, scansione compliance, hardening preventivo, USG Ubuntu Security Guide, drift di configurazione]
parent: security/compliance/_index
related: [security/compliance/audit-logging, security/autorizzazione/opa, security/supply-chain/admission-control, security/runtime/falco, ci-cd/strategie/pipeline-security]
official_docs: https://www.cisecurity.org/cis-benchmarks
status: draft
difficulty: advanced
last_updated: 2026-10-02
---

# CIS Benchmarks e Compliance Scanning

## Panoramica

I **CIS Benchmarks** (Center for Internet Security) sono baseline di hardening pubblicate e versionate per centinaia di piattaforme: Linux, Kubernetes, Docker, PostgreSQL, i servizi managed dei cloud provider. Ogni benchmark è un elenco numerato di *raccomandazioni* (es. `1.2.1 Ensure that the --anonymous-auth argument is set to false`) con rationale, procedura di audit e procedura di remediation. Il **compliance scanning** automatizza la verifica: uno strumento legge la configurazione reale di nodo o cluster e la confronta con la baseline, producendo PASS/FAIL per ogni controllo.

Questo è **hardening preventivo misurabile** e complementa gli altri strati della sicurezza:

- l'[audit logging](audit-logging.md) ricostruisce *cosa è successo* (post-hoc);
- [Falco](../runtime/falco.md) rileva comportamenti anomali *mentre accadono*;
- [OPA](../autorizzazione/opa.md) e l'[admission control](../supply-chain/admission-control.md) bloccano risorse non conformi *al momento della richiesta* (admission-time);
- i CIS Benchmark verificano la **configurazione statica** di nodi, control plane e host *prima* che qualcuno li attacchi.

Si usa per: onboarding di nuovi nodi/cluster, evidenza per audit (PCI-DSS, ISO 27001, SOC 2, requisiti DISA), rilevamento di *configuration drift*. **Non** sostituisce vulnerability scanning (CVE) né runtime detection: un nodo 100% CIS-compliant può comunque eseguire un'immagine vulnerabile.

## Concetti Chiave

!!! note "Benchmark vs Profile vs Level"
    - **Benchmark**: il documento per una piattaforma e versione (es. *CIS Kubernetes Benchmark v1.x*, *CIS Ubuntu Linux 22.04 LTS Benchmark*).
    - **Level 1**: controlli a basso impatto operativo, applicabili quasi ovunque.
    - **Level 2**: controlli più stringenti, per ambienti ad alta sensibilità; possono rompere funzionalità.
    - **Profile** (SCAP/OpenSCAP): sottoinsieme di regole di un benchmark (es. `cis_level1_server`, `stig`).
    - **Scored / Automated** vs **Not Scored / Manual**: i controlli manuali richiedono giudizio umano e finiscono come `WARN` nei tool.

| Termine | Significato |
|---|---|
| **SCAP** | Security Content Automation Protocol: famiglia di standard NIST per esprimere e valutare compliance |
| **XCCDF** | Formato XML delle checklist (regole, profili, risultati) |
| **OVAL** | Linguaggio XML per le definizioni dei test sul sistema |
| **Data stream (`ds.xml`)** | File SCAP che impacchetta XCCDF + OVAL; es. `ssg-ubuntu2204-ds.xml` |
| **STIG** | Security Technical Implementation Guide, baseline DISA (difesa USA); più prescrittiva dei CIS |
| **Compliance as code** | Controlli espressi in file versionati, eseguibili in CI/CD |
| **Drift** | Divergenza tra configurazione attuale e baseline approvata |

### CIS vs OPA: non sono alternativi

| Aspetto | OPA / Gatekeeper / Kyverno | CIS Benchmark scanner |
|---|---|---|
| Oggetto valutato | Risorse Kubernetes in ingresso (Pod, Ingress…) | Config di kubelet, API server, etcd, host OS, file permissions |
| Momento | Runtime / admission-time | Scan periodico o on-demand |
| Azione tipica | Blocca (deny) la richiesta | Report PASS/FAIL, remediation separata |
| Esempio | "Nessun container privileged" | "`--anonymous-auth=false` sul kubelet", "`/etc/kubernetes/admin.conf` è `600`" |

Un cluster ben protetto usa **entrambi**: policy admission per i workload, benchmark scan per l'infrastruttura sottostante.

## Architettura / Come Funziona

I tre strumenti coprono livelli diversi:

```
┌──────────────────────────────────────────────────────────────┐
│  Workload (Pod, Deployment)  → OPA / Kyverno (admission)     │
├──────────────────────────────────────────────────────────────┤
│  Kubernetes (control plane,  → kube-bench (CIS K8s)          │
│  kubelet, etcd, policies)      InSpec (con train-kubernetes) │
├──────────────────────────────────────────────────────────────┤
│  Host OS (RHEL/Ubuntu/…)     → OpenSCAP (CIS, STIG)          │
│                                InSpec (linux-baseline)       │
├──────────────────────────────────────────────────────────────┤
│  Immagini container          → oscap-docker/podman, InSpec   │
└──────────────────────────────────────────────────────────────┘
```

Flusso comune:

1. **Baseline** scelta e versionata (benchmark + profilo + versione).
2. **Scanner** esegue i check sul target (locale, SSH, Job in-cluster).
3. **Report** machine-readable (JSON/XML/JUnit) + human-readable (HTML/CLI).
4. **Gate / ticket**: la pipeline fallisce o apre un'issue sui FAIL non in whitelist.
5. **Remediation** manuale o automatica (Ansible, bash generato), poi **re-scan**.

### Tabella comparativa: quando usare cosa

| | **kube-bench** | **OpenSCAP** | **Chef InSpec** |
|---|---|---|---|
| Scope | Solo Kubernetes (nodi + control plane) | OS-level (Linux), anche immagini container | Multi-target: OS, cloud, DB, K8s, container |
| Baseline | CIS Kubernetes e varianti managed (EKS, GKE, AKS, OpenShift) | CIS, DISA STIG, PCI-DSS, ANSSI via SCAP Security Guide | Profili propri o community (dev-sec, CIS wrapper) |
| Formato regole | YAML (`cfg/<benchmark>/*.yaml`) | XML SCAP (XCCDF/OVAL) | Ruby DSL |
| Remediation | Testo nel report (manuale) | Genera script bash/Ansible, `--remediate` | Nessuna: è audit-only |
| Personalizzazione | Media (override YAML) | Bassa (tailoring file XML) | Alta (codice) |
| Output | CLI, JSON, JUnit, Prometheus via exporter | HTML, XML ARF, XCCDF results | CLI, JSON, JUnit, HTML (via reporter) |
| Scegli quando | Hardening cluster K8s, esami CIS | Requisiti STIG/PCI su host RHEL/Ubuntu | Vuoi un unico framework e controlli custom in CI |

!!! tip "Regola pratica"
    Cluster K8s → **kube-bench**. Flotta di host Linux con requisito STIG/CIS formale → **OpenSCAP**. Controlli custom aziendali o target eterogenei → **InSpec**. Spesso si combinano: kube-bench + OpenSCAP sui nodi, InSpec per i controlli applicativi.

## Configurazione & Pratica

### kube-bench

[kube-bench](https://github.com/aquasecurity/kube-bench) (Aqua Security, Apache-2) esegue i check del CIS Kubernetes Benchmark. Deve girare **sul nodo** (accede a file di config, processi e permessi), quindi in cluster si usa un Job con `hostPID` e mount host in sola lettura.

#### Esecuzione one-shot (binario sul nodo)

```bash
# Rileva automaticamente la versione K8s e il tipo di nodo
sudo kube-bench run

# Solo un target e solo alcuni check
sudo kube-bench run --targets node
sudo kube-bench run --targets master --check 1.2.1,1.2.2

# Benchmark esplicito (utile se l'autodetect sbaglia)
sudo kube-bench run --benchmark cis-1.9

# Output JSON / JUnit per pipeline
sudo kube-bench run --json > kube-bench.json
sudo kube-bench run --junit > kube-bench-junit.xml
```

I benchmark disponibili si trovano nella directory `cfg/` del repo (`cis-1.x`, `eks-1.x.x`, `gke-1.x.x`, `aks-1.x.x`, `rh-1.x` per OpenShift): usare sempre quello che corrisponde a **distribuzione e versione** del cluster.

#### Esecuzione in cluster (Job)

```yaml
# job-kube-bench.yaml — versione semplificata del job.yaml ufficiale
apiVersion: batch/v1
kind: Job
metadata:
  name: kube-bench-node
  namespace: security
spec:
  template:
    spec:
      hostPID: true                       # necessario per ispezionare i processi kubelet
      restartPolicy: Never
      nodeSelector:
        kubernetes.io/os: linux
      containers:
        - name: kube-bench
          image: docker.io/aquasec/kube-bench:latest   # in produzione: pin su tag/digest
          command: ["kube-bench", "run", "--targets", "node", "--json"]
          volumeMounts:
            - { name: var-lib-kubelet, mountPath: /var/lib/kubelet, readOnly: true }
            - { name: etc-systemd,     mountPath: /etc/systemd,     readOnly: true }
            - { name: etc-kubernetes,  mountPath: /etc/kubernetes,  readOnly: true }
      volumes:
        - { name: var-lib-kubelet, hostPath: { path: /var/lib/kubelet } }
        - { name: etc-systemd,     hostPath: { path: /etc/systemd } }
        - { name: etc-kubernetes,  hostPath: { path: /etc/kubernetes } }
```

```bash
kubectl apply -f job-kube-bench.yaml
kubectl -n security logs job/kube-bench-node
```

!!! warning "Il Job monta path dell'host"
    `hostPID` + `hostPath` sono esattamente ciò che una policy PSS/OPA di solito vieta. Esegui il Job in un namespace dedicato con eccezione esplicita e **eliminalo a fine scan**. Per scansionare *tutti* i nodi serve un DaemonSet o un Job per nodo (`nodeName`/`nodeSelector`).

#### File di check e lettura dei risultati

Ogni benchmark in `cfg/<benchmark>/` contiene:

| File | Contenuto |
|---|---|
| `master.yaml` | Controlli sul control plane (API server, scheduler, controller manager) |
| `etcd.yaml` | Controlli su etcd |
| `controlplane.yaml` | Config del control plane (autenticazione, logging) |
| `node.yaml` | Controlli su kubelet e file dei worker |
| `policies.yaml` | RBAC, Pod Security, network policy, gestione secret |
| `managedservices.yaml` | Controlli per servizi managed (varianti EKS/GKE/AKS) |
| `config.yaml` | Path e nomi dei binari/file per la distribuzione |

Esempio di output:

```text
[INFO] 4 Worker Node Security Configuration
[INFO] 4.2 Kubelet
[FAIL] 4.2.1 Ensure that the --anonymous-auth argument is set to false (Automated)
[PASS] 4.2.2 Ensure that the --authorization-mode argument is not set to AlwaysAllow (Automated)
[WARN] 4.2.9 Ensure that the --event-qps argument is set to 0 or a level which ensures appropriate event capture (Manual)

== Remediations node ==
4.2.1 If using a Kubelet config file, edit the file to set `authentication: anonymous: enabled` to false ...

== Summary node ==
17 checks PASS
 2 checks FAIL
 9 checks WARN
 0 checks INFO
```

- **PASS**: configurazione conforme.
- **FAIL**: non conforme — la sezione *Remediations* spiega come correggere.
- **WARN**: controllo manuale o non verificabile automaticamente. **Non è un pass**: va valutato a mano e documentato.
- **INFO**: informativo.

#### Override dei check

Per escludere un check accettato come rischio (con motivazione tracciata) o adattare i path, si fornisce una config custom:

```bash
kube-bench run --config-dir /etc/kube-bench/cfg --config /etc/kube-bench/cfg/config.yaml
```

```yaml
# /etc/kube-bench/cfg/config.yaml — adatta i path alla distribuzione
node:
  kubelet:
    bins: ["kubelet"]
    confs: ["/var/lib/kubelet/config.yaml"]
    defaultconf: "/var/lib/kubelet/config.yaml"
    kubeconfig: ["/etc/kubernetes/kubelet.conf"]
```

#### Automazione: CronJob + export verso Prometheus/Grafana

kube-bench non espone metriche nativamente. Pattern consigliato: un CronJob esegue lo scan in JSON e un piccolo step converte il summary in metriche (Pushgateway o textfile collector), poi si visualizza in [Grafana](../../monitoring/tools/grafana.md).

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: kube-bench-weekly
  namespace: security
spec:
  schedule: "0 3 * * 0"                  # domenica 03:00
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      template:
        spec:
          hostPID: true
          restartPolicy: Never
          containers:
            - name: kube-bench
              image: docker.io/aquasec/kube-bench:latest
              command: ["/bin/sh", "-c"]
              args:
                - |
                  kube-bench run --targets node --json > /tmp/out.json
                  # estrai i totali dal JSON e pubblica sul Pushgateway
                  FAIL=$(grep -o '"total_fail":[0-9]*' /tmp/out.json | head -1 | cut -d: -f2)
                  WARN=$(grep -o '"total_warn":[0-9]*' /tmp/out.json | head -1 | cut -d: -f2)
                  cat <<EOF | wget -qO- --post-file=/dev/stdin http://pushgateway.monitoring:9091/metrics/job/kube-bench
                  kube_bench_checks_failed ${FAIL:-0}
                  kube_bench_checks_warn ${WARN:-0}
                  EOF
              volumeMounts:
                - { name: var-lib-kubelet, mountPath: /var/lib/kubelet, readOnly: true }
                - { name: etc-kubernetes,  mountPath: /etc/kubernetes,  readOnly: true }
          volumes:
            - { name: var-lib-kubelet, hostPath: { path: /var/lib/kubelet } }
            - { name: etc-kubernetes,  hostPath: { path: /etc/kubernetes } }
```

```yaml
# Alert Prometheus: nuovi FAIL rispetto alla baseline accettata
groups:
  - name: cis-compliance
    rules:
      - alert: CISBenchmarkFailures
        expr: kube_bench_checks_failed > 0
        for: 5m
        labels: { severity: warning }
        annotations:
          summary: "kube-bench: {{ $value }} controlli CIS in FAIL"
```

Per la gestione di Pushgateway/job batch vedi [Prometheus](../../monitoring/tools/prometheus.md). In alternativa, strumenti come Trivy Operator (`ClusterComplianceReport`) o Kubescape producono report di compliance come CRD/metriche già integrate.

### OpenSCAP

[OpenSCAP](https://www.open-scap.org/) (`oscap`) valuta host Linux contro contenuti SCAP. I contenuti per RHEL/Rocky/Alma, Ubuntu, Debian, SLES ecc. arrivano dal progetto **SCAP Security Guide (SSG / ComplianceAsCode)**.

```bash
# RHEL / Rocky / Alma
sudo dnf install -y openscap-scanner scap-security-guide
ls /usr/share/xml/scap/ssg/content/            # ssg-rhel9-ds.xml, ...

# Ubuntu: contenuti SSG da pacchetto/release upstream, oppure
# Ubuntu Security Guide (USG, richiede Ubuntu Pro) che incapsula oscap:
sudo apt install -y openscap-scanner ssg-base ssg-debderived   # contenuto derivato, verificare disponibilità
sudo usg audit cis_level1_server                               # alternativa Ubuntu Pro
```

#### Elencare i profili e lanciare una scansione

```bash
DS=/usr/share/xml/scap/ssg/content/ssg-rhel9-ds.xml

# Quali profili offre il data stream?
oscap info --profiles "$DS"
#   xccdf_org.ssgproject.content_profile_cis_server_l1
#   xccdf_org.ssgproject.content_profile_stig
#   ...

# Valutazione con report HTML (nessuna modifica al sistema)
sudo oscap xccdf eval \
  --profile xccdf_org.ssgproject.content_profile_cis_server_l1 \
  --results   /var/tmp/results.xml \
  --report    /var/tmp/report.html \
  "$DS"
```

#### DISA STIG vs CIS

Stessa macchina, profili diversi: `stig` applica le regole DISA (più restrittive, richieste in ambito difesa/gov), `cis_*_l1/l2` quelle CIS. I due insiemi **si sovrappongono ma non coincidono**: alcune regole sono in conflitto (es. valori di timeout, opzioni di mount). Si sceglie **un** profilo target per macchina, non si sommano.

#### Remediation

```bash
# 1) Genera uno script bash dalle regole FAIL di un risultato
oscap xccdf generate fix \
  --fix-type bash \
  --result-id "" \
  --output remediate.sh \
  /var/tmp/results.xml

# 2) Oppure formato Ansible
oscap xccdf generate fix --fix-type ansible \
  --profile xccdf_org.ssgproject.content_profile_cis_server_l1 \
  --output remediate.yml "$DS"

# 3) Remediation diretta durante la scansione (invasiva!)
sudo oscap xccdf eval --remediate \
  --profile xccdf_org.ssgproject.content_profile_cis_server_l1 "$DS"
```

!!! warning "Remediation automatica = rischio di downtime"
    Regole come disabilitare filesystem, cambiare PAM, SSH o auditd possono tagliarti fuori dalla macchina o rompere applicazioni. Testa **sempre** su un clone/staging, ispeziona lo script generato, applica via config management (Ansible) con rollout graduale e mantieni un accesso console out-of-band.

#### Tailoring

Per escludere regole o cambiare valori senza modificare il contenuto upstream si usa un *tailoring file* (generabile con `autotailor` o SCAP Workbench) passato con `--tailoring-file tailoring.xml`.

#### Immagini e container

```bash
# Scansione di un'immagine (pacchetto oscap-containers, richiede Docker/Podman)
oscap-podman myregistry/app:1.4 xccdf eval \
  --profile xccdf_org.ssgproject.content_profile_cis_server_l1 \
  --report /tmp/image-report.html "$DS"

# Equivalente Docker (oscap-docker)
sudo oscap-docker image myregistry/app:1.4 xccdf eval \
  --profile xccdf_org.ssgproject.content_profile_cis_server_l1 \
  --report /tmp/image-report.html "$DS"
```

La scansione di un'immagine valuta il filesystem dell'immagine: molte regole host-level (kernel, mount, servizi) non sono applicabili. Per le CVE usa [image scanning](../supply-chain/image-scanning.md); per l'hardening del daemon e delle immagini Docker vedi [Docker — Sicurezza](../../containers/docker/sicurezza.md).

### Chef InSpec

[InSpec](https://docs.chef.io/inspec/) (Progress Chef) descrive i controlli in un **Ruby DSL** dichiarativo, raggruppati in *profili* versionabili, eseguibili in locale, via SSH/WinRM, su container, cloud API e cluster K8s tramite i *transport plugin* (train).

!!! note "Licenza"
    Dalla versione 5 InSpec richiede accettazione della licenza (`--chef-license accept`) e l'uso commerciale può richiedere un abbonamento Progress. **Cinc Auditor** è il fork open source compatibile (stesso DSL, comando `cinc-auditor`) per chi vuole evitare vincoli di licenza.

#### Profilo minimale

```bash
inspec init profile company-linux-baseline
```

```ruby
# company-linux-baseline/controls/ssh.rb
control 'ssh-01' do
  impact 1.0
  title 'SSH: root login disabilitato'
  desc  'CIS 5.2.10 — PermitRootLogin deve essere "no".'
  tag cis: '5.2.10', severity: 'high'

  describe sshd_config do
    its('PermitRootLogin') { should cmp 'no' }
    its('PasswordAuthentication') { should cmp 'no' }
  end
end

control 'fs-01' do
  impact 0.7
  title 'Permessi di /etc/shadow'
  describe file('/etc/shadow') do
    it { should exist }
    its('mode')  { should cmp '0640' }
    its('owner') { should eq 'root' }
  end
end

control 'svc-01' do
  impact 0.5
  title 'Servizio telnet non installato'
  describe package('telnetd') do
    it { should_not be_installed }
  end
end
```

```yaml
# company-linux-baseline/inspec.yml
name: company-linux-baseline
title: Baseline Linux aziendale
version: 1.0.0
supports:
  - platform-family: debian
  - platform-family: redhat
depends:                      # riuso di profili community
  - name: linux-baseline
    url: https://github.com/dev-sec/linux-baseline/archive/master.tar.gz
```

#### Esecuzione

```bash
inspec check company-linux-baseline                                   # lint del profilo

# Locale
inspec exec company-linux-baseline --chef-license accept

# Remoto via SSH
inspec exec company-linux-baseline -t ssh://ec2-user@10.0.1.15 -i ~/.ssh/id_ed25519

# Container in esecuzione
inspec exec company-linux-baseline -t docker://<container-id>

# Report multipli
inspec exec company-linux-baseline \
  --reporter cli json:/tmp/inspec.json junit2:/tmp/inspec-junit.xml
```

L'exit code è **non-zero** se ci sono controlli falliti (100 = controlli falliti, 101 = solo controlli saltati; exit code distinti attivi di default), quindi si presta direttamente a fare da gate.

#### InSpec vs OpenSCAP

| | OpenSCAP | InSpec |
|---|---|---|
| Linguaggio | XML SCAP (XCCDF/OVAL), difficile da scrivere a mano | Ruby DSL leggibile e testabile |
| Contenuti | Ampi e certificati (CIS, STIG) pronti | Meno contenuti ufficiali; community (dev-sec) o profili propri |
| Remediation | Generata | Non inclusa |
| Portabilità | Linux-centrico | Linux, Windows, cloud, DB, K8s |
| Certificazione formale SCAP | Sì (NIST validated) | No |

#### Integrazione in pipeline CI/CD come gate

Compliance-as-code: i profili stanno in Git, la pipeline li esegue contro un'istanza effimera (AMI, immagine VM, container) **prima** della promozione. Il quadro generale della pipeline è in [Pipeline Security](../../ci-cd/strategie/pipeline-security.md).

```yaml
# .github/workflows/compliance.yml
name: compliance-gate
on:
  pull_request:
    paths: ["images/**", "compliance/**"]

jobs:
  inspec:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build immagine di test
        run: docker build -t app:test images/app

      - name: Avvia container
        run: docker run -d --name target app:test sleep infinity

      - name: InSpec gate
        run: |
          curl -fsSL https://omnitruck.chef.io/install.sh | sudo bash -s -- -P inspec
          inspec exec compliance/company-linux-baseline \
            -t docker://target --chef-license accept \
            --reporter cli junit2:inspec-junit.xml

      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: inspec-report
          path: inspec-junit.xml
```

Per kube-bench in CI si usa lo stesso schema: scan su un cluster di test (kind/k3d non è rappresentativo del control plane managed — meglio un cluster di staging reale) e fail sul numero di `FAIL` oltre la baseline accettata.

## Best Practices

- **Pin della versione del benchmark** (`--benchmark cis-1.9`, profilo SSG con versione): le baseline cambiano tra release; senza pin i risultati non sono confrontabili nel tempo.
- **Baseline di rischio accettato**: i FAIL non risolvibili vanno in un file di eccezioni versionato con motivazione, owner e scadenza — non ignorati in silenzio.
- **Scan continuo, non una tantum**: CronJob/pipeline periodiche per intercettare il drift; salva i report JSON come evidenza audit.
- **Shift-left**: scansiona l'immagine/AMI "golden" in CI, così i nodi nascono già conformi, e il runtime scan serve solo a rilevare drift.
- **Hardening via codice**: applica la remediation con Ansible/Terraform/cloud-init, mai a mano sui singoli nodi (non riproducibile).
- **Tratta i `WARN` come lavoro aperto**: sono controlli manuali; documenta l'esito della verifica umana.
- **Level 1 per default**, Level 2 solo dove il rischio lo giustifica e dopo test applicativi.
- **Non scambiare compliance per sicurezza**: un benchmark è una baseline minima. Affianca CVE scanning, admission policy e runtime detection.

!!! tip "Prioritizza per impatto"
    Parti dai FAIL su superficie di attacco esposta (anonymous auth su kubelet, API server insecure port, SSH root login, permessi su certificati e kubeconfig), poi il resto. Ordinare per `impact` in InSpec o per `severity` in SCAP aiuta a non annegare in centinaia di FAIL.

## Troubleshooting

### kube-bench su cluster managed (EKS/GKE/AKS): molti check falliscono o sono "non applicabili"

**Sintomo**: `[FAIL]` o errori tipo `Failed to run ... /etc/kubernetes/manifests/kube-apiserver.yaml: no such file` sui target `master`/`etcd`.

**Causa**: il control plane è gestito dal provider e non è accessibile; il benchmark generico `cis-1.x` assume file e processi che non esistono. I FAIL sono **falsi positivi**.

**Soluzione**: usa il benchmark dedicato alla piattaforma e limita ai worker:

```bash
kube-bench run --benchmark eks-1.5.0 --targets node,policies,managedservices
# GKE / AKS analoghi: gke-1.x.x, aks-1.x.x
```

Verifica i nomi esatti con `ls cfg/` o `kube-bench --help` per la tua versione; nei Job usa le varianti `job-eks.yaml` / `job-gke.yaml` / `job-aks.yaml` del repo. I controlli sul control plane sono responsabilità del provider (vedi shared responsibility) e si evidenziano con la documentazione del provider, non con lo scan.

### kube-bench: "Unable to determine benchmark version" / versione sbagliata

**Sintomo**: errore all'avvio, oppure vengono eseguiti check di una versione non coerente col cluster.

**Causa**: autodetect fallita (Job senza accesso a `kubectl`/API o versione non mappata).

**Soluzione**:

```bash
kube-bench version
kube-bench run --benchmark cis-1.9      # oppure --version 1.29 per la mappatura
kubectl version --short 2>/dev/null || kubectl version
```

Aggiorna l'immagine kube-bench a una release che include il benchmark per la tua versione K8s.

### kube-bench in Job: tutti i check del nodo restano `WARN`/`FAIL` per file mancanti

**Sintomo**: `[FAIL] 4.1.1 ... file not found`, anche se il file esiste sull'host.

**Causa**: mancano `hostPID: true` o i mount `hostPath` (`/var/lib/kubelet`, `/etc/kubernetes`, `/etc/systemd`), oppure il path del kubelet config è non standard (k3s, RKE2, Talos).

**Soluzione**: verifica i mount nel Job e personalizza `config.yaml` con i path reali; per distribuzioni particolari (RKE2, k3s) esistono benchmark/profili dedicati (`rke2-cis-*`, `k3s-cis-*`).

### OpenSCAP: "No profiles / Could not find Profile" o risultati tutti `notapplicable`

**Sintomo**: `oscap: Could not find Profile 'xccdf_org...'` oppure regole `notapplicable`.

**Causa**: data stream di un'altra OS/versione (es. `ssg-rhel8-ds.xml` su RHEL 9), o ID profilo errato.

**Soluzione**:

```bash
cat /etc/os-release
ls /usr/share/xml/scap/ssg/content/ | grep -i "$(. /etc/os-release; echo $ID)"
oscap info --profiles /usr/share/xml/scap/ssg/content/ssg-<os>-ds.xml
```

Usa il data stream che corrisponde a distribuzione **e** major version, e copia l'ID profilo esattamente come elencato.

### OpenSCAP: scansione molto lenta o HTML report enorme

**Sintomo**: `oscap xccdf eval` impiega decine di minuti.

**Causa**: regole che scandiscono l'intero filesystem (file world-writable, SUID, ownership) su grandi volumi o mount di rete.

**Soluzione**: escludi i mount remoti, usa un tailoring file per disabilitare le regole di scansione filesystem sui path dati, esegui in finestra di manutenzione.

### Remediation automatica ha rotto un servizio o l'accesso SSH

**Sintomo**: dopo `--remediate` o script generato, SSH non accetta più login, un servizio non parte, mount `noexec` bloccano software.

**Causa**: regole del profilo (PAM lockout, `PasswordAuthentication no` senza chiavi, `noexec` su `/tmp`/`/var/tmp`, firewall default-deny) applicate senza test.

**Soluzione**: ripristina da console/snapshot; riapplica su staging, genera lo script (`generate fix`) e rivedilo, escludi le regole incompatibili con tailoring documentato, deploy graduale con Ansible.

### InSpec: `License acceptance required` / exit code inatteso in CI

**Sintomo**: la pipeline si blocca con messaggio di licenza, oppure fallisce con exit code 100/101 senza chiarezza.

**Causa**: licenza non accettata in modo non interattivo; exit code 100 = controlli falliti, 101 = controlli saltati (skipped).

**Soluzione**:

```bash
export CHEF_LICENSE=accept-silent            # oppure --chef-license accept
inspec exec profile --reporter cli json:out.json
echo "exit: $?"                              # 0 ok, 100 fail, 101 skipped
```

Valuta Cinc Auditor se la licenza è un ostacolo. Per tollerare gli skip, gestisci l'exit code nello script di pipeline.

## Relazioni

??? info "Audit Logging e Runtime Security — Approfondimento"
    L'audit log ricostruisce gli eventi dopo l'incidente; i benchmark riducono la superficie prima. I check CIS sull'API server (`--audit-log-path`, `--audit-policy-file`) verificano proprio che l'audit logging sia abilitato.

    **Approfondimento completo →** [Audit Logging](audit-logging.md)

??? info "OPA — Approfondimento"
    OPA valuta policy su richieste e risorse (admission-time); i CIS Benchmark valutano la configurazione statica di nodi e control plane. Sono complementari.

    **Approfondimento completo →** [OPA](../autorizzazione/opa.md)

??? info "Admission Control — Approfondimento"
    Gatekeeper/Kyverno possono far rispettare a livello di workload molti controlli della sezione *policies* del CIS Kubernetes Benchmark (no privileged, no hostPath, ecc.).

    **Approfondimento completo →** [Admission Control](../supply-chain/admission-control.md)

??? info "Falco — Approfondimento"
    Falco rileva a runtime comportamenti che violano l'hardening (es. modifica di file sensibili); il benchmark scan verifica che la configurazione di partenza sia corretta.

    **Approfondimento completo →** [Falco](../runtime/falco.md)

??? info "Pipeline Security — Approfondimento"
    Inserisce i compliance scan come stage della pipeline; qui sono dettagliati gli strumenti concreti (kube-bench, OpenSCAP, InSpec) da usare in quello stage.

    **Approfondimento completo →** [Pipeline Security](../../ci-cd/strategie/pipeline-security.md)

## Riferimenti

- [CIS Benchmarks](https://www.cisecurity.org/cis-benchmarks) — download dei benchmark (registrazione richiesta per i PDF)
- [kube-bench](https://github.com/aquasecurity/kube-bench) — repository, `cfg/` dei benchmark e manifest Job
- [OpenSCAP](https://www.open-scap.org/) — documentazione di `oscap` e SCAP Workbench
- [ComplianceAsCode / SCAP Security Guide](https://github.com/ComplianceAsCode/content) — contenuti CIS, STIG, PCI-DSS per le principali distribuzioni
- [DISA STIGs](https://public.cyber.mil/stigs/) — baseline DISA
- [Chef InSpec](https://docs.chef.io/inspec/) — DSL, resources, reporter
- [Cinc Auditor](https://cinc.sh/) — fork open source di InSpec
- [dev-sec baselines](https://dev-sec.io/) — profili InSpec community (linux-baseline, docker, ssh)
