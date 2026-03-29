---
title: "TLS/mTLS da Codice — Java, .NET, Go"
slug: tls-da-codice
category: dev
tags: [tls, mtls, java, dotnet, go, certificati, ssl, security, x509, keystor, truststore]
search_keywords: [tls codice applicativo, mtls applicazione, tls java, java ssl, java keystore, java truststore, sslcontext java, sslsocketfactory, java keystoremanager, jks pkcs12, keystore type, truststore java, java httpclient tls, resttemplate tls, webclient tls certificato client, spring boot mtls, spring webclient client certificate, hot reload certificati, certificate rotation no restart, tls dotnet, dotnet ssl, x509certificate2, sslstream dotnet, httpclienthandler clientcertificates, csharp tls, dotnet mtls, dotnet httpclient tls, pem dotnet, tls go, golang tls, tls config golang, x509 cert pool, tls loadx509keypair, tls certificate go, golang mtls, go http tls, go grpc tls, caricamento certificati k8s volume, kubernetes secret certificato, certificato montato volume, debug tls, javax net debug, sslkeylogfile, wireshark tls decrypt, trust bundle applicativo, system trust store, certificati radice sistema, ssl handshake failed, handshake error tls, certificate verification failed, unknown certificate authority, certificate expired debug, mTLS microservizi codice]
parent: dev/sicurezza/_index
related: [security/autenticazione/mtls-spiffe, security/pki-certificati/cert-manager, networking/fondamentali/tls-ssl-basics, dev/linguaggi/java-spring-boot, dev/linguaggi/dotnet, dev/linguaggi/go]
official_docs: https://pkg.go.dev/crypto/tls
status: complete
difficulty: advanced
last_updated: 2026-03-28
---

# TLS/mTLS da Codice — Java, .NET, Go

## Panoramica

TLS (Transport Layer Security) e mTLS (Mutual TLS) sono protocolli che la maggior parte dei team affronta due volte: una volta quando configura l'infrastruttura (cert-manager, Vault, PKI interna), e una volta quando deve **far funzionare il codice applicativo** — ovvero caricare certificati, configurare trust store, presentare un certificato client. Questi due livelli sono concettualmente separati e spesso gestiti da team diversi.

Questo documento copre **esclusivamente la prospettiva del developer**: come configurare TLS nel codice, come caricare un certificato client da file/secret Kubernetes, come validare un certificato server con una CA privata, e come gestire la rotazione dei certificati senza riavviare l'applicazione. Le sezioni sono organizzate per linguaggio (Java, .NET, Go) ed è possibile leggerle indipendentemente.

Quando serve questo documento: implementi mTLS tra microservizi e devi caricare il certificato del servizio nel codice; usi una CA privata e il client HTTP rifiuta la connessione con "unknown certificate authority"; devi ruotare i certificati ogni 24h senza downtime; devi debuggare un handshake TLS fallito.

!!! warning "Separazione di responsabilità"
    L'emissione, il rinnovo e la distribuzione dei certificati è responsabilità dell'infrastruttura (cert-manager, Vault PKI). Il codice applicativo deve **leggere** i certificati da dove l'infrastruttura li mette (file system, secret Kubernetes, Vault API) e configurare le librerie TLS di conseguenza. Non hardcodare mai un certificato nel codice sorgente.

---

## Concetti Chiave

### Terminologia: KeyStore, TrustStore, Trust Bundle

| Concetto | Cosa contiene | Chi lo usa |
|---|---|---|
| **KeyStore** (Java) / **PFX/PKCS12** | Il certificato del servizio + la chiave privata | L'applicazione quando deve **presentarsi** (mTLS client o server) |
| **TrustStore** (Java) / **CA bundle** | I certificati delle CA che considera affidabili | L'applicazione quando deve **verificare** il certificato dell'altro lato |
| **Trust di sistema** | CA bundle del SO (`/etc/ssl/certs/`, Windows Cert Store) | Default per la maggior parte degli HTTP client — non include CA private |
| **Trust bundle applicativo** | CA bundle caricato esplicitamente nel codice | Necessario per CA private o per isolare il trust applicativo da quello del SO |

!!! tip "CA privata vs trust di sistema"
    Se la tua organizzazione usa una CA interna (Vault PKI, cert-manager con Issuer interno), il suo certificato radice **non** è nel trust store di sistema delle immagini container. Devi distribuirlo e configurarlo esplicitamente in ogni applicazione, oppure aggiungerlo all'immagine base.

### Formato dei Certificati

```
PEM (Base64 + header leggibili):
-----BEGIN CERTIFICATE-----
MIIBxTCCAW+gAwIBAgIJAP...
-----END CERTIFICATE-----

DER (binario, equivalente al PEM ma non leggibile):
Usato principalmente su Windows e nei KeyStore Java legacy.

PKCS12 / PFX:
Bundle binario che contiene cert + chiave privata (protetto da password).
Usato su: Windows (.pfx), Java recente (default da Java 9+).

JKS (Java KeyStore):
Formato proprietario Java, legacy. Deprecato da Java 9+ in favore di PKCS12.
Ancora presente in sistemi legacy. Non usare per nuovi progetti.
```

