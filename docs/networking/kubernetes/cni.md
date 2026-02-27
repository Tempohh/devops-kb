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
last_updated: 2026-02-24
---

# CNI — Container Network Interface

## Panoramica

CNI (Container Network Interface) è la specifica che definisce come i plugin di rete devono configurare le interfacce di rete nei container. Quando Kubernetes crea un pod, chiama il plugin CNI per assegnare un IP al pod, configurare le route necessarie e garantire la connettività con il resto del cluster. Senza un CNI plugin installato, i pod restano in stato `Pending`.

La scelta del CNI plugin è una delle decisioni architetturali più importanti in un cluster Kubernetes: impatta performance, funzionalità di sicurezza (Network Policy), osservabilità e compatibilità con il cloud provider. I tre CNI più diffusi sono **Flannel** (semplicità), **Calico** (BGP + NetworkPolicy avanzate) e **Cilium** (eBPF, massima performance e osservabilità).

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

| Sintomo | Causa | Soluzione |
|---------|-------|-----------|
| Pod bloccato in `ContainerCreating` | CNI non installato o errore CNI | `kubectl describe pod`, log del CNI su `/var/log/` |
| Pod non si parlano tra nodi diversi | Firewall blocca VXLAN (UDP 8472) o BGP (TCP 179) | Aprire le porte necessarie |
| Packet loss intermittente | MTU mismatch | Ridurre MTU pod di 50-100 byte |
| NetworkPolicy non applicata | CNI non supporta NetworkPolicy (Flannel) | Migrare a Calico o Cilium |
| DNS lento | kube-dns/CoreDNS sovraccarico | Scalare CoreDNS, aggiungere NodeLocal DNSCache |

```bash
# Debug connettività con netshoot
kubectl run netshoot --image=nicolaka/netshoot --rm -it -- bash
# Inside: ping, traceroute, tcpdump, dig, nmap disponibili

# Verifica log CNI
journalctl -u kubelet | grep cni

# Traceroute tra pod
kubectl exec pod-a -- traceroute $(kubectl get pod pod-b -o jsonpath='{.status.podIP}')
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
