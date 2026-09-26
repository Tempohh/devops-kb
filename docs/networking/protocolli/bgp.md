---
title: "BGP — Border Gateway Protocol"
slug: bgp
category: networking
tags: [bgp, routing, ebgp, ibgp, direct-connect, bfd, rpki, metallb, cilium, calico]
search_keywords: [border gateway protocol, bgp-4, ebgp, ibgp, asn, autonomous system, as_path, local_pref, med, communities, best path selection, route reflector, bfd, route dampening, rpki, rov, bgp hijack, route leak, aws direct connect, transit vif, private vif, transit gateway, site-to-site vpn, ecmp, cilium bgp control plane, calico bgp, metallb, frr, bird, vtysh, birdc, calicoctl, prepend, multihop, ttl security, gtsm, md5, tcp-ao, graceful restart, add-path, anycast, peering, transit, ixp]
parent: networking/protocolli/_index
related: [networking/kubernetes/cni, networking/sicurezza/ddos-protezione, networking/sicurezza/vpn-ipsec, networking/fondamentali/tcpip, cloud/aws/networking/vpc-avanzato, cloud/azure/networking/connettivita]
official_docs: https://www.rfc-editor.org/rfc/rfc4271
status: complete
difficulty: advanced
last_updated: 2026-09-26
---

# BGP — Border Gateway Protocol

## Panoramica

BGP-4 (RFC 4271) è il protocollo di routing **path-vector** che tiene insieme Internet: scambia raggiungibilità di prefissi IP tra **Autonomous System (AS)**, cioè insiemi di reti sotto un'unica amministrazione di routing identificati da un **ASN**. A differenza degli IGP (OSPF, IS-IS), che ottimizzano una metrica su un'unica rete, BGP applica **policy**: decide *quali* route accettare, annunciare e preferire in base a relazioni commerciali e tecniche (transit, peering, cliente).

In ambito DevOps/cloud BGP compare in tre scenari ricorrenti: (1) **connettività ibrida** verso il cloud (AWS Direct Connect, Transit Gateway con VPN dinamica, Azure ExpressRoute); (2) **Kubernetes su bare metal**, dove Cilium, Calico o MetalLB annunciano Pod CIDR e LoadBalancer IP al router top-of-rack; (3) **datacenter leaf-spine** con eBGP come unico protocollo di fabric.

Non si usa BGP quando basta un routing statico o un IGP: la convergenza è più lenta (secondi, non millisecondi) e la configurazione è più delicata. Il suo punto di forza è scalabilità (oltre 1 milione di prefissi nella tabella globale IPv4) e controllo granulare delle policy.

## Concetti Chiave

### AS e ASN

| Tipo | Range | Note |
|------|-------|------|
| ASN pubblici 2-byte | 1–64495 | Assegnati dai RIR (RIPE, ARIN, ...) |
| ASN privati 2-byte | 64512–65534 | RFC 6996; non annunciabili su Internet |
| ASN 4-byte (RFC 6793) | 65536–4294967295 | Notazione asdot `X.Y` o asplain |
| ASN privati 4-byte | 4200000000–4294967294 | RFC 6996; comodi nei fabric con molti nodi |

### eBGP vs iBGP

| Aspetto | eBGP | iBGP |
|---------|------|------|
| Peer | AS diversi | Stesso AS |
| TTL default | 1 (peer direttamente connessi) | 255 |
| AS_PATH | L'AS locale è **preposto** all'annuncio | Non modificato |
| Next-hop | Riscritto con l'IP del router | **Non** riscritto (serve `next-hop-self` o IGP) |
| AD (Cisco) | 20 | 200 |
| Loop prevention | AS_PATH contiene il proprio ASN → scarta | **Split horizon**: route iBGP non rianunciate a altri peer iBGP |

Lo split horizon iBGP impone un **full mesh** tra i router dell'AS, oppure **Route Reflector** (RFC 4456) o confederation per scalare.

### Path attributes