### TLS Standard vs mTLS

```
TLS Standard (HTTPS normale):
  Client → ClientHello
  Server ← ServerHello + Certificate_SERVER
  Client verifica cert server (è in TrustStore?)
  Client ← FinishedHandshake
  ══ Solo il server è autenticato ══

mTLS (Mutual TLS):
  Client → ClientHello
  Server ← ServerHello + Certificate_SERVER + CertificateRequest
  Client → Certificate_CLIENT + CertificateVerify
  Server verifica cert client (è firmato da CA accettata?)
  ══ Entrambi i lati sono autenticati ══
```

---

## Java — KeyStore, TrustStore, SSLContext

### Caricamento KeyStore e TrustStore

```java
import javax.net.ssl.*;
import java.security.KeyStore;
import java.io.FileInputStream;

/**
 * Crea un SSLContext configurato con:
 * - KeyStore: certificato client + chiave privata (mTLS)
 * - TrustStore: CA bundle per verificare il server
 */
public SSLContext buildSSLContext(
    String keyStorePath,    // /certs/client.p12 (da Secret K8s montato)
    String keyStorePass,    // da env var / Vault
    String trustStorePath,  // /certs/ca-bundle.p12
    String trustStorePass
) throws Exception {

    // 1. KeyStore — certificato client (per mTLS)
    KeyStore keyStore = KeyStore.getInstance("PKCS12");
    try (FileInputStream fis = new FileInputStream(keyStorePath)) {
        keyStore.load(fis, keyStorePass.toCharArray());
    }
    KeyManagerFactory kmf = KeyManagerFactory.getInstance(
        KeyManagerFactory.getDefaultAlgorithm() // "SunX509"
    );
    kmf.init(keyStore, keyStorePass.toCharArray());

    // 2. TrustStore — CA per verificare il server
    KeyStore trustStore = KeyStore.getInstance("PKCS12");
    try (FileInputStream fis = new FileInputStream(trustStorePath)) {
        trustStore.load(fis, trustStorePass.toCharArray());
    }
    TrustManagerFactory tmf = TrustManagerFactory.getInstance(
        TrustManagerFactory.getDefaultAlgorithm() // "PKIX"
    );
    tmf.init(trustStore);

    // 3. Composizione SSLContext
    SSLContext sslContext = SSLContext.getInstance("TLS");
    sslContext.init(
        kmf.getKeyManagers(),
        tmf.getTrustManagers(),
        null  // SecureRandom — null usa default JVM
    );
    return sslContext;
}
```

```java
// Solo TrustStore (TLS normale, senza certificato client):
public SSLContext buildTrustOnlySSLContext(String caCertPath) throws Exception {
    // Carica un singolo certificato CA in formato PEM
    CertificateFactory cf = CertificateFactory.getInstance("X.509");
    X509Certificate caCert;
    try (FileInputStream fis = new FileInputStream(caCertPath)) {
        caCert = (X509Certificate) cf.generateCertificate(fis);
    }

    KeyStore trustStore = KeyStore.getInstance(KeyStore.getDefaultType());
    trustStore.load(null); // inizializza truststore vuoto
    trustStore.setCertificateEntry("internal-ca", caCert);

    TrustManagerFactory tmf = TrustManagerFactory.getInstance(
        TrustManagerFactory.getDefaultAlgorithm()
    );
    tmf.init(trustStore);

    SSLContext ctx = SSLContext.getInstance("TLS");
    ctx.init(null, tmf.getTrustManagers(), null);
    return ctx;
}
```

### Spring Boot — WebClient con Certificato Client

```java
// pom.xml: io.projectreactor.netty:reactor-netty-http (transitiva da spring-webflux)

import io.netty.handler.ssl.SslContext;
import io.netty.handler.ssl.SslContextBuilder;
import reactor.netty.http.client.HttpClient;
import org.springframework.web.reactive.function.client.WebClient;

@Configuration
public class WebClientConfig {

    @Value("${tls.cert-path:/certs/client.crt}")
    private String certPath;

    @Value("${tls.key-path:/certs/client.key}")
    private String keyPath;

    @Value("${tls.ca-path:/certs/ca.crt}")
    private String caPath;

    @Bean
    public WebClient secureWebClient() throws SSLException {
        // Netty SslContextBuilder — usa file PEM direttamente
        SslContext sslContext = SslContextBuilder.forClient()
            .keyManager(new File(certPath), new File(keyPath))  // mTLS: cert+key client
            .trustManager(new File(caPath))                     // CA per verificare server
            .build();

        HttpClient httpClient = HttpClient.create()
            .secure(ssl -> ssl.sslContext(sslContext));

        return WebClient.builder()
            .clientConnector(new ReactorClientHttpConnector(httpClient))
            .baseUrl("https://internal-service.svc.cluster.local")
            .build();
    }
}
```

