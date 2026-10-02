---
title: "Synthetic Monitoring"
slug: synthetic-monitoring
category: monitoring
tags: [synthetic-monitoring, blackbox, prometheus, uptime, observability, probing]
search_keywords: [synthetic monitoring, monitoraggio sintetico, black-box monitoring, blackbox exporter, uptime monitoring, uptime check, probe esterno, health check esterno, Checkly, Grafana Synthetic Monitoring, Playwright scheduled check, canary check, DNS monitoring, TLS certificate expiry, ICMP probe, HTTP probe, TCP probe, active monitoring, outside-in monitoring, Pingdom, UptimeRobot, Datadog Synthetics]
parent: monitoring/tools/_index
related: [monitoring/tools/prometheus, monitoring/alerting/alertmanager, monitoring/alerting/prometheus-rules, ci-cd/strategie/deployment-strategies, monitoring/sre/slo-sla-sli]
official_docs: https://github.com/prometheus/blackbox_exporter
status: complete
difficulty: intermediate
last_updated: 2026-10-02
---

# Synthetic Monitoring

## Panoramica

Il **synthetic monitoring** (o **black-box monitoring**) simula richieste reali verso un sistema dall'esterno — HTTP GET su un endpoint pubblico, handshake TCP, risoluzione DNS, ping ICMP — e misura disponibilità, latenza e correttezza della risposta. A differenza del monitoring tradizionale (metriche, log, tracce), che è **white-box** e osserva cosa succede *dentro* l'applicazione, il synthetic monitoring osserva il sistema **da fuori**, esattamente come lo vedrebbe un utente reale.

Serve perché white-box monitoring non copre tutto: un load balancer mal configurato, una zona DNS rotta, un certificato TLS scaduto, una CDN che restituisce errori, un firewall che blocca una porta — nessuno di questi problemi genera metriche applicative anomale, perché l'applicazione stessa è sana. Se nessun probe arriva dall'esterno, nessuno se ne accorge finché non arriva una segnalazione utente.

Si usa per: uptime check su endpoint pubblici, validazione di scadenza certificati TLS, verifica raggiungibilità multi-regione, test end-to-end di flussi critici (login, checkout). Non sostituisce metriche/log/tracce: li completa, coprendo il perimetro esterno del sistema che l'instrumentazione interna non può vedere.

## Concetti Chiave

!!! note "White-box vs Black-box Monitoring"
    - **White-box**: richiede instrumentazione del codice o accesso interno al sistema (metriche Prometheus, log applicativi, tracce OpenTelemetry). Risponde a "perché è lento?".
    - **Black-box**: nessun accesso interno richiesto, simula un client esterno (probe HTTP/TCP/DNS/ICMP). Risponde a "è raggiungibile e funziona dal punto di vista dell'utente?".

    I due approcci sono complementari: un alert black-box dice *che* qualcosa è rotto esternamente, i segnali white-box dicono *perché*.

### Tipologie di probe

| Tipo | Cosa verifica | Esempio di uso |
|---|---|---|
| **HTTP/HTTPS** | Status code, corpo risposta, redirect, tempo di risposta | Endpoint API pubblico, pagina di login |
| **TCP connect** | Apertura connessione su porta | Database raggiungibile da rete esterna, SMTP |
| **DNS** | Risoluzione corretta di un nome, tempo di lookup | Validare che una zona DNS risponda come atteso |
| **ICMP (ping)** | Raggiungibilità di rete a livello IP | Host raggiungibile, perdita pacchetti |
| **TLS/Certificati** | Validità e scadenza del certificato | Allerta su certificati in scadenza entro N giorni |
| **Scripted / multi-step** | Sequenze di azioni (login → naviga → checkout) | Flussi critici che un singolo GET non copre |

### Single-probe vs Scripted synthetic

Un probe singolo (HTTP GET su `/health`) copre la raggiungibilità di base. Non basta per flussi che richiedono stato (login, carrello, pagamento multi-step): per questi servono script che replicano l'interazione utente, tipicamente con un browser headless (Playwright, Puppeteer) eseguito su scheduling.

## Architettura / Come Funziona

Il pattern più diffuso nell'ecosistema Prometheus è il **Blackbox Exporter**: non misura nulla da solo, ma su richiesta esegue un probe verso un target e restituisce il risultato come metriche Prometheus. Prometheus quindi "scrapea" l'exporter, che a sua volta esegue il probe verso il target reale — il target del probe non è l'exporter stesso.

```
┌─────────────┐   scrape /probe?target=X   ┌──────────────────┐   HTTP/TCP/DNS/ICMP   ┌─────────────┐
│  Prometheus │ ─────────────────────────▶ │ Blackbox Exporter │ ────────────────────▶ │   Target    │
│             │ ◀───────────────────────── │   (porta 9115)    │ ◀──────────────────── │  (esterno)  │
└─────────────┘      metriche probe_*      └──────────────────┘      risposta probe    └─────────────┘
```

