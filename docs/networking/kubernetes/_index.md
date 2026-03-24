---
title: "Kubernetes Networking"
slug: kubernetes-networking
category: networking
tags: [kubernetes, networking, cni, ingress, network-policy, service, pod]
parent: networking
status: complete
difficulty: advanced
last_updated: 2026-03-09
---

# Kubernetes Networking

Il networking in Kubernetes è il sistema che permette a pod, servizi e componenti esterni di comunicare tra loro. Kubernetes definisce un modello di rete con tre requisiti fondamentali: ogni pod ha un IP unico e routable nel cluster, tutti i pod possono comunicare con tutti gli altri pod senza NAT, e i nodi possono comunicare con i pod. Implementare questi requisiti è compito dei **CNI plugin**.

## Il Modello di Rete Kubernetes

Kubernetes astrae la rete attraverso strati:

```
Internet
    │
Ingress Controller    ← L7 routing, TLS termination
    │
Service (LoadBalancer/NodePort/ClusterIP)
    │
Endpoints → Pod IP addresses
    │
CNI Plugin (Calico, Cilium, Flannel...)
    │
Rete fisica/overlay
```

!!! info "Flat Network"
    Kubernetes usa una **flat network**: ogni pod ha un IP nel range del cluster (es. `10.244.0.0/16`) accessibile da qualsiasi nodo senza NAT. Questo è diverso dalla rete Docker tradizionale dove i container comunicano via NAT.

## Argomenti in questa Sezione

### [CNI — Container Network Interface](cni.md)
I plugin CNI implementano il modello di rete Kubernetes: Calico (BGP + NetworkPolicy), Cilium (eBPF, alta performance, Layer 7 policy), Flannel (overlay semplice). Confronto, criteri di scelta e concetti di overlay network.

### [Ingress e Ingress Controller](ingress.md)
Come esporre servizi Kubernetes all'esterno via HTTP/HTTPS: Ingress resource, Ingress Controller (Nginx, Traefik, HAProxy), TLS con cert-manager, path-based e host-based routing. La base per ogni ambiente Kubernetes in produzione.

### [Network Policies](network-policies.md)
Firewall a livello di pod: controllare quale pod può comunicare con quale altro pod o namespace. Default-deny, ingress/egress rules, selettori per label. Fondamentale per la sicurezza in ambienti multi-tenant.

## Quale CNI Scegliere

Il CNI plugin è una delle decisioni architetturali più durature di un cluster Kubernetes: è difficile da cambiare dopo il deploy. La scelta dipende da performance, funzionalità di sicurezza e integrazione con il cloud provider.

| Scenario | CNI | Motivo |
|----------|-----|--------|
| Cluster semplice, priorità alla facilità di setup | **Flannel** | Overlay VXLAN semplice, zero configurazione, nessun supporto nativo a NetworkPolicy |
| NetworkPolicy enforcement, BGP routing, cloud e on-premise | **Calico** | BGP nativo (no overlay su reti che lo supportano), NetworkPolicy completa, ampiamente diffuso |
| Massima performance, osservabilità L7, eBPF, large cluster | **Cilium** | Sostituisce kube-proxy con eBPF, Hubble per observability, NetworkPolicy estesa con CiliumNetworkPolicy |
| Cloud provider gestito (EKS, GKE, AKS) | **CNI del provider** | aws-vpc-cni, gke-dataplane-v2 (Cilium), Azure CNI — integrazione nativa con il networking cloud |
| Service mesh + CNI in un unico stack | **Cilium** | Cilium può agire da CNI e da service mesh contemporaneamente, riducendo il numero di componenti |

!!! tip "Punto di partenza consigliato"
    Per nuovi cluster su cloud pubblico usa il **CNI nativo del provider** (aws-vpc-cni, Azure CNI). Per on-premise o quando serve NetworkPolicy avanzata, scegli **Calico** per maturità o **Cilium** per performance e observability eBPF.

## Relazioni con altri Argomenti

- **Service Mesh**: Istio e Linkerd si sovrappongono ai CNI per aggiungere mTLS, osservabilità e traffic management
- **Load Balancing**: i Kubernetes Service di tipo LoadBalancer si integrano con il cloud provider LB (AWS ALB, Azure LB)
- **Sicurezza**: le Network Policies sono il complemento Kubernetes delle firewall rules tradizionali
- **API Gateway**: Kong Ingress Controller, Traefik estendono l'Ingress con funzionalità di API Gateway
