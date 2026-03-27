---
title: "Machine Learning — Fondamentali"
slug: machine-learning
category: ai
tags: [machine-learning, supervised, unsupervised, reinforcement-learning, training, gradient-descent]
search_keywords: [ML, apprendimento automatico, supervised learning, unsupervised learning, reinforcement learning, classificazione, regressione, clustering, scikit-learn, gradient descent, overfitting, underfitting, cross-validation, feature engineering]
parent: ai/fondamentali/_index
related: [ai/fondamentali/deep-learning, ai/training/fine-tuning, ai/training/valutazione]
official_docs: https://scikit-learn.org/stable/user_guide.html
status: complete
difficulty: beginner
last_updated: 2026-03-27
---

# Machine Learning — Fondamentali

## Panoramica

Il Machine Learning (ML) è un sottoinsieme dell'intelligenza artificiale in cui i sistemi imparano automaticamente dai dati senza essere esplicitamente programmati con regole fisse. Invece di scrivere `if condizione: allora azione`, si fornisce al sistema esempi di input/output e l'algoritmo generalizza un modello. Questo approccio è potente quando le regole sono troppe, troppo complesse, o sconosciute a priori.

Il ML si suddivide in tre paradigmi principali basati sulla natura dei dati di addestramento: supervised learning (dati etichettati), unsupervised learning (dati senza label), e reinforcement learning (agente in un ambiente con reward). Ogni paradigma ha i propri algoritmi, metriche di valutazione e casi d'uso ottimali. Per i sistemi DevOps, il ML classico è particolarmente utile per anomaly detection, classificazione di log, previsione della capacità e analisi di time series infrastrutturali.

## 1. Supervised Learning

Nel supervised learning il dataset contiene coppie (input X, label Y). Il modello impara una funzione f(X) ≈ Y che generalizza a nuovi esempi mai visti. Si divide in due sotto-problemi principali:

- **Classificazione**: Y è una categoria discreta (spam/non-spam, critico/warning/info)
- **Regressione**: Y è un valore continuo (CPU usage futuro, latenza prevista)

### Algoritmi principali

**Linear Regression / Logistic Regression**
Modelli lineari interpretabili, veloci, utili come baseline.

```python
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

pipeline = Pipeline([
    ('scaler', StandardScaler()),
    ('classifier', LogisticRegression(C=1.0, max_iter=1000))
])
pipeline.fit(X_train, y_train)
print(f"Accuracy: {pipeline.score(X_test, y_test):.3f}")
```

**Decision Trees e Random Forest**
I Decision Tree spezzano i dati in base a soglie sulle feature. I Random Forest aggregano centinaia di decision tree (ensemble), riducendo la varianza e migliorando la robustezza. Ottimi per dati tabellari.

```python
from sklearn.ensemble import RandomForestClassifier

rf = RandomForestClassifier(
    n_estimators=100,      # numero di alberi
    max_depth=10,          # profondità massima (regolarizzazione)
    min_samples_leaf=5,    # anti-overfitting
    random_state=42
)
rf.fit(X_train, y_train)

# Feature importance: utile per capire quali feature contano
importances = rf.feature_importances_
```

**Gradient Boosting (XGBoost, LightGBM)**
Algoritmi ensemble che costruiscono alberi sequenzialmente, ognuno corregge gli errori del precedente. Stato dell'arte per dati tabellari in competizioni ML.

```python
import xgboost as xgb

model = xgb.XGBClassifier(
    n_estimators=500,
    learning_rate=0.05,
    max_depth=6,
    subsample=0.8,
    colsample_bytree=0.8,
    use_label_encoder=False,
    eval_metric='logloss'
)
model.fit(X_train, y_train, eval_set=[(X_val, y_val)], early_stopping_rounds=50)
```

**Support Vector Machines (SVM)**
Trova l'iperpiano che massimizza il margine tra le classi. Efficace in spazi ad alta dimensione. Meno scalabile con dataset grandi (O(n²) o O(n³)).

**Neural Networks** (vedi [Deep Learning](deep-learning.md))

### Metriche di valutazione — Classificazione

| Metrica | Formula | Quando Usarla |
|---------|---------|---------------|
| **Accuracy** | (TP+TN) / total | Classi bilanciate |
| **Precision** | TP / (TP+FP) | Minimizzare falsi positivi (es. alert spam) |
| **Recall** | TP / (TP+FN) | Minimizzare falsi negativi (es. anomaly detection) |
| **F1 Score** | 2×(P×R)/(P+R) | Bilanciamento precision/recall |
| **AUC-ROC** | Area sotto la curva ROC (Receiver Operating Characteristic — curva che mostra il tradeoff tra tasso di veri positivi e falsi positivi al variare della soglia) | Valutazione robusta con classi sbilanciate |

