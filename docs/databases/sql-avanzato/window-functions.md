---
title: "Window Functions"
slug: window-functions
category: databases
tags: [sql, window-functions, analytics, ranking, aggregation, postgresql]
search_keywords: [window function, over clause, partition by, order by window, rank, dense_rank, row_number, ntile, lag, lead, first_value, last_value, nth_value, running total, cumulative sum, moving average, percentile, frame clause, rows between, range between, groups between, current row, unbounded preceding, unbounded following]
parent: databases/sql-avanzato/_index
related: [databases/sql-avanzato/query-optimizer, databases/sql-avanzato/partitioning]
official_docs: https://www.postgresql.org/docs/current/tutorial-window.html
status: complete
difficulty: intermediate
last_updated: 2026-02-24
---

# Window Functions

## Panoramica

Una window function calcola un valore **per ogni riga** basandosi su un insieme di righe correlate (la "finestra"), senza collassare le righe come farebbe GROUP BY. È la differenza tra "dammi il totale per categoria" (GROUP BY, 1 riga per categoria) e "dimmi il totale cumulato a ogni riga mantenendo i dettagli" (window function, N righe con aggregato).

```sql
-- GROUP BY: perde il dettaglio delle righe
SELECT categoria, SUM(importo) AS totale
FROM ordini
GROUP BY categoria;
-- → 3 righe (una per categoria)

-- Window function: mantiene tutte le righe + aggiunge il totale
SELECT id, categoria, importo,
       SUM(importo) OVER (PARTITION BY categoria) AS totale_categoria
FROM ordini;
-- → N righe, ognuna con il totale della propria categoria
```

## Anatomia di una Window Function

```sql
funzione() OVER (
    [PARTITION BY colonna, ...]      -- Divide in gruppi (come GROUP BY ma senza collassare)
    [ORDER BY colonna [DESC], ...]   -- Ordine dentro la finestra
    [frame_clause]                   -- Quale sottoinsieme di righe considerare
)
```

Il **frame** (opzionale) definisce l'intervallo di righe relativo alla riga corrente:

```sql
ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW    -- Dal primo all'attuale (default per running total)
ROWS BETWEEN 2 PRECEDING AND 2 FOLLOWING             -- ±2 righe (media mobile)
ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING    -- Dall'attuale all'ultimo
RANGE BETWEEN INTERVAL '7 days' PRECEDING AND CURRENT ROW  -- Ultimi 7 giorni
```

---

## Ranking Functions

### ROW_NUMBER, RANK, DENSE_RANK

```sql
SELECT
    nome,
    categoria,
    punteggio,
    -- ROW_NUMBER: numero progressivo univoco (1, 2, 3, 4...)
    ROW_NUMBER() OVER (PARTITION BY categoria ORDER BY punteggio DESC) AS posizione,

    -- RANK: pari merito = stesso rank, poi gap (1, 2, 2, 4...)
    RANK()       OVER (PARTITION BY categoria ORDER BY punteggio DESC) AS rank,

    -- DENSE_RANK: pari merito = stesso rank, no gap (1, 2, 2, 3...)
    DENSE_RANK() OVER (PARTITION BY categoria ORDER BY punteggio DESC) AS dense_rank

FROM classifiche;
```

```
nome    categoria  punteggio  posizione  rank  dense_rank
Alice   A          100        1          1     1
Bob     A          95         2          2     2
Carol   A          95         3          2     2
Dave    A          80         4          4     3
```

**Caso d'uso classico**: trovare il top-N per categoria (es. i 3 prodotti più venduti per categoria):

```sql
-- Top 3 prodotti per categoria
WITH ranked AS (
    SELECT
        prodotto_id, categoria, vendite,
        ROW_NUMBER() OVER (PARTITION BY categoria ORDER BY vendite DESC) AS rn
    FROM vendite_mensili
)
SELECT * FROM ranked WHERE rn <= 3;
```

### NTILE

Divide le righe in N bucket di dimensione uguale:

```sql
SELECT
    cliente_id,
    fatturato_annuo,
    NTILE(4) OVER (ORDER BY fatturato_annuo DESC) AS quartile
    -- 1 = top 25%, 2 = secondo 25%, 3 = terzo 25%, 4 = bottom 25%
FROM clienti;
```

---

## Aggregate Functions come Window

Qualsiasi funzione aggregata (`SUM`, `AVG`, `MIN`, `MAX`, `COUNT`) può essere usata come window function aggiungendo `OVER()`:

### Running Total (Somma Cumulata)

```sql
SELECT
    data,
    importo,
    SUM(importo) OVER (ORDER BY data
                       ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS totale_cumulato
FROM transazioni
ORDER BY data;
```

```
data        importo  totale_cumulato
2024-01-01  100      100
2024-01-02  250      350
2024-01-03  -50      300
2024-01-04  400      700
```

### Media Mobile (Moving Average)

```sql
-- Media mobile a 7 giorni di vendite
SELECT
    data,
    vendite,
    AVG(vendite) OVER (
        ORDER BY data
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW  -- 7 giorni: i 6 precedenti + il corrente
    ) AS media_7gg
FROM vendite_giornaliere;
```

### Percentuale sul Totale

