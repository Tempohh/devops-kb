# KB Saturation Report — 2026-09-28 (sessione #696)

## Gate meccanico

```
file_count: 314, target: 330, over_target: false, headroom: 16, category_saturated_pct: 85
```

Invariato da #649...#694 (nessun file aggiunto/rimosso da #694 a #696, stesso giorno).

## Nota di cadenza

Il report #694 raccomandava di non ripetere una sessione `proposal` prima del
2026-10-04. Questo task (id 696, P2) è arrivato comunque lo stesso giorno di
#694 — eseguito perché già in coda, con approccio conservativo invariato
(nessuna proposta forzata solo per "riempire").

## Focus usato in questa sessione

Come raccomandato da #694: rotazione su `docs/security/` e `docs/messaging/`
(categorie non ancora in focus nel ciclo recente).

File letti (frontmatter + apertura, 8) + 1 verifica mirata via grep:
`messaging/rabbitmq/architettura.md`, `messaging/rabbitmq/clustering-ha.md`,
`messaging/rabbitmq/deployment.md`, `messaging/rabbitmq/vs-kafka.md`,
`security/compliance/audit-logging.md`, `security/autenticazione/mtls-spiffe.md`,
`security/network/zero-trust.md`, `security/autorizzazione/opa.md`,
`security/secret-management/vault.md` + `kubernetes-secrets.md`.
Verifica mirata: `security/autenticazione/_index.md` (mappa argomenti),
grep su `messaging/` per `oauth2_backend|sasl_external`.

## Risultato

Tutti i file letti sono `status: complete`, `related` ricchi, `search_keywords`
abbondanti. `security/` e `messaging/kafka/` risultano molto curati e già
allo stesso standard delle sessioni precedenti (nessun gap in kafka/,
secret-management/, autorizzazione/).

Trovata un'unica asimmetria reale: `messaging/kafka/` ha una sottocartella
dedicata `sicurezza/` (3 file: ACL, SASL, TLS) mentre `messaging/rabbitmq/`
non ha equivalente — TLS/LDAP compaiono solo come sotto-sezione operativa in
`deployment.md` (focus K8s operator), senza copertura di OAuth2 plugin,
SASL EXTERNAL/mTLS client-cert auth, o pattern di permessi avanzati. Verificato
via grep che nessun file messaging/ menziona `oauth2_backend` o `sasl_external`.
→ prop-122 (new-file, medium, score medium).

Nessun'altra proposta generata: `secret-management/` (Vault + K8s Secrets +
ESO) è già a un livello di dettaglio comparabile a quello richiesto per un file
nuovo — aggiungere altro sarebbe ridondante. `security/autenticazione/` copre
i tre meccanismi enterprise rilevanti per un contesto DevOps/platform
(OAuth2/OIDC, JWT, mTLS/SPIFFE); temi come passkey/WebAuthn sono stati
valutati ma scartati — riguardano più UX applicativa che infrastruttura
DevOps, fuori scope per questa KB.

## Categorie vicine alla saturazione

Invariato rispetto a #694 (nessun cambiamento).

## Categorie con gap reali

- `messaging/rabbitmq/`: manca profondità dedicata su sicurezza (OAuth2,
  SASL EXTERNAL, permessi avanzati) rispetto al livello già raggiunto da
  `messaging/kafka/sicurezza/`. → prop-122.

## Prossima sessione consigliata

Non prima di 2026-10-04 (stesso cooldown ribadito da #694, ora manato per
la terza volta di fila dal trigger P2 — considerare di distanziare la
generazione di questo tipo di task se il pattern continua). Focus successivo:
se prop-122 viene approvata e implementata, verificare reciprocità dei
`related` tra il nuovo file e `messaging/kafka/sicurezza/*`; altrimenti
considerare una sessione `currency` su `databases/kubernetes-cloud/managed-databases.md`
(più vecchio `last_updated` visto finora, 2026-03-29) invece di un'altra
sessione `proposal`.