```yaml
# application.yml — percorsi certificati da Secret K8s montato
tls:
  cert-path: /certs/tls.crt   # chiave: tls.crt nel Secret
  key-path: /certs/tls.key    # chiave: tls.key nel Secret
  ca-path: /certs/ca.crt      # chiave: ca.crt nel Secret (o ca.pem)
```

### Spring Boot — RestTemplate (legacy/bloccante)

```java
@Bean
public RestTemplate secureRestTemplate() throws Exception {
    SSLContext sslContext = buildSSLContext(
        certPath, certPassword, trustStorePath, trustStorePassword
    );
    SSLConnectionSocketFactory socketFactory =
        new SSLConnectionSocketFactory(sslContext);
    CloseableHttpClient httpClient = HttpClients.custom()
        .setSSLSocketFactory(socketFactory)
        .build();
    HttpComponentsClientHttpRequestFactory factory =
        new HttpComponentsClientHttpRequestFactory(httpClient);
    return new RestTemplate(factory);
}
```

### Java — Hot Reload Certificati senza Restart

Quando cert-manager emette nuovi certificati, scrive i nuovi file sul file system del pod (tramite Secret montato). L'applicazione deve ricaricarli senza riavviare.

```java
@Component
public class ReloadableSSLContextManager {

    private volatile SSLContext currentContext;
    private final String certPath;
    private final String keyPath;
    private final String caPath;

    public ReloadableSSLContextManager(
        @Value("${tls.cert-path}") String certPath,
        @Value("${tls.key-path}") String keyPath,
        @Value("${tls.ca-path}") String caPath
    ) throws Exception {
        this.certPath = certPath;
        this.keyPath = keyPath;
        this.caPath = caPath;
        this.currentContext = loadContext();
    }

    // Chiamato ogni N minuti dallo scheduler
    @Scheduled(fixedDelayString = "${tls.reload-interval-ms:300000}")
    public void reloadIfChanged() {
        try {
            SSLContext newCtx = loadContext();
            this.currentContext = newCtx; // swap atomico (volatile)
            log.info("SSLContext ricaricato con successo");
        } catch (Exception e) {
            log.warn("Reload SSLContext fallito, uso il precedente: {}", e.getMessage());
            // non propagare — usa il vecchio context
        }
    }

    public SSLContext get() { return currentContext; }

    private SSLContext loadContext() throws Exception {
        // usa buildSSLContext() da PEM file
        return buildSSLContextFromPem(certPath, keyPath, caPath);
    }
}
```

!!! warning "Volatile non basta per oggetti complessi"
    `volatile` garantisce visibilità del riferimento, non dell'oggetto. Il pattern sopra è sicuro perché `SSLContext` è immutabile dopo `init()`: creiamo un nuovo oggetto e lo sostituiamo atomicamente. Non tentare di mutare un `SSLContext` esistente.

---

## .NET — X509Certificate2, SslStream, HttpClient

### Caricamento Certificati da PEM e PFX

```csharp
using System.Security.Cryptography.X509Certificates;
using System.Net.Security;
using System.Net.Http;

// Da PFX (PKCS12) — con password
var cert = new X509Certificate2("/certs/client.pfx", "password");

// Da PEM (cert + key separati) — .NET 5+
var cert = X509Certificate2.CreateFromPemFile(
    certPemFilePath: "/certs/tls.crt",
    keyPemFilePath:  "/certs/tls.key"
);

// Da PEM in memoria (es. letti da env var o Vault)
string certPem = File.ReadAllText("/certs/tls.crt");
string keyPem  = File.ReadAllText("/certs/tls.key");
var cert = X509Certificate2.CreateFromPem(certPem, keyPem);
```

```csharp
// Caricamento CA bundle personalizzato per validare server con CA privata
var caCert = new X509Certificate2("/certs/ca.crt");

// Aggiungi la CA a uno store temporaneo
var customCaStore = new X509Store(StoreName.CertificateAuthority, StoreLocation.LocalMachine);
// ATTENZIONE: modifica lo store permanente del SO — preferire la callback custom
// Alternativa sicura: validazione custom in HttpClientHandler (vedi sotto)
```

### HttpClient con Certificato Client e CA Privata

```csharp
// Configurazione completa: certificato client (mTLS) + CA privata per server
public static HttpClient CreateMtlsClient(
    string clientCertPath,
    string clientKeyPath,
    string caCertPath)
{
    // Certificato client per autenticarsi al server (mTLS)
    var clientCert = X509Certificate2.CreateFromPemFile(clientCertPath, clientKeyPath);

    // CA per validare il certificato del server
    var caCert = new X509Certificate2(caCertPath);

    var handler = new HttpClientHandler();
    handler.ClientCertificates.Add(clientCert);

    // Validazione custom del server cert — evita di modificare il CA store di sistema
    handler.ServerCertificateCustomValidationCallback = (message, cert, chain, errors) =>
    {
        // Costruisci una chain con la CA privata
        var customChain = new X509Chain();
        customChain.ChainPolicy.TrustMode = X509ChainTrustMode.CustomRootTrust;
        customChain.ChainPolicy.CustomTrustStore.Add(caCert);
        customChain.ChainPolicy.RevocationMode = X509RevocationMode.NoCheck;

        bool valid = customChain.Build(new X509Certificate2(cert!));
        if (!valid)
        {
            var errors2 = customChain.ChainStatus
                .Select(s => s.StatusInformation)
                .ToList();
            // log errors2
        }
        return valid;
    };

    return new HttpClient(handler)
    {
        BaseAddress = new Uri("https://internal-service.svc.cluster.local")
    };
}
```

