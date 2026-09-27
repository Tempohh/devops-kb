---
title: "Network Troubleshooting — Diagnosi di Rete a Strati"
slug: network-troubleshooting
category: networking
tags: [troubleshooting, dns, tcpdump, mtr, ss, conntrack, mtu, netshoot, debugging]
search_keywords: [network troubleshooting, diagnosi di rete, debug rete, dig, nslookup, dig +trace, ping, mtr, traceroute, ss, netstat, tcpdump, bpf filter, wireshark, pcap, curl timing, curl -w, openssl s_client, conntrack, nf_conntrack table full, mtu, pmtud, pmtud blackhole, mss clamping, icmp fragmentation needed, asymmetric routing, routing asimmetrico, port exhaustion, ephemeral ports, snat exhaustion, kubectl debug, netshoot, ephemeral container, vpc flow logs, reachability analyzer, connection refused, connection timed out, syn-sent, close-wait, time-wait, retransmission, packet loss, latenza, packet capture, metodologia troubleshooting, layered troubleshooting]
parent: networking/fondamentali
related: [networking/fondamentali/dns, networking/fondamentali/tcpip, networking/fondamentali/tls-ssl-basics, networking/fondamentali/nat, networking/fondamentali/ebpf, networking/kubernetes/cni, containers/kubernetes/troubleshooting, cloud/aws/networking/vpc]
official_docs: https://man7.org/linux/man-pages/man8/ss.8.html
status: reviewed
difficulty: intermediate
last_updated: 2026-09-26
last_verified: 2026-09-27
---

# Network Troubleshooting — Diagnosi di Rete a Strati

## Panoramica

Il troubleshooting di rete efficace non è "provare comandi a caso": è una **metodologia a strati** che parte dal basso della catena di dipendenze e sale, escludendo a ogni passo una classe intera di cause. Un'applicazione che "non risponde" può avere quattro problemi molto diversi: il nome non si risolve (DNS), il pacchetto non arriva (L3), la porta non accetta la connessione (L4), o il livello applicativo/cifrato rifiuta l'handshake (TLS/L7). Ogni strato ha un comando che lo isola.

La sequenza consigliata è **DNS → connettività L3 → porta L4 → TLS → L7**. Il vantaggio è che l'errore riportato dal client (`Name or service not known`, `No route to host`, `Connection refused`, `Connection timed out`, `certificate verify failed`, `502`) indica già lo strato colpevole. Il costo del metodo è basso: ogni strato richiede 1-2 comandi.

Quando **non** usare questo approccio: se il problema è intermittente e correlato al carico (perdita pacchetti sporadica, tabella conntrack piena), la diagnosi puntuale non basta e servono metriche continue (node_exporter, VPC Flow Logs) oltre ai comandi qui descritti.

## Concetti Chiave

!!! note "Il sintomo indica lo strato"
    | Errore del client | Strato probabile |
    |---|---|
    | `Could not resolve host`, `NXDOMAIN`, `SERVFAIL` | DNS |
    | `No route to host`, `Network is unreachable` | L3 (routing, ARP, SG/NACL) |
    | `Connection refused` (RST immediato) | L4: host raggiungibile, nessun processo in ascolto (o REJECT firewall) |
    | `Connection timed out` | L3/L4: pacchetti scartati silenziosamente (DROP, SG, routing asimmetrico) |
    | `SSL: certificate verify failed`, `handshake failure` | TLS |
    | `502/503/504`, risposta lenta | L7 / backend / timeout intermedi |

### Refused vs Timeout

La distinzione più utile in assoluto:

- **Refused** → qualcuno ha risposto con `RST`. L'host è vivo e il percorso funziona; la porta è chiusa o un firewall usa `REJECT`.
- **Timeout** → nessuna risposta. Il SYN si è perso: firewall con `DROP`, security group, route mancante, host spento, routing asimmetrico.

### Stati TCP che contano