Il pattern di configurazione in Prometheus è noto come **"probe as a target"**: il job non scrapea direttamente l'endpoint da monitorare, ma passa l'endpoint come parametro `target` all'exporter, e usa `relabel_configs` per riscrivere l'indirizzo effettivo dello scrape verso l'exporter stesso.

Per scenari multi-step o con necessità di eseguire probe da più regioni geografiche distinte, si usano piattaforme SaaS dedicate (Grafana Cloud Synthetic Monitoring, Checkly, Datadog Synthetics) o script Playwright schedulati via cron/CI, che pubblicano a loro volta metriche compatibili con Prometheus/OpenTelemetry.

## Configurazione & Pratica

### Blackbox Exporter — configurazione moduli

```yaml
# blackbox.yml
modules:
  http_2xx:
    prober: http
    timeout: 5s
    http:
      valid_http_versions: ["HTTP/1.1", "HTTP/2.0"]
      valid_status_codes: [200, 201, 202]  # vuoto = default 2xx
      method: GET
      fail_if_ssl: false
      fail_if_not_ssl: true          # forza HTTPS
      tls_config:
        insecure_skip_verify: false  # non disabilitare in produzione

  http_post_2xx:
    prober: http
    http:
      method: POST
      headers:
        Content-Type: application/json
      body: '{"check":"synthetic"}'

  tcp_connect:
    prober: tcp
    timeout: 5s

  dns_resolve:
    prober: dns
    dns:
      query_name: "example.com"
      query_type: "A"
      valid_rcodes: ["NOERROR"]

  icmp_ping:
    prober: icmp
    timeout: 5s
    icmp:
      preferred_ip_protocol: "ip4"
```

### Prometheus — pattern "probe as a target"

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'blackbox-http'
    metrics_path: /probe
    params:
      module: [http_2xx]
    static_configs:
      - targets:
          - https://api.example.com/health
          - https://www.example.com
    relabel_configs:
      - source_labels: [__address__]
        target_label: __param_target      # il target reale diventa parametro
      - source_labels: [__param_target]
        target_label: instance             # label leggibile nelle metriche/alert
      - target_label: __address__
        replacement: blackbox-exporter:9115 # lo scrape va sempre verso l'exporter
