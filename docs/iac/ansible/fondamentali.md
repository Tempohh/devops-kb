---
title: "Ansible — Fondamentali"
slug: ansible-fondamentali
category: iac
tags: [ansible, iac, configuration-management, automation, agentless, playbook, yaml]
search_keywords: [ansible, playbook, inventory, roles, vault, moduli, configuration management, agentless, ssh, yaml, automation, provisioning, idempotente, idempotency, task, handler, template, jinja2, galaxy, collections, become, privilege escalation, ad-hoc, ansible-playbook, ansible-vault, ansible-galaxy, red hat]
parent: iac/ansible/_index
related: [iac/terraform/fondamentali, iac/terraform/state-management, containers/kubernetes/workloads, ci-cd/pipeline/github-actions]
official_docs: https://docs.ansible.com
status: complete
difficulty: intermediate
last_updated: 2026-03-24
---

# Ansible — Fondamentali

## Panoramica

Ansible è lo strumento di **configuration management agentless** più diffuso nel settore DevOps. A differenza di Puppet o Chef, non richiede l'installazione di agent sui nodi: la comunicazione avviene via **SSH** (Linux/macOS) o **WinRM** (Windows), con le credenziali già disponibili. Si descrive lo stato desiderato del sistema in file YAML chiamati **playbook**, e Ansible garantisce che i nodi raggiungano quello stato in modo **idempotente** — eseguire lo stesso playbook più volte produce sempre lo stesso risultato. Ansible è complementare a Terraform: Terraform provisiona l'infrastruttura (VM, reti, database), Ansible configura il software sopra quelle risorse (installa pacchetti, configura servizi, deploy applicazioni). Red Hat ne ha acquisito lo sviluppo e offre anche **Ansible Automation Platform** per ambienti enterprise.

## Concetti Chiave

!!! note "Architettura Agentless"
    Il control node (dove gira Ansible) si connette ai managed nodes via SSH. Non c'è daemon da installare: bastano Python e SSH sul nodo target.

### Inventory

L'inventory definisce i nodi gestiti da Ansible. Può essere statico (file INI o YAML) o dinamico (script o plugin che interrogano API cloud).

```ini
# inventory/hosts.ini — Inventory statico INI
[webservers]
web1.example.com
web2.example.com ansible_user=ubuntu ansible_port=2222

[databases]
db1.example.com ansible_host=10.0.1.10

[production:children]
webservers
databases

[all:vars]
ansible_user=ec2-user
ansible_ssh_private_key_file=~/.ssh/prod.pem
```

```yaml
# inventory/hosts.yaml — Inventory statico YAML
all:
  children:
    webservers:
      hosts:
        web1.example.com:
          ansible_user: ubuntu
        web2.example.com:
    databases:
      hosts:
        db1.example.com:
          ansible_host: 10.0.1.10
  vars:
    ansible_ssh_private_key_file: ~/.ssh/prod.pem
```

### Playbook

Un playbook è un file YAML che definisce una serie di **play**. Ogni play mappa un gruppo di host a una lista di **task**.

```yaml
# deploy-webserver.yaml
---
- name: Configura web server Nginx
  hosts: webservers
  become: true          # esegui come sudo
  vars:
    nginx_port: 80
    app_dir: /var/www/html

  tasks:
    - name: Installa Nginx
      ansible.builtin.package:
        name: nginx
        state: present

    - name: Crea directory applicazione
      ansible.builtin.file:
        path: "{{ app_dir }}"
        state: directory
        owner: www-data
        group: www-data
        mode: '0755'

    - name: Deploy configurazione Nginx
      ansible.builtin.template:
        src: templates/nginx.conf.j2
        dest: /etc/nginx/nginx.conf
        owner: root
        group: root
        mode: '0644'
      notify: restart nginx

    - name: Assicura che Nginx sia in esecuzione e abilitato
      ansible.builtin.service:
        name: nginx
        state: started
        enabled: true

  handlers:
    - name: restart nginx
      ansible.builtin.service:
        name: nginx
        state: restarted
```

### Moduli

I moduli sono le unità di lavoro di Ansible. Ogni task invoca un modulo. Esistono centinaia di moduli built-in e migliaia di moduli aggiuntivi tramite Ansible Galaxy.