| Stato (`ss`) | Significato diagnostico |
|---|---|
| `SYN-SENT` accumulati | Il client invia SYN e non riceve SYN-ACK: firewall/route/server down |
| `SYN-RECV` accumulati | Il server riceve SYN ma l'ACK finale non arriva: SYN flood o percorso di ritorno rotto |
| `ESTAB` | Connessione stabilita |
| `CLOSE-WAIT` accumulati | Il peer ha chiuso, **l'applicazione locale non chiama `close()`**: bug applicativo (leak di socket) |
| `TIME-WAIT` numerosi | Normale su client con molte connessioni brevi; problema solo se esaurisce le porte effimere |
| `FIN-WAIT-2` | Attesa del FIN del peer, tipico se il peer è bloccato |

## Architettura / Come Funziona

### Il flusso diagnostico

```
1. DNS      dig / nslookup           → il nome diventa un IP?
2. L3       ping / mtr / ip route    → il pacchetto arriva? dove si perde?
3. L4       ss / nc / curl -v        → la porta accetta connessioni?
4. TLS      openssl s_client         → handshake e certificato ok?
5. L7       curl -w / logs           → la risposta è corretta e veloce?
6. Cattura  tcpdump / Wireshark      → verità assoluta sul filo
```

Regola pratica: **se un passo fallisce, non salire**. Diagnosticare TLS quando il DNS restituisce un IP sbagliato fa perdere tempo.

### Dove osservare

Un pacchetto attraversa: applicazione → socket → netfilter/conntrack → routing → interfaccia → rete → (SG/NACL/firewall) → interfaccia remota → netfilter → socket remoto. Catturare su **entrambi** i lati con `tcpdump` permette di capire dove sparisce: se il SYN esce dal client ma non compare sul server, il problema è nel mezzo; se compare sul server ma non parte il SYN-ACK, è il server (firewall locale, nessun listener, rp_filter).

## Configurazione & Pratica

### 1. DNS — `dig` e `nslookup`

```bash
# Risposta compatta: solo l'IP
dig +short api.example.com

# Risposta completa con TTL, server interrogato e tempo di query
dig api.example.com A

# Interroga un resolver specifico (esclude il resolver locale)
dig @1.1.1.1 api.example.com

# Segue la delegazione dalla root: trova zone mal delegate / glue mancanti
dig +trace api.example.com

# Altri record
dig api.example.com AAAA +short
dig example.com NS +short
dig -x 203.0.113.10 +short          # reverse lookup
```

Output commentato:

```text
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 41022     # NOERROR = ok; NXDOMAIN = non esiste; SERVFAIL = errore del resolver/DNSSEC
;; flags: qr rd ra; QUERY: 1, ANSWER: 1                       # ra = recursion available
;; ANSWER SECTION:
api.example.com.   300  IN  A   203.0.113.10                  # 300 = TTL residuo in secondi
;; Query time: 23 msec                                        # >200 ms: resolver lento o cache miss
;; SERVER: 10.0.0.2#53(10.0.0.2)                              # resolver realmente usato
```

```bash
# Confronta ciò che il resolver di sistema vede con ciò che dice il DNS autoritativo
getent hosts api.example.com        # usa nsswitch (come le applicazioni)
dig @ns1.example.com api.example.com +norecurse

# nslookup (interattivo o one-shot)
nslookup api.example.com 8.8.8.8
```

!!! warning "dig non è ciò che vede l'applicazione"
    `dig` interroga direttamente il DNS e ignora `/etc/hosts`, `nsswitch.conf` e le cache locali (systemd-resolved, nscd). Per riprodurre ciò che vede l'app usare `getent hosts` o `curl -v`. In Kubernetes pesa anche `ndots:5` in `resolv.conf`, che moltiplica le query per nomi non FQDN.

### 2. Connettività L3 — `ping` e `mtr`

```bash
ping -c 4 203.0.113.10
mtr -rwzbc 100 203.0.113.10         # report, wide, AS, IP+nome, 100 cicli
```

Output `mtr` commentato:

```text
HOST: client                      Loss%   Snt   Last   Avg  Best  Wrst StDev
  1. 10.0.0.1                      0.0%   100    0.4   0.5   0.3   1.1   0.1
  2. 192.0.2.1                     0.0%   100    2.1   2.3   1.9   4.0   0.4
  3. 198.51.100.7                 45.0%   100   12.0  13.1  11.8  40.2   4.5   # loss solo QUI...
  4. 203.0.113.9                   0.0%   100   14.2  14.5  13.9  16.0   0.6   # ...ma 0% a valle: ICMP rate-limited, NON è vera perdita
  5. 203.0.113.10                  0.0%   100   14.8  15.0  14.1  17.3   0.7
```

