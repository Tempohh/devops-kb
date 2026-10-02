# KB Saturation Report — 2026-10-02 (sessione #711)

## Gate meccanico

```
file_count: 321, target: 330, over_target: false, headroom: 9, category_saturated_pct: 85, allow_zero_proposals: true
```

Sotto target (headroom 9): proposte di espansione ammesse se superano il test
di utilità. Nota di cadenza: sessione #709 raccomandava "non prima di
2026-10-09" — arrivata comunque in anticipo (dispatch da coda automazione,
non controllabile da questa sessione). Verificato prima lo stato delle
proposte precedenti: prop-130 (`messaging/pulsar/fondamentali.md`) risulta
committata (commit a37741cd, auto #710). Nessuna proposta pendente duplicata
in `_automation/proposals/pending/` (vuota a inizio sessione).

## Focus usato in questa sessione

Il report #709 raccomandava, in caso di arrivo anticipato, di spostare il
focus su `docs/networking/` o `docs/security/` (non esplorate in profondità
da più sessioni `proposal` consecutive). Applicato: entrambe analizzate, con
enfasi su `security/` dove è emerso il gap più netto.

File letti/ispezionati: censimento strutturale di tutte le categorie
(`docs/**/*.md`, conteggio per categoria principale); lettura completa di
`docs/networking/` (elenco strutturale dei 44 file, nessuna lettura a
campione necessaria — struttura già molto profonda); lettura completa di
`docs/security/autenticazione/_index.md`, `docs/security/compliance/_index.md`
e `audit-logging.md` (struttura); grep mirati su `saml`, `ldap`, `ipv6`,
`kube-bench|cis benchmark|openscap|inspec` su tutta la KB; confronto
`docs/security/network/zero-trust.md` vs `docs/networking/sicurezza/zero-trust.md`
(verificato: coppia intenzionale cross-referenziata, due angolazioni diverse
— non duplicazione, nessun gap).

## Risultato

**`docs/networking/`**: molto maturo (44 file, 6 sottocategorie: fondamentali,
protocolli, load-balancing, service-mesh, kubernetes, sicurezza, api-gateway).
Nessun gap reale trovato con score alto — IPv6 è menzionato in 7 file ma
approfondirlo come topic standalone sarebbe simmetria formale IPv4/IPv6 senza
un problema operativo distinto documentato (scartato).

**Gap reale trovato #1 — `docs/security/compliance/`**: la categoria contiene
un solo file (`audit-logging.md`, ricostruzione post-hoc) nonostante il
frontmatter dell'indice citi esplicitamente SOC2/ISO27001/PCI-DSS. Manca
completamente l'hardening *proattivo* misurabile contro baseline riconosciute:
"kube-bench"/"CIS benchmark" compaiono solo come menzioni sparse in 6+ file
(container-runtime, docker/sicurezza, aws/security/compliance-audit, ecc.)
senza mai un riferimento centrale end-to-end (kube-bench, OpenSCAP, InSpec).

**Gap reale trovato #2 — `docs/security/autenticazione/`**: copre OAuth2/OIDC,
JWT, mTLS/SPIFFE ma zero contenuto operativo su SAML e LDAP/Active Directory,
meccanismi ancora obbligatori in molti contesti enterprise/legacy (vincolo
organizzativo, non scelta tecnica) e che compaiono nella KB solo come
menzioni di protocollo/porta in file di networking.

## Proposte generate

- **prop-131** (high, new-file) — `security/compliance/cis-benchmarks-compliance-scanning.md`
  (kube-bench, OpenSCAP, InSpec — colma il gap compliance proattiva vs
  audit-logging reattivo)
- **prop-132** (medium, new-file) — `security/autenticazione/saml-ldap-enterprise-sso.md`
  (SAML/LDAP come vincolo enterprise, complemento a OAuth2/OIDC già coperto)

## Categorie vicine alla saturazione

`docs/dev/`, `docs/ci-cd/testing/` (confermate sature, sessioni precedenti).
`docs/containers/` e `docs/iac/` mature (confermato sessione #709).
`docs/messaging/` matura dopo prop-130 (Pulsar aggiunto).
`docs/networking/` risulta matura dopo l'analisi di questa sessione — nessun
gap reale con score alto individuato.

## Categorie con gap reali

`docs/security/compliance/` e `docs/security/autenticazione/` — vedi proposte
sopra. `docs/security/` nel complesso resta la categoria con più margine
operativo residuo tra quelle esplorate finora.

## Prossima sessione consigliata

Non prima di 2026-10-09. Verificare prima l'implementazione di prop-131 e
prop-132. Se arriva comunque in anticipo, continuare l'esplorazione di
`docs/security/` (es. `autorizzazione/` oltre OPA/RBAC, o `secret-management/`
oltre Vault/K8s secrets) prima di aprire nuove categorie.
