---
title: "Ansible — Roles, Collections e Pattern Enterprise"
slug: ansible-roles-collections
category: iac
tags: [ansible, roles, collections, galaxy, vault, molecule, enterprise, testing, automation]
search_keywords: [ansible roles, ansible collections, ansible galaxy, ansible vault, molecule, private automation hub, PAH, ansible-galaxy init, requirements.yml, vault-id, vault password file, ANSIBLE_VAULT_PASSWORD_FILE, encrypt_string, dynamic inventory, group_vars, host_vars, multi-environment, tagging strategy, idempotency check, ansible-lint, ansible testing, role dependencies, meta/main.yml, jinja2 template, ansible enterprise, ansible riutilizzo, collections namespace, community.general, community.postgresql, geerlingguy, ansible molecule docker, converge, verify, molecule test, ansible check diff, CI ansible, pipeline ansible, vault prod dev, vault-id multipli, ansible role layout, defaults vars differenza, role handler, role template, ansible include_role, ansible import_role, ansible tags, red hat automation platform]
parent: iac/ansible/_index
related: [iac/ansible/fondamentali, iac/terraform/fondamentali, ci-cd/github-actions/_index, security/secret-management/vault]
official_docs: https://docs.ansible.com/ansible/latest/user_guide/playbooks_reuse_roles.html
status: complete
difficulty: intermediate
last_updated: 2026-04-03
---

# Ansible — Roles, Collections e Pattern Enterprise

## Panoramica

I **role** sono l'unità fondamentale di riuso in Ansible: incapsulano task, variabili, template, handler e file in una struttura di directory standardizzata, rendendo il codice trasportabile tra progetti e condivisibile su Ansible Galaxy. Le **collection** sono il livello superiore: un namespace che raggruppa più role, moduli personalizzati, plugin e playbook sotto un'unica entità versionata (`namespace.collection_name`). Mentre un role risolve un singolo problema (es. installare Nginx), una collection risolve un dominio intero (es. `community.postgresql` per tutto ciò che riguarda PostgreSQL). **Ansible Vault** cifra i segreti direttamente nei file YAML del progetto, eliminando la dipendenza da sistemi esterni per i casi d'uso più semplici. Questo documento copre la struttura enterprise di un progetto Ansible: dalla directory layout di un role, al pinning delle dipendenze, alla gestione dei segreti multi-ambiente, fino al testing automatizzato con Molecule.

## Concetti Chiave

### Role vs Collection

| Caratteristica | Role | Collection |
|---|---|---|
| Granularità | Singolo strumento/servizio | Dominio completo |
| Contenuto | tasks, handlers, templates, files, vars, defaults, meta | roles + modules + plugins + playbooks |
| Namespace | `roles/nginx/` | `community.docker`, `amazon.aws` |
| Distribuzione | Ansible Galaxy (legacy) | Ansible Galaxy / Automation Hub |
| Versioning | tag Git del role | versione collection in `galaxy.yml` |
| Import | `roles:` in playbook | `collections:` in playbook o `ansible.cfg` |

!!! note "La Collection è il formato moderno"
    Red Hat ha introdotto le collection con Ansible 2.9. Tutti i nuovi moduli sono distribuiti come collection, non come moduli built-in. `ansible.builtin.*` rimane stabile, ma tutto il resto (community.docker, kubernetes.core, amazon.aws) vive in collection separate. Per i role custom interni, il formato role rimane la scelta corretta.

### `defaults/` vs `vars/` — Differenza Critica

!!! warning "Priorità variabili: errore più comune nei role"
    `defaults/main.yml` ha la **priorità più bassa** nell'intera gerarchia Ansible — è pensato per valori che l'utente del role **può e dovrebbe** overridare. `vars/main.yml` ha **alta priorità** e sovrascrive quasi tutto (incluso group_vars e host_vars) — usarlo solo per costanti interne del role che non devono mai essere cambiate dall'esterno.

```yaml
# roles/nginx/defaults/main.yml
# ✅ Override consentito — l'utente del role può cambiare questi valori
---
nginx_version: "1.24.*"
nginx_port: 80
nginx_ssl_port: 443
nginx_worker_processes: "auto"
nginx_worker_connections: 1024
nginx_client_max_body_size: "10m"
nginx_locations: []
enable_ssl: false
nginx_user: www-data
```