Regola di lettura: **la perdita è reale solo se persiste fino all'ultimo hop**. Una perdita su un hop intermedio seguita da 0% a valle indica solo che quel router limita le risposte ICMP. La latenza che salta a un hop e resta alta nei successivi indica il vero collo di bottiglia (link congestionato, tratta intercontinentale).

```bash
# Le VM cloud spesso bloccano ICMP: verifica con TCP invece
mtr -rwT -P 443 -c 50 api.example.com
traceroute -T -p 443 api.example.com
ip route get 203.0.113.10           # quale interfaccia/gateway userebbe il kernel
ip neigh show                       # ARP/ND: FAILED = host L2 non risponde
```

### 3. Porta L4 — `ss`, `nc`, `curl -v`

```bash
# Sul server: c'è un listener sulla porta?
ss -tlnp | grep ':8080'
# LISTEN 0 4096 0.0.0.0:8080 ... users:(("java",pid=812,fd=41))
# Attenzione: 127.0.0.1:8080 = ascolta solo in locale, irraggiungibile dall'esterno

# Sul client: test rapido della porta
nc -zv -w 3 203.0.113.10 443
curl -v --connect-timeout 5 telnet://203.0.113.10:443

# Riepilogo socket per stato
ss -s
ss -tan state syn-sent               # connessioni bloccate in uscita
ss -tan state close-wait | wc -l     # leak di socket applicativi
ss -tanp state established '( dport = :5432 )'
ss -ti dst 203.0.113.10              # info TCP interne: rtt, cwnd, retrans
```

Output `ss -s` commentato:

```text
Total: 18432
TCP:   17960 (estab 1210, closed 16400, orphaned 12, timewait 16350)   # timewait alto: client con molte connessioni brevi
```

!!! tip "Reset vs drop in un colpo solo"
    `curl -v --connect-timeout 5 https://host:443` restituisce `Connection refused` in millisecondi (RST) oppure attende 5 s e fallisce con `Connection timed out` (DROP). Il tempo di fallimento è già un dato diagnostico.

### 4. TLS — `openssl s_client`

```bash
openssl s_client -connect api.example.com:443 -servername api.example.com </dev/null 2>/dev/null \
  | openssl x509 -noout -subject -issuer -dates -ext subjectAltName

# Mostra catena completa e risultato della verifica
openssl s_client -connect api.example.com:443 -servername api.example.com -showcerts -verify_return_error

# Forza una versione/protocollo o ALPN
openssl s_client -connect api.example.com:443 -tls1_2
openssl s_client -connect api.example.com:443 -alpn h2
```

Da controllare: `Verify return code: 0 (ok)`, date `notAfter`, SAN che contiene l'hostname, catena completa (intermediate mancanti sono la causa più comune di `unable to get local issuer certificate`). **`-servername` è obbligatorio** per SNI: senza, un server multi-host restituisce il certificato di default.

### 5. L7 e timing — `curl -w`

```bash
curl -o /dev/null -s -w '\
dns:        %{time_namelookup}s\n\
connect:    %{time_connect}s\n\
tls:        %{time_appconnect}s\n\
ttfb:       %{time_starttransfer}s\n\
total:      %{time_total}s\n\
http_code:  %{http_code}\n\
remote_ip:  %{remote_ip}\n' https://api.example.com/health
```

```text
dns:        0.512s      # lento: resolver o ndots; atteso <50 ms
connect:    0.530s      # connect - dns = 18 ms di RTT TCP → rete ok
tls:        0.585s      # tls - connect = 55 ms handshake
ttfb:       2.610s      # ttfb - tls = 2 s di elaborazione backend → problema applicativo
total:      2.640s
http_code:  200
```

I tempi sono **cumulativi**: per isolare uno strato si sottrae il valore precedente. Questo distingue in un solo comando rete lenta, TLS lento e backend lento.