```csharp
// In ASP.NET Core — DI con IHttpClientFactory
// Program.cs
builder.Services.AddHttpClient("internal-service", client =>
{
    client.BaseAddress = new Uri("https://internal-service.svc.cluster.local");
})
.ConfigurePrimaryHttpMessageHandler(() =>
{
    var cert = X509Certificate2.CreateFromPemFile(
        builder.Configuration["Tls:CertPath"]!,
        builder.Configuration["Tls:KeyPath"]!
    );
    var handler = new HttpClientHandler();
    handler.ClientCertificates.Add(cert);
    // ... ServerCertificateCustomValidationCallback
    return handler;
});
```

### SslStream — TLS a Livello Basso

```csharp
// Utile per protocolli custom su TCP (non HTTP)
using var tcpClient = new TcpClient("internal-service", 8443);
using var sslStream = new SslStream(
    tcpClient.GetStream(),
    leaveInnerStreamOpen: false,
    userCertificateValidationCallback: (sender, cert, chain, errors) =>
    {
        // Validazione custom — stesso pattern di sopra
        return errors == SslPolicyErrors.None;
    }
);

var clientCert = X509Certificate2.CreateFromPemFile("/certs/tls.crt", "/certs/tls.key");
await sslStream.AuthenticateAsClientAsync(new SslClientAuthenticationOptions
{
    TargetHost = "internal-service",
    ClientCertificates = new X509CertificateCollection { clientCert },
    EnabledSslProtocols = SslProtocols.Tls13 | SslProtocols.Tls12,
    CertificateRevocationCheckMode = X509RevocationMode.NoCheck
});

// Ora puoi usare sslStream come uno stream normale (Read/Write)
```

### .NET — Hot Reload Certificati

```csharp
// IHttpClientFactory ricrea i handler periodicamente (HandlerLifetime, default 2 min).
// Configura un lifetime adeguato alla frequenza di rotazione.
builder.Services.AddHttpClient("internal-service")
    .SetHandlerLifetime(TimeSpan.FromMinutes(5)) // ricrea il handler ogni 5 min
    .ConfigurePrimaryHttpMessageHandler(() =>
    {
        // Ogni volta che il handler viene ricreato, legge i file aggiornati
        var cert = X509Certificate2.CreateFromPemFile(
            Environment.GetEnvironmentVariable("TLS_CERT_PATH")!,
            Environment.GetEnvironmentVariable("TLS_KEY_PATH")!
        );
        var handler = new HttpClientHandler();
        handler.ClientCertificates.Add(cert);
        return handler;
    });
```

!!! tip "IHttpClientFactory e rotazione"
    `IHttpClientFactory` è il meccanismo raccomandato in .NET per gestire la rotazione dei certificati: il `HandlerLifetime` controlla ogni quanto viene ricreato il `HttpClientHandler` — e ogni ricreazione rilegge i file. Evita di tenere un riferimento diretto a `HttpClient` come singleton se stai ruotando certificati.

---

## Go — tls.Config, x509.CertPool, tls.LoadX509KeyPair

### Configurazione Base TLS Client con CA Privata

```go
package main

import (
    "crypto/tls"
    "crypto/x509"
    "net/http"
    "os"
)

// NewTLSClientWithCustomCA crea un http.Client che verifica il server
// contro una CA privata anziché il system trust store.
func NewTLSClientWithCustomCA(caCertPath string) (*http.Client, error) {
    caPEM, err := os.ReadFile(caCertPath)
    if err != nil {
        return nil, fmt.Errorf("lettura CA cert: %w", err)
    }

    certPool := x509.NewCertPool()
    if !certPool.AppendCertsFromPEM(caPEM) {
        return nil, fmt.Errorf("nessun certificato PEM valido in %s", caCertPath)
    }

    tlsCfg := &tls.Config{
        RootCAs:    certPool,        // sovrascrive il system trust store
        MinVersion: tls.VersionTLS12,
    }

    return &http.Client{
        Transport: &http.Transport{TLSClientConfig: tlsCfg},
    }, nil
}
```

### mTLS — Certificato Client + CA per il Server