```yaml
# roles/nginx/vars/main.yml
# ❌ Non pensato per override — costanti interne del role
---
nginx_config_dir: /etc/nginx
nginx_sites_available: /etc/nginx/sites-available
nginx_sites_enabled: /etc/nginx/sites-enabled
nginx_pid_file: /var/run/nginx.pid
# Questi path sono fissi per Nginx su Debian/Ubuntu — non ha senso parametrizzarli
```

## Architettura / Come Funziona

### Layout Completo di un Role

```bash
# Genera la struttura con ansible-galaxy
ansible-galaxy role init roles/nginx

# Output — struttura creata automaticamente:
roles/nginx/
├── defaults/
│   └── main.yml          # Variabili con bassa priorità — override-friendly
├── vars/
│   └── main.yml          # Variabili con alta priorità — costanti interne
├── tasks/
│   ├── main.yml          # Entry point — include altri file tasks per organizzazione
│   ├── install.yml       # Task di installazione
│   ├── configure.yml     # Task di configurazione
│   └── debian.yml        # Task OS-specifici (include condizionale)
├── handlers/
│   └── main.yml          # Handler (restart/reload servizi)
├── templates/
│   └── nginx.conf.j2     # Template Jinja2
├── files/
│   └── index.html        # File statici (copiati as-is, senza rendering)
├── meta/
│   └── main.yml          # Metadati Galaxy + dipendenze da altri role
├── tests/
│   ├── inventory          # Inventory per test rapido del role
│   └── test.yml           # Playbook di test minimale
└── README.md
```

### Role Nginx Completo — Esempio Pratico

```yaml
# roles/nginx/tasks/main.yml
---
- name: Include task specifici per OS
  ansible.builtin.include_tasks: "{{ ansible_os_family | lower }}.yml"

- name: Include task di installazione
  ansible.builtin.import_tasks: install.yml

- name: Include task di configurazione
  ansible.builtin.import_tasks: configure.yml
```

```yaml
# roles/nginx/tasks/install.yml
---
- name: Assicura che Nginx sia installato
  ansible.builtin.package:
    name: "nginx={{ nginx_version }}"
    state: present
    update_cache: true
  notify: restart nginx

- name: Assicura che la directory sites-available esista
  ansible.builtin.file:
    path: "{{ nginx_sites_available }}"
    state: directory
    owner: root
    group: root
    mode: '0755'
```

```yaml
# roles/nginx/tasks/configure.yml
---
- name: Deploy configurazione principale Nginx
  ansible.builtin.template:
    src: nginx.conf.j2
    dest: "{{ nginx_config_dir }}/nginx.conf"
    owner: root
    group: root
    mode: '0644'
    validate: "nginx -t -c %s"   # Valida config prima di sovrascrivere
  notify: reload nginx

- name: Rimuovi configurazione default Nginx
  ansible.builtin.file:
    path: "{{ nginx_sites_enabled }}/default"
    state: absent
  notify: reload nginx

- name: Assicura che Nginx sia avviato e abilitato al boot
  ansible.builtin.service:
    name: nginx
    state: started
    enabled: true
```

```yaml
# roles/nginx/handlers/main.yml
---
- name: restart nginx
  ansible.builtin.service:
    name: nginx
    state: restarted

- name: reload nginx
  ansible.builtin.service:
    name: nginx
    state: reloaded

# Nota: reload è preferibile a restart per zero-downtime config reload
```

```jinja2
{# roles/nginx/templates/nginx.conf.j2 #}
user {{ nginx_user }};
worker_processes {{ nginx_worker_processes }};
pid {{ nginx_pid_file }};

events {
    worker_connections {{ nginx_worker_connections }};
    multi_accept on;
}

http {
    sendfile on;
    tcp_nopush on;
    keepalive_timeout 65;
    client_max_body_size {{ nginx_client_max_body_size }};

    include /etc/nginx/mime.types;
    default_type application/octet-stream;

    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent"';

    access_log /var/log/nginx/access.log main;
    error_log  /var/log/nginx/error.log warn;

    server {
        listen {{ nginx_port }} default_server;
        server_name {{ inventory_hostname }};

        {% if enable_ssl %}
        listen {{ nginx_ssl_port }} ssl;
        ssl_certificate /etc/ssl/certs/{{ inventory_hostname }}.crt;
        ssl_certificate_key /etc/ssl/private/{{ inventory_hostname }}.key;
        ssl_protocols TLSv1.2 TLSv1.3;
        {% endif %}

        {% for location in nginx_locations %}
        location {{ location.path }} {
            proxy_pass {{ location.backend }};
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_connect_timeout {{ location.timeout | default(30) }}s;
        }
        {% endfor %}
    }
}
```