| Modulo | Categoria | Uso |
|---|---|---|
| `ansible.builtin.package` | Sistema | Gestione pacchetti (yum, apt, dnf) |
| `ansible.builtin.service` | Sistema | Gestione servizi systemd |
| `ansible.builtin.file` | Filesystem | Crea file, directory, symlink |
| `ansible.builtin.copy` | Filesystem | Copia file statici |
| `ansible.builtin.template` | Filesystem | Copia file con rendering Jinja2 |
| `ansible.builtin.user` | Sistema | Gestione utenti |
| `ansible.builtin.command` | Esecuzione | Esegue comando (no shell) |
| `ansible.builtin.shell` | Esecuzione | Esegue comando con shell |
| `ansible.builtin.git` | SCM | Clone/update repository git |
| `ansible.builtin.uri` | Web | HTTP requests |
| `ansible.builtin.debug` | Debug | Stampa variabili/messaggi |
| `ansible.builtin.assert` | Test | Verifica condizioni |
| `community.docker.docker_container` | Docker | Gestione container |
| `kubernetes.core.k8s` | Kubernetes | Applica manifest K8s |
| `amazon.aws.ec2_instance` | AWS | Gestione istanze EC2 |

### Variabili e Precedenza

Ansible ha un sistema di precedenza variabili (dal più basso al più alto):

```
1. Default role (role/defaults/main.yaml)
2. Inventory group_vars/all
3. Inventory group_vars/[gruppo]
4. Inventory host_vars/[host]
5. Facts raccolti (gather_facts)
6. Variabili play (vars:)
7. Variabili extra file (-e @file.yaml)
8. Variabili extra CLI (-e "var=value") ← massima priorità
```

```yaml
# group_vars/webservers.yaml
nginx_version: "1.24"
app_port: 8080

# host_vars/web1.example.com.yaml
app_port: 9090  # override solo per web1
```

### Handlers

Gli handler sono task speciali eseguiti solo se notificati. Vengono eseguiti una sola volta alla fine del play, anche se notificati più volte — ideali per riavvii di servizi.

```yaml
tasks:
  - name: Aggiorna config applicazione
    ansible.builtin.template:
      src: app.conf.j2
      dest: /etc/app/app.conf
    notify:
      - reload app
      - notify monitoring

handlers:
  - name: reload app
    ansible.builtin.service:
      name: myapp
      state: reloaded

  - name: notify monitoring
    ansible.builtin.uri:
      url: "https://monitoring.internal/deploy"
      method: POST
```

## Architettura / Come Funziona

### Flusso di esecuzione

```
Control Node
     │
     │  SSH / WinRM
     ▼
Managed Node
  1. Ansible copia il modulo (Python) in /tmp su ogni nodo
  2. Esegue il modulo
  3. Raccoglie il risultato (changed/ok/failed)
  4. Rimuove il file temporaneo
  5. Riporta il risultato al control node
```

### Facts

I facts sono variabili raccolte automaticamente all'inizio di ogni play (se `gather_facts: true`, default). Includono OS, IP, CPU, memoria, filesystem, ecc.

```yaml
- name: Mostra facts del sistema
  ansible.builtin.debug:
    msg: "OS: {{ ansible_os_family }}, IP: {{ ansible_default_ipv4.address }}"
```

```bash
# Visualizza tutti i facts di un host
ansible web1.example.com -i inventory/ -m setup
ansible web1.example.com -i inventory/ -m setup -a "filter=ansible_os_family"
```

### Struttura Progetto Consigliata

```
progetto/
├── ansible.cfg               # Configurazione Ansible
├── inventory/
│   ├── production/
│   │   ├── hosts.yaml
│   │   ├── group_vars/
│   │   │   ├── all.yaml
│   │   │   └── webservers.yaml
│   │   └── host_vars/
│   │       └── web1.example.com.yaml
│   └── staging/
│       └── hosts.yaml
├── playbooks/
│   ├── site.yaml             # Playbook master
│   ├── webservers.yaml
│   └── databases.yaml
├── roles/
│   ├── nginx/
│   └── postgresql/
└── requirements.yaml         # Dipendenze Galaxy
```

