---
title: "AWS Networking"
slug: networking-aws
category: cloud
tags: [aws, networking, vpc, route53, cloudfront, direct-connect, vpn, transit-gateway]
search_keywords: [AWS networking, AWS VPC, Route 53, CloudFront, Direct Connect, AWS VPN, Transit Gateway, PrivateLink, VPC Peering, NAT Gateway, Internet Gateway, Elastic IP, security groups, NACLs, AWS networking fundamentals]
parent: cloud/aws/_index
related: [cloud/aws/compute/ec2, cloud/aws/security/network-security]
official_docs: https://docs.aws.amazon.com/vpc/
status: complete
difficulty: intermediate
last_updated: 2026-02-25
---

# AWS Networking

Il networking è la fondamenta di ogni architettura AWS. VPC, subnets, routing e le interconnessioni tra servizi determinano sicurezza, performance e resilienza.

## Sezioni

<div class="grid cards" markdown>

- :material-router-network: **[VPC Fondamentali](vpc.md)**

    Virtual Private Cloud, subnets, routing, IGW, NAT Gateway, Security Groups, NACLs

- :material-vector-combine: **[VPC Avanzato](vpc-avanzato.md)**

    VPC Peering, Transit Gateway, PrivateLink, VPN Site-to-Site, Direct Connect, Client VPN

- :material-dns: **[Route 53](route53.md)**

    DNS managed, routing policies, health checks, private hosted zones, DNSSEC

- :material-web: **[CloudFront & CDN](cloudfront.md)**

    CDN globale, distributions, caching, Lambda@Edge, CloudFront Functions, WAF integration

</div>

---

## Networking AWS — Quick Reference

```
Internet → Internet Gateway → VPC → Public Subnet → EC2 (public IP)
Internet → Internet Gateway → VPC → Public Subnet → NAT Gateway
                                  → Private Subnet → EC2 (no public IP)
                                                      (outbound via NAT GW)

On-premises → VPN / Direct Connect → Virtual Private Gateway → VPC
On-premises → Direct Connect → Transit Gateway → VPC-A, VPC-B, VPC-C...
```

**Default VPC** — ogni account AWS ha un VPC di default per Region:
- CIDR: `172.31.0.0/16`
- Subnet pubblica in ogni AZ
- Internet Gateway già allegato
- Ideale per test rapidi — non usare in produzione

---

## Confronto Opzioni di Connettività

| Opzione | Use Case | Latenza | Sicurezza | Costo |
|---------|----------|---------|-----------|-------|
| **Internet Gateway** | Traffico pubblico verso/da Internet | Standard | Pubblica | Gratuito |
| **NAT Gateway** | Outbound solo da subnet private | Standard | Privato | $0.045/hr + dati |
| **VPC Peering** | Connessione 2 VPC (stesso/altro account) | Bassa | Privato | Solo dati |
| **Transit Gateway** | Hub per molti VPC e on-premises | Bassa | Privato | $0.05/hr + dati |
| **PrivateLink** | Accesso privato a servizi AWS/SaaS | Bassa | Privato | $0.01/hr + dati |
| **Site-to-Site VPN** | On-premises ↔ AWS via Internet | Media | Cifrato | $0.05/hr |
| **Direct Connect** | On-premises ↔ AWS dedicated line | Molto bassa | Dedicato | $$$ |
| **Client VPN** | Developer → VPC via VPN | Media | Cifrato | $0.10/hr + connessioni |