```yaml
# roles/nginx/meta/main.yml
---
galaxy_info:
  author: team-platform
  description: Installa e configura Nginx come reverse proxy
  license: MIT
  min_ansible_version: "2.14"
  platforms:
    - name: Ubuntu
      versions: ["22.04", "24.04"]
    - name: Debian
      versions: ["11", "12"]

# Dipendenze da altri role — vengono eseguite PRIMA di questo role
dependencies:
  - role: common          # Installa pacchetti di base, configura NTP, ecc.
  - role: certbot         # Gestisce certificati SSL
    when: enable_ssl | default(false)
```

## Ansible Galaxy e Collections

### Differenza Role vs Collection

```bash
# ── ROLE SINGOLO ──────────────────────────────────────────────────
# Installa un singolo role da Galaxy
ansible-galaxy role install geerlingguy.nginx
ansible-galaxy role install geerlingguy.postgresql --version 3.5.0

# I role vengono installati in roles/ (o in ~/.ansible/roles se globale)
# Struttura: roles/geerlingguy.nginx/tasks/main.yml, ecc.

# ── COLLECTION ────────────────────────────────────────────────────
# Installa una collection (formato moderno)
ansible-galaxy collection install community.postgresql
ansible-galaxy collection install amazon.aws:6.5.0

# Le collection vengono installate in collections/ansible_collections/
# Struttura: collections/ansible_collections/community/postgresql/
```

### requirements.yml — Pinning per Riproducibilità

!!! tip "Versiona sempre le dipendenze"
    Senza version pinning, `ansible-galaxy install -r requirements.yml` può installare versioni diverse in momenti diversi, rompendo il build. Specifica sempre versioni esatte in produzione e range compatibili in sviluppo.

```yaml
# requirements.yml — dipendenze del progetto
---
collections:
  # Versione esatta — per ambienti di produzione
  - name: community.docker
    version: "3.8.0"

  # Range compatibile — accetta patch e minor, non major
  - name: kubernetes.core
    version: ">=2.4.0,<3.0.0"

  # Da repository privato (Automation Hub aziendale)
  - name: myorg.internal_tools
    source: https://automation-hub.internal/api/galaxy/
    version: "1.2.0"

  # Dalla community
  - name: community.postgresql
    version: "3.4.0"
  - name: amazon.aws
    version: "7.1.0"
  - name: community.general
    version: ">=8.0.0"

roles:
  # Role community da Galaxy
  - name: geerlingguy.nginx
    version: "3.2.0"

  # Role da repository Git privato
  - name: myorg.hardening
    src: https://github.com/myorg/ansible-role-hardening
    version: "v2.1.0"
    scm: git
```

```bash
# Installazione completa delle dipendenze
ansible-galaxy install -r requirements.yml
ansible-galaxy collection install -r requirements.yml

# Oppure in un unico comando (Ansible >= 2.10)
ansible-galaxy install -r requirements.yml --roles-path ./roles

# Verifica cosa è installato
ansible-galaxy collection list
ansible-galaxy role list
```

### Private Automation Hub

**Ansible Automation Hub** (Red Hat) e la versione open source **Pulp/Galaxy NG** permettono di ospitare internamente collection aziendali e mirror di collection pubbliche.

```ini
# ansible.cfg — configurazione per Automation Hub privato
[galaxy]
server_list = automation_hub, release_galaxy

[galaxy_server.automation_hub]
url = https://automation-hub.internal/api/galaxy/
auth_url = https://sso.internal/auth/realms/ansible/protocol/openid-connect/token
token = <token_generato_dall_hub>

[galaxy_server.release_galaxy]
url = https://galaxy.ansible.com/
# Nessun token — accesso pubblico
```