| Attributo | Classe | Uso |
|-----------|--------|-----|
| `AS_PATH` | Well-known mandatory | Lista di AS attraversati; più corto = preferito; base anti-loop |
| `NEXT_HOP` | Well-known mandatory | IP a cui inoltrare il traffico |
| `ORIGIN` | Well-known mandatory | IGP (i) < EGP (e) < incomplete (?) |
| `LOCAL_PREF` | Well-known discretionary | Solo dentro l'AS; **più alto = preferito**; default 100 |
| `MED` | Optional non-transitive | Suggerisce ai vicini l'ingresso preferito; **più basso = preferito** |
| `COMMUNITY` | Optional transitive | Tag 32-bit `ASN:valore`; base del traffic engineering |
| `LARGE_COMMUNITY` | Optional transitive | Tag 96-bit (RFC 8092), adatti ad ASN 4-byte |
| `WEIGHT` | Locale (Cisco/FRR) | Non propagato; preferenza più alta per singolo router |

!!! note "Communities well-known"
    `NO_EXPORT` (65535:65281) non rianuncia fuori dall'AS; `NO_ADVERTISE` (65535:65282) non rianuncia a nessun peer; `GRACEFUL_SHUTDOWN` (65535:0, RFC 8326) chiede al vicino di abbassare la preferenza prima di una manutenzione.

### Best-path selection

A parità di prefisso (longest match vince sempre, prima di BGP), il router sceglie in ordine:

1. **Weight** più alto (Cisco/FRR, locale)
2. **LOCAL_PREF** più alto
3. Route originata localmente (`network`/`redistribute`/`aggregate`)
4. **AS_PATH** più corto
5. **ORIGIN** più basso (IGP < EGP < incomplete)
6. **MED** più basso (confrontato solo tra route dello stesso AS vicino, salvo `always-compare-med`)
7. **eBGP** preferito su iBGP
8. Metrica IGP verso il next-hop più bassa
9. Se abilitato `multipath`: si installano più route (ECMP) e si esce qui
10. Route più vecchia (stabilità), poi **router-id** più basso, poi indirizzo del vicino più basso

!!! tip "Ricordare l'ordine"
    LOCAL_PREF batte AS_PATH: per controllare il traffico *in uscita* si usa LOCAL_PREF, per influenzare il traffico *in ingresso* si usano prepend, MED e communities.

### Finite State Machine e timers

```
Idle → Connect → Active → OpenSent → OpenConfirm → Established
```

| Stato | Significato | Se resta bloccato |
|-------|-------------|-------------------|
| `Idle` | Nessun tentativo in corso | Config errata, peer non definito, prefix-limit superato, backoff dopo errore |
| `Connect` | TCP handshake su porta 179 in corso | Nessuna risposta al SYN (ACL/firewall/routing) |
| `Active` | TCP fallito, si riprova (**non** significa "attivo") | Porta 179 chiusa, MD5 errato, TTL, peer non configurato lato remoto |
| `OpenSent` | OPEN inviato, attende OPEN dal peer | Mismatch versione/ASN/hold-time |
| `OpenConfirm` | OPEN ricevuto, attende KEEPALIVE | Raro; capability mismatch |
| `Established` | Sessione attiva, scambio UPDATE | — |

| Timer | Default | Note |
|-------|---------|------|
| Keepalive | 60 s (Cisco/FRR) | 1/3 dell'hold time |
| Hold time | 180 s (Cisco) / 90 s (Junos) | Si negozia il minimo tra i due peer |
| ConnectRetry | 120 s (RFC: 120) | Ritentativo TCP |
| MRAI eBGP / iBGP | 30 s / 5 s (RFC) | Intervallo minimo tra UPDATE per prefisso |

Con timer BGP i failure detection richiede decine di secondi. **BFD** (RFC 5880) rileva il guasto del link in 100–300 ms e abbatte subito la sessione BGP.

## Architettura / Come Funziona

### Tabelle e flusso delle route

```
   Peer eBGP ──UPDATE──▶ Adj-RIB-In ──inbound policy──▶ Loc-RIB ──best path──▶ FIB (kernel)
                                                          │
                                       outbound policy ◀──┘
                                             │
   Peer eBGP ◀──UPDATE── Adj-RIB-Out ◀───────┘
```

- **Adj-RIB-In**: route ricevute grezze da ciascun peer.
- **Loc-RIB**: route accettate dopo la policy di input e selezionate come best path.
- **Adj-RIB-Out**: route che si annunciano a ciascun peer dopo la policy di output.

Le policy si scrivono con **route-map**/**prefix-list**/**community-list** (FRR, Cisco) o **filter** (BIRD).

### Route Reflector e fabric datacenter