### 6. Cattura pacchetti — `tcpdump` e Wireshark

```bash
# Traffico verso un host e porta, senza risolvere i nomi, con timestamp
sudo tcpdump -i any -nn -tttt host 203.0.113.10 and port 443

# SYN senza SYN-ACK: solo pacchetti con flag SYN (senza ACK)
sudo tcpdump -i eth0 -nn 'tcp[tcpflags] & (tcp-syn|tcp-ack) == tcp-syn'

# Solo RST (connessioni rifiutate/abortite)
sudo tcpdump -i eth0 -nn 'tcp[tcpflags] & tcp-rst != 0'

# ICMP frag-needed (PMTUD): type 3 code 4
sudo tcpdump -i eth0 -nn 'icmp[0] == 3 and icmp[1] == 4'

# Salva su file per Wireshark, limitando la dimensione catturata
sudo tcpdump -i eth0 -nn -s 128 -w /tmp/cap.pcap -c 5000 'host 203.0.113.10'
```

Lettura di un handshake fallito:

```text
10:01:02.001 IP 10.0.0.5.51234 > 203.0.113.10.443: Flags [S], seq 100, win 64240, length 0
10:01:03.003 IP 10.0.0.5.51234 > 203.0.113.10.443: Flags [S], seq 100, ...     # retransmit dopo 1 s
10:01:05.007 IP 10.0.0.5.51234 > 203.0.113.10.443: Flags [S], seq 100, ...     # dopo 2 s (backoff esponenziale)
# Nessun [S.] di risposta → SYN scartato: firewall/SG/route. Catturare sul server per capire se il SYN arriva.
```

In Wireshark i filtri equivalenti: `tcp.analysis.retransmission`, `tcp.analysis.lost_segment`, `tcp.flags.reset == 1`, `tcp.analysis.zero_window`, `dns && dns.flags.rcode != 0`. `Statistics → TCP Stream Graphs → Time-Sequence` mostra visivamente stalli e ritrasmissioni.

!!! warning "Cattura in produzione"
    Usare sempre filtri BPF stretti, `-c` o `-G` per limitare durata/dimensione e `-s` per troncare il payload. Un `tcpdump` senza filtro su un host carico può saturare CPU e disco, e il payload può contenere dati sensibili (token, PII). Cancellare i `.pcap` a fine analisi.

### 7. Conntrack — tabella piena

```bash
# Utilizzo attuale vs limite
sysctl net.netfilter.nf_conntrack_count net.netfilter.nf_conntrack_max
conntrack -C                          # numero di entry
conntrack -L -p tcp --state ESTABLISHED | head
conntrack -S                          # statistiche: insert_failed, drop, invalid
conntrack -L | awk '{print $4}' | sort | uniq -c | sort -rn     # distribuzione per stato

# Log del kernel
dmesg -T | grep -i conntrack
# nf_conntrack: nf_conntrack: table full, dropping packet
```

```bash
# Rimedio: alza il limite e abbassa i timeout (persistere in /etc/sysctl.d/)
sudo sysctl -w net.netfilter.nf_conntrack_max=524288
sudo sysctl -w net.netfilter.nf_conntrack_tcp_timeout_established=3600
sudo sysctl -w net.netfilter.nf_conntrack_tcp_timeout_time_wait=30
# Hash size ~ max/4
echo 131072 | sudo tee /sys/module/nf_conntrack/parameters/hashsize
```

Sintomo tipico: timeout **intermittenti** su nuove connessioni mentre quelle esistenti funzionano, picco di `insert_failed`/`drop` in `conntrack -S`. Il default (spesso 65536-262144) è insufficiente su nodi Kubernetes con molti Service.

### 8. MTU e PMTUD blackhole

Sintomo classico: **handshake TCP e richieste piccole funzionano, i trasferimenti grandi si bloccano** (es. il TLS `ServerHello` con catena grande non arriva, `git push`, upload, VPN/tunnel).