```bash
# Pubblica una collection sull'hub interno
ansible-galaxy collection build                    # Crea .tar.gz
ansible-galaxy collection publish myorg-tools-1.0.0.tar.gz \
  --server automation_hub
```

## Ansible Vault — Gestione Segreti

### Crittografia di File vs Singole Stringhe

```bash
# ── FILE VAULT ────────────────────────────────────────────────────
# Crea un file cifrato da zero (apre editor)
ansible-vault create inventories/production/group_vars/all/vault.yml

# Cifra un file esistente (in-place)
ansible-vault encrypt inventories/production/group_vars/all/secrets.yml

# Edita un file cifrato (decifrare → editor → cifrare)
ansible-vault edit inventories/production/group_vars/all/vault.yml

# Visualizza senza modificare
ansible-vault view inventories/production/group_vars/all/vault.yml

# Decifra un file (da usare solo in ambienti sicuri)
ansible-vault decrypt inventories/production/group_vars/all/vault.yml

# ── ENCRYPT_STRING — valori inline ────────────────────────────────
# Cifra una singola stringa e produce il blocco YAML da incollare
ansible-vault encrypt_string 'SuperSecret123!' --name 'db_password'

# Output da incollare nel playbook/vars:
# db_password: !vault |
#   $ANSIBLE_VAULT;1.1;AES256
#   38306231343437616337356537...
```

```yaml
# inventories/production/group_vars/all/vault.yml
# (file cifrato con ansible-vault encrypt)
---
vault_db_password: "SuperSecret123!"
vault_api_key: "abc123def456ghi789"
vault_ssh_private_key: |
  -----BEGIN OPENSSH PRIVATE KEY-----
  b3BlbnNzaC1rZXktdjEAAAA...
  -----END OPENSSH PRIVATE KEY-----
```

```yaml
# inventories/production/group_vars/all/vars.yml
# (file in chiaro — referenzia le variabili vault con prefisso vault_)
---
db_password: "{{ vault_db_password }}"
api_key: "{{ vault_api_key }}"
# Pattern consigliato: separa vars (chiaro) da vault (cifrato)
# I file in chiaro documentano quali segreti esistono senza esporli
```

### Vault-ID Multipli — Ambienti Separati

I **vault-id** permettono di avere password diverse per ambienti diversi nello stesso progetto, senza mescolare i segreti.

```bash
# Cifra con vault-id specifico per ambiente
ansible-vault encrypt_string 'ProdSecret' \
  --vault-id prod@~/.vault-pass-prod \
  --name 'db_password'
# Output: $ANSIBLE_VAULT;1.2;AES256;prod  ← label "prod" nel ciphertext

ansible-vault encrypt_string 'StagingSecret' \
  --vault-id staging@~/.vault-pass-staging \
  --name 'db_password'

# Esegui playbook con entrambe le password (Ansible decifra in automatico
# usando il vault-id corretto presente nel ciphertext)
ansible-playbook site.yml \
  --vault-id prod@~/.vault-pass-prod \
  --vault-id staging@~/.vault-pass-staging
```

### Integrazione CI/CD

!!! warning "Non committare mai la vault password"
    La vault password non deve mai essere in un file committato nel repository. Usa variabili d'ambiente del CI/CD system (GitHub Actions secrets, GitLab CI variables, Jenkins credentials) e scrivi il valore in un file temporaneo a runtime.

```yaml
# .github/workflows/deploy.yml
---
name: Deploy Ansible

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python e Ansible
        run: |
          pip install ansible ansible-lint

      - name: Installa dipendenze Galaxy
        run: ansible-galaxy install -r requirements.yml

      - name: Scrivi vault password da secret CI
        run: echo "${{ secrets.ANSIBLE_VAULT_PASS }}" > /tmp/.vault-pass
        # File temporaneo — non viene committato

      - name: Dry run (check + diff)
        env:
          ANSIBLE_VAULT_PASSWORD_FILE: /tmp/.vault-pass
        run: |
          ansible-playbook -i inventories/production/ site.yml \
            --check --diff

      - name: Deploy
        if: github.ref == 'refs/heads/main'
        env:
          ANSIBLE_VAULT_PASSWORD_FILE: /tmp/.vault-pass
        run: |
          ansible-playbook -i inventories/production/ site.yml

      - name: Rimuovi vault password file
        if: always()
        run: rm -f /tmp/.vault-pass
```

