---
title: "CNI — Container Network Interface"
slug: cni
category: networking
tags: [kubernetes, cni, calico, cilium, flannel, overlay, ebpf, bgp, networking]
search_keywords: [container network interface, cni plugin, pod networking, overlay network, vxlan, geneve, bgp, calico, cilium, flannel, weave, ebpf, pod cidr, cluster cidr, ip-in-ip, wireguard, network policy enforcement, kube-proxy replacement, hubble, network observability]
parent: networking/kubernetes/_index
related: [networking/kubernetes/network-policies, networking/kubernetes/ingress, networking/service-mesh/istio]
official_docs: https://www.cni.dev/docs/
status: complete
difficulty: advanced
last_updated: 2026-03-29
---

# CNI — Container Network Interface

## Panoramica

CNI (Container Network Interface) è la specifica che definisce come i plugin di rete devono configurare le interfacce di rete nei container. Quando Kubernetes crea un pod, chiama il plugin CNI per assegnare un IP al pod, configurare le route necessarie e garantire la connettività con il resto del cluster. Senza un CNI plugin installato, i pod restano in stato `Pending`.

La scelta del CNI plugin è una delle decisioni architetturali più importanti in un cluster Kubernetes: impatta performance, funzionalità di sicurezza (Network Policy), osservabilità e compatibilità con il cloud provider. I tre CNI più diffusi sono **Flannel** (semplicità), **Calico** (BGP + NetworkPolicy avanzate) e **Cilium** (eBPF, massima performance e osservabilità).

## Prerequisiti

Questo argomento presuppone familiarità con:
- [Indirizzi IP e Subnetting](../fondamentali/indirizzi-ip-subnetting.md) — CIDR notation, subnetting, come funzionano gli indirizzi IP in una rete
- [TCP/IP](../fondamentali/tcpip.md) — routing IP, come i pacchetti attraversano la rete
- Kubernetes di base — pod, node, namespace, deployment (documentazione non ancora presente in questa KB)

Senza questi concetti, alcune sezioni potrebbero risultare difficili da contestualizzare.

## Concetti Chiave

### Come funziona il networking Kubernetes

```
Cluster CIDR: 10.244.0.0/16  (range IP per tutti i pod)
Service CIDR: 10.96.0.0/12   (range IP per i Kubernetes Services)

Node 1 (10.0.0.1):
  Pod A: 10.244.0.1/24
  Pod B: 10.244.0.2/24
  Pod subnet: 10.244.0.0/24

Node 2 (10.0.0.2):
  Pod C: 10.244.1.1/24
  Pod D: 10.244.1.2/24
  Pod subnet: 10.244.1.0/24
```

Il CNI deve garantire che Pod A (10.244.0.1) possa raggiungere Pod C (10.244.1.1) — su nodi fisici diversi — senza NAT.

### Overlay vs Underlay Network

| Approccio | Come funziona | Pro | Contro |
|-----------|--------------|-----|--------|
| **Overlay (VXLAN/Geneve)** | Incapsula i pacchetti pod in pacchetti UDP della rete fisica | Funziona su qualsiasi rete fisica | Overhead di incapsulamento, MTU |
| **BGP (no overlay)** | Annuncia le route pod via BGP alla rete fisica | Nessun overhead, performance native | Richiede switch/router con supporto BGP |
| **eBPF (kernel bypass)** | Processa i pacchetti nel kernel con eBPF senza userspace | Massima performance, ricca osservabilità | Kernel Linux 5.8+ richiesto |

## Confronto CNI Plugin

| Feature | Flannel | Calico | Cilium |
|---------|---------|--------|--------|
| Meccanismo | VXLAN overlay | BGP o VXLAN | eBPF |
| NetworkPolicy | No (solo base) | Sì (avanzate) | Sì (L3/L4/L7) |
| Performance | Media | Alta | Massima |
| Osservabilità | Minima | Media | Eccellente (Hubble) |
| Complessità | Bassa | Media | Alta |
| kube-proxy replacement | No | No (opzionale) | Sì (nativo) |
| Multicluster | No | Sì | Sì |
| Casi d'uso | Dev, piccoli cluster | Produzione generale | High-performance, compliance |