```ini
# ansible.cfg
[defaults]
inventory = inventory/production/
roles_path = roles/
collections_path = collections/
host_key_checking = False
stdout_callback = yaml
forks = 10

[privilege_escalation]
become = True
become_method = sudo
```

## Roles

I role sono l'unità di riuso di Ansible. Incapsulano task, variabili, template, handler e file in una struttura standardizzata.

```
roles/nginx/
├── defaults/
│   └── main.yaml        # Variabili default (override consentito)
├── vars/
│   └── main.yaml        # Variabili fisse (override sconsigliato)
├── tasks/
│   └── main.yaml        # Lista task principali
├── handlers/
│   └── main.yaml        # Handler del role
├── templates/
│   └── nginx.conf.j2    # Template Jinja2
├── files/
│   └── index.html       # File statici
├── meta/
│   └── main.yaml        # Metadati e dipendenze da altri roles
└── README.md
```

```yaml
# roles/nginx/tasks/main.yaml
---
- name: Installa Nginx
  ansible.builtin.package:
    name: "nginx={{ nginx_version }}"
    state: present

- name: Include tasks per OS specifico
  ansible.builtin.include_tasks: "{{ ansible_os_family }}.yaml"

- name: Deploy configurazione
  ansible.builtin.template:
    src: nginx.conf.j2
    dest: /etc/nginx/nginx.conf
  notify: restart nginx
```

```yaml
# Utilizzo di un role in un playbook
- name: Setup web servers
  hosts: webservers
  roles:
    - role: nginx
      vars:
        nginx_version: "1.24.*"
    - role: certbot
      when: enable_ssl | default(false)
```

### Ansible Galaxy & Collections

Galaxy è il repository pubblico di role e collection. Le **collection** sono il formato moderno (raggruppa moduli, plugin, role).

```yaml
# requirements.yaml
---
collections:
  - name: community.docker
    version: ">=3.4.0"
  - name: kubernetes.core
    version: "2.4.0"
  - name: amazon.aws
    version: ">=6.0.0"

roles:
  - name: geerlingguy.nginx
    version: "3.2.0"
```

```bash
# Installa dipendenze
ansible-galaxy install -r requirements.yaml
ansible-galaxy collection install -r requirements.yaml
```

## Ansible Vault

Vault cifra dati sensibili (password, chiavi API, certificati) direttamente nei file YAML.

```bash
# Crea file cifrato
ansible-vault create secrets.yaml

# Cifra file esistente
ansible-vault encrypt vars/secrets.yaml

# Edita file cifrato
ansible-vault edit vars/secrets.yaml

# Visualizza file cifrato
ansible-vault view vars/secrets.yaml

# Decifra file cifrato
ansible-vault decrypt vars/secrets.yaml

# Esegui playbook con vault
ansible-playbook site.yaml --ask-vault-pass
ansible-playbook site.yaml --vault-password-file ~/.vault_pass

# Cifra singolo valore (inline)
ansible-vault encrypt_string 'my_secret_password' --name 'db_password'
```

```yaml
# vars/secrets.yaml (file vault)
---
db_password: !vault |
  $ANSIBLE_VAULT;1.1;AES256
  38306231...

# Oppure: cifra l'intero file con ansible-vault encrypt
db_password: "SuperSecretPassword123"
api_key: "abc123def456"
```

!!! warning "Vault Password in CI/CD"
    Non hardcodare la vault password nei pipeline. Usa variabili d'ambiente (`ANSIBLE_VAULT_PASSWORD_FILE`) o secret manager (AWS Secrets Manager, HashiCorp Vault).

## Configurazione & Pratica

### Comandi Principali

```bash
# Test connettività (ad-hoc ping)
ansible all -i inventory/ -m ping
ansible webservers -i inventory/production/ -m ping

# Esegui comando ad-hoc
ansible webservers -i inventory/ -m command -a "uptime"
ansible webservers -i inventory/ -m shell -a "df -h | grep /var"

# Esegui playbook
ansible-playbook -i inventory/ playbooks/site.yaml
ansible-playbook -i inventory/ playbooks/site.yaml --limit web1.example.com
ansible-playbook -i inventory/ playbooks/site.yaml --tags "nginx,ssl"
ansible-playbook -i inventory/ playbooks/site.yaml --skip-tags "debug"

# Dry run (check mode)
ansible-playbook -i inventory/ playbooks/site.yaml --check

# Verbose output
ansible-playbook -i inventory/ playbooks/site.yaml -v    # verbose
ansible-playbook -i inventory/ playbooks/site.yaml -vvv  # molto verbose

# Lista host che verrebbero impattati
ansible-playbook -i inventory/ playbooks/site.yaml --list-hosts

# Lista task che verrebbero eseguiti
ansible-playbook -i inventory/ playbooks/site.yaml --list-tasks
```