## Configurazione & Pratica

### Struttura Progetto Multi-Environment Enterprise

```
ansible-project/
├── ansible.cfg                          # Config progetto (non globale)
├── requirements.yml                     # Dipendenze Galaxy/Hub
├── site.yml                             # Playbook master (include altri)
│
├── inventories/
│   ├── production/
│   │   ├── hosts.yml                    # Host produzione
│   │   ├── group_vars/
│   │   │   ├── all/
│   │   │   │   ├── vars.yml             # Variabili comuni (chiaro)
│   │   │   │   └── vault.yml            # Segreti produzione (cifrato)
│   │   │   ├── webservers/
│   │   │   │   ├── vars.yml
│   │   │   │   └── vault.yml
│   │   │   └── databases/
│   │   │       └── vars.yml
│   │   └── host_vars/
│   │       └── web1.prod.example.com/
│   │           └── vars.yml             # Override specifico per host
│   └── staging/
│       ├── hosts.yml
│       └── group_vars/
│           └── all/
│               ├── vars.yml
│               └── vault.yml            # Password staging (diversa)
│
├── playbooks/
│   ├── site.yml                         # Entry point master
│   ├── webservers.yml
│   ├── databases.yml
│   └── maintenance/
│       ├── patching.yml
│       └── rotate-credentials.yml
│
└── roles/
    ├── common/                          # Role base — applicato a tutti i nodi
    ├── nginx/
    ├── postgresql/
    └── app-deploy/
```

```yaml
# site.yml — playbook master
---
- name: Apply common role to all hosts
  hosts: all
  roles:
    - common

- import_playbook: playbooks/webservers.yml
- import_playbook: playbooks/databases.yml
```

### Group Vars e Host Vars — Gerarchia Override

```yaml
# inventories/production/group_vars/all/vars.yml
---
env: production
log_level: warn
app_replicas: 3
monitoring_enabled: true
```

```yaml
# inventories/production/group_vars/webservers/vars.yml
---
nginx_port: 443
enable_ssl: true
nginx_worker_processes: 4
# Override per il gruppo webservers — sovrascrive group_vars/all
```

```yaml
# inventories/production/host_vars/web1.prod.example.com/vars.yml
---
nginx_worker_connections: 2048
# Override per il singolo host — ha la priorità più alta tra i file di inventory
```

### Dynamic Inventory — Plugin AWS

```yaml
# inventories/production/hosts.aws_ec2.yml
# Nomina il file *.aws_ec2.yml — Ansible riconosce automaticamente il plugin
---
plugin: amazon.aws.aws_ec2
regions:
  - eu-west-1
  - eu-central-1

filters:
  "tag:Environment": production
  "tag:ManagedBy": ansible
  instance-state-name: running

# Raggruppa i nodi per tag
keyed_groups:
  - key: tags.Role
    prefix: role_
    separator: ""
  - key: tags.Service
    prefix: service_

# Variabili da aggiungere a ogni host
compose:
  ansible_host: public_ip_address
  ansible_user: "'ec2-user'"
```

```bash
# Verifica il dynamic inventory senza eseguire nulla
ansible-inventory -i inventories/production/ --list
ansible-inventory -i inventories/production/ --graph
```

### Tagging Strategy — Esecuzione Selettiva

```yaml
# roles/nginx/tasks/configure.yml
---
- name: Deploy configurazione Nginx
  ansible.builtin.template:
    src: nginx.conf.j2
    dest: /etc/nginx/nginx.conf
  tags:
    - nginx
    - config
    - webservers

- name: Aggiorna certificati SSL
  ansible.builtin.copy:
    src: "{{ cert_file }}"
    dest: /etc/ssl/certs/
  tags:
    - nginx
    - ssl
    - certificates
```

