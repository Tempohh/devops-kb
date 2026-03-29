---
title: "Architettura OpenShift"
slug: architettura
category: containers
tags: [openshift, architettura, cvo, mco, machine-api, operators, etcd, control-plane]
search_keywords: [openshift architecture, Cluster Version Operator, Machine Config Operator, machine-api openshift, openshift control plane, openshift node management, openshift cluster operators, openshift MachineSet, openshift MachineConfigPool, openshift etcd operator, openshift day-2 operations]
parent: containers/openshift/_index
related: [containers/kubernetes/architettura, containers/openshift/operators-olm]
official_docs: https://docs.openshift.com/container-platform/latest/architecture/architecture.html
status: complete
difficulty: expert
last_updated: 2026-03-29
---

# Architettura OpenShift

## "Operators All the Way Down"

L'insight fondamentale di OpenShift è che **ogni componente del cluster è gestito da un Operator**. Non c'è stato del cluster che viene gestito manualmente — tutto è riconciliato continuamente.

```
OpenShift — Operator Hierarchy

  Cluster Version Operator (CVO)
  ├── Gestisce la versione del cluster e coordina gli upgrade
  ├── Installa e aggiorna i Cluster Operators
  └── Cluster Operators (uno per componente):
      ├── etcd operator                 → gestisce etcd (backup, scaling, encryption)
      ├── kube-apiserver operator       → gestisce kube-apiserver
      ├── kube-scheduler operator       → gestisce kube-scheduler
      ├── kube-controller-manager op.  → gestisce kube-controller-manager
      ├── machine-config operator       → gestisce la configurazione dei nodi OS
      ├── ingress operator              → gestisce il HAProxy router
      ├── image-registry operator       → gestisce il registry interno
      ├── console operator              → gestisce la web console
      ├── monitoring operator           → gestisce Prometheus stack
      ├── network operator              → gestisce OVN-Kubernetes CNI
      ├── authentication operator       → gestisce OAuth server
      ├── cloud-credential operator     → gestisce credenziali cloud
      └── ... (50+ cluster operators)
```

```bash
# Vedi lo stato di tutti i Cluster Operators
oc get clusteroperators
# NAME                                       VERSION   AVAILABLE   PROGRESSING   DEGRADED
# authentication                             4.15.0    True        False         False
# cloud-credential                           4.15.0    True        False         False
# etcd                                       4.15.0    True        False         False
# ingress                                    4.15.0    True        False         False
# kube-apiserver                             4.15.0    True        False         False
# machine-config                             4.15.0    True        False         False
# ...

# DEGRADED=True → qualcosa non va
oc describe clusteroperator etcd
# → mostra i Conditions e il messaggio di errore
```

---

## Cluster Version Operator (CVO) — Gestione del Lifecycle

Il **CVO** è il "controller dei controller": gestisce la versione di OpenShift e coordina gli upgrade.

```
OCP Upgrade Flow

  admin: oc adm upgrade --to=4.15.3

  CVO:
  1. Scarica il release payload da quay.io/openshift-release-dev/ocp-release:4.15.3
     (manifest OCI contenente tutti i manifesti del cluster)
  2. Verifica la firma crittografica del payload
  3. Precondition checks (cluster sano, nessun degraded operator)
  4. Aggiorna i CRD e le API custom di OpenShift
  5. Aggiorna i Cluster Operators in ordine di precedenza:
     - Prima: etcd, kube-apiserver, kube-controller-manager, kube-scheduler
     - Poi: authentication, image-registry, ingress, monitoring
     - Infine: machine-config (aggiorna i nodi OS)

  Machine Config Operator (MCO):
  6. Aggiorna i master node in rolling fashion (un alla volta)
  7. Aggiorna i worker node per MachineConfigPool
     (default: 1 nodo alla volta, configurabile)

  Total upgrade time: 1-4 ore tipicamente
```

```bash
# Stato upgrade in corso
oc get clusterversion
# NAME      VERSION   AVAILABLE   PROGRESSING   SINCE   STATUS
# version   4.14.12   True        True          5m      Working towards 4.15.3

# Dettaglio upgrade
oc describe clusterversion version
# Conditions:
#   Progressing: Working towards 4.15.3: 87% complete
#   History:
#     State: Completed Version: 4.14.12
#     State: Partial   Version: 4.15.3  ← in corso

# Canali di upgrade disponibili
oc get clusterversion -o yaml | grep channel
# channel: stable-4.15

# Cambia canale (es. per upgrade a versione major)
oc patch clusterversion/version --type=merge -p '{"spec":{"channel":"stable-4.15"}}'
```

---

## Machine Config Operator (MCO) — Gestione OS dei Nodi

Il **MCO** gestisce la configurazione dei nodi a livello di sistema operativo (RHCOS - Red Hat CoreOS). Ogni modifica all'OS dei nodi passa attraverso MCO.

