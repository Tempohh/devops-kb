---
title: "VPN e IPsec"
slug: vpn-ipsec
category: networking
tags: [vpn, ipsec, wireguard, openvpn, tunneling, sicurezza, site-to-site, remote-access]
search_keywords: [virtual private network, ipsec vpn, ikev2, esp, ah, wireguard vpn, openvpn, site to site vpn, remote access vpn, tunneling, ssl vpn, l2tp, pptp, strongswan, libreswan, aws vpn, azure vpn gateway, split tunneling, full tunneling, perfect forward secrecy, psk, certificates vpn]
parent: networking/sicurezza/_index
related: [networking/sicurezza/firewall-waf, networking/sicurezza/zero-trust, networking/fondamentali/tls-ssl-basics]
official_docs: https://www.wireguard.com/papers/wireguard.pdf
status: complete
difficulty: advanced
last_updated: 2026-03-09
---

# VPN e IPsec

## Panoramica

Una VPN (Virtual Private Network) crea un tunnel cifrato su una rete pubblica (Internet), permettendo a siti remoti o utenti di comunicare come se fossero sulla stessa rete privata. Esistono due categorie principali: **IPsec** (standard di settore, complesso, ampiamente supportato su hardware di rete) e **WireGuard/OpenVPN** (più semplici, implementati in software, ideali per remote access e cloud).

Per un'infrastruttura DevOps moderna, i casi d'uso tipici sono: connettere data center on-premise al cloud (site-to-site), accesso sicuro dei developer alla rete interna (remote access), e connessione sicura tra cloud region.

!!! info "VPN vs Zero Trust"
    Le VPN tradizionali danno accesso all'intera rete interna una volta autenticati — approccio "castle and moat". Zero Trust Network Access (ZTNA) è l'alternativa moderna che concede accesso per singola applicazione con verifica continua dell'identità. Per nuove implementazioni, valutare ZTNA prima della VPN.

## Prerequisiti

Questo argomento presuppone familiarità con:
- [TLS/SSL Basics](../fondamentali/tls-ssl-basics.md) — crittografia simmetrica/asimmetrica, scambio di chiavi, certificati (IPsec usa concetti analoghi)
- [TCP/IP](../fondamentali/tcpip.md) — routing IP, come i pacchetti viaggiano da A a B (necessario per capire tunneling)
- [Modello OSI](../fondamentali/modello-osi.md) — IPsec opera a L3, OpenVPN a L4/L7: il layer impatta il comportamento con NAT e firewall

Senza questi concetti, alcune sezioni potrebbero risultare difficili da contestualizzare.

## Concetti Chiave

### IPsec — Architettura

IPsec opera a livello IP (Layer 3) e offre due modi di funzionamento:

| Modalità | Cosa cifra | Header IP originale | Uso |
|----------|-----------|--------------------|----|
| **Transport** | Solo il payload (dati) | Visibile | Host-to-host (raro) |
| **Tunnel** | Tutto il pacchetto IP originale | Incapsulato in nuovo header | Site-to-site, remote access |

**Protocolli IPsec:**
- **AH (Authentication Header)**: autenticazione e integrità, nessuna cifratura — raramente usato da solo
- **ESP (Encapsulating Security Payload)**: cifratura + autenticazione + integrità — il protocollo standard
- **IKE/IKEv2 (Internet Key Exchange)**: negozia i parametri SA (Security Association) e scambia le chiavi

### Confronto Tecnologie VPN

| Aspetto | IPsec/IKEv2 | WireGuard | OpenVPN |
|---------|-------------|-----------|---------|
| Standard | IETF standard | De facto | De facto |
| Performance | Alta | Massima | Media |
| Configurazione | Complessa | Semplicissima | Media |
| Codebase | Grande | ~4000 righe | Grande |
| NAT traversal | Con NAT-T | Nativo | Sì |
| Mobile support | iOS/Android nativo | Con app | Con app |
| Hardware support | Ampio (router/firewall) | In crescita | Limitato |
| Porte | UDP 500, 4500 | UDP (configurabile) | UDP 1194 / TCP 443 |

### Modalità VPN

**Site-to-Site:**
```
Rete A (10.0.0.0/8)                 Rete B (172.16.0.0/12)
    │                                    │
 VPN GW-A ────[ Internet - Tunnel ]──── VPN GW-B
    │                                    │
 Tutti i host possono comunicare tra loro
```

**Remote Access:**
```
Laptop remoto (IP pubblico)
    │
    └── VPN Client
        │ Tunnel cifrato
        ▼
     VPN Server
        │
     Rete interna (10.0.0.0/8)
     ├── Database: 10.0.1.10
     ├── Kubernetes: 10.0.2.0/24
     └── Internal tools: 10.0.3.0/24
```

## Architettura / Come Funziona