## Architettura / Come Funziona

### Flannel — VXLAN Overlay

```
Pod A (Node 1)                    Pod B (Node 2)
  10.244.0.1                        10.244.1.1
      │                                 │
  veth pair                         veth pair
      │                                 │
  cni0 bridge (10.244.0.1/24)      cni0 bridge (10.244.1.1/24)
      │                                 │
  flannel.1 (VXLAN)                flannel.1 (VXLAN)
      │                                 │
  eth0 (10.0.0.1)     UDP/8472     eth0 (10.0.0.2)
      └─────────────────────────────────┘
         Rete fisica (pacchetto incapsulato)
```

Flannel incapsula i pacchetti pod in datagrammi UDP usando il protocollo VXLAN. Il pacchetto risultante viaggia sulla rete fisica come traffico normale.

### Calico — BGP

```
Node 1 (10.0.0.1)                 Node 2 (10.0.0.2)
  BIRD (BGP daemon)  ←── BGP ───→  BIRD (BGP daemon)
  Annuncia: 10.244.0.0/24          Annuncia: 10.244.1.0/24
      │                                 │
  Route: 10.244.1.0/24 → eth0      Route: 10.244.0.0/24 → eth0
      │                                 │
  eth0 (10.0.0.1)       Native IP   eth0 (10.0.0.2)
      └─────────────────────────────────┘
         Rete fisica (nessun overhead)
```

Calico usa BGP per annunciare le subnet dei pod di ogni nodo agli altri nodi. I pacchetti viaggiano nativamente senza incapsulamento (in modalità BGP puro).

### Cilium — eBPF

```
Pod A                             Pod B
  │                                 │
  veth                             veth
  │                                 │
eBPF program (kernel)           eBPF program (kernel)
  ├── Policy enforcement L3/L4/L7  ├── Policy enforcement L3/L4/L7
  ├── Load balancing               ├── Load balancing
  ├── NAT                          ├── NAT
  └── Observability (flow log)     └── Observability (flow log)
  │                                 │
  eth0                             eth0
```

Cilium usa programmi eBPF caricati nel kernel Linux per processare i pacchetti senza passare per userspace. Può sostituire completamente kube-proxy.

## Configurazione & Pratica

### Installare Flannel

```bash
# Installazione base (dopo kubeadm init con --pod-network-cidr=10.244.0.0/16)
kubectl apply -f https://raw.githubusercontent.com/flannel-io/flannel/master/Documentation/kube-flannel.yml

# Verifica
kubectl get pods -n kube-flannel
kubectl get nodes  # Tutti devono essere Ready
```

### Installare Calico

```bash
# Installa con Helm (raccomandato)
helm repo add projectcalico https://docs.tigera.io/calico/charts
helm install calico projectcalico/tigera-operator \
  --namespace tigera-operator \
  --create-namespace

# Attendi che i pod siano Ready
kubectl get pods -n calico-system -w

# Configura IP pool
cat <<EOF | kubectl apply -f -
apiVersion: projectcalico.org/v3
kind: IPPool
metadata:
  name: default-ipv4-ippool
spec:
  cidr: 10.244.0.0/16
  ipipMode: Never         # BGP puro, no overlay
  natOutgoing: true
  disabled: false
EOF
```

### Installare Cilium

```bash
# Installa CLI cilium
curl -L --remote-name-all https://github.com/cilium/cilium-cli/releases/latest/download/cilium-linux-amd64.tar.gz
tar xzvf cilium-linux-amd64.tar.gz && mv cilium /usr/local/bin/

# Installa Cilium nel cluster
cilium install --version 1.15.0

# Verifica status e connettività
cilium status --wait
cilium connectivity test

# Abilita Hubble (osservabilità)
cilium hubble enable --ui
cilium hubble ui  # Apre la UI
```