Nei datacenter leaf-spine è comune **eBGP ovunque**: ogni leaf ha un ASN privato proprio (o uno per rack), gli spine condividono un ASN. Evita IGP e route reflector, e usa `AS_PATH` come meccanismo anti-loop naturale. Con iBGP si usano Route Reflector: il RR "riflette" le route ai client, rompendo il requisito di full mesh; il rischio è la visibilità di un solo best path (mitigabile con **ADD-PATH**, RFC 7911).

### Sicurezza del piano di controllo

| Meccanismo | Protegge da | Note |
|------------|------------|------|
| TCP MD5 (RFC 2385) | Reset TCP spoofati | Legacy; chiave condivisa; supportato da AWS Direct Connect |
| TCP-AO (RFC 5925) | Come MD5, ma con algoritmi moderni | Non ovunque supportato |
| GTSM / TTL security (RFC 5082) | Attacchi da remoto: accetta solo TTL 255 | Incompatibile con multihop non diretto |
| Prefix-list + max-prefix | Leak di route, table overflow | Sempre su peering esterni |
| **RPKI ROV** (RFC 6811) | Origin hijack | Valida che l'ASN origine sia autorizzato da una **ROA** |

## Configurazione & Pratica

### FRRouting: eBGP base con policy

```bash
# Entrare nella shell FRR (integrata) e configurare
vtysh
```

```text
! /etc/frr/frr.conf
frr defaults datacenter
router bgp 65010
 bgp router-id 10.0.0.1
 bgp log-neighbor-changes
 no bgp default ipv4-unicast
 neighbor 192.0.2.2 remote-as 65020
 neighbor 192.0.2.2 description upstream-A
 neighbor 192.0.2.2 password S3gretoLungo!
 neighbor 192.0.2.2 ttl-security hops 1
 neighbor 192.0.2.2 bfd
 neighbor 192.0.2.2 timers 10 30
 !
 address-family ipv4 unicast
  network 10.10.0.0/16
  neighbor 192.0.2.2 activate
  neighbor 192.0.2.2 prefix-list ANNUNCI-OUT out
  neighbor 192.0.2.2 route-map DA-UPSTREAM in
  neighbor 192.0.2.2 maximum-prefix 1000 90 restart 5
  maximum-paths 4
 exit-address-family
!
ip prefix-list ANNUNCI-OUT seq 10 permit 10.10.0.0/16
ip prefix-list ANNUNCI-OUT seq 100 deny any
!
route-map DA-UPSTREAM permit 10
 set local-preference 200
```

`no bgp default ipv4-unicast` evita di attivare per errore l'address family; `maximum-prefix` chiude la sessione se il vicino annuncia più prefissi del previsto (protezione da leak).

### Comandi di verifica

```bash
# Riepilogo sessioni (stato, prefissi ricevuti, uptime)
vtysh -c "show ip bgp summary"

# Dettaglio di un vicino: stato FSM, timer, capability, ultimo errore
vtysh -c "show bgp neighbors 192.0.2.2"

# Route ricevute PRIMA della policy (richiede soft-reconfiguration inbound) / dopo la policy
vtysh -c "show ip bgp neighbors 192.0.2.2 received-routes"
vtysh -c "show ip bgp neighbors 192.0.2.2 routes"

# Route annunciate a un vicino
vtysh -c "show ip bgp neighbors 192.0.2.2 advertised-routes"

# Dettaglio di un prefisso: tutti i path e quello selezionato (>)
vtysh -c "show ip bgp 10.20.0.0/16"

# BIRD 2
birdc show protocols
birdc show protocols all upstream_a
birdc show route protocol upstream_a
birdc show route for 10.20.0.0/16 all

# Applicare una nuova policy senza abbattere la sessione (soft reset)
vtysh -c "clear ip bgp 192.0.2.2 soft in"
```

### AWS Direct Connect: eBGP su Private/Transit VIF