```go
// NewMTLSClient configura mTLS completo:
// - certFile/keyFile: certificato del servizio (presentato al server)
// - caCertFile: CA per verificare il certificato del server
func NewMTLSClient(certFile, keyFile, caCertFile string) (*http.Client, error) {
    // 1. Carica il certificato client
    clientCert, err := tls.LoadX509KeyPair(certFile, keyFile)
    if err != nil {
        return nil, fmt.Errorf("caricamento certificato client: %w", err)
    }

    // 2. Carica la CA per verificare il server
    caPEM, err := os.ReadFile(caCertFile)
    if err != nil {
        return nil, fmt.Errorf("lettura CA: %w", err)
    }
    certPool := x509.NewCertPool()
    certPool.AppendCertsFromPEM(caPEM)

    // 3. Composizione tls.Config
    tlsCfg := &tls.Config{
        Certificates: []tls.Certificate{clientCert}, // presentato al server
        RootCAs:      certPool,                       // per verificare il server
        MinVersion:   tls.VersionTLS12,
    }

    return &http.Client{
        Transport: &http.Transport{TLSClientConfig: tlsCfg},
    }, nil
}
```

### Go — Certificati da Volume Kubernetes Montato

Quando cert-manager emette un Secret di tipo `kubernetes.io/tls`, Kubernetes lo monta come:
- `/certs/tls.crt` — certificato del servizio (PEM)
- `/certs/tls.key` — chiave privata (PEM)
- `/certs/ca.crt` — certificato CA (PEM, se incluso nel Secret)

```go
package tlsconfig

import (
    "crypto/tls"
    "crypto/x509"
    "os"
    "time"
    "sync"
    "path/filepath"
)

// WatchedTLSConfig mantiene un tls.Config aggiornato via file watcher.
// Usato quando i certificati vengono ruotati da cert-manager.
type WatchedTLSConfig struct {
    mu      sync.RWMutex
    current *tls.Config
    certsDir string
}

func NewWatched(certsDir string) (*WatchedTLSConfig, error) {
    w := &WatchedTLSConfig{certsDir: certsDir}
    if err := w.reload(); err != nil {
        return nil, err
    }
    go w.watch()
    return w, nil
}

func (w *WatchedTLSConfig) reload() error {
    cert, err := tls.LoadX509KeyPair(
        filepath.Join(w.certsDir, "tls.crt"),
        filepath.Join(w.certsDir, "tls.key"),
    )
    if err != nil {
        return fmt.Errorf("LoadX509KeyPair: %w", err)
    }

    caPEM, err := os.ReadFile(filepath.Join(w.certsDir, "ca.crt"))
    if err != nil {
        return fmt.Errorf("lettura ca.crt: %w", err)
    }
    pool := x509.NewCertPool()
    pool.AppendCertsFromPEM(caPEM)

    cfg := &tls.Config{
        Certificates: []tls.Certificate{cert},
        RootCAs:      pool,
        MinVersion:   tls.VersionTLS12,
    }

    w.mu.Lock()
    w.current = cfg
    w.mu.Unlock()
    return nil
}

// watch controlla periodicamente i file e ricarica se cambiati.
// Alternativa robusta: usare fsnotify per notifiche inotify.
func (w *WatchedTLSConfig) watch() {
    ticker := time.NewTicker(5 * time.Minute)
    for range ticker.C {
        if err := w.reload(); err != nil {
            // log error — continua con il config precedente
            continue
        }
    }
}

// GetTLSConfig restituisce la config corrente (thread-safe).
func (w *WatchedTLSConfig) GetTLSConfig() *tls.Config {
    w.mu.RLock()
    defer w.mu.RUnlock()
    return w.current
}
```

```go
// Uso: http.Server che ricarica i certificati server senza restart
watcher, _ := tlsconfig.NewWatched("/certs")

server := &http.Server{
    Addr: ":8443",
    TLSConfig: &tls.Config{
        // GetCertificate viene chiamato ad ogni TLS handshake
        GetCertificate: func(info *tls.ClientHelloInfo) (*tls.Certificate, error) {
            cfg := watcher.GetTLSConfig()
            if len(cfg.Certificates) == 0 {
                return nil, fmt.Errorf("nessun certificato disponibile")
            }
            cert := cfg.Certificates[0]
            return &cert, nil
        },
        ClientAuth: tls.RequireAndVerifyClientCert, // mTLS server-side
    },
}
// NOTA: con GetCertificate configurato, non passare certFile/keyFile a ListenAndServeTLS
server.ListenAndServeTLS("", "")
```

### Go — gRPC con mTLS

```go
import (
    "google.golang.org/grpc"
    "google.golang.org/grpc/credentials"
)

// Client gRPC con mTLS
func NewGRPCConn(target, certFile, keyFile, caFile string) (*grpc.ClientConn, error) {
    tlsCfg := &tls.Config{
        Certificates: func() []tls.Certificate {
            cert, _ := tls.LoadX509KeyPair(certFile, keyFile)
            return []tls.Certificate{cert}
        }(),
        RootCAs: func() *x509.CertPool {
            pool := x509.NewCertPool()
            ca, _ := os.ReadFile(caFile)
            pool.AppendCertsFromPEM(ca)
            return pool
        }(),
        MinVersion: tls.VersionTLS12,
    }

    creds := credentials.NewTLS(tlsCfg)
    return grpc.Dial(target, grpc.WithTransportCredentials(creds))
}
```