```bash
# Test: pacchetto di dimensione crescente con Don't Fragment
# payload 1472 + 28 byte header = 1500
ping -M do -s 1472 203.0.113.10       # Linux
ping -f -l 1472 203.0.113.10          # Windows

# Se 1472 fallisce e 1372 passa, il path MTU è < 1500
ping -M do -s 1372 203.0.113.10
# "Frag needed and DF set (mtu = 1400)" → il router segnala correttamente l'MTU
# Nessuna risposta sopra la soglia → ICMP frag-needed bloccato = PMTUD blackhole

tracepath -n 203.0.113.10             # scopre il PMTU hop per hop
ip link show eth0 | grep mtu
```

Rimedi:

```bash
# 1. MSS clamping su router/gateway/nodo che fa da tunnel
sudo iptables -t mangle -A FORWARD -p tcp --tcp-flags SYN,RST SYN \
  -j TCPMSS --clamp-mss-to-pmtu

# 2. Abbassare l'MTU dell'interfaccia/overlay
sudo ip link set dev eth0 mtu 1400
```

Nota: overlay (VXLAN, WireGuard, IPsec, GRE) sottraggono 50-80 byte all'MTU. Il CNI deve essere configurato con MTU coerente (es. Calico `mtu: 1440` su VXLAN). Il fix corretto è **non bloccare ICMP tipo 3 code 4** nei firewall/security group.

### 9. Routing asimmetrico

Il pacchetto di andata passa per un percorso, il ritorno per un altro (o un altro firewall stateful): il firewall che vede solo metà della connessione la scarta come `INVALID`. Sintomo: SYN visibile sul server, SYN-ACK inviato, ma il client non lo riceve o il flusso si interrompe.

```bash
# Quale percorso userebbe la risposta?
ip route get 10.0.0.5 from 203.0.113.10 iif eth0
ip rule show; ip route show table all
# Reverse-path filtering: scarta pacchetti con sorgente non raggiungibile dall'interfaccia di ingresso
sysctl net.ipv4.conf.all.rp_filter        # 1=strict, 2=loose
nstat -az | grep -i IPReversePathFilter   # contatore drop rp_filter
```

Su host multi-homed (due NIC) usare policy routing (`ip rule`) o impostare `rp_filter=2`.

### 10. Port exhaustion e SNAT

Un client (o un NAT gateway) può avere al massimo ~28.000 porte effimere (`net.ipv4.ip_local_port_range` = 32768-60999) **per tupla (IP sorgente, IP dest, porta dest)**. Molte connessioni brevi verso lo stesso backend riempiono `TIME-WAIT` e finiscono le porte.

```bash
sysctl net.ipv4.ip_local_port_range
ss -tan state time-wait dst 203.0.113.10:443 | wc -l   # vicino a ~28k = esaurimento
# Errore applicativo: "Cannot assign requested address" (EADDRNOTAVAIL)

# Rimedi
sudo sysctl -w net.ipv4.ip_local_port_range="1024 65000"
sudo sysctl -w net.ipv4.tcp_tw_reuse=1        # riuso TIME-WAIT per connessioni in uscita
# Soluzione vera: connection pooling / keep-alive nell'applicazione
```

Con SNAT (NAT Gateway, `iptables MASQUERADE`) il limite si applica per IP pubblico di uscita: un AWS NAT Gateway supporta ~55.000 connessioni simultanee per destinazione (per IP), e la metrica CloudWatch `ErrorPortAllocation` segnala l'esaurimento. Vedi [NAT](nat.md).

### 11. Kubernetes — `kubectl debug` e netshoot

Le immagini applicative sono spesso distroless e prive di `curl`, `dig`, `tcpdump`. Si usa un **ephemeral container** che condivide il network namespace del Pod.

```bash
# Aggiunge un container di debug al Pod esistente (stesso netns, non riavvia il Pod)
kubectl debug -it pod/api-7d9f8 --image=nicolaka/netshoot --target=api -- bash

# Dentro netshoot: tutti gli strumenti nello stesso netns dell'app
dig +short kubernetes.default.svc.cluster.local
curl -sv http://backend.prod.svc:8080/health
ss -tanp
tcpdump -i eth0 -nn -w /tmp/cap.pcap port 8080     # cattura del traffico del Pod
# Copia il pcap in locale (da un altro terminale)
kubectl cp api-7d9f8:/tmp/cap.pcap ./cap.pcap -c debugger-xxxxx

# Debug del nodo (netns dell'host, filesystem su /host)
kubectl debug node/ip-10-0-1-23 -it --image=nicolaka/netshoot

# Pod temporaneo autonomo per testare Service/DNS dal cluster
kubectl run tmp-shell --rm -it --image=nicolaka/netshoot -- bash
```