```
MCO Architecture

  MachineConfig (CRD)          MachineConfigPool
  +-----------------+          +-------------------+
  | 00-worker       |          | worker pool:       |
  | 01-kubelet      |    →     |   machineConfigs:  |
  | 50-workers-chro |          |   00-worker        |
  | nyd             |          |   01-kubelet       |
  |                 |          |   50-workers-chrony|
  +-----------------+          |   role: worker     |
                               +-------------------+
                                         |
                               MCO renders the merged config
                                         |
                               +---------v---------+
                               | Node: coreos      |
                               | /etc/chrony.conf  |
                               | /etc/kubernetes/  |
                               | kubelet.conf      |
                               | (applied via rpm- |
                               |  ostree)          |
                               +-------------------+
```

```yaml
# MachineConfig — aggiunge configurazione ai nodi worker
apiVersion: machineconfiguration.openshift.io/v1
kind: MachineConfig
metadata:
  labels:
    machineconfiguration.openshift.io/role: worker  # target: worker nodes
  name: 99-worker-custom-chrony
spec:
  config:
    ignition:
      version: 3.2.0
    storage:
      files:
        - path: /etc/chrony.conf
          mode: 0644
          contents:
            source: data:text/plain;charset=utf-8;base64,c2VydmVyIG50cC5pbnRlcm5hbC5jb21wYW55LmNvbSBpYnVyc3QKZHJpZnRmaWxlIC92YXIvbGliL2Nocm9ueS9kcmlmdAo=
    systemd:
      units:
        - name: custom-service.service
          enabled: true
          contents: |
            [Unit]
            Description=Custom Service
            After=network.target
            [Service]
            ExecStart=/usr/local/bin/custom-daemon
            [Install]
            WantedBy=multi-user.target
  kernelArguments:
    add:
      - "net.ipv4.ip_forward=1"
      - "vm.max_map_count=262144"
```

```bash
# Stato MachineConfigPool
oc get mcp
# NAME     CONFIG                   UPDATED   UPDATING   DEGRADED
# master   rendered-master-abc123   True      False      False
# worker   rendered-worker-def456   True      False      False

# Pausa un MachineConfigPool (evita drain automatico durante la manutenzione)
oc patch mcp/worker --type merge -p '{"spec":{"paused":true}}'
oc patch mcp/worker --type merge -p '{"spec":{"paused":false}}'  # riprendi

# Vedere la configurazione renderizzata (merged)
oc get mc rendered-worker-def456 -o yaml | head -50
```

---

## Machine API — Gestione dei Nodi come Cattle

Il **Machine API** permette di gestire i nodi infrastrutturali come oggetti Kubernetes, su cloud e on-premise.

```yaml
# MachineSet — definisce un gruppo di macchine identiche (come ReplicaSet per nodi)
apiVersion: machine.openshift.io/v1beta1
kind: MachineSet
metadata:
  name: cluster-worker-eu-west-1a
  namespace: openshift-machine-api
spec:
  replicas: 3
  selector:
    matchLabels:
      machine.openshift.io/cluster-api-cluster: cluster-name
      machine.openshift.io/cluster-api-machineset: cluster-worker-eu-west-1a
  template:
    spec:
      providerSpec:
        value:
          # AWS provider config
          apiVersion: awsproviderconfig.openshift.io/v1beta1
          kind: AWSMachineProviderConfig
          ami:
            id: ami-0abc123def456789  # RHCOS AMI
          instanceType: m5.2xlarge
          placement:
            availabilityZone: eu-west-1a
            region: eu-west-1
          subnet:
            filters:
              - name: tag:Name
                values: [cluster-subnet-private-eu-west-1a]
          securityGroups:
            - filters:
                - name: tag:Name
                  values: [cluster-worker-sg]
          iamInstanceProfile:
            id: cluster-worker-profile
          blockDevices:
            - ebs:
                volumeSize: 120
                volumeType: gp3
                iops: 3000
                encrypted: true
          tags:
            - name: kubernetes.io/cluster/cluster-name
              value: owned
```

```bash
# Scaling del nodo tramite MachineSet (come kubectl scale per pod)
oc scale machineset/cluster-worker-eu-west-1a --replicas=5 \
    -n openshift-machine-api

# Stato macchine
oc get machines -n openshift-machine-api
# NAME                             PHASE     NODE               AGE
# cluster-worker-eu-west-1a-abc   Running   worker-1.cluster   5d
# cluster-worker-eu-west-1a-def   Provisioning                 2m

# MachineHealthCheck — auto-replace macchine non sane
oc get machinehealthcheck -n openshift-machine-api
```

---

## etcd su OpenShift — Operator Managed

```bash
# OpenShift gestisce etcd tramite l'etcd operator
oc get pods -n openshift-etcd
# NAME                                          READY   STATUS
# etcd-master-0.cluster.internal               4/4     Running
# etcd-master-1.cluster.internal               4/4     Running
# etcd-master-2.cluster.internal               4/4     Running

# Backup etcd (via job)
oc debug node/master-0.cluster.internal -- \
    chroot /host /usr/local/bin/cluster-backup.sh /var/home/core/assets/backup/

# Verifica stato etcd
oc exec -n openshift-etcd etcd-master-0 -c etcd -- \
    etcdctl endpoint health \
    --endpoints=https://master-0:2379,https://master-1:2379,https://master-2:2379
```

---

## Troubleshooting