### IPsec/IKEv2 — Handshake

```
Client                              Server
  |                                   |
  |── IKE_SA_INIT ─────────────────>|
  |   (algoritmi, DH group, nonce)   |
  |<── IKE_SA_INIT ─────────────────|
  |    (algoritmi negoziati, chiave DH)
  |                                   |
  |── IKE_AUTH ──────────────────────>|
  |   (identità, certificato/PSK)    |
  |<── IKE_AUTH ─────────────────────|
  |    (child SA stabilita)          |
  |                                   |
  |══ Dati cifrati con ESP ══════════|
```

**Phase 1 (IKE SA)**: negozia i parametri per proteggere la comunicazione IKE stessa (DH key exchange, algoritmi).
**Phase 2 (Child SA / IPsec SA)**: negozia i parametri per il traffico dati (quale traffico, cifratura, integrità).

### WireGuard — Architettura Semplificata

WireGuard è radicalmente più semplice:

```
# Ogni peer ha:
# - Chiave privata (generata localmente, mai condivisa)
# - Chiave pubblica (condivisa con i peer)
# - Lista di allowed IPs (subnet che possono passare dal peer)

# Handshake: 1 RTT, basato su Noise Protocol Framework
# Crittografia: Curve25519, ChaCha20-Poly1305, Blake2s
# Nessuna negoziazione di algoritmi — solo i migliori
```

## Configurazione & Pratica

### WireGuard — Setup Site-to-Site

```bash
# Installa WireGuard
apt install wireguard

# Genera chiavi su entrambi i server
wg genkey | tee server-private.key | wg pubkey > server-public.key
wg genkey | tee client-private.key | wg pubkey > client-public.key

cat server-private.key  # Es: 8GboYh...
cat server-public.key   # Es: xYmDMH...
```

```ini
# /etc/wireguard/wg0.conf — Server A (10.0.0.0/8)

[Interface]
Address = 10.100.0.1/30         # IP tunnel per questo peer
PrivateKey = <SERVER-A-PRIVATE-KEY>
ListenPort = 51820

# Routing: forward il traffico verso la rete locale
PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE

[Peer]
PublicKey = <SERVER-B-PUBLIC-KEY>
AllowedIPs = 10.100.0.2/32, 172.16.0.0/12   # IP tunnel B + rete B
Endpoint = <SERVER-B-PUBLIC-IP>:51820
PersistentKeepalive = 25    # Mantieni vivo attraverso NAT
```

```ini
# /etc/wireguard/wg0.conf — Server B (172.16.0.0/12)

[Interface]
Address = 10.100.0.2/30
PrivateKey = <SERVER-B-PRIVATE-KEY>
ListenPort = 51820

PostUp = iptables -A FORWARD -i %i -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
PostDown = iptables -D FORWARD -i %i -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE

[Peer]
PublicKey = <SERVER-A-PUBLIC-KEY>
AllowedIPs = 10.100.0.1/32, 10.0.0.0/8     # IP tunnel A + rete A
Endpoint = <SERVER-A-PUBLIC-IP>:51820
PersistentKeepalive = 25
```

```bash
# Avvia WireGuard
systemctl enable --now wg-quick@wg0

# Verifica stato
wg show
# Output:
# interface: wg0
#   public key: xYmDMH...
#   listening port: 51820
#
# peer: <SERVER-B-PUBLIC-KEY>
#   endpoint: x.x.x.x:51820
#   allowed ips: 10.100.0.2/32, 172.16.0.0/12
#   latest handshake: 5 seconds ago
#   transfer: 1.23 MiB received, 456 KiB sent

# Test connettività
ping 10.100.0.2          # Ping tunnel endpoint
ping 172.16.0.1          # Ping host in rete remota
```

### StrongSwan — IPsec/IKEv2

```bash
# Installa
apt install strongswan strongswan-pki

# Genera CA e certificati
cd /etc/ipsec.d/

# Root CA
ipsec pki --gen --type rsa --size 4096 --outform pem > private/ca-key.pem
ipsec pki --self --ca --lifetime 3650 \
  --in private/ca-key.pem --type rsa \
  --dn "CN=VPN Root CA, O=MyOrg, C=IT" \
  --outform pem > cacerts/ca-cert.pem

# Certificato server
ipsec pki --gen --type rsa --size 2048 --outform pem > private/server-key.pem
ipsec pki --pub --in private/server-key.pem --type rsa | \
  ipsec pki --issue --lifetime 1825 \
  --cacert cacerts/ca-cert.pem --cakey private/ca-key.pem \
  --dn "CN=vpn.example.com, O=MyOrg, C=IT" \
  --san vpn.example.com \
  --flag serverAuth --flag ikeIntermediate \
  --outform pem > certs/server-cert.pem
```

