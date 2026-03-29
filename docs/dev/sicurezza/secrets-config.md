---
title: "Secrets e Config da Codice — Kubernetes, Vault, Cloud SDK"
slug: secrets-config
category: dev
tags: [secrets, kubernetes, vault, spring, dotnet, go, aws, azure, configuration, security]
search_keywords: [secrets da codice, kubernetes secrets developer, env var vs volume, hot reload secrets, spring cloud kubernetes, refreshscope spring, configmap hot reload, ioptionsmonitor dotnet, viper watchconfig go, vault agent sidecar, vault sidecar injector, vault agent token renewal, vault lease renewal, vault agent template, external secrets operator developer, eso kubernetes, aws secrets manager sdk, aws sdk secrets, secretsmanager java, boto3 secrets manager, azure key vault sdk, azure key vault java, azure key vault dotnet, key vault go, secret in log, logback masking, sensitive data dotnet, serilog masking, secret hard-coded, secret stack trace, secret environment variable exposure, kubernetes configmap reload, spring actuator refresh, microservizi secrets, dynamic secrets kubernetes, secrets rotation codice]
parent: dev/sicurezza/_index
related: [security/secret-management/kubernetes-secrets, security/secret-management/vault, dev/linguaggi/java-spring-boot, dev/linguaggi/dotnet, dev/linguaggi/go]
official_docs: https://kubernetes.io/docs/concepts/configuration/secret/
status: complete
difficulty: intermediate
last_updated: 2026-03-28
---

# Secrets e Config da Codice — Kubernetes, Vault, Cloud SDK

## Panoramica

Gestire i segreti in un microservizio Kubernetes coinvolge due livelli distinti: l'**infrastruttura** (chi crea e gestisce il Kubernetes Secret, l'ExternalSecret, il Vault path) e il **codice applicativo** (come legge il valore, come si aggiorna quando cambia, come evita di esporlo accidentalmente). Questo documento copre esclusivamente il secondo livello.

La scelta fondamentale è **come iniettare il segreto nel processo**: come variabile d'ambiente (`env:`) o come file montato in un volume (`volumeMounts:`). Non è una scelta estetica — ha implicazioni dirette sulla sicurezza, sulla possibilità di aggiornamento a caldo, e su cosa succede in caso di rotazione. Poi ci sono i pattern avanzati: leggere il segreto direttamente dall'SDK cloud (AWS Secrets Manager, Azure Key Vault), usare il Vault Agent Sidecar, o affidarsi all'External Secrets Operator per sincronizzare i segreti come file.

!!! warning "Premessa: segreti non sono configurazione"
    Non gestire segreti e configurazione ordinaria con gli stessi pattern. Una ConfigMap è progettata per essere leggibile (`kubectl describe configmap` mostra il contenuto). Un Secret Kubernetes ha controllo RBAC separato e, con la crittografia at-rest abilitata, protezione aggiuntiva. Trattarli come equivalenti è un errore di progettazione.

---

## Concetti Chiave

### Env Var vs Volume Montato — Confronto Decisionale

| Criterio | Variabile d'Ambiente | File Montato (Volume) |
|---|---|---|
| **Hot reload** | Impossibile senza restart del pod | Possibile con watcher del filesystem |
| **Visibilità** | `kubectl describe pod`, `/proc/PID/environ`, log di errore | Solo chi può leggere il filesystem del container |
| **Dimensione massima** | ~1MB (limite etcd) | Illimitata praticamente |
| **Formato** | Stringa flat | Qualsiasi formato (JSON, PEM, properties) |
| **Rotazione** | Richiede rolling restart | Il file viene aggiornato automaticamente da kubelet |
| **Debugging** | Facile (visibile in env) | Richiede `kubectl exec` nel container |
| **Rischio accidentale** | Alto: visibile in core dump, stack trace, log | Basso: solo path nel log, non il valore |

**Regola pratica:**
- Usare **env var** per: flag di feature, URL di servizi interni, parametri non sensibili, valori che non cambiano a runtime
- Usare **volume montato** per: password, token, chiavi API, certificati, qualsiasi dato sensibile che potrebbe essere ruotato

```yaml
# PREFERITO per segreti: montare come file
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
      - name: app
        image: myapp:latest
        # ✅ Parametri non sensibili come env var
        env:
        - name: APP_ENV
          value: "production"
        - name: LOG_LEVEL
          value: "info"
        - name: DB_HOST
          valueFrom:
            configMapKeyRef:
              name: app-config
              key: db.host
        # ✅ Segreti come file montati
        volumeMounts:
        - name: db-credentials
          mountPath: /etc/secrets/db
          readOnly: true
        - name: api-key
          mountPath: /etc/secrets/api
          readOnly: true
      volumes:
      - name: db-credentials
        secret:
          secretName: orders-db-credentials
          defaultMode: 0400   # Lettura solo dal owner (uid del processo app)
      - name: api-key
        secret:
          secretName: stripe-api-key
          defaultMode: 0400
```