### Template Jinja2

Ansible usa Jinja2 per i template, con accesso a tutte le variabili e i facts.

```jinja2
{# templates/nginx.conf.j2 #}
user www-data;
worker_processes {{ ansible_processor_vcpus | default(2) }};

http {
    server {
        listen {{ nginx_port | default(80) }};
        server_name {{ inventory_hostname }};

        root {{ app_dir }};

        {% if enable_ssl | default(false) %}
        listen 443 ssl;
        ssl_certificate /etc/ssl/certs/{{ inventory_hostname }}.crt;
        {% endif %}

        {% for location in nginx_locations | default([]) %}
        location {{ location.path }} {
            proxy_pass {{ location.backend }};
        }
        {% endfor %}
    }
}
```

### Loop e Condizioni

```yaml
tasks:
  # Loop su lista
  - name: Installa pacchetti richiesti
    ansible.builtin.package:
      name: "{{ item }}"
      state: present
    loop:
      - git
      - curl
      - htop
      - vim

  # Loop su dizionario
  - name: Crea utenti
    ansible.builtin.user:
      name: "{{ item.name }}"
      groups: "{{ item.groups }}"
      shell: "{{ item.shell | default('/bin/bash') }}"
    loop: "{{ app_users }}"

  # Condizioni (when)
  - name: Installa pacchetti Debian-specific
    ansible.builtin.apt:
      name: apt-transport-https
      state: present
    when: ansible_os_family == "Debian"

  - name: Configurazione solo in produzione
    ansible.builtin.template:
      src: prod-config.j2
      dest: /etc/app/config.yaml
    when:
      - "'production' in group_names"
      - app_version is defined
```

### Gestione Errori

```yaml
tasks:
  # Ignora errore e continua
  - name: Prova a fermare servizio (potrebbe non esistere)
    ansible.builtin.service:
      name: oldservice
      state: stopped
    ignore_errors: true

  # Cambia definizione di "failure"
  - name: Controlla se processo è in esecuzione
    ansible.builtin.command: pgrep myapp
    register: pgrep_result
    failed_when: pgrep_result.rc not in [0, 1]

  # Cambia definizione di "changed"
  - name: Esegui script idempotente
    ansible.builtin.command: /usr/local/bin/setup.sh
    changed_when: false

  # Block/rescue/always (try/catch/finally)
  - name: Deploy applicazione
    block:
      - name: Ferma applicazione
        ansible.builtin.service:
          name: myapp
          state: stopped
      - name: Deploy nuovo binario
        ansible.builtin.copy:
          src: myapp-v2
          dest: /usr/local/bin/myapp
    rescue:
      - name: Rollback a versione precedente
        ansible.builtin.copy:
          src: myapp-v1-backup
          dest: /usr/local/bin/myapp
    always:
      - name: Avvia applicazione
        ansible.builtin.service:
          name: myapp
          state: started
```

## Best Practices

### Idempotenza

!!! tip "Usa sempre moduli built-in"
    Preferisci `ansible.builtin.package` a `command: apt install`. I moduli sono idempotenti per design; `command`/`shell` non lo sono.

```yaml
# ❌ Non idempotente
- name: Installa nginx
  ansible.builtin.command: apt-get install -y nginx

# ✅ Idempotente
- name: Installa nginx
  ansible.builtin.apt:
    name: nginx
    state: present
```

### Organizzazione

- **Usa role per tutto il riuso**: anche un role con 5 task è giustificato se usato in più playbook
- **`group_vars/all.yaml`** per variabili condivise, `group_vars/[gruppo].yaml` per variabili gruppo-specifiche
- **Versiona le dipendenze**: specifica sempre la versione in `requirements.yaml`
- **Testa con `--check`** prima di applicare in produzione
- **`ansible.cfg` per progetto**: non usare configurazioni globali in `~/.ansible.cfg`

