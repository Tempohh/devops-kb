---
title: "Indirizzi IP e Subnetting"
slug: indirizzi-ip-subnetting
category: networking
tags: [ip, subnetting, cidr, ipv4, ipv6, networking]
search_keywords: [indirizzi ip, ipv4 classi, subnetting cidr, subnet mask calcolo, vlsm variable length subnet mask, ipv6 notation, indirizzi privati rfc1918, 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16, supernetting, network address, broadcast address]
parent: networking/fondamentali
related: [networking/fondamentali/tcpip]
official_docs: https://www.rfc-editor.org/rfc/rfc4632
status: complete
difficulty: intermediate
last_updated: 2026-02-24
---

# Indirizzi IP e Subnetting

## Panoramica

Un indirizzo IP è l'identificatore logico univoco assegnato a ogni interfaccia di rete in una rete IP. IPv4 usa indirizzi a 32 bit (circa 4,3 miliardi di combinazioni), mentre IPv6 ne usa 128 bit per risolvere l'esaurimento degli indirizzi. Il subnetting è la tecnica di suddivisione di uno spazio di indirizzi in sottoreti più piccole: permette di ottimizzare l'uso degli indirizzi, isolare segmenti di rete per motivi di sicurezza e gestire il routing in modo gerarchico. In ambito DevOps, la pianificazione degli indirizzi è fondamentale per il design di VPC cloud, cluster Kubernetes, reti aziendali e VPN.

## Concetti Chiave

### Struttura di un Indirizzo IPv4

Un indirizzo IPv4 è composto da 32 bit, scritti in notazione dotted-decimal (4 ottetti decimali separati da punto):

```
192      .  168      .  1        .  100
11000000    10101000    00000001    01100100
```

Ogni indirizzo è diviso in due parti:
- **Parte di rete (network)**: identifica la sottorete
- **Parte di host**: identifica il dispositivo nella sottorete

La **subnet mask** determina dove finisce la parte di rete e dove inizia quella di host.

### Notazione CIDR

CIDR (Classless Inter-Domain Routing, RFC 4632) sostituisce il sistema a classi con una notazione compatta: l'indirizzo di rete seguito da `/N` dove N è il numero di bit della parte di rete.

```
192.168.1.0/24  →  subnet mask: 255.255.255.0  →  24 bit di rete, 8 bit di host
10.0.0.0/8      →  subnet mask: 255.0.0.0       →  8 bit di rete, 24 bit di host
172.16.0.0/12   →  subnet mask: 255.240.0.0     →  12 bit di rete, 20 bit di host
```

### Classi IPv4 (sistema classful — storico)

| Classe | Range | Subnet Mask Default | Host per Rete | Uso Originale |
|---|---|---|---|---|
| A | 1.0.0.0 – 126.255.255.255 | /8 (255.0.0.0) | 16.777.214 | Grandi organizzazioni |
| B | 128.0.0.0 – 191.255.255.255 | /16 (255.255.0.0) | 65.534 | Organizzazioni medie |
| C | 192.0.0.0 – 223.255.255.255 | /24 (255.255.255.0) | 254 | Piccole reti |
| D | 224.0.0.0 – 239.255.255.255 | N/A | N/A | Multicast |
| E | 240.0.0.0 – 255.255.255.255 | N/A | N/A | Riservato (sperimentale) |

!!! note "Nota"
    Il sistema classful è obsoleto. Oggi si usa esclusivamente CIDR. Tuttavia conoscere le classi è utile per capire i range privati e la terminologia legacy.

### Indirizzi Privati (RFC 1918)

Questi range non sono instradabili su internet e sono riservati per usi interni (RFC 1918):

| Range | CIDR | Classe Originale | Host Disponibili |
|---|---|---|---|
| 10.0.0.0 – 10.255.255.255 | 10.0.0.0/8 | A | 16.777.214 |
| 172.16.0.0 – 172.31.255.255 | 172.16.0.0/12 | B | 1.048.574 |
| 192.168.0.0 – 192.168.255.255 | 192.168.0.0/16 | C | 65.534 |

### Indirizzi Speciali

| Indirizzo | Significato |
|---|---|
| 127.0.0.1 / 127.0.0.0/8 | Loopback (localhost) |
| 0.0.0.0/0 | Default route ("tutto il traffico") |
| 169.254.0.0/16 | Link-local (APIPA — assegnato automaticamente se DHCP non disponibile) |
| 255.255.255.255 | Broadcast limitato |
| x.x.x.255 | Broadcast diretto della subnet (ultimo indirizzo usabile) |
| x.x.x.0 | Indirizzo di rete (primo indirizzo, non assegnabile a host) |

## Come Funziona

### Calcolo del Subnetting — Step by Step

**Esempio: Dividere 192.168.1.0/24 in 4 sottoreti di uguale dimensione**

**Step 1 — Quanti bit aggiuntivi servono?**
Per creare 4 sottoreti: 2^n ≥ 4 → n = 2 bit aggiuntivi di rete.
Nuova prefix length: /24 + 2 = **/26**