```bash
# Esegui solo task con tag "config" (es. solo push di configurazioni)
ansible-playbook -i inventories/production/ site.yml --tags config

# Esegui solo task Nginx, saltando certificati
ansible-playbook -i inventories/production/ site.yml \
  --tags nginx --skip-tags ssl

# Lista tutti i tag presenti nel playbook
ansible-playbook -i inventories/production/ site.yml --list-tags
```

## Testing con Molecule

### Setup e Struttura

```bash
# Installa Molecule con driver Docker
pip install molecule molecule-docker ansible-lint

# Crea scenario di test per un role esistente
cd roles/nginx
molecule init scenario --driver-name docker

# Struttura creata:
# roles/nginx/molecule/
# └── default/
#     ├── molecule.yml        # Config scenario (driver, platforms)
#     ├── converge.yml        # Playbook che applica il role
#     ├── verify.yml          # Playbook di verifica post-convergenza
#     └── prepare.yml         # Playbook opzionale di preparazione
```

```yaml
# roles/nginx/molecule/default/molecule.yml
---
dependency:
  name: galaxy
  options:
    requirements-file: requirements.yml

driver:
  name: docker

platforms:
  - name: ubuntu-22
    image: geerlingguy/docker-ubuntu2204-ansible:latest
    pre_build_image: true
    command: /lib/systemd/systemd   # Abilita systemd nel container
    privileged: true
    volumes:
      - /sys/fs/cgroup:/sys/fs/cgroup:rw
    cgroupns_mode: host

  - name: debian-12
    image: geerlingguy/docker-debian12-ansible:latest
    pre_build_image: true
    command: /lib/systemd/systemd
    privileged: true

provisioner:
  name: ansible
  config_options:
    defaults:
      callbacks_enabled: profile_tasks

verifier:
  name: ansible
```

```yaml
# roles/nginx/molecule/default/converge.yml
---
- name: Converge
  hosts: all
  become: true

  vars:
    nginx_port: 80
    nginx_locations:
      - path: /api
        backend: http://localhost:8080

  roles:
    - role: nginx
```

```yaml
# roles/nginx/molecule/default/verify.yml
---
- name: Verify
  hosts: all
  become: true
  gather_facts: false

  tasks:
    - name: Verifica che Nginx sia in esecuzione
      ansible.builtin.service_facts:

    - name: Assert che nginx.service sia active
      ansible.builtin.assert:
        that:
          - "'nginx' in services"
          - "services['nginx'].state == 'running'"
          - "services['nginx'].status == 'enabled'"
        fail_msg: "Nginx non è in esecuzione o non è abilitato"

    - name: Verifica che la porta 80 risponda
      ansible.builtin.uri:
        url: http://localhost:80
        status_code: [200, 301, 302, 404]
        # 404 è accettabile — il server risponde, anche se la pagina non esiste
      register: nginx_response

    - name: Verifica configurazione Nginx sintatticamente valida
      ansible.builtin.command: nginx -t
      changed_when: false
      register: nginx_test
```

```bash
# Ciclo completo di test
molecule test

# Equivale a:
# molecule create       → Crea i container
# molecule prepare      → Esegue prepare.yml (opzionale)
# molecule converge     → Esegue converge.yml (applica il role)
# molecule idempotency  → Esegue converge.yml una seconda volta (0 changed?)
# molecule verify       → Esegue verify.yml (asserzioni)
# molecule destroy      → Distrugge i container

# Debug — mantieni i container dopo i test per ispezione
molecule converge
molecule login --host ubuntu-22   # Shell interattiva nel container
molecule destroy
```

### Pipeline CI per Role con Molecule

```yaml
# .github/workflows/role-ci.yml
---
name: Role CI

on:
  push:
    paths:
      - "roles/**"
  pull_request:
    paths:
      - "roles/**"

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Installa dipendenze
        run: pip install ansible ansible-lint yamllint
      - name: Lint YAML
        run: yamllint roles/
      - name: Lint Ansible
        run: ansible-lint roles/

  molecule-test:
    runs-on: ubuntu-latest
    needs: lint
    strategy:
      matrix:
        role: [nginx, postgresql, common]  # Test paralleli per role

    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Installa dipendenze
        run: pip install ansible molecule molecule-docker
      - name: Esegui Molecule
        working-directory: roles/${{ matrix.role }}
        run: molecule test
```