Checklist Kubernetes a strati:

```bash
kubectl get endpoints backend -n prod          # vuoto = selector sbagliato o Pod non Ready
kubectl get pods -n kube-system -l k8s-app=kube-dns
kubectl exec -it deploy/api -- cat /etc/resolv.conf     # ndots:5, nameserver = ClusterIP di CoreDNS
kubectl get networkpolicy -A                   # una policy può causare timeout (DROP)
kubectl logs -n kube-system -l k8s-app=kube-dns --tail=50
```

Vedi anche [CNI](../kubernetes/cni.md) e [Troubleshooting Kubernetes](../../containers/kubernetes/troubleshooting.md).

!!! note "Ephemeral container e restrizioni"
    `kubectl debug --target` richiede che il runtime supporti il process namespace sharing; con Pod Security `restricted` l'ephemeral container può richiedere `securityContext` esplicito, e per `tcpdump` servono le capability `NET_RAW`/`NET_ADMIN` (`--profile=netadmin` nelle versioni recenti di kubectl).

### 12. Cloud — VPC Flow Logs e Reachability Analyzer

Quando il problema è nel piano di rete del cloud (SG, NACL, route table) i comandi sull'host non bastano.

```bash
# AWS Reachability Analyzer: analisi statica del path senza inviare traffico
aws ec2 create-network-insights-path \
  --source i-0abc123 --destination i-0def456 \
  --protocol tcp --destination-port 443
aws ec2 start-network-insights-analysis --network-insights-path-id nip-0123456789
aws ec2 describe-network-insights-analyses --network-insights-analysis-ids nia-0123 \
  --query 'NetworkInsightsAnalyses[0].{ok:NetworkPathFound,expl:Explanations[0].ExplanationCode}'
# ExplanationCode es.: ENI_SG_RULES_MISMATCH, NO_ROUTE_TO_DESTINATION, ...
```

```text
# Riga VPC Flow Log (formato default v2):
# version account eni srcaddr dstaddr srcport dstport protocol packets bytes start end action log-status
2 123456789012 eni-0a1 10.0.1.5 10.0.2.9 51234 5432 6 4 240 1726000000 1726000060 REJECT OK
# REJECT su ingresso = SG o NACL. Se l'andata è ACCEPT ma il ritorno è REJECT → NACL stateless
# (le NACL sono stateless: servono regole anche per le porte effimere 1024-65535 in ritorno).
```

Interrogazione con CloudWatch Logs Insights:

```bash
# filtro per REJECT verso la porta del servizio
fields @timestamp, srcAddr, dstAddr, dstPort, action
| filter dstPort = 5432 and action = "REJECT"
| stats count() by srcAddr
| sort count desc
```

I Flow Logs mostrano **solo** ACCEPT/REJECT a livello di ENI, non il perché a livello applicativo, e non catturano DNS verso il resolver VPC (`169.254.169.253`/VPC+2), traffico metadata e DHCP. Vedi [VPC](../../cloud/aws/networking/vpc.md).

## Tabella Sintomo → Causa → Comando