### Verifica Connettività Pod

```bash
# Test connettività base tra pod su nodi diversi
kubectl run test-a --image=busybox --restart=Never -- sleep 3600
kubectl run test-b --image=busybox --restart=Never -- sleep 3600

IP_B=$(kubectl get pod test-b -o jsonpath='{.status.podIP}')
kubectl exec test-a -- ping -c3 $IP_B

# Verifica routing sul nodo
# (su Node 1)
ip route show | grep 10.244
# Output atteso (Calico BGP):
# 10.244.1.0/24 via 10.0.0.2 dev eth0 proto bird  ← route verso Node 2

# Dump flussi con Cilium/Hubble
hubble observe --namespace default --follow

# Debug CNI
ls /etc/cni/net.d/  # File configurazione CNI
ls /opt/cni/bin/    # Binari plugin CNI
```

### MTU e VXLAN

```bash
# VXLAN aggiunge 50 byte di overhead → ridurre MTU dei pod
# MTU fisica: 1500 → MTU pod con VXLAN: 1450

# Verifica MTU in un pod
kubectl exec mypod -- ip link show eth0
# 2: eth0@if123: mtu 1450

# Verifica in Calico
kubectl get configmap calico-config -n kube-system -o yaml | grep mtu
```

## Best Practices

- **Scegliere il CNI in base alle esigenze reali**: Flannel per ambienti dev/test, Calico per produzione con NetworkPolicy avanzate, Cilium per alta performance o compliance L7
- **Pod CIDR non sovrapposto**: assicurarsi che il CIDR dei pod non si sovrapponga alla rete fisica o ad altri cluster
- **NetworkPolicy dal giorno 1**: qualsiasi CNI che supporti NetworkPolicy deve avere un default-deny policy configurata subito
- **Monitorare MTU**: problemi di MTU causano packet loss silenzioso — verificare sempre la MTU end-to-end
- **Non cambiare CNI dopo il deploy**: la migrazione da un CNI all'altro richiede ricreazione dei pod — pianificare la scelta prima

## Troubleshooting

### Scenario 1 — Pod bloccato in ContainerCreating

**Sintomo:** Il pod resta in stato `ContainerCreating` indefinitamente, mai `Running`.

**Causa:** Il CNI plugin non è installato, non è in esecuzione su quel nodo, o ha prodotto un errore durante la configurazione dell'interfaccia di rete del pod.

**Soluzione:** Verificare lo stato dei pod CNI sul nodo e i log di kubelet per il messaggio di errore specifico.

```bash
# Descrivi il pod per vedere l'errore CNI
kubectl describe pod <pod-name>
# Cercare: "failed to set up pod network" o "network plugin not ready"

# Verifica che i pod CNI siano Running su TUTTI i nodi
kubectl get pods -n kube-system -l k8s-app=flannel    # Flannel
kubectl get pods -n calico-system                       # Calico
kubectl get pods -n kube-system -l k8s-app=cilium      # Cilium

# Log kubelet sul nodo problematico
journalctl -u kubelet --since "10 min ago" | grep -i cni

# Verifica presenza dei file CNI
ls /etc/cni/net.d/   # Deve contenere *.conf o *.conflist
ls /opt/cni/bin/     # Deve contenere i binari (bridge, flannel, calico, ecc.)
```

---

### Scenario 2 — Pod su nodi diversi non si raggiungono

**Sintomo:** `ping` tra pod su nodi diversi fallisce; pod sullo stesso nodo si raggiungono correttamente.

**Causa:** Il firewall del cloud/OS blocca il traffico overlay (UDP 8472 per VXLAN) o BGP (TCP 179). In alternativa, le route BGP non vengono annunciate correttamente.

**Soluzione:** Aprire le porte richieste dal CNI e verificare le route di rete tra nodi.