### Performance

```yaml
# ansible.cfg — ottimizzazioni
[defaults]
forks = 20                    # Parallelismo (default 5)
pipelining = True             # Riduce connessioni SSH (richiede requiretty=False in sudoers)
gather_facts = smart          # Cache i facts per sessione

[ssh_connection]
ssh_args = -o ControlMaster=auto -o ControlPersist=60s  # Connection multiplexing
```

### Anti-Pattern da Evitare

| Anti-Pattern | Problema | Alternativa |
|---|---|---|
| `command: apt install pkg` | Non idempotente | `ansible.builtin.apt: name: pkg state: present` |
| Password in plaintext nei vars | Sicurezza | Ansible Vault |
| Inventory statico con IP hardcodati | Non scalabile | Dynamic inventory plugin |
| `ignore_errors: true` ovunque | Maschera problemi | `failed_when` con condizione specifica |
| Role monolitici con 100+ task | Non manutenibile | Role piccoli e componibili |

## Troubleshooting

### Connettività SSH

```bash
# Verifica accesso SSH manuale
ssh -i ~/.ssh/key.pem -o StrictHostKeyChecking=no ec2-user@host

# Debug connessione Ansible
ansible web1.example.com -m ping -vvv

# Problemi con host key
# In ansible.cfg:
host_key_checking = False
# Oppure via env:
ANSIBLE_HOST_KEY_CHECKING=False ansible-playbook ...
```

### Privilege Escalation

```bash
# Testa sudo senza password
ansible web1 -m command -a "sudo -l" -b

# Errore "sudo: a password is required"
# Aggiungi in sudoers sul nodo: ec2-user ALL=(ALL) NOPASSWD: ALL
# Oppure usa --ask-become-pass per ambienti interattivi
```

### Debug Variabili

```yaml
- name: Debug variabili
  ansible.builtin.debug:
    var: hostvars[inventory_hostname]

- name: Debug variabile specifica
  ansible.builtin.debug:
    msg: "Port: {{ nginx_port }}, OS: {{ ansible_os_family }}"

- name: Stampa tutte le variabili
  ansible.builtin.debug:
    var: vars
```

### Errori Comuni

| Errore | Causa | Soluzione |
|---|---|---|
| `UNREACHABLE! SSH Error` | Connettività o credenziali | Verifica SSH manuale, controlla `ansible_user` e chiave |
| `MODULE FAILURE - Could not find module` | Collection mancante | `ansible-galaxy collection install ...` |
| `AnsibleUndefinedVariable` | Variabile non definita | Usa `default()`: `{{ var \| default('value') }}` |
| `Timeout` su task lunghi | `async_timeout` troppo basso | Usa `async` e `poll` per task lunghi |
| Vault `ERROR! Decryption failed` | Password vault errata | Verifica `--vault-password-file` o `ANSIBLE_VAULT_PASSWORD_FILE` |

## Relazioni

??? info "Terraform — Integrazione IaC Completa"
    Terraform e Ansible si complementano: Terraform crea l'infrastruttura, Ansible la configura. Il pattern tipico è un pipeline CI/CD che esegue `terraform apply` e poi `ansible-playbook` sulle risorse appena create, usando l'output di Terraform come inventory dinamico.

    **Approfondimento completo →** [Terraform Fondamentali](../terraform/fondamentali.md)

??? info "CI/CD Pipeline — Ansible in Automazione"
    Ansible si integra nativamente nei pipeline CI/CD. GitHub Actions, GitLab CI e Jenkins hanno action/plugin dedicati. Il pattern GitOps prevede che ogni push a `main` esegua il playbook corrispondente sull'ambiente target.

## Riferimenti

- [Documentazione Ufficiale Ansible](https://docs.ansible.com)
- [Ansible Best Practices](https://docs.ansible.com/ansible/latest/tips_tricks/ansible_tips_tricks.html)
- [Ansible Galaxy](https://galaxy.ansible.com)
- [Ansible Lint](https://ansible-lint.readthedocs.io) — linter per playbook
- [Molecule](https://ansible.readthedocs.io/projects/molecule/) — framework di testing per role