!!! tip "Classi sbilanciate"
    In anomaly detection i casi anomali sono rari (es. 0.1% del dataset). L'accuracy del 99.9% si ottiene predicendo sempre "normale". Usare F1, AUC-ROC, o class_weight='balanced' nel modello.

### Metriche di valutazione — Regressione

| Metrica | Descrizione |
|---------|-------------|
| MAE (Mean Absolute Error) | Errore medio assoluto — interpretabile nell'unità della target |
| MSE / RMSE | Penalizza errori grandi più di MAE |
| R² (R-squared) | Frazione di varianza spiegata (1.0 = perfetto) |
| MAPE | Errore percentuale medio — utile per confronto tra scale |

## 2. Unsupervised Learning

Nessuna label: il modello deve trovare strutture, pattern e raggruppamenti nei dati autonomamente.

### Clustering

**K-Means**: partiziona i dati in K cluster minimizzando la varianza intra-cluster.

```python
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

# Scegliere K con il metodo del gomito (elbow method)
inertias = []
for k in range(2, 11):
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    km.fit(X)
    inertias.append(km.inertia_)

# K ottimale = punto in cui la curva "piega"
km_final = KMeans(n_clusters=4, random_state=42, n_init=10)
labels = km_final.fit_predict(X)
print(f"Silhouette Score: {silhouette_score(X, labels):.3f}")
```

**DBSCAN** (Density-Based Spatial Clustering of Applications with Noise): identifica cluster di forma arbitraria raggruppando punti vicini tra loro, e marca come outlier i punti isolati. Utile per anomaly detection: i punti che non appartengono a nessun cluster sono anomalie.

```python
from sklearn.cluster import DBSCAN

db = DBSCAN(eps=0.5, min_samples=5)
labels = db.fit_predict(X)
outliers = X[labels == -1]  # -1 = outlier
```

### Riduzione Dimensionale

**PCA (Principal Component Analysis)**: proietta i dati in uno spazio a dimensione inferiore mantenendo la massima varianza. Utile come preprocessing.

```python
from sklearn.decomposition import PCA

pca = PCA(n_components=0.95)  # mantieni 95% della varianza
X_reduced = pca.fit_transform(X_scaled)
print(f"Dimensioni ridotte da {X.shape[1]} a {X_reduced.shape[1]}")
```

**t-SNE** (t-Distributed Stochastic Neighbor Embedding) **/ UMAP** (Uniform Manifold Approximation and Projection): tecniche di proiezione non-lineare che riducono i dati in 2D o 3D per visualizzazione. Non usare per preprocessing, solo per esplorazione visiva.

**Autoencoder**: rete neurale che impara una rappresentazione compressa. L'encoder comprime, il decoder ricostruisce. Usato per anomaly detection (errore di ricostruzione alto = anomalia).

## 3. Reinforcement Learning

Un **agente** interagisce con un **environment**, compie **azioni**, osserva lo **stato** risultante e riceve un **reward**. L'obiettivo è massimizzare il reward cumulativo nel tempo (discounted return).

```
Agente → Azione → Environment → Nuovo Stato + Reward → Agente
```

### Algoritmi principali

| Algoritmo | Tipo | Caratteristiche |
|-----------|------|-----------------|
| Q-Learning | Model-free, value-based | Tabellare, semplice, non scala |
| DQN | Deep Q-Network | Q-Learning + neural network, Atari |
| PPO (Proximal Policy Optimization) | Policy gradient | Stabile, usato per RLHF degli LLM |
| SAC (Soft Actor-Critic) | Actor-critic, off-policy | Efficiente, continous action spaces |
| A3C / A2C (Asynchronous / Advantage Actor-Critic) | Actor-critic, on-policy | Parallelizzabile |

### RL per LLM — RLHF

Il Reinforcement Learning from Human Feedback (RLHF) è il meccanismo che ha trasformato i LLM pre-trainati in assistenti utili e sicuri (ChatGPT, Claude). Il processo in tre fasi:

```
1. SFT (Supervised Fine-Tuning)
   Dati: (prompt, risposta ideale) da annotatori umani
   Output: modello SFT

2. Reward Model
   Dati: (prompt, risposta A, risposta B, preferenza umana)
   Output: modello che assegna uno score a ogni risposta

3. PPO/REINFORCE
   Il modello SFT genera risposte → il Reward Model le valuta
   → PPO aggiorna il modello per massimizzare il reward
   KL divergence penalty: penalità basata sulla KL divergence (Kullback-Leibler divergence — misura quanto due distribuzioni di probabilità differiscono tra loro) che evita che il modello si allontani troppo dalla SFT policy
```

## 4. Training Loop e Ottimizzazione

### Gradient Descent

Il gradient descent aggiorna i parametri θ nella direzione opposta al gradiente della loss:

```
θ_new = θ_old - learning_rate × ∇L(θ)
```

**Varianti:**

| Variante | Batch Size | Caratteristiche |
|----------|-----------|-----------------|
| Batch GD | Intero dataset | Stabile, lento, impraticabile per grandi dataset |
| Stochastic GD (SGD) | 1 sample | Rumoroso, sfugge minimi locali, lento |
| Mini-batch GD | 32-512 sample | Bilancia stabilità e velocità. Standard in pratica |

**Optimizer moderni:**

```python
# SGD con momentum — storia degli aggiornamenti
optimizer = torch.optim.SGD(model.parameters(), lr=0.01, momentum=0.9, weight_decay=1e-4)

# Adam — momento adattivo per ogni parametro
# β1=0.9 (media exp gradiente), β2=0.999 (media exp gradiente²), ε=1e-8
optimizer = torch.optim.Adam(model.parameters(), lr=1e-3, betas=(0.9, 0.999))

# AdamW — Adam con weight decay corretto (migliore per LLM)
optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, weight_decay=0.01)
```

## 5. Overfitting e Underfitting

Il **bias-variance tradeoff** è il compromesso fondamentale del ML:

- **Underfitting (alto bias)**: il modello è troppo semplice, non cattura i pattern (training error alto)
- **Overfitting (alta varianza)**: il modello memorizza il training set, non generalizza (training error basso, validation error alto)

```
Training Loss     ↓↓↓ (sempre scende con più training)
Validation Loss   ↓↓ poi ↑↑ (risale quando inizia overfitting)
                      ^
                  Early Stopping qui
```

### Tecniche di Regolarizzazione

**L1 (Lasso)**: aggiunge |θ| alla loss. Produce pesi sparsi (feature selection automatica).

**L2 (Ridge / Weight Decay)**: aggiunge θ² alla loss. Riduce i pesi grandi uniformemente.

```python
# sklearn
from sklearn.linear_model import Ridge, Lasso
ridge = Ridge(alpha=1.0)   # L2
lasso = Lasso(alpha=0.1)   # L1

# PyTorch
optimizer = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-4)  # L2
```

**Dropout**: durante il training, azzera casualmente una frazione p dei neuroni. Forza il modello a non dipendere da singoli neuroni. Disattivato durante l'inferenza.

**Early Stopping**: monitora la validation loss, interrompe il training quando smette di migliorare.

```python
from sklearn.neural_network import MLPClassifier
mlp = MLPClassifier(early_stopping=True, validation_fraction=0.1, n_iter_no_change=10)
```

**Data Augmentation**: aumenta artificialmente il training set con trasformazioni (rotazioni, flip, rumore). Cruciale per computer vision.

## 6. Feature Engineering

Le feature sono le variabili di input fornite al modello. La qualità delle feature spesso conta più della scelta dell'algoritmo.

### Normalizzazione / Scaling

```python
from sklearn.preprocessing import StandardScaler, MinMaxScaler, RobustScaler

# StandardScaler: media=0, std=1. Per algoritmi basati su distanza (SVM, KNN — K-Nearest Neighbors)
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X_train)  # fit solo su train!

# MinMaxScaler: range [0,1]. Per reti neurali con sigmoid/tanh
scaler = MinMaxScaler()

# RobustScaler: usa mediana e IQR. Resistente agli outlier
scaler = RobustScaler()
```

### Encoding Variabili Categoriche

```python
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder
import pandas as pd

# One-Hot: crea colonna binaria per ogni categoria (no ordinamento implicito)
# Attenzione al curse of dimensionality con alta cardinalità
ohe = OneHotEncoder(handle_unknown='ignore', sparse_output=False)

# Target Encoding: sostituisce la categoria con la media della target
# Rischio: data leakage — usare con cross-validation
df['categoria_encoded'] = df.groupby('categoria')['target'].transform('mean')

# Label Encoding: per target e variabili ordinali
enc = OrdinalEncoder()
```

