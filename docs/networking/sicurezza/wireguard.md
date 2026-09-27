---
title: "WireGuard"
slug: wireguard
category: networking
tags: [wireguard, vpn, tunneling, cryptography, sicurezza, kubernetes, site-to-site, mesh]
search_keywords: [wireguard vpn, wg, wg-quick, wg0.conf, noise protocol, noise ik, curve25519, chacha20-poly1305, cryptokey routing, allowedips, persistentkeepalive, wg genkey, wg pubkey, wg genpsk, preshared key, hub and spoke, site to site vpn, full mesh, tailscale, netbird, headscale, netmaker, cilium wireguard, calico wireguard, transparent encryption, vpn ec2, alternativa vpn ipsec, openvpn, mtu 1420, udp 51820, kernel vpn, boringtun, wireguard-go]
parent: networking/sicurezza/_index
related: [networking/sicurezza/vpn-ipsec, networking/sicurezza/zero-trust, networking/sicurezza/firewall-waf, networking/fondamentali/nat, networking/fondamentali/network-troubleshooting, networking/kubernetes/cni, cloud/aws/networking/vpc]
official_docs: https://www.wireguard.com/
status: reviewed
difficulty: intermediate
last_updated: 2026-09-26
last_verified: 2026-09-27
---

# WireGuard

## Panoramica

WireGuard è una VPN a livello 3 (IP) integrata nel kernel Linux dalla versione 5.6 (2020), disponibile anche per Windows, macOS, BSD, Android e iOS. Il codebase è di circa 4.000 righe nel kernel (contro le centinaia di migliaia di IPsec/OpenVPN), quindi è auditabile, con una superficie di attacco ridotta. Espone una normale interfaccia di rete (`wg0`) su cui si applica il routing standard.

Perché esiste: IPsec è interoperabile ma complesso (IKE, SA, proposal da negoziare), OpenVPN è flessibile ma gira in userspace ed è più lento. WireGuard adotta **una sola suite crittografica fissa**, nessuna negoziazione di algoritmi, nessun daemon di controllo e uno stato minimo: un peer è definito da una chiave pubblica e da una lista di IP consentiti.

Quando usarlo: remote access, site-to-site tra cloud/on-premise, overlay tra nodi, cifratura del traffico pod-to-pod in Kubernetes. Quando NON usarlo: interoperabilità con hardware di rete che parla solo IPsec (es. Site-to-Site VPN gestita AWS/Azure), ambienti che richiedono algoritmi certificati FIPS 140 (ChaCha20 e Curve25519 non sono nel perimetro FIPS classico), o necessità di autenticazione con certificati X.509/utente-password nativa.

## Concetti Chiave

!!! note "Cryptokey routing"
    Ogni peer è associato a una chiave pubblica e a una lista `AllowedIPs`. In **uscita** `AllowedIPs` funge da tabella di routing (il pacchetto va al peer la cui lista contiene la destinazione, longest prefix match). In **ingresso** funge da ACL: un pacchetto decifrato da un peer è accettato solo se l'IP sorgente rientra nei suoi `AllowedIPs`.

| Elemento | Descrizione |
|---|---|
| Chiave privata/pubblica | Curve25519 (32 byte, base64). Identità del peer; non esistono certificati né CA |
| Preshared key (opzionale) | Chiave simmetrica aggiuntiva mixata nell'handshake: difesa post-quantum "best effort" |
| `AllowedIPs` | Routing + ACL per peer (vedi sopra) |
| `Endpoint` | `IP:porta` UDP del peer; appreso dinamicamente dal roaming se non specificato |
| `PersistentKeepalive` | Intervallo (s) di pacchetti keepalive; necessario dietro NAT |
| Handshake | Rinnovato ogni ~2 minuti (o ogni 2^60 messaggi); nuove chiavi di sessione a ogni rekey |

### Modello crittografico

WireGuard usa il framework **Noise** (pattern `Noise_IKpsk2`) con primitive fisse:

- **Curve25519** per lo scambio di chiavi ECDH
- **ChaCha20-Poly1305** (AEAD) per cifratura e autenticazione dei pacchetti
- **BLAKE2s** per hashing, **HKDF** per la derivazione delle chiavi
- **SipHash24** per le hashtable interne, **Cookie** per la protezione DoS dell'handshake

Proprietà: Perfect Forward Secrecy (chiavi di sessione effimere), protezione da replay (contatore con finestra), identity hiding parziale e risposta **silenziosa**: un peer non risponde a pacchetti da chiavi sconosciute, quindi la porta UDP non è rilevabile con una scansione.

### Confronto con IPsec e OpenVPN

| Aspetto | WireGuard | IPsec/IKEv2 | OpenVPN |
|---|---|---|---|
| Livello / trasporto | L3, UDP | L3, ESP + UDP 500/4500 | L2/L3, UDP o TCP |
| Implementazione | Kernel (userspace: wireguard-go, BoringTun) | Kernel + daemon IKE | Userspace |
| Negoziazione algoritmi | Nessuna (suite fissa) | Complessa (proposal) | TLS cipher suite |
| Autenticazione | Chiavi pubbliche statiche | PSK / certificati / EAP | Certificati / user-pass |
| Assegnazione IP dinamica | No (statica per peer) | Sì (config payload) | Sì (push) |
| HA / failover nativo | No | Parziale (DPD, dual tunnel cloud) | Parziale |
| Performance | Molto alta | Alta (con offload HW) | Media |
| Interoperabilità hardware | Limitata | Ampia | Media |

## Architettura / Come Funziona

Il flusso di un pacchetto in uscita:

1. Il kernel instrada il pacchetto verso `wg0` (route verso la subnet del peer).
2. WireGuard cerca tra i peer quello con `AllowedIPs` che contiene l'IP di destinazione.
3. Se non esiste una sessione valida (o è scaduta), avvia l'handshake verso `Endpoint`: 1 round-trip (initiation + response), poi il primo pacchetto dati conferma.
4. Il pacchetto viene cifrato, incapsulato in UDP e inviato all'`Endpoint`.

In ingresso: il pacchetto UDP cifrato è decifrato, si identifica il peer dalla sessione, si verifica che l'IP sorgente interno sia in `AllowedIPs` del peer, quindi si consegna allo stack IP.

**Roaming**: l'`Endpoint` di un peer si aggiorna automaticamente quando arriva un pacchetto autenticato da un nuovo IP/porta. Questo rende WireGuard adatto a client mobili. Non esiste il concetto di "server" e "client": è una relazione simmetrica; per convenzione chi ha IP pubblico stabile fa da hub.

**Assenza di stato visibile**: senza traffico, l'interfaccia non trasmette nulla (nessun keepalive di default). Un tunnel "up" significa solo che l'interfaccia esiste; l'unico indicatore reale è `latest handshake` in `wg show`.

## Configurazione & Pratica

### Installazione e generazione chiavi

```bash
# Debian/Ubuntu (kernel >= 5.6 include il modulo)
sudo apt install wireguard wireguard-tools

# Genera chiave privata e pubblica (umask restrittiva: la privata è un segreto)
umask 077
wg genkey | tee privatekey | wg pubkey > publickey

# Preshared key opzionale, una per coppia di peer
wg genpsk > psk-peerA-peerB
```

!!! warning "Protezione delle chiavi private"
    La chiave privata in `wg0.conf` (permessi `600`, owner root) è l'unica identità del peer. Non committarla in Git; distribuiscila via secret manager (Vault, AWS Secrets Manager, SOPS). Una chiave compromessa richiede la rimozione manuale del peer da tutti gli altri nodi.

### Hub-and-spoke (remote access)

Hub con IP pubblico (`203.0.113.10`), spoke dietro NAT.