```sql
SELECT
    categoria,
    prodotto,
    vendite,
    -- Percentuale sul totale della categoria
    ROUND(100.0 * vendite / SUM(vendite) OVER (PARTITION BY categoria), 1) AS pct_categoria,
    -- Percentuale sul totale assoluto
    ROUND(100.0 * vendite / SUM(vendite) OVER (), 2) AS pct_totale
FROM vendite;
```

---

## LAG e LEAD — Accesso alle Righe Precedenti/Successive

```sql
SELECT
    data,
    vendite,
    -- Vendite del giorno precedente
    LAG(vendite, 1) OVER (ORDER BY data) AS ieri,
    -- Variazione giorno su giorno
    vendite - LAG(vendite, 1) OVER (ORDER BY data) AS delta,
    -- Variazione percentuale
    ROUND(100.0 * (vendite - LAG(vendite, 1) OVER (ORDER BY data))
          / NULLIF(LAG(vendite, 1) OVER (ORDER BY data), 0), 1) AS delta_pct,
    -- Vendite del giorno successivo (look-ahead)
    LEAD(vendite, 1) OVER (ORDER BY data) AS domani

FROM vendite_giornaliere;
```

**Caso d'uso: rilevare gap temporali** (es. sessioni utente con inattività > 30 minuti):

```sql
WITH eventi_con_lag AS (
    SELECT
        user_id,
        timestamp,
        LAG(timestamp) OVER (PARTITION BY user_id ORDER BY timestamp) AS prev_ts
    FROM eventi_utente
),
sessioni AS (
    SELECT
        user_id,
        timestamp,
        -- Nuovo inizio sessione se il gap supera 30 minuti
        CASE WHEN timestamp - prev_ts > INTERVAL '30 minutes'
             OR prev_ts IS NULL
             THEN 1 ELSE 0 END AS nuova_sessione
    FROM eventi_con_lag
)
SELECT
    user_id,
    -- Assegna un ID sessione incrementale per ogni sessione
    SUM(nuova_sessione) OVER (PARTITION BY user_id ORDER BY timestamp) AS sessione_id,
    timestamp
FROM sessioni;
```

---

## FIRST_VALUE, LAST_VALUE, NTH_VALUE

```sql
SELECT
    ordine_id,
    prodotto,
    prezzo,
    -- Il prezzo del primo prodotto in questo ordine
    FIRST_VALUE(prezzo) OVER (PARTITION BY ordine_id ORDER BY prezzo DESC) AS prezzo_max,
    -- Il prezzo del secondo prodotto (secondo per prezzo)
    NTH_VALUE(prezzo, 2) OVER (
        PARTITION BY ordine_id
        ORDER BY prezzo DESC
        ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING  -- frame completo
    ) AS secondo_prezzo

FROM righe_ordine;
```

!!! warning "LAST_VALUE e il frame predefinito"
    `LAST_VALUE()` senza frame clause esplicita usa il frame default `RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW` — quindi restituisce il valore della riga corrente, non dell'ultima. Per ottenere l'ultimo valore usare `ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING`.

---

## Percentili Statistici

```sql
SELECT
    categoria,
    -- Mediana (50° percentile)
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY prezzo) AS mediana,
    -- 95° percentile (es. per SLA response time)
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY response_time_ms) AS p95,
    -- Percentile discreto (valore reale dalla distribuzione)
    PERCENTILE_DISC(0.75) WITHIN GROUP (ORDER BY prezzo) AS p75_discreto

FROM prodotti
GROUP BY categoria;
```

---

## Performance delle Window Functions

Le window function eseguono **dopo** WHERE, GROUP BY, e HAVING, ma prima di ORDER BY e LIMIT finali. Non possono essere filtrate con WHERE (usare CTE):

```sql
-- SBAGLIATO: non puoi filtrare direttamente sulla window function
SELECT * FROM vendite
WHERE RANK() OVER (ORDER BY importo DESC) <= 10;  -- ERROR

-- CORRETTO: CTE o subquery
WITH ranked AS (
    SELECT *, RANK() OVER (ORDER BY importo DESC) AS rnk
    FROM vendite
)
SELECT * FROM ranked WHERE rnk <= 10;
```

**Ottimizzazione**: se usi più window function con la stessa `OVER()`, PostgreSQL esegue una sola passata. Window function con `OVER()` diversi richiedono passate separate — può essere costoso su tabelle grandi.

```sql
-- Una sola passata (stessa window)
SELECT
    SUM(importo)   OVER (PARTITION BY categoria ORDER BY data) AS sum_cat,
    AVG(importo)   OVER (PARTITION BY categoria ORDER BY data) AS avg_cat,
    COUNT(*)       OVER (PARTITION BY categoria ORDER BY data) AS count_cat
FROM vendite;

-- Due passate (window diverse)
SELECT
    SUM(importo) OVER (PARTITION BY categoria) AS sum_cat,  -- window 1
    SUM(importo) OVER (PARTITION BY regione)   AS sum_reg   -- window 2
FROM vendite;
-- → considerare materializzare i risultati con CTE se il costo è alto
```

## Relazioni

??? info "Query Optimizer — Come vengono eseguiti i piani con window"
    Come leggere EXPLAIN ANALYZE per query con window function.

    **Approfondimento →** [Query Optimizer](query-optimizer.md)

## Riferimenti

- [PostgreSQL Window Functions](https://www.postgresql.org/docs/current/tutorial-window.html)
- [Mode Analytics — Window Functions Guide](https://mode.com/sql-tutorial/sql-window-functions/)