### Feature Selection

```python
from sklearn.feature_selection import SelectKBest, f_classif, RFE

# Selezione univariata (test statistico)
selector = SelectKBest(score_func=f_classif, k=20)
X_selected = selector.fit_transform(X, y)

# Recursive Feature Elimination con un modello
from sklearn.ensemble import RandomForestClassifier
rfe = RFE(estimator=RandomForestClassifier(), n_features_to_select=20)
X_rfe = rfe.fit_transform(X, y)
```

## 7. Cross-Validation

La cross-validation stima le performance del modello su dati non visti in modo più robusto di un singolo split.

```python
from sklearn.model_selection import cross_val_score, StratifiedKFold

# K-Fold standard
cv_scores = cross_val_score(model, X, y, cv=5, scoring='f1_weighted')
print(f"F1 medio: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}")

# Stratified K-Fold (mantiene proporzione delle classi in ogni fold)
skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
cv_scores = cross_val_score(model, X, y, cv=skf, scoring='roc_auc')

# Time Series: non usare K-Fold, usare TimeSeriesSplit
from sklearn.model_selection import TimeSeriesSplit
tscv = TimeSeriesSplit(n_splits=5)
```

## 8. Pipeline scikit-learn

Il Pipeline di scikit-learn garantisce che preprocessing e modello siano trattati come un unico oggetto, prevenendo data leakage.

```python
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import GridSearchCV

# Preprocessing per colonne diverse
numeric_features = ['cpu_usage', 'memory_gb', 'latency_ms']
categorical_features = ['region', 'instance_type']

preprocessor = ColumnTransformer(transformers=[
    ('num', StandardScaler(), numeric_features),
    ('cat', OneHotEncoder(handle_unknown='ignore'), categorical_features)
])

# Pipeline completa
pipeline = Pipeline([
    ('preprocessor', preprocessor),
    ('classifier', GradientBoostingClassifier(random_state=42))
])

# Hyperparameter tuning con GridSearch
param_grid = {
    'classifier__n_estimators': [100, 200],
    'classifier__max_depth': [3, 5],
    'classifier__learning_rate': [0.05, 0.1]
}
grid_search = GridSearchCV(pipeline, param_grid, cv=5, scoring='f1_weighted', n_jobs=-1)
grid_search.fit(X_train, y_train)

print(f"Best params: {grid_search.best_params_}")
print(f"Test score: {grid_search.score(X_test, y_test):.3f}")
```

## Best Practices

- **Baseline prima**: inizia sempre con un modello semplice (logistic regression, decision tree). Misura il miglioramento degli algoritmi complessi rispetto alla baseline.
- **Fit solo su training**: scaler, encoder, e qualsiasi trasformazione si fittano SOLO sul training set e si applicano poi a validation e test.
- **Metriche giuste**: scegli le metriche PRIMA di vedere i risultati. Le metriche dipendono dal business (falso positivo vs falso negativo ha costi diversi).
- **Reproducibilità**: imposta `random_state` / seed ovunque. Versiona i dati (DVC — Data Version Control, lo standard per versionare dataset come Git versiona il codice).
- **Feature importance**: interpreta il modello per capire cosa sta imparando.
- **Monitor drift**: in produzione, i dati cambiano nel tempo. Il **concept drift** si verifica quando cambia la relazione tra le feature e la target (es. i pattern di frode cambiano). Il **data drift** si verifica quando cambia la distribuzione delle feature di input (es. nuovi tipi di utenti). Monitora distribuzioni delle feature e performance del modello per rilevarli.

## Troubleshooting

### Scenario 1 — Overfitting: validation loss risale mentre training loss scende

**Sintomo**: Training accuracy alta (>95%), validation accuracy molto più bassa o in calo progressivo. Gap crescente tra training e validation loss.

**Causa**: Il modello memorizza il training set invece di generalizzare. Cause tipiche: modello troppo complesso, dataset troppo piccolo, nessuna regolarizzazione.

**Soluzione**: Ridurre la complessità del modello, aggiungere regolarizzazione, usare early stopping o data augmentation.