```ini
# /etc/wireguard/wg0.conf — HUB
[Interface]
Address    = 10.100.0.1/24
ListenPort = 51820
PrivateKey = <HUB_PRIVATE_KEY>
# NAT verso Internet per i client che usano il full tunnel
PostUp   = sysctl -w net.ipv4.ip_forward=1; iptables -t nat -A POSTROUTING -s 10.100.0.0/24 -o eth0 -j MASQUERADE; iptables -A FORWARD -i wg0 -j ACCEPT; iptables -A FORWARD -o wg0 -j ACCEPT
PostDown = iptables -t nat -D POSTROUTING -s 10.100.0.0/24 -o eth0 -j MASQUERADE; iptables -D FORWARD -i wg0 -j ACCEPT; iptables -D FORWARD -o wg0 -j ACCEPT

[Peer]  # laptop-alice
PublicKey    = <ALICE_PUBLIC_KEY>
PresharedKey = <PSK_ALICE>
AllowedIPs   = 10.100.0.2/32

[Peer]  # laptop-bob
PublicKey  = <BOB_PUBLIC_KEY>
AllowedIPs = 10.100.0.3/32
```

```ini
# /etc/wireguard/wg0.conf — SPOKE (laptop)
[Interface]
Address    = 10.100.0.2/24
PrivateKey = <ALICE_PRIVATE_KEY>
DNS        = 10.100.0.1

[Peer]  # hub
PublicKey           = <HUB_PUBLIC_KEY>
PresharedKey        = <PSK_ALICE>
Endpoint            = 203.0.113.10:51820
# Split tunnel: solo le reti aziendali. Full tunnel: 0.0.0.0/0, ::/0
AllowedIPs          = 10.100.0.0/24, 10.20.0.0/16
PersistentKeepalive = 25
```

```bash
# Gestione con wg-quick
sudo wg-quick up wg0
sudo systemctl enable --now wg-quick@wg0   # avvio al boot
sudo wg show                               # stato, handshake, byte trasferiti
sudo wg syncconf wg0 <(wg-quick strip wg0) # applica modifiche ai peer senza riavviare l'interfaccia
```

### Site-to-site con routing e NAT

Due sedi: A (`192.168.10.0/24`, gateway pubblico `198.51.100.1`) e B (`192.168.20.0/24`, gateway `203.0.113.5`). Tunnel `10.255.0.0/30`.

```ini
# Gateway A — /etc/wireguard/wg0.conf
[Interface]
Address    = 10.255.0.1/30
ListenPort = 51820
PrivateKey = <A_PRIVATE_KEY>

[Peer]  # gateway B
PublicKey  = <B_PUBLIC_KEY>
Endpoint   = 203.0.113.5:51820
# Include la LAN remota: wg-quick crea la route automaticamente
AllowedIPs = 10.255.0.2/32, 192.168.20.0/24
PersistentKeepalive = 25
```

```bash
# Su ENTRAMBI i gateway: abilita il forwarding in modo persistente
echo 'net.ipv4.ip_forward=1' | sudo tee /etc/sysctl.d/99-wg.conf
sudo sysctl --system

# Firewall: consenti UDP 51820 in ingresso e il forwarding tra LAN e wg0 (nftables)
sudo nft add rule inet filter input udp dport 51820 accept
sudo nft add rule inet filter forward iifname "wg0" oifname "eth1" accept
sudo nft add rule inet filter forward iifname "eth1" oifname "wg0" ct state established,related accept

# Senza route sui client della LAN, il gateway deve essere il default GW
# oppure aggiungere sull'host: ip route add 192.168.20.0/24 via 192.168.10.1
```

!!! tip "NAT non necessario in site-to-site"
    Se le due LAN hanno subnet distinte e i gateway sono raggiungibili come next-hop, il traffico è instradato puro senza NAT: si preserva l'IP sorgente reale (utile per log e ACL). Il masquerade serve solo per l'accesso a Internet in full tunnel o quando le LAN si sovrappongono. Vedi [NAT](../fondamentali/nat.md).