| Sintomo | Causa probabile | Comando di verifica |
|---|---|---|
| `Could not resolve host` | Resolver irraggiungibile, record mancante, `ndots` | `dig +short host`, `dig @8.8.8.8 host`, `cat /etc/resolv.conf` |
| DNS lento a intermittenza | Cache miss, UDP perso, conntrack race su UDP 53 | `dig host` (Query time), `conntrack -S`, `tcpdump port 53` |
| `Connection refused` | Nessun listener o REJECT | `ss -tlnp \| grep :PORT`, `nc -zv host port` |
| `Connection timed out` | DROP (SG/NACL/firewall), route mancante | `mtr -T -P port host`, `tcpdump 'tcp[tcpflags]&tcp-syn!=0'` su entrambi i lati |
| Molti `SYN-SENT` | Server irraggiungibile/filtrato | `ss -tan state syn-sent` |
| Molti `CLOSE-WAIT` | Leak socket nell'app | `ss -tanp state close-wait`, heap/thread dump app |
| Piccole richieste ok, grandi si bloccano | MTU/PMTUD blackhole | `ping -M do -s 1472`, `tracepath`, MSS clamping |
| Timeout intermittenti su nuove connessioni | `nf_conntrack: table full` | `conntrack -C`, `dmesg \| grep conntrack` |
| `Cannot assign requested address` | Port exhaustion / SNAT | `ss -tan state time-wait \| wc -l`, `ErrorPortAllocation` |
| SYN-ACK inviato, client non lo vede | Routing asimmetrico, rp_filter | `ip route get`, `sysctl rp_filter`, `tcpdump` su entrambi |
| `certificate verify failed` | Catena incompleta, CA non fidata, SAN errato, scaduto | `openssl s_client -showcerts -servername` |
| TTFB alto, connect basso | Backend lento | `curl -w` (`time_starttransfer`) |
| Pod raggiunge Service A ma non B | NetworkPolicy, endpoints vuoti | `kubectl get endpoints`, `kubectl get netpol` |
| Solo cross-AZ/VPC fallisce | Route/peering/NACL/SG | Reachability Analyzer, Flow Logs |

## Best Practices

- **Procedere per strati** e annotare cosa è stato escluso: evita di ripetere test.
- **Riprodurre dal punto di vista del client reale** (stesso Pod, stessa subnet, stesso resolver): un test dal laptop non prova nulla su un Pod in un'altra VPC.
- **Catturare su entrambi i lati** con lo stesso filtro e confrontare i timestamp: è l'unico modo per stabilire dove sparisce il pacchetto.
- **Preferire TCP a ICMP** per testare raggiungibilità in cloud (`mtr -T`, `nc -z`): ICMP è spesso filtrato senza che l'applicazione ne risenta.
- **Non bloccare ICMP tipo 3 code 4** (frag-needed) e tipo 11: rompe PMTUD e `traceroute`.
- **Monitorare in modo proattivo** conntrack (`nf_conntrack_count/max`), stati TCP e `ErrorPortAllocation` invece di scoprirli in incidente.
- **Preparare un toolkit** (immagine netshoot approvata, runbook con i comandi) prima dell'incidente.
- **Anti-pattern**: riavviare il servizio "per vedere se passa" senza prima raccogliere `ss`, log e cattura: si perde l'evidenza.

!!! tip "Raccogli prima di riavviare"
    Prima di qualsiasi restart salva `ss -tanp`, `conntrack -S`, `dmesg -T | tail -100` e una breve `tcpdump`. Il riavvio azzera gli stati che permettono la diagnosi post-mortem.

## Troubleshooting

### Scenario 1: `Connection timed out` solo da alcune subnet

**Sintomo**: `curl: (28) Connection timed out after 5001 milliseconds` da una subnet, ok da un'altra.
**Causa**: security group o NACL che non include il CIDR sorgente, oppure route table della subnet priva della rotta di ritorno.
**Soluzione**:
```bash
# Sul server, cattura SYN dalla subnet problematica
sudo tcpdump -i any -nn 'src net 10.1.0.0/24 and tcp[tcpflags]&tcp-syn!=0'
# Nessun pacchetto → il blocco è a monte (SG/NACL/route): eseguire Reachability Analyzer
# Pacchetti visibili ma senza SYN-ACK → firewall locale o rp_filter: iptables -S, nft list ruleset
```

### Scenario 2: Upload/download grandi bloccati, richieste piccole ok

**Sintomo**: `curl` a un endpoint HTTPS si blocca dopo `Client hello`, oppure `git push` si appende.
**Causa**: MTU del path inferiore a 1500 (tunnel/overlay) con ICMP frag-needed filtrato → PMTUD blackhole.
**Soluzione**:
```bash
ping -M do -s 1472 host      # fallisce
ping -M do -s 1372 host      # passa
sudo iptables -t mangle -A FORWARD -p tcp --tcp-flags SYN,RST SYN -j TCPMSS --clamp-mss-to-pmtu
```