## Best Practices

!!! tip "Convenzioni per role riutilizzabili"
    Un role ben progettato ha tutte le variabili in `defaults/`, non usa path hardcodati, e funziona su almeno due distribuzioni Linux diverse. Se un role contiene logica solo per un progetto, non merita di essere un role — mettila direttamente nel playbook.

### Regole per Role Enterprise

- **Un role = una responsabilità**: `nginx` installa Nginx, `ssl-certs` gestisce i certificati. Non mescolare.
- **Prefissa le variabili** con il nome del role: `nginx_port`, non `port`. Evita collisioni con altri role.
- **Usa `import_tasks` per task fissi** e `include_tasks` per task condizionali (es. per OS diversi): `import_tasks` è risolto a parse-time (più efficiente), `include_tasks` a runtime (necessario per variabili nel nome file).
- **Gestisci idempotenza**: ogni task deve poter girare 2+ volte senza effetti collaterali. Controlla con `molecule test` che il secondo `converge` dia 0 `changed`.

```yaml
# ✅ Uso corretto import_tasks vs include_tasks
tasks:
  # Import — risolto a parse-time, sempre eseguito
  - ansible.builtin.import_tasks: install.yml
    tags: install

  # Include — risolto a runtime, per OS-specific o condizionali
  - ansible.builtin.include_tasks: "{{ ansible_os_family | lower }}.yml"
    when: ansible_os_family in ['Debian', 'RedHat']
```

### Idempotency Check in CI

```bash
# In CI, esegui sempre con --check --diff prima del deploy reale
# Rileva configurational drift e cambiamenti non intenzionali
ansible-playbook -i inventories/production/ site.yml --check --diff

# Verifica idempotency manualmente
ansible-playbook -i inventories/production/ site.yml   # Prima esecuzione
ansible-playbook -i inventories/production/ site.yml   # Seconda esecuzione
# Se la seconda esecuzione mostra "changed=0", il playbook è idempotente
```

### Anti-Pattern Enterprise

| Anti-Pattern | Problema | Soluzione |
|---|---|---|
| Role con 200+ task in un unico file | Non manutenibile, difficile da testare | Spezza in `include_tasks` per funzionalità |
| Password in `defaults/main.yml` | Esposte in chiaro nel repo | Usa Vault + `group_vars/all/vault.yml` |
| Role senza `meta/main.yml` | Dipendenze implicite, ordine di esecuzione non garantito | Dichiara sempre le dipendenze in `meta/` |
| `become: true` a livello playbook | Privilegio escalation ovunque | Usa `become: true` solo nei task che ne hanno bisogno |
| Nessun tagging nei task | Impossibile eseguire subset selettivi | Tagga ogni task logicamente (deploy, config, ssl, ...) |
| Dynamic inventory senza caching | Query API cloud ad ogni esecuzione | Configura `cache: true` nel plugin e `cache_timeout` |

## Troubleshooting

### Role non trovato

```bash
# Sintomo:
# ERROR! the role 'nginx' was not found

# Causa 1: roles_path non configurato
# Soluzione: verifica ansible.cfg
cat ansible.cfg | grep roles_path
# Deve contenere: roles_path = roles/

# Causa 2: il role è installato globalmente ma non localmente
ansible-galaxy role list  # Mostra dove sono installati i role
# Installa localmente nel progetto
ansible-galaxy role install geerlingguy.nginx -p ./roles/
```

### Vault: Decryption Failed

```bash
# Sintomo:
# ERROR! Decryption failed (no vault secrets would decrypt)

# Causa 1: password errata o file password vuoto
cat ~/.vault-pass      # Verifica che non sia vuoto
echo -n "" | wc -c    # 0 = file vuoto — problema!

# Causa 2: vault-id label non corrisponde
# Il ciphertext ha label "prod" ma stai usando vault-id "staging"
ansible-vault view vault.yml --vault-id prod@~/.vault-pass-prod

# Causa 3: ANSIBLE_VAULT_PASSWORD_FILE punta a file inesistente
echo $ANSIBLE_VAULT_PASSWORD_FILE
ls -la $ANSIBLE_VAULT_PASSWORD_FILE
```