### Full-mesh gestito

Gestire N(N-1)/2 coppie a mano non scala. Piani di controllo che automatizzano distribuzione chiavi, NAT traversal (STUN/ICE, relay DERP/TURN) e ACL:

| Strumento | Modello | Note |
|---|---|---|
| **Tailscale** | SaaS control plane, client basato su wireguard-go | ACL per identità (SSO), MagicDNS, subnet router, exit node |
| **Headscale** | Control plane Tailscale self-hosted open source | Singolo tailnet, adatto a homelab/team piccoli |
| **NetBird** | Open source, self-hostable | Peer-to-peer con policy di accesso per gruppi |
| **Netmaker** | Gestione di reti WireGuard kernel | Orientato a site-to-site e mesh |

### Uso in Kubernetes

I CNI moderni offrono cifratura trasparente node-to-node con WireGuard, senza sidecar (vedi [CNI](../kubernetes/cni.md)):

```bash
# Cilium: abilita cifratura trasparente WireGuard (Helm)
helm upgrade cilium cilium/cilium -n kube-system --reuse-values \
  --set encryption.enabled=true \
  --set encryption.type=wireguard

# Verifica
kubectl -n kube-system exec ds/cilium -- cilium status | grep -i encryption
kubectl -n kube-system exec ds/cilium -- cilium encrypt status
```

```bash
# Calico: abilita WireGuard sul cluster (richiede kernel con modulo wireguard)
calicoctl patch felixconfiguration default --type='merge' \
  -p '{"spec":{"wireguardEnabled":true}}'

# Verifica: ogni nodo espone l'interfaccia wireguard.cali e la chiave pubblica
kubectl get node <nodo> -o yaml | grep -i wireguard
```

La cifratura è applicata al traffico pod-to-pod tra nodi diversi; il traffico intra-nodo non è cifrato. È un controllo complementare all'mTLS del service mesh (vedi [Zero Trust](zero-trust.md)), non un sostituto: cifra il trasporto ma non autentica il workload applicativo.

### Deploy su EC2 come alternativa alla Site-to-Site VPN AWS

Una istanza EC2 con WireGuard può collegare on-premise a una [VPC](../../cloud/aws/networking/vpc.md) a costo ridotto e con configurazione semplice.

```bash
# Requisiti EC2:
# 1) Elastic IP associato
# 2) Security Group: UDP 51820 da IP pubblico della sede
# 3) Source/Dest check DISABILITATO (altrimenti AWS scarta il traffico instradato)
aws ec2 modify-instance-attribute --instance-id i-0abc123 --no-source-dest-check

# 4) Route table della VPC: destinazione LAN on-prem -> ENI/instance dell'istanza WireGuard
aws ec2 create-route --route-table-id rtb-0abc123 \
  --destination-cidr-block 192.168.10.0/24 --instance-id i-0abc123
```

| Aspetto | VPN Site-to-Site AWS (IPsec) | WireGuard su EC2 |
|---|---|---|
| HA | 2 tunnel su 2 AZ gestiti da AWS | Nessuno nativo: serve secondo nodo + failover di route (script/Lambda) |
| Throughput | ~1,25 Gbps per tunnel | Limitato da tipo istanza (network baseline) |
| Gestione chiavi | Gestita, PSK per tunnel | Rotazione manuale (nessun meccanismo integrato) |
| Costo | Fee orario + trasferimento dati | Costo istanza + trasferimento dati |
| Routing dinamico | BGP | Statico (o BGP con FRR sopra il tunnel) |

!!! warning "Limiti operativi"
    L'istanza EC2 è un single point of failure e un nodo da patchare. Non esiste scadenza delle chiavi né revoca centralizzata: la rotazione richiede di aggiornare `PublicKey` su entrambi i lati. Per produzione critica preferire la VPN gestita o Transit Gateway; usare WireGuard per dev/test, backup path o carichi tolleranti al failover.

## Best Practices