```yaml
# EVITARE per segreti critici: env var dirette
# Questo è accettabile per ambienti di sviluppo, non produzione
env:
- name: DB_PASSWORD  # ❌ Visibile in kubectl describe pod, /proc, core dump
  valueFrom:
    secretKeyRef:
      name: orders-db-credentials
      key: password
```

### Come Kubernetes Aggiorna i Secret Montati

Quando il valore di un Kubernetes Secret viene aggiornato (o quando l'External Secrets Operator ne sincronizza una nuova versione), kubelet aggiorna automaticamente i file montati nel pod entro il `syncPeriod` (default: 1 minuto). I file vengono scritti atomicamente tramite symlink.

```
Aggiornamento Secret in etcd
         │
         ▼
  kubelet rileva il cambiamento
         │
  (entro syncPeriod, default ~60s)
         │
         ▼
  Crea nuova versione file in:
  /etc/secrets/db/..data_tmp_XXXXX
         │
         ▼
  Atomic symlink swap:
  /etc/secrets/db/..data → nuova versione
         │
         ▼
  Il file /etc/secrets/db/password
  ora punta al nuovo valore
```

**Le variabili d'ambiente NON vengono mai aggiornate** — sono impostate all'avvio del processo e rimangono fisse per tutta la vita del container. L'unico modo per aggiornare un segreto in una env var è ricreare il pod.

---

## Hot Reload — Come Aggiornare la Config Senza Restart

### Java / Spring Boot con Spring Cloud Kubernetes

Spring Cloud Kubernetes permette di ricaricare automaticamente la configurazione quando un ConfigMap o un Secret Kubernetes viene aggiornato.

```xml
<!-- pom.xml: dipendenze necessarie -->
<dependency>
    <groupId>org.springframework.cloud</groupId>
    <artifactId>spring-cloud-starter-kubernetes-client-config</artifactId>
</dependency>
<dependency>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-actuator</artifactId>
</dependency>
```

```yaml
# application.yaml
spring:
  cloud:
    kubernetes:
      config:
        enabled: true
        name: app-config         # Nome del ConfigMap da leggere
        namespace: production
      secrets:
        enabled: true
        name: app-secrets        # Nome del Secret Kubernetes da leggere
        namespace: production
      reload:
        enabled: true
        mode: polling            # oppure: event (watch API Kubernetes)
        period: 15000            # ms — controlla ogni 15 secondi (solo per polling)
        strategy: refresh        # oppure: restart_context, shutdown
```

```java
// Bean con valori ricaricabili — richiede @RefreshScope
// Quando la config viene ricaricata, questo bean viene distrutto e ricreato

import org.springframework.cloud.context.config.annotation.RefreshScope;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

@Service
@RefreshScope                    // ← Fondamentale: senza questo il bean non si aggiorna
public class PaymentGatewayService {

    @Value("${stripe.api-key}")  // Letto dal Secret Kubernetes
    private String stripeApiKey;

    @Value("${payment.timeout-ms:5000}")  // Letto dal ConfigMap con default
    private int timeoutMs;

    public String processPayment(String amount) {
        // Ogni volta che questo metodo viene chiamato dopo un refresh,
        // stripeApiKey e timeoutMs hanno i valori aggiornati
        return callStripeApi(stripeApiKey, amount, timeoutMs);
    }
}
```

```java
// Alternativa: @ConfigurationProperties con @RefreshScope
// Preferibile per gruppi di configurazione correlata

@ConfigurationProperties(prefix = "database")
@RefreshScope
@Component
public class DatabaseConfig {
    private String host;
    private int port;
    private String password;      // Dall'environment → dal Secret montato
    private int maxPoolSize;

    // Getters e setters (o usare @ConstructorBinding con Lombok @Data)
    public String getPassword() { return password; }
    public void setPassword(String password) { this.password = password; }
    // ...
}
```

!!! warning "Limiti di @RefreshScope"
    `@RefreshScope` ricrea il bean, ma non chiude le connessioni aperte. Se stai usando un connection pool (HikariCP), le connessioni esistenti continuano a usare la vecchia password. Il pool drena e riapre le connessioni gradualmente, ma c'è una finestra transitoria. Per database, considera di affidarti al Vault Agent Sidecar con lease renewal automatico invece di refreshare la password direttamente.

```yaml
# RBAC necessario per Spring Cloud Kubernetes (mode: event/watch)
# Il ServiceAccount del pod deve poter leggere ConfigMap e Secret
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: app-config-reader
  namespace: production
rules:
- apiGroups: [""]
  resources: ["configmaps", "secrets"]
  verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: app-config-reader-binding
  namespace: production
subjects:
- kind: ServiceAccount
  name: orders-service-sa
roleRef:
  kind: Role
  name: app-config-reader
  apiGroup: rbac.authorization.k8s.io
```

### .NET con IOptionsMonitor<T>

In .NET il pattern nativo per configurazione ricaricabile è `IOptionsMonitor<T>`. Non richiede librerie esterne — è parte di `Microsoft.Extensions.Configuration`.

```csharp
// appsettings.json o variabili d'ambiente
// Il file di configurazione viene riletto automaticamente se il filesystem provider
// è configurato con reloadOnChange: true

// Program.cs — configurazione del provider
var builder = WebApplication.CreateBuilder(args);

// Aggiunge lettura da file montato Kubernetes (ricaricato automaticamente)
builder.Configuration.AddKeyPerFile(
    directoryPath: "/etc/secrets/app",   // Percorso del volume Kubernetes
    optional: false,
    reloadOnChange: true                 // Abilita il FileSystemWatcher
);

// Registra la sezione di configurazione
builder.Services.Configure<StripeOptions>(
    builder.Configuration.GetSection("Stripe"));
```

```csharp
// StripeOptions.cs — POCO per la configurazione
public class StripeOptions
{
    public string ApiKey { get; set; } = string.Empty;
    public string WebhookSecret { get; set; } = string.Empty;
    public bool EnableTestMode { get; set; }
}
```

```csharp
// PaymentService.cs — consumer con IOptionsMonitor<T>
public class PaymentService
{
    private readonly IOptionsMonitor<StripeOptions> _optionsMonitor;
    private readonly ILogger<PaymentService> _logger;

    public PaymentService(
        IOptionsMonitor<StripeOptions> optionsMonitor,
        ILogger<PaymentService> logger)
    {
        _optionsMonitor = optionsMonitor;
        _logger = logger;

        // Callback chiamato ogni volta che la configurazione viene ricaricata
        _optionsMonitor.OnChange(newOptions => {
            _logger.LogInformation("Stripe config reloaded — test mode: {TestMode}",
                newOptions.EnableTestMode);
            // Non loggare mai newOptions.ApiKey o newOptions.WebhookSecret!
        });
    }

    public async Task<PaymentResult> ProcessAsync(decimal amount)
    {
        // .CurrentValue restituisce SEMPRE il valore corrente (post-reload)
        var options = _optionsMonitor.CurrentValue;

        // Usare options.ApiKey per questa chiamata specifica
        return await CallStripeAsync(options.ApiKey, amount);
    }
}
```

!!! tip "IOptionsSnapshot vs IOptionsMonitor"
    - `IOptions<T>`: singleton, non si aggiorna mai — da evitare per segreti
    - `IOptionsSnapshot<T>`: scoped, ricarica a ogni request HTTP — buono per web app
    - `IOptionsMonitor<T>`: singleton con callback OnChange — il migliore per background services e hot reload con notifica

### Go con viper.WatchConfig

```go
// config/config.go
package config

import (
    "log"
    "sync"
    "time"

    "github.com/fsnotify/fsnotify"
    "github.com/spf13/viper"
)

type AppConfig struct {
    mu     sync.RWMutex
    viper  *viper.Viper
}

func NewAppConfig(configPath string) *AppConfig {
    v := viper.New()
    v.SetConfigFile(configPath)   // Es: "/etc/secrets/app/config.yaml"
    v.SetConfigType("yaml")

    // Abilita anche env var come override (utile per sviluppo locale)
    v.AutomaticEnv()

    if err := v.ReadInConfig(); err != nil {
        log.Fatalf("cannot read config: %v", err)
    }

    cfg := &AppConfig{viper: v}

    // Abilita il filesystem watcher — si aggiorna quando il file cambia
    v.WatchConfig()
    v.OnConfigChange(func(e fsnotify.Event) {
        cfg.mu.Lock()
        defer cfg.mu.Unlock()
        log.Printf("Config reloaded: %s", e.Name)
        // Non loggare valori sensibili qui
    })

    return cfg
}

// Accesso thread-safe con RWMutex
func (c *AppConfig) GetAPIKey() string {
    c.mu.RLock()
    defer c.mu.RUnlock()
    return c.viper.GetString("api_key")
}

func (c *AppConfig) GetDBPassword() string {
    c.mu.RLock()
    defer c.mu.RUnlock()
    return c.viper.GetString("db.password")
}
```

```go
// main.go — utilizzo
func main() {
    cfg := config.NewAppConfig("/etc/secrets/app/config.yaml")

    // Il server usa sempre cfg.GetAPIKey() che ritorna il valore corrente
    http.HandleFunc("/payment", func(w http.ResponseWriter, r *http.Request) {
        apiKey := cfg.GetAPIKey()  // Thread-safe, sempre aggiornato
        processPayment(apiKey, r)
    })

    log.Fatal(http.ListenAndServe(":8080", nil))
}
```

!!! warning "viper.WatchConfig e volume Kubernetes"
    Kubernetes aggiorna i file montati tramite atomic symlink swap (il path `..data` viene rimpiazzato). Alcuni filesystem watcher non rilevano questo tipo di aggiornamento perché tracciano l'inode originale, non il path. Se `OnConfigChange` non si attiva, verificare che `fsnotify` supporti il sistema operativo del container (Linux: inotify, sì supportato). In caso di problemi, usare polling con un ticker invece del watcher.

---

## Vault Agent Sidecar — Dal Punto di Vista del Developer

Il **Vault Agent Sidecar** è un container aggiuntivo iniettato automaticamente nel pod dall'Injector di Vault. Il suo ruolo: autenticarsi a Vault, ottenere i segreti, e scriverli come file nel filesystem condiviso col container principale. L'applicazione legge file come se fossero normali file locali — non sa che esistono Vault.

```
Pod:
┌──────────────────────────────────────────────┐
│  vault-agent (sidecar)   │  app container    │
│                          │                   │
│  1. Kubernetes auth      │                   │
│  2. Ottiene token Vault  │                   │
│  3. Legge secrets        │                   │
│  4. Scrive in:           │  Legge da:        │
│     /vault/secrets/      │  /vault/secrets/  │
│  5. Rinnova lease        │  (filesystem      │
│     automaticamente      │   condiviso)      │
└──────────────────────────┴───────────────────┘
         emptyDir volume condiviso
```

```yaml
# L'annotation configura il sidecar — non serve modificare il Deployment manualmente
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orders-service
spec:
  template:
    metadata:
      annotations:
        # Abilita l'iniezione del sidecar
        vault.hashicorp.com/agent-inject: "true"
        vault.hashicorp.com/role: "orders-service"

        # Inietta il segreto DB come file /vault/secrets/database
        vault.hashicorp.com/agent-inject-secret-database: "secret/data/production/orders/database"

        # Template personalizzato — trasforma il JSON di Vault in un formato usabile
        vault.hashicorp.com/agent-inject-template-database: |
          {{- with secret "secret/data/production/orders/database" -}}
          DB_HOST={{ .Data.data.host }}
          DB_PORT={{ .Data.data.port }}
          DB_USER={{ .Data.data.username }}
          DB_PASS={{ .Data.data.password }}
          {{- end }}

        # Inietta le credenziali AWS dinamiche (lease: 1h, rinnovate automaticamente)
        vault.hashicorp.com/agent-inject-secret-aws: "aws/creds/orders-role"
        vault.hashicorp.com/agent-inject-template-aws: |
          {{- with secret "aws/creds/orders-role" -}}
          AWS_ACCESS_KEY_ID={{ .Data.access_key }}
          AWS_SECRET_ACCESS_KEY={{ .Data.secret_key }}
          {{- end }}
    spec:
      serviceAccountName: orders-service-sa  # Usato per Kubernetes auth con Vault
      containers:
      - name: orders-service
        image: orders-service:latest
        # L'applicazione legge i file scritti dal sidecar
        # /vault/secrets/database → file con le credenziali DB
        # /vault/secrets/aws      → file con le credenziali AWS temporanee
```

```java
// Java: leggere i file scritti dal Vault Agent
// Preferire source-file-as-env approach per non cambiare il codice applicativo
// Oppure leggerli direttamente:

@Component
public class VaultSecretsLoader implements InitializingBean {

    @Value("${VAULT_SECRETS_PATH:/vault/secrets}")
    private String secretsPath;

    private Properties dbCredentials = new Properties();

    @Override
    public void afterPropertiesSet() throws Exception {
        loadFromFile(Paths.get(secretsPath, "database"));
    }

    private void loadFromFile(Path path) throws IOException {
        try (InputStream in = Files.newInputStream(path)) {
            dbCredentials.load(in);
        }
    }

    public String getDbPassword() {
        return dbCredentials.getProperty("DB_PASS");
    }
}
```

```bash
# Debug: ispezionare i file scritti dal vault-agent sidecar
kubectl exec -it orders-service-xyz -- cat /vault/secrets/database
# Output (formattato dal template):
# DB_HOST=postgres-primary.production.svc.cluster.local
# DB_PORT=5432
# DB_USER=orders_user_20260328
# DB_PASS=A1b2C3d4e5F6...

# Verificare che il sidecar stia rinnovando il lease
kubectl logs orders-service-xyz -c vault-agent | grep -i "lease\|renew\|token"
```

---

## External Secrets Operator — Come Appare al Developer

L'External Secrets Operator (ESO) è configurato dall'infrastruttura, ma il developer deve sapere **cosa si trova nel filesystem** dopo che ESO ha sincronizzato il segreto.

```yaml
# Cosa l'infrastruttura crea (ExternalSecret) — il developer NON tocca questo
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: orders-secrets
  namespace: production
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  target:
    name: orders-app-secret       # ← Questo è il Kubernetes Secret risultante
    creationPolicy: Owner
  data:
  - secretKey: DB_PASSWORD        # ← Questa è la chiave nel Secret Kubernetes
    remoteRef:
      key: production/orders/database
      property: password
  - secretKey: STRIPE_KEY
    remoteRef:
      key: production/orders/stripe
      property: api_key
```

```yaml
# Il developer monta il Secret risultante nel Deployment — esattamente come un normale K8s Secret
spec:
  template:
    spec:
      containers:
      - name: orders-service
        volumeMounts:
        - name: app-secrets
          mountPath: /etc/app/secrets
          readOnly: true
      volumes:
      - name: app-secrets
        secret:
          secretName: orders-app-secret  # Il Secret creato da ESO
          # Struttura risultante nel filesystem:
          # /etc/app/secrets/DB_PASSWORD  → "s3cr3t-passw0rd"
          # /etc/app/secrets/STRIPE_KEY   → "sk_live_abc123..."
```

!!! tip "ESO e hot reload"
    ESO sincronizza il Secret Kubernetes ogni `refreshInterval`. Quando il Secret viene aggiornato, kubelet aggiorna i file montati entro ~60s. Il codice con watcher del filesystem (Go: viper.WatchConfig, .NET: reloadOnChange, Spring: reload.enabled) vede l'aggiornamento automaticamente senza nessuna modifica al Deployment.

---

## SDK Cloud — Leggere Segreti Direttamente

In alcuni scenari è preferibile leggere il segreto dall'SDK cloud anziché affidarsi a Kubernetes Secrets. Tipicamente quando: il segreto ha un TTL cortissimo, si vuole audit trail granulare di chi ha letto cosa, o l'applicazione gira fuori da Kubernetes.

### AWS Secrets Manager — Java

```java
// Dipendenza Maven
// <dependency>
//   <groupId>software.amazon.awssdk</groupId>
//   <artifactId>secretsmanager</artifactId>
// </dependency>

import software.amazon.awssdk.services.secretsmanager.SecretsManagerClient;
import software.amazon.awssdk.services.secretsmanager.model.GetSecretValueRequest;
import software.amazon.awssdk.services.secretsmanager.model.GetSecretValueResponse;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Duration;

@Component
public class AwsSecretsLoader {

    private final SecretsManagerClient client;
    private final ObjectMapper objectMapper;

    // Cache in memoria per evitare chiamate API eccessive
    private volatile String cachedApiKey;
    private volatile Instant cacheExpiry = Instant.EPOCH;
    private static final Duration CACHE_TTL = Duration.ofMinutes(5);

    public AwsSecretsLoader() {
        // Autenticazione automatica: IRSA (IAM Role for Service Account) in Kubernetes,
        // instance role su EC2, credenziali locali in sviluppo
        this.client = SecretsManagerClient.builder()
            .region(Region.US_EAST_1)
            .build();
        this.objectMapper = new ObjectMapper();
    }

    public synchronized String getStripeApiKey() {
        if (Instant.now().isAfter(cacheExpiry)) {
            GetSecretValueRequest request = GetSecretValueRequest.builder()
                .secretId("production/orders/stripe")
                .build();

            GetSecretValueResponse response = client.getSecretValue(request);
            Map<String, String> secretData = objectMapper.readValue(
                response.secretString(), Map.class);

            cachedApiKey = secretData.get("api_key");
            cacheExpiry = Instant.now().plus(CACHE_TTL);
        }
        return cachedApiKey;
    }
}
```

### Azure Key Vault — .NET

```csharp
// NuGet: Azure.Security.KeyVault.Secrets, Azure.Identity

using Azure.Identity;
using Azure.Security.KeyVault.Secrets;
using Microsoft.Extensions.Caching.Memory;

public class AzureKeyVaultSecretService
{
    private readonly SecretClient _client;
    private readonly IMemoryCache _cache;

    public AzureKeyVaultSecretService(IMemoryCache cache)
    {
        // DefaultAzureCredential prova in ordine:
        // 1. Managed Identity (in Azure) / Workload Identity (in AKS)
        // 2. Azure CLI (sviluppo locale)
        // 3. Visual Studio (sviluppo locale)
        var credential = new DefaultAzureCredential();

        _client = new SecretClient(
            new Uri("https://mycompany-kv.vault.azure.net/"),
            credential);
        _cache = cache;
    }

    public async Task<string> GetSecretAsync(string secretName)
    {
        // Cache con sliding expiration per ridurre le chiamate API
        return await _cache.GetOrCreateAsync(
            $"kv:{secretName}",
            async entry =>
            {
                entry.SlidingExpiration = TimeSpan.FromMinutes(10);
                KeyVaultSecret secret = await _client.GetSecretAsync(secretName);
                return secret.Value;
            });
    }
}
```

```csharp
// Integrazione con IConfiguration — tutti i segreti del Key Vault
// diventano disponibili come se fossero in appsettings.json

// Program.cs
builder.Configuration.AddAzureKeyVault(
    new Uri("https://mycompany-kv.vault.azure.net/"),
    new DefaultAzureCredential(),
    new KeyVaultSecretManager());  // Usa il mapping di default: secret-name → Secret:Name

// Poi nel servizio:
public class MyService
{
    private readonly IConfiguration _config;

    public MyService(IConfiguration config) { _config = config; }

    public void DoWork()
    {
        var apiKey = _config["Stripe--ApiKey"];  // Legge da Key Vault (-- → :)
    }
}
```

### Go — AWS Secrets Manager

```go
// go get github.com/aws/aws-sdk-go-v2/service/secretsmanager

package secrets

import (
    "context"
    "encoding/json"
    "sync"
    "time"

    "github.com/aws/aws-sdk-go-v2/config"
    "github.com/aws/aws-sdk-go-v2/service/secretsmanager"
)

type SecretsCache struct {
    client    *secretsmanager.Client
    mu        sync.RWMutex
    cache     map[string]cachedSecret
}

type cachedSecret struct {
    value   string
    expires time.Time
}

func NewSecretsCache() (*SecretsCache, error) {
    // Autenticazione: IRSA in Kubernetes, instance profile su EC2
    cfg, err := config.LoadDefaultConfig(context.Background())
    if err != nil {
        return nil, err
    }
    return &SecretsCache{
        client: secretsmanager.NewFromConfig(cfg),
        cache:  make(map[string]cachedSecret),
    }, nil
}

func (s *SecretsCache) GetSecret(ctx context.Context, secretID string) (string, error) {
    s.mu.RLock()
    if cached, ok := s.cache[secretID]; ok && time.Now().Before(cached.expires) {
        s.mu.RUnlock()
        return cached.value, nil
    }
    s.mu.RUnlock()

    // Cache miss o scaduto: chiama AWS
    s.mu.Lock()
    defer s.mu.Unlock()

    input := &secretsmanager.GetSecretValueInput{SecretId: &secretID}
    result, err := s.client.GetSecretValue(ctx, input)
    if err != nil {
        return "", err
    }

    s.cache[secretID] = cachedSecret{
        value:   *result.SecretString,
        expires: time.Now().Add(5 * time.Minute),
    }
    return *result.SecretString, nil
}
```

---

## Anti-Pattern: Segreti che Finiscono Nei Log

Questo è il vettore di data breach più sottovalutato. Un segreto che appare in un log è compromesso: i log vengono centralizzati (Elastic, Loki, Splunk), conservati per mesi, e accessibili a molti team.

### Pattern Pericoloso 1 — Logging di Oggetti Contenenti Segreti

```java
// ❌ ERRORE: toString() dell'oggetto config espone il segreto nel log
@ConfigurationProperties("stripe")
public class StripeConfig {
    private String apiKey;
    private String webhookSecret;
    // Lombok @Data genera automaticamente toString() con tutti i campi!
    // Log: StripeConfig(apiKey=sk_live_abc123, webhookSecret=whsec_xyz789)
}

// ✅ CORRETTO: escludere i campi sensibili da toString()
@ConfigurationProperties("stripe")
@ToString(exclude = {"apiKey", "webhookSecret"})  // Lombok
public class StripeConfig {
    private String apiKey;
    private String webhookSecret;
    // Log: StripeConfig()
}
```

### Pattern Pericoloso 2 — Stack Trace con Valori Sensibili

```java
// ❌ ERRORE: il valore del segreto finisce nella exception
String apiKey = loadApiKey();
try {
    callApi(apiKey);
} catch (Exception e) {
    // Se callApi lancia "Invalid API key: sk_live_abc123", il valore è nel log
    log.error("API call failed: {}", e.getMessage(), e);
}

// ✅ CORRETTO: loggare solo un'indicazione, mai il valore
try {
    callApi(apiKey);
} catch (Exception e) {
    log.error("API call failed — check API key configuration (key length: {})",
        apiKey != null ? apiKey.length() : "null", e);
}
```

### Pattern Pericoloso 3 — HTTP Client Debug Logging

```java
// ❌ ERRORE: logging debug degli header HTTP espone Authorization: Bearer <token>
// In Spring Boot, NON abilitare mai questo in produzione:
# application.yaml
logging:
  level:
    org.springframework.web.client.RestTemplate: DEBUG   # ❌ Espone headers + body
    org.apache.http.wire: DEBUG                          # ❌ Espone traffico HTTP raw

// ✅ CORRETTO: logging selettivo senza header sensibili
// Usare un ClientHttpRequestInterceptor che maschera gli header
@Component
public class MaskingLoggingInterceptor implements ClientHttpRequestInterceptor {
    private static final Logger log = LoggerFactory.getLogger(MaskingLoggingInterceptor.class);

    @Override
    public ClientHttpResponse intercept(HttpRequest request, byte[] body,
            ClientHttpRequestExecution execution) throws IOException {
        // Logga URL e metodo (utile per debug), NON gli header
        log.debug("HTTP {} {}", request.getMethod(), request.getURI());
        return execution.execute(request, body);
    }
}
```

### Logback — Mascherare Pattern Sensibili

```xml
<!-- logback-spring.xml — mascherare pattern sensibili a livello di appender -->
<configuration>
    <conversionRule conversionWord="maskedMsg"
        converterClass="com.myapp.logging.MaskingConverter"/>

    <appender name="STDOUT" class="ch.qos.logback.core.ConsoleAppender">
        <encoder>
            <pattern>%d{ISO8601} %level [%thread] %logger - %maskedMsg%n</pattern>
        </encoder>
    </appender>
</configuration>
```

```java
// MaskingConverter.java — sostituisce pattern riconoscibili con [REDACTED]
public class MaskingConverter extends MessageConverter {
    private static final List<Pattern> SENSITIVE_PATTERNS = List.of(
        Pattern.compile("(sk_live_|sk_test_)[a-zA-Z0-9]{20,}"),   // Stripe
        Pattern.compile("(AKIA|ASIA)[A-Z0-9]{16}"),                // AWS Access Key
        Pattern.compile("password['\"]?\\s*[:=]\\s*['\"]?[^\\s,}]+",
            Pattern.CASE_INSENSITIVE)
    );

    @Override
    public String convert(ILoggingEvent event) {
        String message = event.getFormattedMessage();
        for (Pattern pattern : SENSITIVE_PATTERNS) {
            message = pattern.matcher(message).replaceAll("[REDACTED]");
        }
        return message;
    }
}
```

### .NET — Sensitive Data Annotations e Serilog

```csharp
// Serilog con destructuring policy per mascherare campi sensibili

// Program.cs
Log.Logger = new LoggerConfiguration()
    .Destructure.ByTransforming<StripeOptions>(opts => new {
        opts.EnableTestMode,          // Loggato
        ApiKey = "[REDACTED]",        // Mascherato
        WebhookSecret = "[REDACTED]"  // Mascherato
    })
    .WriteTo.Console()
    .CreateLogger();
```

```csharp
// Oppure: usare [SensitiveData] attribute con una policy personalizzata
// (richiede la libreria Destructurama.Attributed)

public class StripeOptions
{
    [SensitiveData]  // ← Serilog lo maschera automaticamente
    public string ApiKey { get; set; } = string.Empty;

    [SensitiveData]
    public string WebhookSecret { get; set; } = string.Empty;

    public bool EnableTestMode { get; set; }
}
```

### Anti-Pattern: Hard-Coded Secrets

```java
// ❌ SEMPRE SBAGLIATO — non farlo mai, nemmeno in test
public class PaymentService {
    private static final String API_KEY = "sk_live_abc123xyz";  // ❌ Nel codice sorgente
    private static final String DB_PASS = "SuperSecret123!";    // ❌ Nel codice sorgente
}

// ✅ CORRETTO: sempre da environment o configurazione esterna
@Value("${stripe.api-key}")               // Da Secret Kubernetes / env var
private String apiKey;

// oppure per test:
@Value("${stripe.api-key:sk_test_mock}")  // Default sicuro per test (chiave di test, non prod)
private String apiKey;
```

!!! warning "Git history e secret hard-coded"
    Se un segreto viene committato per errore, rimuoverlo con un nuovo commit non è sufficiente: rimane nel git history. Bisogna considerare il segreto compromesso e ruotarlo immediatamente. Per evitarlo, usare pre-commit hooks con strumenti come `git-secrets` o `detect-secrets`.

---

## Best Practices

!!! tip "Principi guida"
    1. **Segreti come file, non come env var**: i file vengono aggiornati da kubelet senza restart; le env var no.
    2. **Non loggare mai valori sensibili**: neanche per debug. Loggare la lunghezza, il prefisso, o un hash — mai il valore intero.
    3. **Cache con TTL breve per SDK cloud**: evitare chiamate API per ogni request; 5-10 minuti è un buon compromesso.
    4. **Testare il reload**: scrivere test che verificano che l'applicazione si aggiorna correttamente quando il segreto cambia, senza perdere richieste in volo.
    5. **Principio del minimo privilegio**: ogni servizio legge solo i segreti che gli servono — RBAC per Kubernetes, IAM policy per AWS, Access Policy per Azure Key Vault.

```yaml
# Checklist per un nuovo microservizio con secrets
# 1. ServiceAccount dedicato (non default)
# 2. Secret montati come volume con defaultMode: 0400
# 3. @RefreshScope / IOptionsMonitor / viper.WatchConfig abilitato
# 4. MaskingConverter in Logback o equivalente
# 5. Test del hot reload in CI (modifica il secret, verifica che l'app si aggiorni)
# 6. Nessun segreto in ConfigMap (usa sempre Secret)
# 7. pre-commit hook per rilevare segreti accidentali
```

---

## Troubleshooting

### Il Secret non viene aggiornato nel container dopo la modifica

**Sintomo:** Aggiornato il Kubernetes Secret, ma il container continua a usare il vecchio valore.

**Causa A (env var):** I segreti iniettati come env var non vengono mai aggiornati — sono fissati all'avvio del processo.
```bash
# Verifica se il segreto è in una env var:
kubectl describe pod <pod-name> | grep -A5 "Environment:"
# → Se vedi il valore direttamente (non dal volume), è una env var → richiede restart
kubectl rollout restart deployment <deployment-name>
```

**Causa B (volume, kubelet lag):** Il kubelet aggiorna i file con un ritardo fino a `syncPeriod` (default 60s).
```bash
# Verifica quando è stato aggiornato il file nel container:
kubectl exec <pod-name> -- ls -la /etc/secrets/db/
# Controlla il timestamp del symlink ..data
kubectl exec <pod-name> -- cat /etc/secrets/db/password | wc -c  # Verifica lunghezza
```

**Causa C (applicazione non rilegge il file):** L'applicazione ha letto il file all'avvio e non lo rilegge.
```bash
# Verifica che il watcher sia attivo (Go):
kubectl logs <pod-name> | grep -i "config reloaded\|watchconfig"
# Verifica che @RefreshScope sia attivo (Spring):
kubectl exec <pod-name> -- curl -s http://localhost:8080/actuator/refresh -XPOST
```

### Spring @RefreshScope non aggiorna il bean

**Sintomo:** La configurazione viene ricaricata (log di Spring Cloud Kubernetes lo confermano), ma il servizio continua a usare il vecchio valore.

**Causa:** Il bean non ha `@RefreshScope`, oppure viene iniettato in un bean non-refresh-scope che lo tiene in cache.
```java
// ❌ Questo non si aggiorna: DatabaseService è singleton, tiene il riferimento al vecchio bean
@Service  // Singleton — si aggiorna solo se ha @RefreshScope
public class OrderService {
    private final DatabaseService db;  // DatabaseService ha @RefreshScope, ma...

    public OrderService(DatabaseService db) {
        this.db = db;  // ...questo riferimento punta al vecchio proxy
    }
}

// ✅ Corretto: iniettare tramite ApplicationContext o usare @Lookup
@Service
public class OrderService {
    private final ApplicationContext ctx;

    public OrderService(ApplicationContext ctx) { this.ctx = ctx; }

    public void process() {
        // Ottiene sempre il bean corrente dal contesto (post-refresh)
        DatabaseService db = ctx.getBean(DatabaseService.class);
        db.query(...);
    }
}
```

### viper.WatchConfig non rileva il cambiamento

**Sintomo:** Go con viper, il file viene aggiornato da kubelet, ma `OnConfigChange` non viene chiamato.

**Causa:** Atomic symlink swap di Kubernetes non viene rilevato da alcuni filesystem watcher.
```go
// Soluzione: polling manuale con ticker come fallback
func (c *AppConfig) startPolling(interval time.Duration) {
    go func() {
        ticker := time.NewTicker(interval)
        var lastMod time.Time
        for range ticker.C {
            info, err := os.Stat(c.configPath)
            if err != nil {
                continue
            }
            if info.ModTime().After(lastMod) {
                lastMod = info.ModTime()
                if err := c.viper.ReadInConfig(); err == nil {
                    log.Printf("Config reloaded via polling")
                }
            }
        }
    }()
}
```

### Segreto trovato in log Elastic/Loki — Risposta Incidente

**Sintomo:** Un segreto (token, password, API key) appare in chiaro nei log centralizzati.

**Risposta immediata:**
```bash
# 1. Ruotare IMMEDIATAMENTE il segreto (non aspettare di capire il perché)
# 2. Identificare cosa ha loggato il valore
kubectl logs <pod-name> --previous | grep -n "<parte-del-segreto>"
# 3. Cercare nei log centralizzati per capire l'esposizione
# 4. Applicare il MaskingConverter e fare deploy
# 5. Verificare nei log successivi che il pattern non appaia più
# 6. Aprire un post-mortem — aggiungere il pattern a SENSITIVE_PATTERNS nel converter
```

### IOptionsMonitor non notifica il cambiamento

**Sintomo:** .NET, il file viene aggiornato, ma `OnChange` non viene chiamato.

**Causa:** Il path di configurazione usa symlink (Kubernetes) e `AddKeyPerFile` non segue i symlink per il FileSystemWatcher.
```csharp
// Soluzione: usare AddJsonFile con reloadOnChange su path risolto
var resolvedPath = Path.GetFullPath("/etc/secrets/app/config.json");
builder.Configuration.AddJsonFile(resolvedPath, optional: false, reloadOnChange: true);
```

---

## Relazioni

??? info "Kubernetes Secrets — Prospettiva Ops"
    Come creare, cifrare, gestire il ciclo di vita dei Kubernetes Secrets lato infrastruttura: SealedSecrets, External Secrets Operator setup, crittografia at-rest con KMS.

    **Approfondimento completo →** [Kubernetes Secrets](../../security/secret-management/kubernetes-secrets.md)

??? info "HashiCorp Vault"
    Vault dynamic secrets, PKI engine, Kubernetes auth method. Complementare al Vault Agent Sidecar descritto qui: questo documento copre il lato applicazione, vault.md copre la configurazione del server.

    **Approfondimento completo →** [HashiCorp Vault](../../security/secret-management/vault.md)

??? info "TLS/mTLS da Codice"
    Come caricare certificati TLS nel codice (Java KeyStore, .NET X509Certificate2, Go tls.Config). Complementare a questo documento: gli stessi pattern di hot reload si applicano ai certificati.

    **Approfondimento completo →** [TLS/mTLS da Codice](tls-da-codice.md)

---

## Riferimenti

- [Kubernetes Secrets — documentazione ufficiale](https://kubernetes.io/docs/concepts/configuration/secret/)
- [Spring Cloud Kubernetes — Config Reload](https://docs.spring.io/spring-cloud-kubernetes/reference/spring-cloud-kubernetes-configuration-watcher.html)
- [Vault Agent Injector — Annotazioni](https://developer.hashicorp.com/vault/docs/platform/k8s/injector/annotations)
- [External Secrets Operator](https://external-secrets.io/latest/)
- [AWS SDK for Java v2 — Secrets Manager](https://sdk.amazonaws.com/java/api/latest/software/amazon/awssdk/services/secretsmanager/package-summary.html)
- [Azure Key Vault SDK — .NET](https://learn.microsoft.com/en-us/dotnet/api/overview/azure/key-vault)
- [Viper — WatchConfig](https://github.com/spf13/viper#watching-and-re-reading-config-files)
- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