```python
# Verifica rapida del gap train/validation
from sklearn.model_selection import learning_curve
import numpy as np

train_sizes, train_scores, val_scores = learning_curve(
    model, X, y, cv=5, scoring='f1_weighted',
    train_sizes=np.linspace(0.1, 1.0, 10)
)
print(f"Train score: {train_scores[-1].mean():.3f}")
print(f"Val score:   {val_scores[-1].mean():.3f}")
print(f"Gap:         {train_scores[-1].mean() - val_scores[-1].mean():.3f}")

# Fix: aggiungere regolarizzazione
from sklearn.ensemble import RandomForestClassifier
model = RandomForestClassifier(max_depth=5, min_samples_leaf=10, max_features='sqrt')
```

### Scenario 2 — Classi sbilanciate: il modello predice sempre la classe maggioritaria

**Sintomo**: Accuracy apparentemente alta (es. 99%), ma precision/recall sulla classe minoritaria sono 0. Matrice di confusione con una riga quasi vuota.

**Causa**: Il dataset ha una distribuzione molto sbilanciata (es. 99% negativo, 1% positivo). Il modello minimizza la loss totale predicendo sempre la classe maggioritaria.

**Soluzione**: Usare `class_weight='balanced'`, oversampling (SMOTE) o undersampling, e metriche appropriate (F1, AUC-ROC).

```python
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report
from imblearn.over_sampling import SMOTE

# Opzione 1: class_weight automatico
model = RandomForestClassifier(class_weight='balanced', random_state=42)
model.fit(X_train, y_train)

# Opzione 2: SMOTE - oversampling sintetico della classe minoritaria
smote = SMOTE(random_state=42)
X_resampled, y_resampled = smote.fit_resample(X_train, y_train)
model.fit(X_resampled, y_resampled)

# Usare sempre report completo, non solo accuracy
print(classification_report(y_test, model.predict(X_test)))
```

### Scenario 3 — Data leakage: performance irrealisticamente alte in validazione, pessime in produzione

**Sintomo**: Metriche di validazione eccellenti (F1 > 0.99), ma il modello fallisce completamente su dati reali o in produzione.

**Causa**: Il preprocessing (scaler, encoder, imputazione) è stato fittato sull'intero dataset prima dello split, o le feature includono informazioni future non disponibili al momento della predizione.

**Soluzione**: Usare sempre sklearn Pipeline per garantire che il fit avvenga solo su training data; verificare che nessuna feature sia calcolata su dati futuri.

```python
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# CORRETTO: scaler fittato solo nel training fold della pipeline
pipeline = Pipeline([
    ('scaler', StandardScaler()),   # fit avviene solo su X_train
    ('model', GradientBoostingClassifier())
])
pipeline.fit(X_train, y_train)
print(f"Test score: {pipeline.score(X_test, y_test):.3f}")

# SBAGLIATO (data leakage):
# scaler.fit(X)  # ← usa anche X_test!
# X_scaled = scaler.transform(X)
```

### Scenario 4 — Convergenza lenta o instabile durante il training

**Sintomo**: La loss oscilla molto senza scendere, oppure scende lentissimamente. Con PyTorch/TensorFlow: NaN nella loss dopo qualche epoch.

**Causa**: Learning rate troppo alto (oscillazioni / NaN) o troppo basso (convergenza lenta). Feature non normalizzate con scale molto diverse. Gradient explosion con reti profonde.

**Soluzione**: Normalizzare le feature, usare learning rate scheduling, aggiungere gradient clipping per reti profonde.

```python
import torch
import torch.nn as nn

# Gradient clipping per evitare explosion
optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

for epoch in range(num_epochs):
    loss = compute_loss(model, X_batch, y_batch)
    optimizer.zero_grad()
    loss.backward()
    torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)  # clipping
    optimizer.step()

# Learning rate scheduling: riduci LR quando la loss stagna
scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
    optimizer, mode='min', factor=0.5, patience=5, verbose=True
)
scheduler.step(val_loss)  # chiamare dopo ogni epoch di validazione
```

## Riferimenti

- [scikit-learn User Guide](https://scikit-learn.org/stable/user_guide.html) — Documentazione completa e esempi
- [Hands-On ML with Scikit-Learn, Keras & TensorFlow (Géron)](https://www.oreilly.com/library/view/hands-on-machine-learning/9781492032632/) — Libro di riferimento
- [XGBoost Documentation](https://xgboost.readthedocs.io/) — Gradient boosting ottimizzato
- [Feature Engineering for Machine Learning (Zheng & Casari)](https://www.oreilly.com/library/view/feature-engineering-for/9781491953235/) — Tecniche avanzate
