---
title: "Sicurezza di Rete"
slug: sicurezza
category: networking
tags: [sicurezza, firewall, vpn, zero-trust, ddos, waf]
parent: networking
status: complete
difficulty: advanced
last_updated: 2026-02-24
---

# Sicurezza di Rete

La sicurezza di rete comprende l'insieme di tecnologie, politiche e pratiche per proteggere l'infrastruttura da accessi non autorizzati, attacchi e vulnerabilità. In un contesto DevOps e cloud-native, la superficie di attacco si estende dalla rete fisica ai container, dai microservizi alle API.

## Perché la Sicurezza di Rete è Critica

Il paradigma moderno ha spostato il perimetro difensivo: non esiste più un confine netto tra interno ed esterno. Le organizzazioni operano con carichi di lavoro distribuiti su cloud pubblici, privati e on-premise, con utenti che accedono da qualsiasi posizione e dispositivo. Questo scenario rende i modelli di sicurezza tradizionali basati sul perimetro inadeguati.

!!! warning "Assumption of Breach"
    Il principio guida della sicurezza moderna è assumere che una violazione sia già avvenuta o avverrà. La difesa deve essere progettata per minimizzare l'impatto laterale, non solo per prevenire l'ingresso.

## Argomenti in questa Sezione

### [Firewall e WAF](firewall-waf.md)
Dalla protezione L3/L4 con packet filtering e stateful inspection fino alla protezione applicativa L7 con Web Application Firewall. Copertura di iptables/nftables, cloud security groups (AWS SG, NACL, Azure NSG) e architetture DMZ.

### [VPN e IPsec](vpn-ipsec.md)
Tecnologie di tunneling per la connettività sicura: IPsec (IKEv2, ESP, AH), WireGuard, OpenVPN. Configurazioni site-to-site e remote access, con analisi comparativa e indicazioni su quando usare ciascuna tecnologia.

### [Zero Trust Networking](zero-trust.md)
Il modello di sicurezza che sostituisce il paradigma perimetrale: "never trust, always verify". Principi NIST 800-207, implementazione pratica con identity provider, device posture, micro-segmentazione e service mesh mTLS.

### [Protezione DDoS](ddos-protezione.md)
Difesa contro gli attacchi Distributed Denial of Service: classificazione per layer (volumetrici L3/L4, protocol L4, applicativi L7), strategie di mitigazione (anycast scrubbing, CDN, rate limiting, BGP blackholing) e soluzioni cloud (AWS Shield, Cloudflare, Azure DDoS Protection).

## Relazioni con altri Argomenti

La sicurezza di rete si integra trasversalmente con molte aree della knowledge base:

- **Kubernetes Networking**: Network Policies per la micro-segmentazione dei pod
- **CI/CD**: Pipeline security, secret management
- **Cloud**: Security Groups, VPC design, IAM
- **Containers**: Container security, image scanning

## Principi Generali

1. **Defense in Depth**: nessuna singola tecnologia garantisce sicurezza totale. I controlli di sicurezza devono essere stratificati
2. **Least Privilege**: ogni componente deve avere solo i permessi strettamente necessari
3. **Default Deny**: bloccare tutto per default, abilitare esplicitamente solo il traffico necessario
4. **Visibility First**: non si può proteggere ciò che non si vede. Logging e monitoring sono prerequisiti
5. **Immutable Infrastructure**: ridurre la superficie di attacco usando componenti immutabili e riproducibili