---

## Trust: Sistema vs Bundle Applicativo

### Quando il System Trust Store Non Basta

Le immagini container base (distroless, alpine, scratch) includono o meno i CA bundle di sistema:

```
scratch                →  NESSUN CA bundle — TLS fallisce sempre senza configurazione
gcr.io/distroless/static  →  NESSUN CA bundle
gcr.io/distroless/base    →  Include /etc/ssl/certs/ca-certificates.crt
alpine                 →  Include ca-certificates se installato esplicitamente
ubuntu/debian          →  Include ca-certificates
```

```dockerfile
# Per immagini scratch/distroless/static — copia il CA bundle dall'host
FROM golang:1.22-alpine AS builder
RUN apk add --no-cache ca-certificates
RUN go build -o /service ./cmd/service

FROM scratch
# Copia CA bundle di sistema per TLS verso endpoint pubblici
COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
# Copia il binario
COPY --from=builder /service /service
ENTRYPOINT ["/service"]
```

```dockerfile
# Aggiunta CA privata all'immagine — per microservizi che comunicano internamente
FROM gcr.io/distroless/base
COPY ca-internal.crt /usr/local/share/ca-certificates/ca-internal.crt
# NOTA: distroless non ha update-ca-certificates. Meglio montare via K8s ConfigMap
# o caricarla programmaticamente nel codice.
```

### Distribuzione CA Privata via Kubernetes ConfigMap

```yaml
# ConfigMap con il certificato CA della PKI interna
apiVersion: v1
kind: ConfigMap
metadata:
  name: internal-ca-bundle
  namespace: myapp
data:
  ca.crt: |
    -----BEGIN CERTIFICATE-----
    MIIBxTCCAW+gAwIBAgIJAP...
    -----END CERTIFICATE-----
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: myservice
spec:
  template:
    spec:
      containers:
        - name: app
          volumeMounts:
            - name: ca-bundle
              mountPath: /certs/ca
              readOnly: true
            - name: tls-certs
              mountPath: /certs/service
              readOnly: true
      volumes:
        - name: ca-bundle
          configMap:
            name: internal-ca-bundle
        - name: tls-certs
          secret:
            secretName: myservice-tls  # emesso da cert-manager
```

---

## Rotazione Certificati senza Restart

### Meccanismi per Linguaggio

| Linguaggio | Meccanismo | Note |
|---|---|---|
| Java / WebClient | `SslContextBuilder` + rebuild periodico | Netty ricrea le connessioni usando il nuovo SslContext |
| Java / RestTemplate | Ricrea `HttpClient` + `RestTemplate` periodicamente | Attenzione: le connessioni esistenti usano il vecchio cert |
| .NET | `IHttpClientFactory` + `HandlerLifetime` | Raccomandato. Ricrea handler ogni N minuti |
| Go / http.Client | `GetCertificate` / `GetClientCertificate` callback | Chiamata ad ogni TLS handshake — zero downtime |
| Go / gRPC | `credentials.NewTLS` + connessione nuova | gRPC non supporta TLS config update su connessione esistente |

!!! tip "K8s Secret montato come volume"
    Quando cert-manager rinnova un certificato, Kubernetes aggiorna atomicamente i file nel volume montato (tramite symlink). L'applicazione vede i nuovi file alla prossima lettura. **Non è necessario riavviare il pod** — basta che l'applicazione rilegga periodicamente i file.

!!! warning "Secret montato come env var"
    Se monti il Secret come variabile d'ambiente (envFrom/env), Kubernetes **non aggiorna automaticamente** le env var quando il Secret cambia. Usa sempre i Secret montati come volumi per i certificati.

---

## Debug TLS

### Java — javax.net.debug

```bash
# Attiva logging dettagliato TLS nella JVM
java -Djavax.net.debug=ssl:handshake:verbose -jar myservice.jar

# Output disponibili (combinabili con :):
# ssl       — tutto il debug SSL/TLS
# handshake — solo l'handshake
# record    — record TLS (molto verboso)
# trustmanager — decisioni del trust manager
# keymanager   — selezione del certificato client

# Esempio output handshake:
# javax.net.ssl|DEBUG|...|TLSv1.3 with cipher TLS_AES_256_GCM_SHA384
# javax.net.ssl|DEBUG|...|No available certificate for requested authorities
# ^^ questo significa: il server ha richiesto un cert client, ma nessuno KeyStore è configurato
```

```bash
# Spring Boot: aggiungi nella JVM options di Kubernetes
spec:
  containers:
    - name: myservice
      env:
        - name: JAVA_TOOL_OPTIONS
          value: "-Djavax.net.debug=ssl:handshake"
```

### Go — variabili GODEBUG e SSLKEYLOGFILE