```bash
# Identifica gli IP dei pod in test
kubectl get pods -o wide   # Colonna NODE e IP

# Test ping diretto tra pod
kubectl exec test-a -- ping -c3 <IP_POD_B>

# Verifica route sul nodo (Calico BGP)
ip route show | grep "10.244"
# Atteso: 10.244.1.0/24 via <IP_NODE_2> dev eth0 proto bird

# Testa connettività porta VXLAN (Flannel) tra nodi
nc -zuv <IP_NODE_2> 8472

# Verifica sessioni BGP attive (Calico)
kubectl exec -n calico-system calico-node-<hash> -- birdcl show protocols
# Tutte le sessioni BGP devono essere "Established"

# Tcpdump per catturare traffico VXLAN
tcpdump -i eth0 udp port 8472 -n
```

---

### Scenario 3 — Packet loss intermittente e connessioni instabili

**Sintomo:** Connessioni TCP si chiudono inaspettatamente; `ping` funziona ma con perdite sporadiche; download lenti o interrotti.

**Causa:** MTU mismatch — il CNI overlay (VXLAN/Geneve) aggiunge overhead (~50 byte) ma la MTU dei pod non è stata ridotta di conseguenza. I pacchetti vengono frammentati o scartati.

**Soluzione:** Ridurre la MTU delle interfacce pod (o configurare il CNI per farlo automaticamente).

```bash
# Verifica MTU su un pod
kubectl exec <pod-name> -- ip link show eth0
# "mtu 1500" con VXLAN è sbagliato — deve essere ~1450

# Verifica MTU configurata in Calico
kubectl get configmap calico-config -n kube-system -o yaml | grep -i mtu

# Imposta MTU in Calico (veth MTU)
kubectl patch configmap calico-config -n kube-system \
  --type merge \
  -p '{"data":{"veth_mtu":"1440"}}'

# Verifica MTU nodo
ip link show flannel.1   # Flannel: deve essere ~1450
ip link show vxlan.calico  # Calico VXLAN: deve essere ~1450

# Simula frammentazione (test)
kubectl exec <pod-name> -- ping -M do -s 1450 <IP_altro_pod>
# Se fallisce con "Frag needed": problema MTU confermato
```

---

### Scenario 4 — NetworkPolicy non viene applicata

**Sintomo:** Le `NetworkPolicy` create vengono ignorate; i pod comunicano liberamente nonostante le regole di deny.

**Causa:** Il CNI installato non supporta NetworkPolicy (es. Flannel base) oppure il controller delle policy non è in esecuzione.

**Soluzione:** Verificare che il CNI supporti NetworkPolicy; se si usa Flannel, affiancare Calico solo per le policy (Canal) oppure migrare a Calico/Cilium.

```bash
# Verifica se le NetworkPolicy sono presenti
kubectl get networkpolicies -A

# Test: crea policy default-deny e verifica se blocca traffico
cat <<EOF | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: test-deny
  namespace: default
spec:
  podSelector: {}
  policyTypes: [Ingress]
EOF

# Testa connettività (deve fallire se la policy funziona)
kubectl exec test-a -- wget -T3 -q http://<IP_POD_B>:80
# Se risponde: policy non applicata → CNI non la supporta

# Per Cilium: verifica policy enforcement
cilium policy get
kubectl exec -n kube-system cilium-<hash> -- cilium policy trace \
  --src-k8s-pod default:test-a --dst-k8s-pod default:test-b --dport 80

# Cleanup test
kubectl delete networkpolicy test-deny
```

## Relazioni

??? info "Network Policies — Firewall tra pod"
    Il CNI deve supportare NetworkPolicy per la sicurezza inter-pod.

    **Approfondimento →** [Network Policies](network-policies.md)

??? info "Istio — Service Mesh su CNI"
    Istio si affianca al CNI per aggiungere mTLS e traffic management.

    **Approfondimento →** [Istio](../service-mesh/istio.md)

## Riferimenti

- [CNI Specification](https://www.cni.dev/docs/)
- [Calico Documentation](https://docs.tigera.io/calico/latest/)
- [Cilium Documentation](https://docs.cilium.io/)
- [Flannel on GitHub](https://github.com/flannel-io/flannel)
