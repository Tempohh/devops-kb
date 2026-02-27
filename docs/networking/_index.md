---
title: "Networking"
slug: networking
category: networking
tags: [networking, reti, protocolli, sicurezza, load-balancing, dns, kubernetes]
parent: /
status: complete
difficulty: intermediate
last_updated: 2026-02-24
---

# Networking

La sezione Networking copre tutti gli aspetti delle reti in un contesto DevOps moderno: dai fondamentali del modello OSI e TCP/IP fino alle architetture cloud-native con service mesh, Kubernetes e zero trust. La conoscenza del networking è trasversale a ogni area del DevOps — senza comprendere come i dati viaggiano nella rete, è impossibile progettare sistemi affidabili, sicuri e performanti.

---

## Aree di Conoscenza

<div class="grid cards" markdown>

-   :material-layers:{ .lg .middle } **Fondamentali**

    ---

    Modello OSI, TCP/IP, indirizzi IP, DNS, HTTP/S, TLS

    [:octicons-arrow-right-24: Fondamentali](fondamentali/_index.md)

-   :material-swap-horizontal:{ .lg .middle } **Protocolli**

    ---

    TCP, UDP, HTTP/2, HTTP/3, QUIC, WebSocket, gRPC

    [:octicons-arrow-right-24: Protocolli](protocolli/_index.md)

-   :material-scale-balance:{ .lg .middle } **Load Balancing**

    ---

    Layer 4 vs 7, algoritmi, alta disponibilità, Nginx, HAProxy

    [:octicons-arrow-right-24: Load Balancing](load-balancing/_index.md)

-   :material-api:{ .lg .middle } **API Gateway**

    ---

    Pattern BFF, Kong, rate limiting, routing avanzato

    [:octicons-arrow-right-24: API Gateway](api-gateway/_index.md)

-   :material-vector-polyline:{ .lg .middle } **Service Mesh**

    ---

    Istio, Envoy, Linkerd, mTLS, traffic management, osservabilità

    [:octicons-arrow-right-24: Service Mesh](service-mesh/_index.md)

-   :material-kubernetes:{ .lg .middle } **Kubernetes Networking**

    ---

    CNI (Calico, Cilium), Ingress, Network Policies

    [:octicons-arrow-right-24: Kubernetes](kubernetes/_index.md)

-   :material-shield-lock:{ .lg .middle } **Sicurezza di Rete**

    ---

    Firewall, WAF, VPN, IPsec, Zero Trust, protezione DDoS

    [:octicons-arrow-right-24: Sicurezza](sicurezza/_index.md)

</div>

---

## Percorsi di Studio

### Inizia dai Fondamentali
Se sei nuovo al networking, segui questo ordine:

1. [Modello OSI](fondamentali/modello-osi.md) — il framework concettuale
2. [TCP/IP](fondamentali/tcpip.md) — il protocollo reale di Internet
3. [Indirizzi IP e Subnetting](fondamentali/indirizzi-ip-subnetting.md) — indirizzamento e CIDR
4. [DNS](fondamentali/dns.md) — risoluzione dei nomi
5. [HTTP e HTTPS](fondamentali/http-https.md) — il protocollo del Web
6. [TLS/SSL](fondamentali/tls-ssl-basics.md) — crittografia e certificati

### Percorso DevOps
Per chi deve gestire infrastruttura in produzione:

1. [Load Balancing L4 vs L7](load-balancing/layer4-vs-layer7.md)
2. [Algoritmi di Load Balancing](load-balancing/algoritmi.md)
3. [API Gateway Pattern](api-gateway/pattern-base.md)
4. [Rate Limiting](api-gateway/rate-limiting.md)
5. [Firewall e WAF](sicurezza/firewall-waf.md)

### Percorso Kubernetes
Per chi lavora su Kubernetes:

1. [CNI — Container Network Interface](kubernetes/cni.md)
2. [Ingress e Ingress Controller](kubernetes/ingress.md)
3. [Network Policies](kubernetes/network-policies.md)
4. [Service Mesh — Concetti Base](service-mesh/concetti-base.md)
5. [Istio](service-mesh/istio.md)

---

## Argomenti della Sezione

| Sezione | Argomenti | Livello |
|---------|-----------|---------|
| Fondamentali | OSI, TCP/IP, IP/Subnetting, DNS, HTTP/S, TLS | Beginner |
| Protocolli | TCP/UDP, HTTP/2, HTTP/3, QUIC, WebSocket, gRPC | Intermediate |
| Load Balancing | L4/L7, algoritmi, HA/failover | Intermediate |
| API Gateway | Pattern, Kong, rate limiting | Intermediate |
| Service Mesh | Concetti, Istio, Envoy, Linkerd | Advanced |
| Kubernetes Networking | CNI, Ingress, Network Policies | Advanced |
| Sicurezza di Rete | Firewall/WAF, VPN/IPsec, Zero Trust, DDoS | Advanced |