### Scenario 3: Timeout casuali su un nodo Kubernetes molto carico

**Sintomo**: richieste che a volte falliscono con timeout; `dmesg` riporta `nf_conntrack: table full, dropping packet`.
**Causa**: `nf_conntrack_max` troppo basso per il numero di connessioni del nodo.
**Soluzione**:
```bash
conntrack -C; sysctl net.netfilter.nf_conntrack_max
sudo sysctl -w net.netfilter.nf_conntrack_max=1048576
# In Kubernetes: kube-proxy --conntrack-max-per-core / ConfigMap kube-proxy; considerare eBPF (Cilium) senza conntrack
```

### Scenario 4: `Cannot assign requested address` verso un servizio esterno

**Sintomo**: errori `EADDRNOTAVAIL` sotto carico; migliaia di socket `TIME-WAIT` verso la stessa destinazione.
**Causa**: esaurimento porte effimere (o porte SNAT del NAT Gateway) per la stessa tupla di destinazione.
**Soluzione**:
```bash
ss -tan state time-wait dst 203.0.113.10:443 | wc -l
sudo sysctl -w net.ipv4.ip_local_port_range="1024 65000"
# Definitiva: HTTP keep-alive / connection pool; più IP di uscita (secondary IP su NAT GW)
```

### Scenario 5: Molti `CLOSE-WAIT` che crescono nel tempo

**Sintomo**: `ss -s` mostra migliaia di socket `CLOSE-WAIT`, poi `Too many open files`.
**Causa**: il peer ha chiuso la connessione ma l'applicazione locale non chiama `close()` (leak di connessioni HTTP/DB).
**Soluzione**:
```bash
ss -tanp state close-wait | awk '{print $NF}' | sort | uniq -c | sort -rn | head
ls /proc/<pid>/fd | wc -l ; cat /proc/<pid>/limits | grep 'open files'
# Fix nel codice: chiudere response body/connessioni (try-with-resources, defer resp.Body.Close())
```

## Relazioni

??? info "DNS — Approfondimento"
    Il primo strato da escludere. Comprendere record, TTL, delegazione e `ndots` spiega la maggior parte dei problemi di risoluzione.

    **Approfondimento completo →** [DNS](dns.md)

??? info "TCP/IP — Approfondimento"
    Handshake a tre vie, stati TCP, MTU/MSS e ICMP sono la base per leggere `ss` e `tcpdump`.

    **Approfondimento completo →** [TCP/IP](tcpip.md)

??? info "TLS/SSL — Approfondimento"
    Catena di certificati, SNI e versioni: ciò che `openssl s_client` mostra.

    **Approfondimento completo →** [TLS/SSL Basics](tls-ssl-basics.md)

??? info "NAT — Approfondimento"
    Conntrack e SNAT sono all'origine di tabelle piene e port exhaustion.

    **Approfondimento completo →** [NAT](nat.md)

??? info "eBPF — Approfondimento"
    Strumenti come `bpftrace`, Cilium Hubble e Pixie offrono osservabilità di rete senza cattura completa.

    **Approfondimento completo →** [eBPF](ebpf.md)

## Riferimenti

- [ss(8) — man page](https://man7.org/linux/man-pages/man8/ss.8.html)
- [tcpdump — pcap-filter (sintassi BPF)](https://www.tcpdump.org/manpages/pcap-filter.7.html)
- [mtr — documentazione](https://github.com/traviscross/mtr)
- [nicolaka/netshoot](https://github.com/nicolaka/netshoot)
- [Kubernetes — Debug Running Pods (ephemeral containers)](https://kubernetes.io/docs/tasks/debug/debug-application/debug-running-pod/)
- [AWS Reachability Analyzer](https://docs.aws.amazon.com/vpc/latest/reachability/what-is-reachability-analyzer.html)
- [AWS VPC Flow Logs](https://docs.aws.amazon.com/vpc/latest/userguide/flow-logs.html)
- [RFC 1191 — Path MTU Discovery](https://www.rfc-editor.org/rfc/rfc1191)