**Step 2 — Calcolare la dimensione di ogni sottorete:**
Host bits rimasti: 32 - 26 = 6 bit → 2^6 = 64 indirizzi per sottorete
Host utilizzabili: 64 - 2 = **62 host** (si sottraggono network address e broadcast)

**Step 3 — Elencare le sottoreti:**

| Sottorete | Network Address | Range Host | Broadcast | CIDR |
|---|---|---|---|---|
| 1 | 192.168.1.0 | 192.168.1.1 – 192.168.1.62 | 192.168.1.63 | 192.168.1.0/26 |
| 2 | 192.168.1.64 | 192.168.1.65 – 192.168.1.126 | 192.168.1.127 | 192.168.1.64/26 |
| 3 | 192.168.1.128 | 192.168.1.129 – 192.168.1.190 | 192.168.1.191 | 192.168.1.128/26 |
| 4 | 192.168.1.192 | 192.168.1.193 – 192.168.1.254 | 192.168.1.255 | 192.168.1.192/26 |

### Tabella CIDR di Riferimento

| CIDR | Subnet Mask | Indirizzi Totali | Host Utilizzabili | Uso Tipico |
|---|---|---|---|---|
| /8 | 255.0.0.0 | 16.777.216 | 16.777.214 | Grandi VPC, Class A |
| /16 | 255.255.0.0 | 65.536 | 65.534 | VPC aziendali, AWS VPC default |
| /20 | 255.255.240.0 | 4.096 | 4.094 | Subnet per AZ in cloud |
| /22 | 255.255.252.0 | 1.024 | 1.022 | Subnet medie |
| /24 | 255.255.255.0 | 256 | 254 | Subnet standard LAN |
| /25 | 255.255.255.128 | 128 | 126 | Subnet medie |
| /26 | 255.255.255.192 | 64 | 62 | Subnet piccole |
| /27 | 255.255.255.224 | 32 | 30 | Subnet per servizi specifici |
| /28 | 255.255.255.240 | 16 | 14 | Subnet molto piccole |
| /29 | 255.255.255.248 | 8 | 6 | Point-to-point con alcuni host |
| /30 | 255.255.255.252 | 4 | 2 | Link point-to-point |
| /31 | 255.255.255.254 | 2 | 2* | Link p2p (RFC 3021, no broadcast) |
| /32 | 255.255.255.255 | 1 | 1 | Host singolo, route statica |

*Per /31 non esistono network e broadcast address (RFC 3021).

### IPv6 — Panoramica

IPv6 usa indirizzi a 128 bit scritti in notazione esadecimale (8 gruppi da 16 bit separati da `:`):

```
2001:0db8:85a3:0000:0000:8a2e:0370:7334

# Regole di abbreviazione:
# 1. Omettere gli zeri iniziali in ogni gruppo
2001:db8:85a3:0:0:8a2e:370:7334

# 2. Sostituire una sequenza contigua di gruppi tutti-zero con ::
2001:db8:85a3::8a2e:370:7334
```

| Tipo | Prefisso | Descrizione |
|---|---|---|
| Loopback | ::1/128 | Equivalente di 127.0.0.1 |
| Link-local | fe80::/10 | Assegnato automaticamente, non instradabile |
| Unique Local | fc00::/7 | Equivalente di RFC 1918 (privato) |
| Global Unicast | 2000::/3 | Indirizzi pubblici internet |
| Multicast | ff00::/8 | Multicast |