```
# /etc/ipsec.conf
config setup
    charondebug="ike 1, knl 1, cfg 1"

conn %default
    ikelifetime=60m
    keylife=20m
    rekeymargin=3m
    keyingtries=1
    keyexchange=ikev2
    authby=pubkey

conn ikev2-vpn
    left=%any
    leftid=@vpn.example.com
    leftcert=server-cert.pem
    leftsendcert=always
    leftsubnet=0.0.0.0/0         # Tutto il traffico attraverso il tunnel (full tunnel)

    right=%any
    rightid=%any
    rightauth=eap-mschapv2
    rightsourceip=10.200.0.0/24  # IP pool per i client
    rightdns=8.8.8.8,8.8.4.4

    auto=add
    fragmentation=yes
    dpdaction=clear
```

```
# /etc/ipsec.secrets
: RSA server-key.pem
user1 : EAP "SecurePassword123!"
```

### AWS Site-to-Site VPN

```bash
# Crea Customer Gateway (il tuo router on-premise)
aws ec2 create-customer-gateway \
  --type ipsec.1 \
  --public-ip 203.0.113.10 \   # IP pubblico del tuo router
  --bgp-asn 65000

# Crea Virtual Private Gateway e attaccalo alla VPC
aws ec2 create-vpn-gateway --type ipsec.1
aws ec2 attach-vpn-gateway --vpn-gateway-id vgw-xxx --vpc-id vpc-xxx

# Crea connessione VPN
aws ec2 create-vpn-connection \
  --type ipsec.1 \
  --customer-gateway-id cgw-xxx \
  --vpn-gateway-id vgw-xxx \
  --options '{"StaticRoutesOnly":false}'  # Usa BGP

# Scarica configurazione per il tuo dispositivo
aws ec2 describe-vpn-connections --vpn-connection-ids vpn-xxx
```

## Best Practices

- **WireGuard per nuove implementazioni**: più semplice, più performante, più sicuro per default — preferirlo a IPsec quando non c'è vincolo di interoperabilità hardware
- **IKEv2 per IPsec**: usare sempre IKEv2 (mai IKEv1, mai L2TP/IPsec che usa IKEv1)
- **Certificati invece di PSK**: Pre-Shared Key è scomodo da ruotare e più vulnerabile — usare certificati per produzione
- **PFS (Perfect Forward Secrecy)**: configurare DH group 14+ (o ECDH) per IKEv2 — garantisce che le chiavi di sessione non siano compromesse anche se la chiave a lungo termine lo fosse
- **Monitoring**: monitorare lo stato dei tunnel — i tunnel IPsec cadono silenziosamente; configurare alert su `ike.sa` count
- **Split tunneling**: in remote access VPN, inviare solo il traffico interno attraverso il tunnel — non tutto Internet — per ridurre il carico e non degradare la navigazione dell'utente

## Troubleshooting

| Sintomo | Causa | Soluzione |
|---------|-------|-----------|
| Tunnel non si stabilisce | Porta UDP 500/4500 bloccata | Aprire porte firewall |
| WireGuard: handshake ma nessun traffico | `AllowedIPs` non corretti | Verificare subnet nella configurazione |
| IPsec: `NO_PROPOSAL_CHOSEN` | Algoritmi non compatibili | Allineare cipher suite tra i due estremi |
| Tunnel cade ogni ora | Rekeying fallisce | Verificare certificati e clock NTP sincronizzato |
| Latenza alta | Fragmentation | Ridurre MTU, abilitare MSS clamping |

```bash
# Debug WireGuard
wg show       # Stato dettagliato
tcpdump -i eth0 'udp port 51820'  # Verifica traffico UDP

# Debug StrongSwan/IPsec
ipsec statusall    # Stato completo
ipsec up conn-name  # Forza riconnessione
journalctl -u strongswan -f  # Log live

# Test connettività
ping -I wg0 <peer-ip>     # Ping attraverso interfaccia WireGuard
traceroute <remote-host>  # Verifica path
```

## Relazioni

??? info "Zero Trust — Alternativa moderna alla VPN"
    ZTNA offre accesso per applicazione invece che per rete.

    **Approfondimento →** [Zero Trust Networking](zero-trust.md)

??? info "Firewall e WAF — Integrazione con VPN"
    I firewall gestiscono quali subnet sono accessibili attraverso la VPN.

    **Approfondimento →** [Firewall e WAF](firewall-waf.md)

## Riferimenti

- [WireGuard Whitepaper](https://www.wireguard.com/papers/wireguard.pdf)
- [StrongSwan Documentation](https://docs.strongswan.org/)
- [AWS Site-to-Site VPN](https://docs.aws.amazon.com/vpn/latest/s2svpn/)
- [RFC 7296 — IKEv2](https://www.rfc-editor.org/rfc/rfc7296)