### Scenario 1 — Cluster Operator in stato DEGRADED

**Sintomo:** `oc get clusteroperators` mostra `DEGRADED=True` per uno o più operator.

**Causa:** Errori di configurazione, risorse insufficienti, dipendenze non soddisfatte, o problemi di rete tra componenti del control plane.

**Soluzione:** Ispezionare i Conditions dell'operator degraded per ottenere il messaggio di errore specifico.

```bash
# Identificare l'operator degraded
oc get clusteroperators | grep -v "True.*False.*False"

# Leggere i Conditions con il messaggio di errore
oc describe clusteroperator <nome-operator>
# Cercare: Conditions → Type: Degraded → Message

# Ispezionare i pod del componente (es. per ingress operator)
oc get pods -n openshift-ingress-operator
oc logs -n openshift-ingress-operator deployment/ingress-operator --tail=100

# Forzare la riconciliazione dell'operator (rimuovere la cache)
oc delete pod -n openshift-ingress-operator -l name=ingress-operator
```

---

### Scenario 2 — MachineConfigPool bloccato in UPDATING

**Sintomo:** `oc get mcp` mostra `UPDATING=True` da molto tempo; i nodi non completano il drain/reboot.

**Causa:** Un nodo non riesce a fare il drain (pod non evictable con PodDisruptionBudget troppo restrittivo, pod con `terminationGracePeriodSeconds` elevato), oppure il nodo non riesce ad avviarsi dopo il reboot.

**Soluzione:** Identificare il nodo bloccato e diagnosticare la causa specifica.

```bash
# Trovare il nodo che sta causando il blocco
oc get nodes
# Cercare nodi in stato SchedulingDisabled (drain in corso) o NotReady

# Verificare gli eventi sul nodo
oc describe node <nome-nodo> | grep -A 20 Events

# Se il drain è bloccato, vedere quali pod impediscono l'eviction
oc get pods --all-namespaces --field-selector spec.nodeName=<nome-nodo>

# Se il nodo è in loop di reboot, accedere via debug
oc debug node/<nome-nodo>
chroot /host journalctl -u kubelet --since "30 minutes ago"

# Sbloccare forzatamente (solo se sicuro)
oc adm uncordon <nome-nodo>
```

---

### Scenario 3 — Upgrade del cluster bloccato (CVO)

**Sintomo:** `oc get clusterversion` mostra `PROGRESSING=True` da ore senza avanzare, o percentuale ferma.

**Causa:** Un Cluster Operator prerequisito non riesce ad aggiornarsi, un nodo non completa il reboot post-MCO, o il download del release payload fallisce.

**Soluzione:** Seguire il grafo delle dipendenze del CVO: prima si aggiornano i componenti del control plane, poi MCO aggiorna i nodi.

```bash
# Stato dettagliato del cluster version con history
oc describe clusterversion version

# Identificare quale operator è bloccato
oc get clusteroperators | grep -E "False|True.*True"

# Leggere i log del CVO
oc logs -n openshift-cluster-version \
    deployment/cluster-version-operator --tail=200

# Se un nodo non completa il reboot (MCO phase)
oc get nodes | grep -v Ready
oc get machineconfigpools

# Verificare lo stato della macchina sul cloud provider
oc get machines -n openshift-machine-api | grep -v Running

# In caso di upgrade fallito, annullare e tornare alla versione precedente
oc adm upgrade --allow-not-recommended --to=<versione-precedente>
```

---

### Scenario 4 — Machine API: nodi non vengono provisionati

**Sintomo:** Un MachineSet ha `replicas` aumentate ma le nuove `Machine` rimangono in fase `Provisioning` o `Failed` indefinitamente.

**Causa:** Credenziali cloud insufficienti, quota cloud esaurita, subnet/security group non trovati, AMI/image non disponibile nella regione/zona.

**Soluzione:** Ispezionare i log del machine-api-controller e i messaggi di errore sulla risorsa Machine.

```bash
# Verificare lo stato delle Machine
oc get machines -n openshift-machine-api
# Cercare Phase: Failed o Provisioning da troppo tempo

# Leggere i messaggi di errore sulla Machine specifica
oc describe machine <nome-machine> -n openshift-machine-api
# Cercare: Status → ErrorMessage, ErrorReason

# Log del controller machine-api
oc logs -n openshift-machine-api \
    deployment/machine-api-controllers \
    -c machine-controller --tail=200

# Verificare le credenziali cloud (CloudCredential operator)
oc get cloudcredential cluster -o yaml
oc get clusteroperator cloud-credential

# Verificare quota AWS (se su AWS)
oc get machineset <nome-machineset> -n openshift-machine-api -o yaml
# Controllare instanceType e availability zone
```

---

## Riferimenti

- [OCP Architecture](https://docs.openshift.com/container-platform/latest/architecture/architecture.html)
- [Cluster Version Operator](https://docs.openshift.com/container-platform/latest/updating/understanding-openshift-updates.html)
- [Machine Config Operator](https://docs.openshift.com/container-platform/latest/post_installation_configuration/machine-configuration-tasks.html)
- [Machine API](https://docs.openshift.com/container-platform/latest/machine_management/index.html)