### Molecule: Container non avvia systemd

```bash
# Sintomo:
# Failed to connect to bus: No such file or directory
# (quando il role gestisce servizi systemd)

# Soluzione: usa immagini con systemd preconfigurato
# In molecule.yml usa le immagini di geerlingguy che hanno systemd abilitato:
# geerlingguy/docker-ubuntu2204-ansible
# geerlingguy/docker-debian12-ansible
# E aggiungi privileged: true + volumes per cgroup
```

### Role non idempotente — changed=1 alla seconda esecuzione

```bash
# Sintomo: molecule idempotency check fallisce

# Debug: esegui converge due volte e confronta l'output
molecule converge 2>&1 | grep -E "changed|TASK"

# Cause comuni:
# 1. Uso di command/shell senza changed_when: false
- ansible.builtin.command: /usr/local/bin/setup.sh
  changed_when: false   # ← aggiungere questo

# 2. Template che aggiunge timestamp nell'output
{# Evita: #}
# Generated at {{ ansible_date_time.iso8601 }}
{# Il timestamp cambia ad ogni esecuzione → sempre "changed" #}

# 3. File copiati con permessi che cambiano
- ansible.builtin.copy:
    src: app.conf
    dest: /etc/app.conf
    mode: '0644'   # ← specificare sempre mode esplicito
```

### Collection non trovata dopo installazione

```bash
# Sintomo:
# ERROR! couldn't resolve module/action 'community.postgresql.postgresql_db'

# Verifica path installazione
ansible-galaxy collection list | grep postgresql

# Verifica collections_path in ansible.cfg
[defaults]
collections_path = ./collections:~/.ansible/collections

# Reinstalla nella directory del progetto
ansible-galaxy collection install community.postgresql -p ./collections/
```

## Relazioni

??? info "Ansible — Fondamentali"
    Questo documento approfondisce i role e le collection. Per la base di Ansible (playbook, inventory, moduli, template Jinja2, handlers, variabili), consulta il documento fondamentali.

    **Approfondimento completo →** [Ansible Fondamentali](fondamentali.md)

??? info "Terraform — Integrazione IaC"
    Il pattern tipico enterprise combina Terraform (provisioning infrastruttura) e Ansible (configurazione software). L'output di Terraform (IP, nomi host) alimenta il dynamic inventory di Ansible via terraform-inventory o plugin nativi.

    **Approfondimento completo →** [Terraform Fondamentali](../terraform/fondamentali.md)

??? info "HashiCorp Vault — Segreti Enterprise"
    Ansible Vault copre i casi d'uso base di gestione segreti nel codice. Per secret rotation automatica, PKI, database credentials dinamiche e audit trail centralizzato, HashiCorp Vault è la soluzione enterprise complementare.

    **Approfondimento completo →** [HashiCorp Vault](../../security/secret-management/vault.md)

??? info "GitHub Actions — Pipeline CI/CD"
    L'integrazione Ansible + GitHub Actions permette di eseguire `--check --diff` automaticamente su ogni PR e il deploy reale su merge in main. Vedi esempi di workflow in questo documento e la guida completa alla pipeline CI/CD.

    **Approfondimento completo →** [GitHub Actions](../../ci-cd/github-actions/_index.md)

## Riferimenti

- [Ansible Role — Documentazione Ufficiale](https://docs.ansible.com/ansible/latest/user_guide/playbooks_reuse_roles.html)
- [Ansible Collections Guide](https://docs.ansible.com/ansible/latest/collections_guide/index.html)
- [Ansible Vault — Documentazione](https://docs.ansible.com/ansible/latest/vault_guide/index.html)
- [Molecule — Framework di Testing](https://ansible.readthedocs.io/projects/molecule/)
- [Ansible Lint](https://ansible-lint.readthedocs.io) — linter statico per playbook e role
- [Ansible Galaxy](https://galaxy.ansible.com) — repository pubblico di role e collection
- [Red Hat Ansible Automation Platform](https://www.redhat.com/en/technologies/management/ansible) — piattaforma enterprise con Automation Hub privato
- [geerlingguy Docker Images](https://github.com/geerlingguy/docker-ubuntu2204-ansible) — immagini Docker con systemd per Molecule