La lunghezza del prefisso tipica per un host IPv6 è /128, per una subnet /64 (i 64 bit inferiori sono l'interface ID).

## Configurazione & Pratica

### Design VPC per un Cluster Kubernetes su AWS

Un design tipico per un VPC Kubernetes che usa 10.0.0.0/16:

```
VPC: 10.0.0.0/16  (65.534 indirizzi)
│
├── Subnet Pubblica AZ-A:  10.0.0.0/22   (1.022 host) → Load Balancer, Bastion
├── Subnet Pubblica AZ-B:  10.0.4.0/22   (1.022 host) → Load Balancer, Bastion
├── Subnet Pubblica AZ-C:  10.0.8.0/22   (1.022 host) → Load Balancer, Bastion
│
├── Subnet Privata AZ-A:   10.0.16.0/20  (4.094 host) → Worker Nodes
├── Subnet Privata AZ-B:   10.0.32.0/20  (4.094 host) → Worker Nodes
├── Subnet Privata AZ-C:   10.0.48.0/20  (4.094 host) → Worker Nodes
│
├── Pod CIDR:              10.1.0.0/16   (65.534 pod) → overlay network
└── Service CIDR:          10.2.0.0/16   (65.534 service IP) → kube-proxy
```

!!! warning "Attenzione"
    I CIDR per Pod e Service Kubernetes NON devono sovrapporsi con il CIDR del VPC o con range di reti on-premise raggiungibili tramite VPN/Direct Connect. La sovrapposizione causa problemi di routing impossibili da risolvere senza riconfigurare la rete del cluster.

### Comandi Pratici

```bash
# Visualizzare e gestire indirizzi IP con iproute2
ip addr show                          # Tutte le interfacce
ip addr add 192.168.1.100/24 dev eth0  # Aggiungere IP (temporaneo)
ip addr del 192.168.1.100/24 dev eth0  # Rimuovere IP

# Routing
ip route show                         # Tabella di routing
ip route add 10.0.0.0/8 via 192.168.1.1   # Aggiungere route statica
ip route del 10.0.0.0/8                    # Rimuovere route

# Calcolo subnetting con ipcalc
ipcalc 192.168.1.0/24
# Output:
# Address:   192.168.1.0         11000000.10101000.00000001. 00000000
# Netmask:   255.255.255.0 = 24  11111111.11111111.11111111. 00000000
# Network:   192.168.1.0/24      ...
# HostMin:   192.168.1.1         ...
# HostMax:   192.168.1.254       ...
# Broadcast: 192.168.1.255       ...
# Hosts/Net: 254

# Verifica se un IP appartiene a una subnet (con ipcalc o Python)
python3 -c "import ipaddress; print(ipaddress.ip_address('10.0.1.5') in ipaddress.ip_network('10.0.0.0/16'))"
# True

# Elencare tutte le subnet di una rete padre con Python
python3 -c "import ipaddress; [print(s) for s in ipaddress.ip_network('10.0.0.0/24').subnets(new_prefix=26)]"
# 10.0.0.0/26
# 10.0.0.64/26
# 10.0.0.128/26
# 10.0.0.192/26
```

## Best Practices

- **Pianifica prima di deployare**: una volta assegnato un CIDR a un VPC cloud, non è possibile cambiarlo senza ricreare la rete. Usa una spreadsheet o uno strumento IPAM (IP Address Management) come NetBox o phpIPAM.
- **Usa spazi privati grandi per i VPC cloud**: preferire 10.0.0.0/16 o /8 piuttosto che 192.168.0.0/24. La crescita futura è difficile da prevedere.
- **Evita la sovrapposizione**: documenta tutti i range usati (VPC, on-premise, VPN, Kubernetes) in un IPAM. La sovrapposizione tra reti connesse causa un routing non deterministico che è notoriamente difficile da diagnosticare.
- **Lascia spazio per la crescita**: non riempire subito tutto lo spazio. Riserva range per future AZ, ambienti aggiuntivi, peering con altri VPC.
- **Documentazione come codice**: gestisci gli indirizzi IP come infrastruttura (Terraform, Ansible). Evita modifiche manuali non tracciate.

## Troubleshooting

### Subnet Mask Errata

```bash
# Sintomo: host nella stessa subnet non si raggiungono
# Causa tipica: subnet mask diversa tra i due host

# Host A: ip 192.168.1.10/24 → crede che la rete sia 192.168.1.0
# Host B: ip 192.168.1.200/25 → crede che la rete sia 192.168.1.128
# Risultato: A e B non condividono lo stesso network, ARP fallisce

# Diagnosi:
ip addr show   # Verificare la subnet mask su entrambi gli host
# Correzione: assegnare la stessa subnet mask
```

### Subnet Sovrapposte

```bash
# Sintomo: traffico destinato a rete A finisce su rete B (o viceversa)
# Causa: due reti con CIDR sovrapposti (es. 10.0.0.0/8 e 10.0.0.0/16)

# Diagnosi: il kernel usa la route più specifica (longest prefix match)
ip route show
# Se vedi due route per range sovrapposti, il traffico va sulla più lunga (es. /16 batte /8)

# Verifica con:
ip route get <ip_destinazione>
# Mostra esattamente quale route viene usata per quell'IP
```

### Indirizzo IP in Conflitto (Duplicate IP)

```bash
# Sintomo: connettività intermittente dopo aver aggiunto un nuovo host
# Causa: due host con lo stesso IP nella stessa subnet

# Diagnosi con arping:
arping -I eth0 -c 3 192.168.1.10
# Se ricevi risposte da MAC diversi, c'è un conflitto

# Su Linux, il kernel logga i conflitti:
dmesg | grep "duplicate address"
```

## Riferimenti

- [RFC 1918 — Address Allocation for Private Internets](https://www.rfc-editor.org/rfc/rfc1918)
- [RFC 4632 — Classless Inter-domain Routing (CIDR)](https://www.rfc-editor.org/rfc/rfc4632)
- [RFC 8200 — Internet Protocol, Version 6 (IPv6)](https://www.rfc-editor.org/rfc/rfc8200)
- [ipcalc — IP subnet calculator](http://jodies.de/ipcalc)
- [Subnet Calculator — Solarwinds](https://www.solarwinds.com/free-tools/advanced-subnet-calculator)
- [NetBox — IPAM/DCIM Open Source](https://netbox.dev/)