- **Un peer, una chiave**: non riusare la stessa chiave privata su più dispositivi; la revoca sarebbe impossibile in modo selettivo.
- **AllowedIPs minimi**: assegnare `/32` (e `/128`) per i client; nel hub non includere mai `0.0.0.0/0` per più di un peer (vedi Troubleshooting).
- **PresharedKey** per ogni coppia sensibile come ulteriore livello simmetrico.
- **PersistentKeepalive = 25** solo sul lato dietro NAT; evitarlo altrove (traffico inutile, il tunnel silenzioso è una feature).
- **Cambiare `ListenPort`** non offre sicurezza reale (la porta non risponde comunque), ma può servire per superare firewall che bloccano UDP alti: 443/UDP è spesso permessa.
- **Rotazione chiavi programmata** (es. ogni 6–12 mesi) automatizzata con Ansible/Terraform; documentare la procedura di revoca.
- **Gestire i peer con IaC**: generare `wg0.conf` da template e secret manager, non a mano.
- **Monitoraggio**: esportare `wg show all dump` (Prometheus `wireguard_exporter`) e allarmare su `latest handshake` > 3 minuti per peer con keepalive attivo.
- **Logging**: WireGuard non registra connessioni; per audit e forensics usare log del firewall/conntrack sull'hub.

## Troubleshooting

### Handshake assente (`latest handshake` mancante)

**Sintomo**: `wg show` mostra il peer con `transfer: 0 B received` e nessuna riga `latest handshake`.