```go
// In Go non c'è un flag globale come javax.net.debug.
// Per loggare i dettagli del handshake, aggiungi un VerifyConnection callback:
tlsCfg := &tls.Config{
    VerifyConnection: func(cs tls.ConnectionState) error {
        log.Printf("[TLS] Versione: %s, Cipher: %s, Server: %s",
            tls.VersionName(cs.Version),
            tls.CipherSuiteName(cs.CipherSuite),
            cs.ServerName,
        )
        if len(cs.PeerCertificates) > 0 {
            log.Printf("[TLS] Server cert: CN=%s, Issuer=%s",
                cs.PeerCertificates[0].Subject.CommonName,
                cs.PeerCertificates[0].Issuer.CommonName,
            )
        }
        return nil // nil = connessione accettata
    },
}
```

### SSLKEYLOGFILE — Decifrare il Traffico con Wireshark

```bash
# Applicabile a Go, .NET 5+, e Java (con agent)
# Genera un file con le chiavi di sessione TLS — usabile da Wireshark per decifrare

# Go — imposta la variabile prima di avviare l'applicazione:
export SSLKEYLOGFILE=/tmp/tls-keys.log
# Poi in Go: tls.Config.KeyLogWriter = os.OpenFile(os.Getenv("SSLKEYLOGFILE"), ...)

# .NET — imposta la variabile d'ambiente:
export SSLKEYLOGFILE=/tmp/tls-keys.log
# .NET legge automaticamente questa variabile (System.Net.Http su .NET 5+)

# In Wireshark: Edit → Preferences → Protocols → TLS → (Pre)-Master-Secret log filename
```

```go
// Go — configurazione completa con KeyLogWriter
import "os"

keyLogFile, err := os.OpenFile(
    os.Getenv("SSLKEYLOGFILE"),
    os.O_WRONLY|os.O_CREATE|os.O_APPEND,
    0600,
)
tlsCfg := &tls.Config{
    KeyLogWriter: keyLogFile, // nil se SSLKEYLOGFILE non è impostato
}
// ATTENZIONE: abilitare solo in debug — espone le chiavi di sessione
```

!!! warning "SSLKEYLOGFILE in produzione"
    Scrivere le chiavi di sessione su file permette di decifrare completamente il traffico TLS. Non abilitare mai `SSLKEYLOGFILE` in produzione. Usare solo in ambienti di debug isolati, con accesso controllato al file.

---

## Best Practices

### Configurazione TLS Sicura

```go
// Go — tls.Config consigliata per microservizi interni
tlsCfg := &tls.Config{
    MinVersion: tls.VersionTLS12,       // mai TLS 1.0 / 1.1
    // CipherSuites: ometti per usare il default Go (sicuro e aggiornato)
    // InsecureSkipVerify: MAI true in produzione
    // ServerName: imposta esplicitamente se non coincide col hostname
}
```

```java
// Java — imposta MinVersion e disabilita cipher deboli
SSLContext ctx = SSLContext.getInstance("TLS");
ctx.init(...);
SSLParameters params = ctx.getDefaultSSLParameters();
params.setProtocols(new String[]{"TLSv1.2", "TLSv1.3"});
// In alternativa, proprietà di sistema JVM:
// -Djdk.tls.disabledAlgorithms=SSLv3, TLSv1, TLSv1.1, RC4, DES, MD5withRSA
```

- **Non disabilitare mai la verifica del server** (`InsecureSkipVerify: true` in Go, `TrustAllCertificates()` in Java/Kotlin). In testing usa un'istanza con CA locale.
- **Non hardcodare password KeyStore** nel codice — leggile da variabili d'ambiente o Vault.
- **Preferire PEM files** ai JKS legacy — portabili su tutti i linguaggi, leggibili, compatibili con cert-manager.
- **Usare `ServerName`** in `tls.Config` quando il nome nel certificato non corrisponde all'hostname di connessione (es. connessione a IP, SNI customizzato).

### Pattern di Lettura Sicura dei Certificati da Kubernetes

```go
// Non leggere i file ogni volta — usa una cache con TTL
// Non fallire al startup se i cert non ci sono — logga e riprova
// Usa ReadFile + AppendCertsFromPEM con check sul return value

pool := x509.NewCertPool()
caPEM, err := os.ReadFile(caPath)
if err != nil {
    return fmt.Errorf("impossibile leggere CA: %w", err)
}
if !pool.AppendCertsFromPEM(caPEM) {
    return fmt.Errorf("file %s non contiene certificati PEM validi", caPath)
}
// AppendCertsFromPEM restituisce false se il file esiste ma non ha PEM validi
// — errore silenzioso comune quando il volume non è ancora montato
```

---

## Troubleshooting

### 1. `PKIX path building failed` / `unable to find valid certification path`

**Sintomo:** Java lancia `sun.security.validator.ValidatorException: PKIX path building failed`.

**Causa:** Il TrustStore configurato (o quello di default della JVM) non contiene il certificato CA che ha firmato il server. Comune quando si usa una CA privata.