Ogni **Virtual Interface (VIF)** è una sessione eBGP tra il router on-prem (ASN vostro) e AWS (ASN `7224` per Direct Connect, oppure ASN dell'Amazon-side del Virtual Private Gateway/Direct Connect Gateway).

| VIF | Termina su | Uso |
|-----|-----------|-----|
| Private | VGW o Direct Connect Gateway | Accesso a VPC (max 100 prefissi annunciati da AWS→on-prem per DXGW; limiti da verificare in quota) |
| Transit | Direct Connect Gateway → Transit Gateway | Accesso a molte VPC via TGW; **una sola** Transit VIF per connessione dedicata (hosted: una per connessione) |
| Public | Servizi pubblici AWS | Prefissi pubblici AWS, richiede prefissi pubblici propri |

```text
! Router on-prem (IOS-XE style / FRR equivalente): VIF privata con BGP + BFD + MD5
router bgp 65010
 neighbor 169.254.100.1 remote-as 64512
 neighbor 169.254.100.1 password <BGP-AUTH-KEY-DALLA-CONSOLE-AWS>
 neighbor 169.254.100.1 fall-over bfd
 address-family ipv4
  network 10.10.0.0 mask 255.255.0.0
  neighbor 169.254.100.1 activate
  neighbor 169.254.100.1 route-map DX-OUT out
```

Traffic engineering verso AWS (traffico **in ingresso** nel vostro AS dall'AWS side e viceversa):

```text
! Rendere secondario un percorso DX: prepend AS_PATH sugli annunci verso AWS
route-map DX-SECONDARY-OUT permit 10
 set as-path prepend 65010 65010 65010

! Oppure communities di preferenza AWS su VIF privata/transit (annunciate DA voi):
!   7224:7100 = local preference bassa
!   7224:7200 = local preference media
!   7224:7300 = local preference alta
route-map DX-COMM-OUT permit 10
 set community 7224:7300
```

!!! warning "LOCAL_PREF AWS"
    AWS onora le communities `7224:7100/7200/7300` **solo entro la stessa regione** (per VIF che terminano nella stessa regione) e a parità di lunghezza prefisso. La longest prefix match vince **sempre** su qualsiasi attributo BGP: per un failover forzato si annunciano prefissi più specifici sul link preferito.

Dal lato AWS, verifica con CLI:

```bash
aws directconnect describe-virtual-interfaces \
  --query "virtualInterfaces[].{id:virtualInterfaceId,state:virtualInterfaceState,bgp:bgpPeers[].{s:bgpStatus,p:bgpPeerState}}"
```

Stato atteso: `bgpPeerState: available` e `bgpStatus: up`.

### Transit Gateway con Site-to-Site VPN dinamica e ECMP

Una VPN Site-to-Site con routing dinamico usa 2 tunnel IPsec per connessione, ciascuno con una sessione eBGP verso link-local `169.254.x.x/30`. Con **Transit Gateway** si può abilitare **ECMP** sui tunnel VPN (non disponibile su VGW), moltiplicando la banda oltre il limite di ~1,25 Gbps per tunnel.

```bash
# TGW con supporto ECMP VPN abilitato alla creazione
aws ec2 create-transit-gateway \
  --description "tgw-hub" \
  --options AmazonSideAsn=64512,VpnEcmpSupport=enable,DefaultRouteTableAssociation=enable

# Connessione VPN dinamica (BGP) verso il TGW
aws ec2 create-vpn-connection \
  --type ipsec.1 \
  --customer-gateway-id cgw-0123456789abcdef0 \
  --transit-gateway-id tgw-0123456789abcdef0 \
  --options StaticRoutesOnly=false

# Route apprese via BGP nella route table del TGW
aws ec2 search-transit-gateway-routes \
  --transit-gateway-route-table-id tgw-rtb-0123456789abcdef0 \
  --filters "Name=type,Values=propagated"
```

Requisiti ECMP: stessa lunghezza AS_PATH e stesso MED dai due tunnel; il router on-prem deve annunciare **lo stesso prefisso con attributi uguali** su entrambi i tunnel, e le connessioni devono avere ECMP abilitato su TGW.

### Kubernetes bare metal: Cilium BGP Control Plane

Cilium annuncia Pod CIDR e Service (LoadBalancer/ExternalIP) al router di rete con la CRD `CiliumBGPClusterConfig` (API v2, Cilium ≥ 1.16).

```yaml
apiVersion: cilium.io/v2alpha1
kind: CiliumBGPClusterConfig
metadata:
  name: tor-peering
spec:
  nodeSelector:
    matchLabels:
      bgp: enabled
  bgpInstances:
    - name: instance-65001
      localASN: 65001
      peers:
        - name: tor-a
          peerASN: 65000
          peerAddress: 10.0.0.1
          peerConfigRef:
            name: tor-peer-config
---
apiVersion: cilium.io/v2alpha1
kind: CiliumBGPPeerConfig
metadata:
  name: tor-peer-config
spec:
  timers:
    holdTimeSeconds: 9
    keepAliveTimeSeconds: 3
  gracefulRestart:
    enabled: true
    restartTimeSeconds: 120
  families:
    - afi: ipv4
      safi: unicast
      advertisements:
        matchLabels:
          advertise: bgp
---
apiVersion: cilium.io/v2alpha1
kind: CiliumBGPAdvertisement
metadata:
  name: pod-and-lb
  labels:
    advertise: bgp
spec:
  advertisements:
    - advertisementType: PodCIDR
    - advertisementType: Service
      service:
        addresses: [LoadBalancerIP, ExternalIP]
      selector:
        matchExpressions:
          - {key: bgp-announce, operator: NotIn, values: ["false"]}
```

```bash
# Abilitare il BGP control plane (Helm)
helm upgrade cilium cilium/cilium -n kube-system --reuse-values --set bgpControlPlane.enabled=true

# Stato sessioni e route annunciate
cilium bgp peers
cilium bgp routes advertised ipv4 unicast
```

### Kubernetes: Calico BGP e MetalLB in modalità BGP

Calico (Felix + BIRD) annuncia i Pod CIDR; si configura con `BGPConfiguration` e `BGPPeer`:

```yaml
apiVersion: projectcalico.org/v3
kind: BGPConfiguration
metadata:
  name: default
spec:
  nodeToNodeMeshEnabled: false     # disabilita full mesh iBGP, si usa il ToR
  asNumber: 64512
  serviceLoadBalancerIPs:
    - cidr: 10.96.100.0/24
---
apiVersion: projectcalico.org/v3
kind: BGPPeer
metadata:
  name: tor-a
spec:
  peerIP: 10.0.0.1
  asNumber: 65000
  nodeSelector: rack == 'rack1'
```

```bash
# Stato dei peer BGP sul nodo (richiede calicoctl node status, esegue sul nodo)
sudo calicoctl node status
calicoctl get bgppeers -o wide
```

**MetalLB** in modalità BGP annuncia gli IP dei Service `type: LoadBalancer`:

```yaml
apiVersion: metallb.io/v1beta2
kind: BGPPeer
metadata: {name: tor-a, namespace: metallb-system}
spec:
  myASN: 64512
  peerASN: 65000
  peerAddress: 10.0.0.1
  bfdProfile: fast
---
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata: {name: lb-pool, namespace: metallb-system}
spec:
  addresses: [10.96.100.0/24]
---
apiVersion: metallb.io/v1beta1
kind: BGPAdvertisement
metadata: {name: lb-adv, namespace: metallb-system}
spec:
  ipAddressPools: [lb-pool]
  aggregationLength: 32
```

!!! note "Quale scegliere"
    Se il CNI è già Cilium, il suo BGP Control Plane evita un componente aggiuntivo. Con Calico lo stesso stack copre Pod CIDR e LoadBalancer IP. MetalLB serve quando il CNI non parla BGP (es. Flannel) e serve solo l'esposizione dei Service.

## Best Practices

- **Filtra sempre in ingresso e in uscita** con prefix-list esplicite: mai annunciare o accettare "tutto". Un errore di filtro è l'origine dei principali route leak.
- **`maximum-prefix`** su ogni peer esterno, con soglia di warning e restart automatico.
- **BFD** per failure detection sub-secondo, invece di abbassare troppo hold-time/keepalive.
- **Autenticazione e TTL security**: MD5/TCP-AO più GTSM sui peering diretti.
- **RPKI ROV**: scartare le route `invalid` con validator (Routinator, StayRTR, Fort) collegato via RTR; creare le proprie **ROA** per i prefissi annunciati.
- **Graceful Restart / Graceful Shutdown**: prima di manutenzione annunciare la community `GRACEFUL_SHUTDOWN` per drenare il traffico.
- **Dual link con LOCAL_PREF** per l'uscita e **prepend/communities** per l'ingresso; testare il failover.
- Sui fabric datacenter usare **eBGP con ASN privati 4-byte**, `bgp bestpath as-path multipath-relax` per ECMP tra AS diversi.
- Nei cluster Kubernetes: limitare il `nodeSelector` ai nodi che devono annunciare, e usare `externalTrafficPolicy: Local` con BGP per preservare l'IP sorgente e annunciare solo i nodi che ospitano pod.

!!! warning "Anti-pattern"
    Redistribuire BGP in un IGP (e viceversa) senza filtri. Annunciare `0.0.0.0/0` per errore a un peer di transit. Usare `network` su prefissi non presenti nella RIB (l'annuncio non parte). Dimenticare che senza `route-map`/policy le sessioni eBGP FRR ≥ 8 non scambiano route (`RFC 8212`).

## Troubleshooting

### Sessione bloccata in `Active` o `Idle`

**Sintomo:** `show ip bgp summary` mostra `Active` (o `Idle`) nella colonna State/PfxRcd.

```bash
vtysh -c "show bgp neighbors 192.0.2.2" | grep -Ei "state|last reset|error|notification|connections"

# Raggiungibilità TCP 179 e presenza di ACL/firewall
nc -zv 192.0.2.2 179
sudo tcpdump -ni eth0 'tcp port 179 and host 192.0.2.2'
sudo iptables -S | grep -E '179'
```

**Cause frequenti e soluzioni:**

- **ACL/security group su TCP 179**: aprire 179 in entrambe le direzioni (su AWS: NACL e SG dell'istanza router).
- **MD5 mismatch**: nel log compare `Invalid MD5 digest`; la chiave deve combaciare byte per byte (attenzione a spazi/newline copiando la chiave dalla console AWS).
- **TTL/multihop**: peer non adiacenti richiedono `ebgp-multihop N` (o `ttl-security hops N`); con GTSM entrambi i lati devono concordare.
- **ASN errato**: `OPEN Message Error / Bad Peer AS` → verificare `remote-as` su entrambi i lati.
- **Peer non definito sul lato remoto**: il remoto chiude la connessione; controllare la config `neighbor` di entrambi.
- **Source address sbagliato**: usare `update-source lo0` (iBGP) o l'IP dell'interfaccia corretta.

### Sessione `Established` ma nessuna route annunciata/ricevuta

**Sintomo:** `PfxRcd = 0` oppure `(Policy)`; il vicino non vede il proprio prefisso.

```bash
vtysh -c "show ip bgp neighbors 192.0.2.2 advertised-routes"
vtysh -c "show ip route 10.10.0.0/16"        # il prefisso deve esistere nella RIB
vtysh -c "show route-map DA-UPSTREAM"
```

**Cause:** `network` su un prefisso non presente nella RIB (creare una route `Null0`/di aggregato), address-family non attivata (`neighbor ... activate`), **policy mancante** (RFC 8212: eBGP senza route-map non scambia nulla), filtro in uscita troppo restrittivo, `next-hop` non raggiungibile in iBGP (`next-hop-self`), prefissi `invalid` scartati da ROV. Su Direct Connect: prefisso oltre il limite (100 per Private VIF via DXGW → la sessione resta up ma AWS ignora l'eccedenza; controllare `--bgp-peers` e i limiti di quota) o non contenuto nell'allowed prefixes del DXGW.

### Flapping e route dampening

**Sintomo:** sessione o singoli prefissi che oscillano; log con `Down BGP Notification Hold Timer Expired` o continui UPDATE/WITHDRAW.

```bash
vtysh -c "show bgp neighbors 192.0.2.2" | grep -E "Hold|Keepalive|Last reset|flap"
vtysh -c "show ip bgp dampening flap-statistics"
journalctl -u frr | grep -i "bgp.*down"
```

**Cause:** link instabile (abilitare BFD e verificare errori con `ethtool -S`), CPU del router satura che perde i keepalive, hold-time troppo aggressivo, MTU/PMTUD che blocca UPDATE grossi. **Route dampening** (`bgp dampening 15 750 2000 60`) penalizza i prefissi instabili ma è sconsigliata su Internet moderna (RFC 7196): può sopprimere prefissi legittimi. Meglio correggere la causa.

### Hijack, route leak e validazione RPKI

**Sintomo:** traffico verso un proprio prefisso instradato in un altro AS, o improvvisa latenza/perdita dopo un annuncio di un terzo.

```bash
# Stato di validazione del prefisso (con RTR configurato)
vtysh -c "show rpki prefix-table"
vtysh -c "show ip bgp 203.0.113.0/24"      # cerca "validation-state: invalid"

# Verifica ROA e visibilità esterna
whois -h whois.bgpmon.net 203.0.113.0/24
```

**Azioni:** creare/aggiornare le **ROA** nel portale del RIR (con `maxLength` corretto), attivare ROV (in FRR: blocco `rpki` con cache RTR + route-map con `match rpki invalid` → `deny`), contattare l'operatore che ha annunciato il prefisso e l'upstream per filtrare. Per i leak: prefix-list per cliente derivate da IRR (`bgpq4`), `maximum-prefix`, e le communities di **peer lock**/**only-to-customer (OTC, RFC 9234)**.

### Kubernetes: peer BGP giù o Service non raggiungibile

**Sintomo:** `cilium bgp peers` mostra `active`/`idle`, oppure il LoadBalancer IP non risponde.

```bash
cilium bgp peers
kubectl -n kube-system logs ds/cilium | grep -i bgp
sudo calicoctl node status               # Calico: cercare "Established"
kubectl -n metallb-system logs deploy/controller
kubectl -n metallb-system logs ds/speaker | grep -i bgp
```

**Cause:** label del `nodeSelector` non presente sul nodo, ASN/IP del ToR errati, firewall del nodo che blocca la 179, ToR senza `neighbor` per il nuovo nodo (usare **BGP dynamic neighbors**/`listen range` sul ToR), `externalTrafficPolicy: Cluster` che causa hairpin/perdita IP sorgente, `bgp-announce`/`advertise` label non corrispondenti alla `CiliumBGPAdvertisement`.

## Relazioni

??? info "CNI Kubernetes — Approfondimento"
    Cilium e Calico integrano BGP per annunciare Pod CIDR e Service IP senza overlay, ottenendo routing nativo verso il datacenter.

    **Approfondimento completo →** [CNI Kubernetes](../kubernetes/cni.md)

??? info "DDoS e protezione — Approfondimento"
    BGP è anche il meccanismo di mitigazione DDoS: **RTBH** (Remote Triggered Black Hole) e diversione del traffico verso scrubbing center tramite annunci più specifici o communities.

    **Approfondimento completo →** [DDoS Protezione](../sicurezza/ddos-protezione.md)

??? info "VPN IPsec — Approfondimento"
    Le VPN dinamiche (es. AWS Site-to-Site) trasportano sessioni eBGP dentro tunnel IPsec su indirizzi link-local.

    **Approfondimento completo →** [VPN IPsec](../sicurezza/vpn-ipsec.md)

??? info "AWS VPC avanzato — Approfondimento"
    Transit Gateway, Direct Connect Gateway e route propagation usano BGP per scambiare i prefissi tra on-prem e VPC.

    **Approfondimento completo →** [VPC avanzato](../../cloud/aws/networking/vpc-avanzato.md)

??? info "Azure connettività — Approfondimento"
    ExpressRoute e VPN Gateway di Azure usano BGP (ASN Azure 12076 per il peering ExpressRoute).

    **Approfondimento completo →** [Azure connettività](../../cloud/azure/networking/connettivita.md)

## Riferimenti

- [RFC 4271 — BGP-4](https://www.rfc-editor.org/rfc/rfc4271)
- [RFC 8212 — Default eBGP policy](https://www.rfc-editor.org/rfc/rfc8212)
- [RFC 6811 — BGP Prefix Origin Validation](https://www.rfc-editor.org/rfc/rfc6811)
- [RFC 5880 — BFD](https://www.rfc-editor.org/rfc/rfc5880)
- [FRRouting — BGP](https://docs.frrouting.org/en/latest/bgp.html)
- [BIRD 2 User's Guide](https://bird.network.cz/?get_doc&f=bird.html&v=20)
- [AWS Direct Connect — BGP communities e routing policies](https://docs.aws.amazon.com/directconnect/latest/UserGuide/routing-and-bgp.html)
- [Cilium BGP Control Plane](https://docs.cilium.io/en/stable/network/bgp-control-plane/bgp-control-plane/)
- [Calico — Configure BGP peering](https://docs.tigera.io/calico/latest/networking/configuring/bgp)
- [MetalLB — BGP](https://metallb.universe.tf/concepts/bgp/)