**Cause**: chiave pubblica errata su uno dei due lati (scambio pubblica/privata), `Endpoint` errato, UDP bloccato, orologio non rilevante (WireGuard non richiede NTP preciso, ma il timestamp TAI64N nell'handshake evita replay).

```bash
sudo wg show wg0                           # verificare chiavi e endpoint
sudo tcpdump -ni eth0 udp port 51820       # arrivano pacchetti dal peer?
sudo wg show wg0 public-key                # confrontare con PublicKey configurata sull'altro lato
sudo wg-quick down wg0 && sudo wg-quick up wg0
```

**Soluzione**: correggere le chiavi (tipico errore: incollare la privata al posto della pubblica); se `tcpdump` non vede nulla, il problema è di rete/firewall a monte.

### UDP bloccato o NAT timeout

**Sintomo**: il tunnel funziona per qualche minuto poi si ferma; il peer dietro NAT non riceve più traffico inbound.

**Causa**: il NAT/firewall stateful chiude il mapping UDP inattivo (spesso 30–120 s) e senza traffico in uscita il peer non è più raggiungibile; oppure la rete blocca UDP 51820.

```bash
# Sul peer dietro NAT: keepalive ogni 25 secondi
sudo wg set wg0 peer <PUBKEY> persistent-keepalive 25
# Verifica se la porta UDP raggiunge l'hub
nc -u -vz 203.0.113.10 51820   # non conclusivo (UDP): usare tcpdump sull'hub
```

**Soluzione**: impostare `PersistentKeepalive = 25` sul peer NATtato; se UDP è filtrato, usare 443/UDP o un tunnel UDP-over-TCP (udp2raw, wstunnel), accettando la perdita di prestazioni.

### Handshake OK ma nessun traffico

**Sintomo**: `latest handshake` recente, ma `ping` verso l'IP del peer fallisce o i byte ricevuti crescono senza risposte.

**Cause**: `AllowedIPs` non include la destinazione o l'IP sorgente; `ip_forward` disabilitato; regole FORWARD del firewall; `rp_filter` che scarta pacchetti asimmetrici.

```bash
sysctl net.ipv4.ip_forward                 # deve essere 1 sui gateway
ip route get 192.168.20.5                  # deve passare da wg0
sudo nft list ruleset | grep -E 'wg0|51820'
sudo sysctl -w net.ipv4.conf.all.rp_filter=2   # loose mode se routing asimmetrico
sudo wg show wg0 allowed-ips
```

**Soluzione**: aggiungere la subnet remota ad `AllowedIPs` (su entrambi i lati, in modo speculare), abilitare forwarding e regole FORWARD.

### AllowedIPs sovrapposti

**Sintomo**: solo uno dei peer riceve traffico; aggiungere un secondo peer "spegne" il primo. Comportamento dopo `wg-quick up` con due peer che dichiarano `0.0.0.0/0`.

**Causa**: un prefisso può appartenere a un solo peer; se duplicato, WireGuard lo assegna all'ultimo peer configurato (il precedente lo perde). Con full tunnel su più peer sul client si ottengono route in conflitto.

```bash
sudo wg show wg0 allowed-ips    # cercare prefissi duplicati
```

**Soluzione**: assegnare prefissi disgiunti; per più uscite usare policy routing (`ip rule`, `Table = ...` in wg-quick) o un solo peer con `0.0.0.0/0`.

### MTU e frammentazione

**Sintomo**: ping e SSH funzionano, ma HTTPS/scp si blocca o è lento su trasferimenti grandi; connessioni che si bloccano dopo l'handshake TLS.

**Causa**: l'overhead WireGuard (60 byte su IPv4, 80 su IPv6) riduce la MTU utile. Il default `1420` di wg-quick (basato su 1500 - 80) è sbagliato se il path ha MTU minore (PPPoE 1492, tunnel annidati, alcuni cloud) e l'ICMP "Fragmentation needed" è filtrato (PMTUD black hole).

```bash
ip link show wg0 | grep mtu
# Trova la MTU massima del path (Don't Fragment)
ping -M do -s 1372 -c 3 10.100.0.1          # scendere finché passa
# Imposta MTU in wg0.conf
# [Interface]
# MTU = 1380
# Oppure clamp MSS per traffico TCP forwardato:
sudo iptables -t mangle -A FORWARD -o wg0 -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu
```

**Soluzione**: ridurre `MTU` (es. 1380 o 1280 per IPv6 sicuro) e applicare MSS clamping sul gateway; non bloccare ICMP tipo 3 codice 4.

## Relazioni

??? info "VPN e IPsec — Approfondimento"
    IPsec resta lo standard per l'interoperabilità con hardware e servizi gestiti (AWS/Azure Site-to-Site). WireGuard è preferibile per semplicità e performance quando controlli entrambi gli endpoint.

    **Approfondimento completo →** [VPN e IPsec](vpn-ipsec.md)

??? info "Zero Trust — Approfondimento"
    Una VPN WireGuard fornisce un canale cifrato ma, da sola, concede accesso di rete: Tailscale/NetBird aggiungono policy per identità e device, avvicinandosi a un modello ZTNA.

    **Approfondimento completo →** [Zero Trust Networking](zero-trust.md)

??? info "Firewall e WAF — Approfondimento"
    Le regole iptables/nftables per INPUT (UDP 51820) e FORWARD tra `wg0` e le LAN sono parte integrante di ogni deploy.

    **Approfondimento completo →** [Firewall e WAF](firewall-waf.md)

??? info "Kubernetes CNI — Approfondimento"
    Cilium e Calico usano WireGuard per la cifratura trasparente del traffico tra nodi.

    **Approfondimento completo →** [CNI](../kubernetes/cni.md)

## Riferimenti

- [WireGuard — sito ufficiale e quick start](https://www.wireguard.com/quickstart/)
- [WireGuard Whitepaper (Donenfeld)](https://www.wireguard.com/papers/wireguard.pdf)
- [Noise Protocol Framework](https://noiseprotocol.org/)
- [Cilium — Transparent Encryption with WireGuard](https://docs.cilium.io/en/stable/security/network-encryption/)
- [Calico — Encrypt in-cluster pod traffic](https://docs.tigera.io/calico/latest/network-policy/encrypt-cluster-pod-traffic)
- [Tailscale — How it works](https://tailscale.com/blog/how-tailscale-works)