**Soluzione:**
```bash
# Verifica quale certificato presenta il server:
openssl s_client -connect host:port -showcerts 2>/dev/null | openssl x509 -noout -issuer -subject

# Importa la CA nel TrustStore (solo se usi JKS):
keytool -import -alias internal-ca -file ca.crt -keystore truststore.jks -storepass changeit

# Oppure passa il TrustStore alla JVM:
java -Djavax.net.ssl.trustStore=/certs/truststore.jks \
     -Djavax.net.ssl.trustStorePassword=changeit \
     -jar myservice.jar
```

### 2. `No available certificate for requested authorities`

**Sintomo:** Log Java con `No available certificate for requested authorities` durante handshake mTLS.

**Causa:** Il server ha richiesto un certificato client (`CertificateRequest`), ma il KeyStore dell'applicazione non contiene un certificato firmato da nessuna delle CA che il server accetta.

**Soluzione:** Verificare che il certificato client sia firmato dalla stessa CA che il server si aspetta, e che il KeyStore sia configurato correttamente nel codice.

### 3. `tls: failed to verify certificate: x509: certificate signed by unknown authority`

**Sintomo:** Go ritorna questo errore al momento della connessione.

**Causa:** `RootCAs` nel `tls.Config` è nil (usa il system trust store), che non include la CA privata. Oppure il file CA è vuoto/malformato.

**Soluzione:**
```go
// Debug: stampa quanti cert ha caricato il pool
pool := x509.NewCertPool()
caPEM, _ := os.ReadFile(caPath)
ok := pool.AppendCertsFromPEM(caPEM)
fmt.Printf("CA loaded: %v, pool subjects: %d\n", ok, len(pool.Subjects()))
// Se len == 0 → il file non contiene PEM validi
```

### 4. `certificate has expired or is not yet valid`

**Sintomo:** Qualsiasi linguaggio, errore di validità temporale.

**Causa:** Il certificato è scaduto, oppure c'è uno skew di clock tra i nodi (NTP non sincronizzato).

**Soluzione:**
```bash
# Controlla scadenza certificato:
openssl x509 -in /certs/tls.crt -noout -dates
# Not Before: Feb  1 00:00:00 2026 GMT
# Not After : Mar  1 00:00:00 2026 GMT

# Controlla clock del pod:
kubectl exec -n mynamespace mypod -- date

# Se cert-manager emette certificati ma il pod non si aggiorna:
kubectl describe certificate myservice-cert -n mynamespace
# Cerca: "Certificate is up to date and has not expired"
# Se scaduto: kubectl delete certificate myservice-cert (forza rinnovo)
```

### 5. Certificato Ruotato ma l'Applicazione Usa Ancora il Vecchio

**Sintomo:** cert-manager ha rinnovato il Secret, ma l'applicazione continua a presentare il certificato vecchio.

**Causa:** L'applicazione ha caricato il certificato al startup e non lo ricarica. Oppure il Secret è montato come env var (non aggiornato automaticamente).

**Soluzione:** Implementare il reload periodico (vedi sezione precedente). Verificare che il Secret sia montato come volume, non come env var. In caso di urgenza: `kubectl rollout restart deployment/myservice`.

---

## Relazioni

??? info "mTLS e SPIFFE/SPIRE — Identità dei Workload"
    Questo documento copre come configurare mTLS nel codice. SPIFFE/SPIRE gestisce l'emissione automatica dei certificati e l'identità del workload a livello infrastrutturale.

    **Approfondimento completo →** [mTLS e SPIFFE/SPIRE](../../security/autenticazione/mtls-spiffe.md)

??? info "cert-manager — Emissione Automatica Certificati"
    I certificati usati in questo documento vengono tipicamente emessi e rinnovati da cert-manager. La configurazione del Secret K8s e del Certificate resource è documentata separatamente.

    **Approfondimento completo →** [cert-manager](../../security/pki-certificati/cert-manager.md)

??? info "TLS/SSL — Fondamentali del Protocollo"
    Per capire cosa succede durante un TLS handshake, le differenze tra TLS 1.2 e 1.3, e i cipher suite.

    **Approfondimento completo →** [TLS/SSL Basics](../../networking/fondamentali/tls-ssl-basics.md)

---

## Riferimenti

- [Go crypto/tls package documentation](https://pkg.go.dev/crypto/tls)
- [Go crypto/x509 package documentation](https://pkg.go.dev/crypto/x509)
- [Java JSSE Reference Guide (Oracle)](https://docs.oracle.com/en/java/javase/21/security/java-secure-socket-extension-jsse-reference-guide.html)
- [.NET SslStream documentation (Microsoft)](https://learn.microsoft.com/en-us/dotnet/api/system.net.security.sslstream)
- [.NET X509Certificate2.CreateFromPemFile](https://learn.microsoft.com/en-us/dotnet/api/system.security.cryptography.x509certificates.x509certificate2.createfrompemfile)
- [cert-manager — Mounting Certificates in Pods](https://cert-manager.io/docs/usage/certificate/)