```

Metriche principali esposte da `/probe`:

- `probe_success` (1/0) — esito del probe
- `probe_duration_seconds` — tempo totale del probe
- `probe_http_status_code` — status code ricevuto
- `probe_ssl_earliest_cert_expiry` — timestamp Unix di scadenza del certificato TLS più vicino

### Alerting rule — endpoint down e certificato in scadenza

```yaml
# prometheus-rules.yml
groups:
  - name: synthetic-monitoring
    rules:
      - alert: EndpointDown
        expr: probe_success == 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Endpoint {{ $labels.instance }} non raggiungibile"
          description: "Probe fallito da oltre 5 minuti su {{ $labels.instance }}."

      - alert: TLSCertExpiringSoon
        expr: (probe_ssl_earliest_cert_expiry - time()) / 86400 < 14
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "Certificato TLS di {{ $labels.instance }} in scadenza"
          description: "Scade tra meno di 14 giorni."

      - alert: ProbeLatencyHigh
        expr: probe_duration_seconds > 2
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Probe lento su {{ $labels.instance }}"
```

### Alternative SaaS per scenari multi-step

Quando serve testare un flusso completo (login → aggiungi al carrello → checkout), un singolo probe HTTP non basta:

- **Grafana Cloud Synthetic Monitoring**: probe multi-regione gestiti, integrazione nativa con Grafana, supporta script browser-based.
- **Checkly**: check basati su script Playwright/Puppeteer, scheduling multi-regione, alerting integrato.
- **Script Playwright schedulato**: soluzione self-hosted via cron o pipeline CI, pubblica metriche custom (es. via Pushgateway o OTel) verso lo stack esistente.

```javascript
// checkly-style script: login + verifica elemento post-login
const { chromium } = require("playwright");

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto("https://app.example.com/login");
  await page.fill("#email", process.env.SYNTH_USER);
  await page.fill("#password", process.env.SYNTH_PASS);
  await page.click("button[type=submit]");
  await page.waitForSelector("#dashboard-welcome", { timeout: 10000 });
  await browser.close();
})();
```

## Best Practices

!!! warning "Falsi positivi da probe in singola regione"
    Un probe eseguito da un'unica location può fallire per problemi di rete locali al probe stesso (routing, firewall, provider cloud), non del target. Configurare l'alerting in modo che richieda il fallimento di **più region/probe indipendenti** prima di notificare (es. 3 su 3, o quorum), riducendo drasticamente il rumore.

!!! tip "Soglie diverse da alert interni"
    Gli alert interni (metriche applicative) possono permettersi soglie più aggressive perché il contesto è noto. Gli alert synthetic devono tollerare maggiore varianza di rete: usare `for:` più lunghi (5-10m) e richiedere conferma da probe multipli prima di alertare, per non generare pagine inutili a ogni blip di rete.

!!! tip "Separare canary deployment check da synthetic monitoring continuo"
    I check di canary (Flagger, Argo Rollouts) verificano la salute di una nuova release **durante un rollout**, con metriche a breve termine e rollback automatico. Il synthetic monitoring gira **sempre, in produzione**, indipendentemente da eventuali deploy in corso: i due meccanismi sono complementari, non sostituibili l'uno con l'altro.

!!! warning "Non esporre credenziali nei probe multi-step"
    Script di login sintetici richiedono credenziali dedicate (utente "synthetic" con permessi minimi, mai un account reale). Ruotare periodicamente le credenziali e non loggare mai payload di richiesta/risposta che le contengano.

## Troubleshooting

| Sintomo | Causa probabile | Soluzione |
|---|---|---|
| `probe_success == 0` ma il sito è raggiungibile da browser | Probe da regione/rete con problemi propri (firewall, routing, DNS locale al probe) | Verificare lo stesso probe da un'altra region; richiedere quorum multi-region prima di alertare |
| Probe HTTPS fallisce con errore certificato, ma il browser non mostra warning | Blackbox Exporter non ha la CA custom nel trust store, o `insecure_skip_verify` disattivato su certificati self-signed interni | Montare la CA interna nel container dell'exporter o usare un modulo dedicato con `tls_config.ca_file` |
| `probe_duration_seconds` alto ma l'app non è lenta internamente | Exporter sotto carico, troppi probe concorrenti sulla stessa istanza | Scalare orizzontalmente il Blackbox Exporter o aumentare `scrape_interval` per target non critici |
| Alert di scadenza certificato non scatta mai | Modulo configurato con `fail_if_not_ssl: false` o target non valida correttamente la catena | Verificare `probe_ssl_earliest_cert_expiry` con query diretta su Prometheus; controllare che il modulo HTTPS sia quello effettivamente usato dal job |
| Script Playwright sintetico fallisce in CI ma funziona in locale | Timeout troppo stretti, differenze di rendering headless, selettori instabili | Aumentare timeout di `waitForSelector`, usare selettori basati su `data-testid` invece di classi CSS fragili |

## Relazioni

??? info "Prometheus — Scraping del Blackbox Exporter"
    Il Blackbox Exporter è uno dei tanti exporter che Prometheus scrapea; il pattern "probe as a target" con `relabel_configs` è lo stesso usato per altri exporter dinamici.

    **Approfondimento completo →** [Prometheus](./prometheus.md)

??? info "Alertmanager — Instradamento degli Alert Synthetic"
    Gli alert generati dalle regole su `probe_success` e scadenza certificati vanno instradati con routing e raggruppamento dedicati, per evitare di mischiarli con alert applicativi a priorità diversa.

    **Approfondimento completo →** [Alertmanager](../alerting/alertmanager.md)

??? info "Prometheus Rules — Scrittura delle Regole di Alerting"
    Le regole di alerting mostrate sopra (`EndpointDown`, `TLSCertExpiringSoon`) seguono le stesse convenzioni di sintassi e best practice delle altre recording/alerting rules Prometheus.

    **Approfondimento completo →** [Prometheus Rules](../alerting/prometheus-rules.md)

??? info "Deployment Strategies — Canary Check vs Synthetic Monitoring"
    I check di canary durante un rollout (Flagger, Argo Rollouts) sono un meccanismo distinto dal synthetic monitoring continuo: il primo valuta una release in corso, il secondo sorveglia la produzione in modo permanente.

    **Approfondimento completo →** [Deployment Strategies](../../ci-cd/strategie/deployment-strategies.md)

??? info "SLO/SLA/SLI — Uptime come Indicatore"
    Le metriche `probe_success` raccolte nel tempo sono una fonte diretta per calcolare SLI di disponibilità e verificare il rispetto di SLO di uptime concordati.

    **Approfondimento completo →** [SLO/SLA/SLI](../sre/slo-sla-sli.md)

## Riferimenti

- [Blackbox Exporter — Repository ufficiale](https://github.com/prometheus/blackbox_exporter)
- [Blackbox Exporter — Configurazione moduli](https://github.com/prometheus/blackbox_exporter/blob/master/CONFIGURATION.md)
- [Grafana Cloud Synthetic Monitoring](https://grafana.com/docs/grafana-cloud/monitor-applications/synthetic-monitoring/)
- [Checkly Documentation](https://www.checklyhq.com/docs/)
- [Playwright Documentation](https://playwright.dev/docs/intro)
- [Prometheus — Relabel Configs](https://prometheus.io/docs/prometheus/latest/configuration/configuration/#relabel_config)
