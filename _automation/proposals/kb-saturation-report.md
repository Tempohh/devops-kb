# KB Saturation Report — 2026-09-27 (sessione #649)

## Gate meccanico

```
file_count: 314, target: 330, over_target: false, headroom: 16, category_saturated_pct: 85
```

Sotto target, coerente con la sessione precedente (#645).

## Focus usato in questa sessione

Come raccomandato dal report di #645: lettura di contenuto (non connettività)
su `dev/**` e `messaging/**`, cercando pattern di currency/refusi analoghi a
quelli trovati in `ai/sviluppo/` (currency modello) e `ai/agents/` (refuso
path). 10 file letti in profondità:

- `messaging/rabbitmq/_index.md`, `messaging/kafka/_index.md`,
  `messaging/kafka/fondamenti/_index.md` (i 3 hub più vecchi della sezione,
  `last_updated` 2026-02-23/24/03-03)
- `messaging/kafka/sicurezza/tls-ssl.md`, `sasl.md` (sicurezza Kafka,
  candidati naturali per drift di best practice)
- `messaging/kafka/schema-registry/avro.md`
- `dev/sicurezza/tls-da-codice.md`, `dev/sicurezza/secrets-config.md`
  (documenti "ponte" dev/security, alto rischio di disallineamento se le
  pagine security cambiano)
- `dev/integrazioni/rabbitmq-client.md` (ponte dev/messaging)
- `dev/runtime/jvm-tuning.md`

## Risultato

A differenza della sessione precedente (che in `ai/**` aveva trovato 2 gap
di contenuto su 1 solo giro di lettura), qui i 10 file esaminati sono
risultati **solidi**: nessun model ID datato, nessun comando deprecato,
nessun conflitto con pagine correlate già `reviewed`. Un solo gap reale
trovato, di tipo connettività (non currency):

- **messaging/kafka/_index.md** non linka `messaging/rabbitmq/_index` nel
  `related`, mentre il percorso inverso (rabbitmq → kafka) esiste già.
  → prop-088 (low, fix-relation).

Nessun gap di tipo `new-file` proposto: la sezione `dev/**` e `messaging/**`
sono entrambe già coperte in profondità (RabbitMQ da codice, TLS da codice,
secrets da codice, JVM tuning sono tutti documenti "ponte" già maturi e
cross-referenziati). Non sono emerse lacune che superino il test di utilità
del PASSO 3.

## Categorie vicine alla saturazione

Invariato dalle sessioni precedenti: **databases/**, **dev/linguaggi/**,
**messaging/rabbitmq**, **cloud/aws**, **networking/**, **dev/testing,
dev/data, dev/resilienza, dev/sicurezza, dev/integrazioni**, **monitoring/**,
**iac/**, **cloud/azure/**, **ai/**, **security/**, **containers/**. Con
questa sessione si aggiunge, per lettura di contenuto approfondita (non solo
connettività): `messaging/kafka/**` (fondamenti, sicurezza, schema-registry)
e `dev/sicurezza/**`, `dev/integrazioni/rabbitmq-client.md`,
`dev/runtime/jvm-tuning.md` — tutti confermati di alta qualità e senza gap
di currency.

## Categorie con gap reali

Un solo gap concreto trovato in questa sessione: connettività asimmetrica
`messaging/kafka/_index.md` → `messaging/rabbitmq/_index.md` (vedi sopra,
prop-088). Nessun gap di tipo `new-file` o `extend-section`.

## Prossima sessione consigliata

Non prima di 2026-10-04 (2 giorni oltre quanto raccomandato da #645, in
linea con il ritmo osservato). Il giro di lettura content-focused su
`dev/**`/`messaging/**` può considerarsi concluso per i file più datati
(pre-2026-03-29): erano gli unici a rischio di drift e sono risultati
puliti. Prossimo focus suggerito: proseguire la lettura di contenuto (non
connettività) sulle sezioni **cloud/aws/** e **databases/** — mai state
oggetto di un giro di lettura approfondita mirato a currency/refusi (solo
controlli di connettività hub→figli nelle sessioni #634-#645), e sono tra le
sezioni più vecchie/dense della KB.
