---
title: "Deep Learning — Reti Neurali e Architetture"
slug: deep-learning
category: ai
tags: [deep-learning, neural-networks, cnn, rnn, lstm, transformer, pytorch, training]
search_keywords: [reti neurali, neural network, deep learning, convolutional neural network, recurrent neural network, long short-term memory, attention mechanism, transfer learning, batch normalization, dropout, PyTorch, TensorFlow, GPU training, mixed precision, backpropagation]
parent: ai/fondamentali/_index
related: [ai/fondamentali/machine-learning, ai/modelli/_index, ai/training/fine-tuning, ai/mlops/infrastruttura-gpu]
official_docs: https://pytorch.org/docs/stable/index.html
status: complete
difficulty: intermediate
last_updated: 2026-03-27
---

# Deep Learning — Reti Neurali e Architetture

## Panoramica

Il Deep Learning è un sottoinsieme del Machine Learning basato su reti neurali artificiali con molti strati (layer). A differenza del ML classico che richiede feature engineering manuale, le reti neurali profonde imparano automaticamente rappresentazioni gerarchiche dai dati grezzi. Il termine "deep" si riferisce alla profondità della rete (numero di layer), non a una qualità filosofica. Reti con 2-3 layer nascosti sono già "deep" rispetto ai perceptron a singolo strato.

Le reti neurali sono il fondamento degli LLM moderni: l'architettura Transformer che alimenta Claude, GPT-4 e Llama è costruita su principi di deep learning. Comprendere MLP, attention, normalizzazione e ottimizzatori è essenziale per capire come funzionano e perché si comportano in un certo modo. In questo documento si copre il deep learning "classico" — per i Transformer, vedi la sezione Modelli.

## 1. Il Neurone Artificiale e l'MLP

### Il Neurone

Il neurone artificiale calcola una combinazione lineare degli input, aggiunge un bias, e applica una funzione di attivazione non lineare:

```
output = activation(w₁x₁ + w₂x₂ + ... + wₙxₙ + b)
       = activation(W·x + b)
```

I pesi W e il bias b sono i parametri che il training ottimizza.

### Funzioni di Attivazione

Le attivazioni introducono non-linearità, senza le quali impilare layer sarebbe equivalente a un singolo layer lineare.

| Funzione | Formula | Range | Quando Usarla |
|----------|---------|-------|---------------|
| **ReLU** | max(0, x) | [0, +∞) | Layer nascosti nelle CNN e MLP. Semplice, efficiente |
| **Leaky ReLU** | max(0.01x, x) | (-∞, +∞) | Evita il "dying ReLU problem" |
| **GELU** | x·Φ(x) | (-∞, +∞) | LLM e Transformer (BERT, GPT). Più smooth di ReLU |
| **Sigmoid** | 1/(1+e^(-x)) | (0, 1) | Output layer classificazione binaria |
| **Tanh** | (e^x - e^(-x))/(e^x + e^(-x)) | (-1, 1) | RNN, gate nelle LSTM |
| **Softmax** | e^(xᵢ)/Σe^(xⱼ) | (0, 1), somma=1 | Output layer classificazione multi-classe |

### MLP (Multi-Layer Perceptron)

L'MLP è la rete neurale più semplice: layer di input → uno o più layer nascosti → layer di output. Adatto per dati tabellari.

```python
import torch
import torch.nn as nn

class MLP(nn.Module):
    def __init__(self, input_dim, hidden_dims, output_dim, dropout_rate=0.3):
        super().__init__()
        layers = []
        prev_dim = input_dim
        for hidden_dim in hidden_dims:
            layers.extend([
                nn.Linear(prev_dim, hidden_dim),
                nn.BatchNorm1d(hidden_dim),
                nn.GELU(),
                nn.Dropout(dropout_rate)
            ])
            prev_dim = hidden_dim
        layers.append(nn.Linear(prev_dim, output_dim))
        self.network = nn.Sequential(*layers)

    def forward(self, x):
        return self.network(x)

# Esempio
model = MLP(input_dim=50, hidden_dims=[256, 128, 64], output_dim=10)
print(f"Parametri totali: {sum(p.numel() for p in model.parameters()):,}")
```

## 2. CNN — Convolutional Neural Networks

Le CNN sono progettate per dati con struttura spaziale (immagini, segnali). Invece di connessioni dense tra tutti i neuroni, usano filtri che scorrono localmente sull'input (**convoluzione**).

### Operazioni Fondamentali

**Convoluzione**: un filtro di dimensione (k×k) scorre sull'immagine, calcolando il prodotto scalare in ogni posizione. Impara a rilevare pattern locali (bordi, texture, forme).

**Pooling**: riduce la dimensione spaziale. Max pooling prende il valore massimo in ogni regione — riduce la risoluzione mantenendo le feature più forti.

```python
class SimpleCNN(nn.Module):
    def __init__(self, num_classes=10):
        super().__init__()
        # Feature extractor
        self.features = nn.Sequential(
            nn.Conv2d(3, 64, kernel_size=3, padding=1),   # input: RGB
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),                            # /2 spaziale
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2, 2),
        )
        # Classifier
        self.classifier = nn.Sequential(
            nn.AdaptiveAvgPool2d((4, 4)),  # output size fisso
            nn.Flatten(),
            nn.Linear(128 * 4 * 4, 512),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(512, num_classes)
        )

    def forward(self, x):
        x = self.features(x)
        return self.classifier(x)
```

### Architetture CNN Storiche e Attuali

| Architettura | Anno | Parametri | Contributo Chiave |
|-------------|------|-----------|-------------------|
| LeNet-5 | 1998 | 60K | Prima CNN pratica (MNIST) |
| AlexNet | 2012 | 60M | Vincitore ImageNet, inizio deep learning era |
| VGG-16/19 | 2014 | 138M | Layer piccoli (3×3), profondità |
| ResNet-50 | 2015 | 25M | Skip connections, reti molto profonde |
| EfficientNet | 2019 | 5-66M | Scaling bilanciato (profondità/larghezza/risoluzione) |
| ConvNeXt | 2022 | 28-350M | CNN modernizzata, competitive con ViT |

**ResNet e skip connections** — la svolta che ha permesso reti con 100+ layer:

```python
class ResidualBlock(nn.Module):
    def __init__(self, channels):
        super().__init__()
        self.conv1 = nn.Conv2d(channels, channels, 3, padding=1)
        self.bn1 = nn.BatchNorm2d(channels)
        self.conv2 = nn.Conv2d(channels, channels, 3, padding=1)
        self.bn2 = nn.BatchNorm2d(channels)
        self.relu = nn.ReLU(inplace=True)

    def forward(self, x):
        residual = x  # identità
        out = self.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        return self.relu(out + residual)  # aggiunta dell'identità
```

## 3. RNN, LSTM e GRU

Le architetture ricorrenti gestiscono sequenze di lunghezza variabile (testo, time series, audio) mantenendo uno **stato nascosto** che codifica la "memoria" della sequenza vista finora.

### Vanishing Gradient Problem

Nelle RNN vanilla, il gradiente si moltiplica per la stessa matrice di pesi ad ogni step temporale. Con sequenze lunghe, il gradiente svanisce (→0) o esplode (→∞), rendendo impossibile imparare dipendenze a lungo raggio.

### LSTM — Long Short-Term Memory

L'LSTM risolve il vanishing gradient con una **cella di stato** (cell state) separata e tre gate che controllano il flusso dell'informazione:

```
forget gate:  fₜ = σ(Wf·[hₜ₋₁, xₜ] + bf)     → cosa dimenticare
input gate:   iₜ = σ(Wi·[hₜ₋₁, xₜ] + bi)     → cosa aggiungere
cell update:  C̃ₜ = tanh(Wc·[hₜ₋₁, xₜ] + bc)  → candidato nuovo stato
cell state:   Cₜ = fₜ⊙Cₜ₋₁ + iₜ⊙C̃ₜ           → nuovo stato cella
output gate:  oₜ = σ(Wo·[hₜ₋₁, xₜ] + bo)     → cosa esporre
hidden state: hₜ = oₜ⊙tanh(Cₜ)               → output
```

```python
# Utilizzo in PyTorch
lstm = nn.LSTM(
    input_size=128,    # dimensione embedding
    hidden_size=256,   # dimensione stato nascosto
    num_layers=2,      # LSTM stacked
    batch_first=True,  # input: (batch, seq, feature)
    dropout=0.2,       # dropout tra i layer
    bidirectional=True # processa sequenza in entrambe le direzioni
)

x = torch.randn(32, 50, 128)  # batch=32, seq_len=50, features=128
output, (h_n, c_n) = lstm(x)
# output: (32, 50, 512) — 256*2 per bidirezionale
```

**GRU (Gated Recurrent Unit)**: versione semplificata di LSTM con solo 2 gate (reset, update). Meno parametri, spesso performance simile.

!!! note "LSTM vs Transformer"
    Per task NLP moderni, i Transformer hanno sostituito LSTM grazie all'attention parallela. Le LSTM rimangono utili per edge devices (meno parametri), time series con sequenze molto lunghe, e quando si vuole un'architettura più interpretabile.

## 4. Transfer Learning

Il transfer learning riusa i pesi di un modello pre-addestrato su un task grande (es. ImageNet con 1.2M immagini, 1000 classi) come punto di partenza per un task più piccolo. Drasticamente più efficiente di training from scratch.

```python
import torchvision.models as models

# Carica ResNet50 pre-trainato su ImageNet
backbone = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V2)

# Feature freezing: congela tutto tranne l'ultimo layer
for param in backbone.parameters():
    param.requires_grad = False

# Sostituisci il classifier per il tuo task
num_classes = 5  # es. 5 tipi di anomalie
backbone.fc = nn.Sequential(
    nn.Dropout(0.3),
    nn.Linear(backbone.fc.in_features, num_classes)
)

# Solo i parametri del nuovo classifier verranno aggiornati
trainable_params = sum(p.numel() for p in backbone.parameters() if p.requires_grad)
print(f"Parametri trainabili: {trainable_params:,}")

# Fine-tuning progressivo: dopo alcune epoch, sblocca gli ultimi layer
def unfreeze_layers(model, num_layers_to_unfreeze=2):
    children = list(model.children())
    for layer in children[-num_layers_to_unfreeze:]:
        for param in layer.parameters():
            param.requires_grad = True
```

## 5. Normalizzazione

### Batch Normalization

Normalizza l'attivazione di ogni mini-batch. Riduce la dipendenza dall'inizializzazione dei pesi, permette learning rate più alti, ha un effetto regolarizzante.

```python
# Prima della funzione di attivazione
nn.Sequential(
    nn.Linear(256, 128),
    nn.BatchNorm1d(128),  # per layer fully-connected
    nn.ReLU()
)
# Nei layer convoluzionali: nn.BatchNorm2d(channels)
```

!!! warning "Batch Normalization e batch size piccoli"
    BatchNorm è instabile con batch size < 8-16. Con batch grandi funziona bene. Alternativa: **LayerNorm** (normalizza su features invece che su batch) — usata nei Transformer e quando il batch size è variabile o piccolo.

### Layer Normalization

```python
# Normalizza sull'ultima dimensione (features)
# Non dipende dal batch size — ideale per Transformer e RNN
nn.LayerNorm(normalized_shape=512)
```

## 6. Optimizer e Learning Rate Scheduling

### Optimizer

```python
# SGD con momentum — buono per CNN, richiede tuning LR attento
optimizer = torch.optim.SGD(
    model.parameters(),
    lr=0.1,
    momentum=0.9,
    weight_decay=1e-4,
    nesterov=True
)

# AdamW — standard per Transformer e LLM
# β1 controlla momentum, β2 controlla adattamento LR per parametro
optimizer = torch.optim.AdamW(
    model.parameters(),
    lr=1e-4,
    betas=(0.9, 0.95),   # β2=0.95 per Transformer (default 0.999)
    weight_decay=0.1     # weight decay più alto per LLM
)
```

### Learning Rate Scheduling

```python
# Cosine Annealing: riduce LR con curva coseno — molto usato
scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
    optimizer, T_max=num_epochs, eta_min=1e-6
)

# Warmup + Cosine (standard per Transformer)
# Con transformers library:
from transformers import get_cosine_schedule_with_warmup
scheduler = get_cosine_schedule_with_warmup(
    optimizer,
    num_warmup_steps=500,    # LR cresce linearmente nelle prime 500 iter
    num_training_steps=10000
)

# OneCycleLR (superconvergenza)
scheduler = torch.optim.lr_scheduler.OneCycleLR(
    optimizer, max_lr=0.01, steps_per_epoch=len(train_loader), epochs=30
)
```

## 7. Training Loop PyTorch Completo

```python
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torch.cuda.amp import autocast, GradScaler

def train_epoch(model, loader, optimizer, scheduler, scaler, device):
    model.train()
    total_loss = 0.0
    correct = 0
    total = 0

    for batch_idx, (inputs, targets) in enumerate(loader):
        inputs, targets = inputs.to(device), targets.to(device)
        optimizer.zero_grad()

        # Mixed precision: forward pass in FP16/BF16
        with autocast(dtype=torch.bfloat16):
            outputs = model(inputs)
            loss = criterion(outputs, targets)

        # Backward in FP32 via scaler per evitare underflow
        scaler.scale(loss).backward()

        # Gradient clipping: evita gradient explosion
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

        scaler.step(optimizer)
        scaler.update()
        scheduler.step()

        total_loss += loss.item()
        _, predicted = outputs.max(1)
        correct += predicted.eq(targets).sum().item()
        total += targets.size(0)

    return total_loss / len(loader), correct / total


def evaluate(model, loader, device):
    model.eval()
    total_loss = 0.0
    correct = 0
    total = 0

    with torch.no_grad():
        for inputs, targets in loader:
            inputs, targets = inputs.to(device), targets.to(device)
            outputs = model(inputs)
            loss = criterion(outputs, targets)
            total_loss += loss.item()
            _, predicted = outputs.max(1)
            correct += predicted.eq(targets).sum().item()
            total += targets.size(0)

    return total_loss / len(loader), correct / total


# Setup
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
model = MyModel().to(device)
criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, weight_decay=0.01)
scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=30)
scaler = GradScaler()  # per mixed precision

# Training loop
best_val_acc = 0.0
patience = 10
no_improve = 0

for epoch in range(100):
    train_loss, train_acc = train_epoch(model, train_loader, optimizer, scheduler, scaler, device)
    val_loss, val_acc = evaluate(model, val_loader, device)

    print(f"Epoch {epoch+1:3d} | Train Loss: {train_loss:.4f} Acc: {train_acc:.3f} | "
          f"Val Loss: {val_loss:.4f} Acc: {val_acc:.3f} | LR: {scheduler.get_last_lr()[0]:.2e}")

    # Early stopping + checkpoint
    if val_acc > best_val_acc:
        best_val_acc = val_acc
        no_improve = 0
        torch.save({'epoch': epoch, 'model_state_dict': model.state_dict(),
                    'optimizer_state_dict': optimizer.state_dict(),
                    'val_acc': val_acc}, 'best_model.pt')
    else:
        no_improve += 1
        if no_improve >= patience:
            print(f"Early stopping dopo {patience} epoch senza miglioramento")
            break
```

## 8. GPU Training

### DataParallel (Single Machine, Multi GPU)

```python
# Semplice ma meno efficiente: replica il modello su ogni GPU
# Il gradiente viene calcolato su ogni GPU e aggregato sulla GPU 0
if torch.cuda.device_count() > 1:
    model = nn.DataParallel(model)
model = model.to(device)
```

### DistributedDataParallel (Consigliato)

```python
# Più efficiente: ogni processo gestisce una GPU
# Avvio: torchrun --nproc_per_node=4 train.py

import torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel as DDP

dist.init_process_group(backend='nccl')
local_rank = int(os.environ['LOCAL_RANK'])
device = torch.device(f'cuda:{local_rank}')

model = MyModel().to(device)
model = DDP(model, device_ids=[local_rank])

# Il sampler distribuisce i batch tra i processi
train_sampler = torch.utils.data.distributed.DistributedSampler(train_dataset)
train_loader = DataLoader(train_dataset, sampler=train_sampler, batch_size=64)
```

## 9. Mixed Precision Training

La mixed precision training usa FP16 o BF16 per il forward/backward pass, riducendo l'utilizzo di VRAM fino al 50% e accelerando il training su hardware moderno (Ampere, Hopper).

```python
from torch.cuda.amp import autocast, GradScaler

scaler = GradScaler()  # scala automaticamente la loss per evitare underflow FP16

with autocast(dtype=torch.float16):  # FP16 per Volta/Turing
    output = model(input)
    loss = criterion(output, target)

# BF16 (Brain Float 16) — preferibile su Ampere+ (A100, H100)
# Stesso range di FP32 ma meno precisione. Non richiede GradScaler
with autocast(dtype=torch.bfloat16):
    output = model(input)
    loss = criterion(output, target)
loss.backward()  # backward in BF16, nessun underflow
```

| Formato | Bit | Range | Precisione | Hardware |
|---------|-----|-------|------------|---------|
| FP32 | 32 | ±3.4×10³⁸ | Alta | Tutti |
| FP16 | 16 | ±65504 | Bassa | Volta+ |
| BF16 | 16 | ±3.4×10³⁸ | Media | Ampere+ |
| FP8 | 8 | Limitato | Molto bassa | Hopper (H100) |

## Best Practices

- **Inizia con un modello piccolo**: verifica che il codice funzioni (overfitta su 1 batch), poi scala.
- **Gradient clipping**: usa sempre `clip_grad_norm_(max_norm=1.0)` per evitare gradient explosion.
- **Logging**: tensorboard o W&B per monitorare loss, LR, gradient norms in tempo reale.
- **Checkpoint**: salva modello e optimizer state ogni N epoch. Il checkpoint permette di riprendere il training.
- **Riproducibilità**: `torch.manual_seed(42)`, `torch.backends.cudnn.deterministic = True`.
- **Profiling**: usa `torch.profiler` per identificare bottleneck (data loading spesso è il collo di bottiglia).
- **Transfer learning sempre**: quasi mai si ha abbastanza dati per training from scratch. Inizia da ImageNet, BERT, o altro pre-trained model.

## Troubleshooting

### Scenario 1 — Loss diventa NaN o esplode durante il training

**Sintomo**: la loss sale a `inf` o diventa `NaN` dopo poche iterazioni; le metriche smettono di aggiornarsi.

**Causa**: gradient explosion (gradienti troppo grandi moltiplicano i pesi fino a overflow), oppure learning rate eccessivamente alto, o input non normalizzati.

**Soluzione**: abilita gradient clipping, riduci il learning rate, verifica che gli input siano normalizzati.

```python
# 1. Gradient clipping — inserire subito prima di optimizer.step()
torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

# 2. Rilevare NaN nei gradienti prima dello step
for name, param in model.named_parameters():
    if param.grad is not None and torch.isnan(param.grad).any():
        print(f"NaN gradient in: {name}")

# 3. Controlla statistiche input
print(f"Input mean: {inputs.mean():.4f}, std: {inputs.std():.4f}")
# Se std >> 1 o mean >> 0 → normalizza
inputs = (inputs - inputs.mean()) / (inputs.std() + 1e-8)
```

---

### Scenario 2 — CUDA out of memory (OOM)

**Sintomo**: `RuntimeError: CUDA out of memory. Tried to allocate X GiB`.

**Causa**: batch size troppo grande, accumulo di tensori nel grafico computazionale (dimenticato `.detach()` o `torch.no_grad()`), o modello troppo grande per la VRAM disponibile.

**Soluzione**: riduci batch size, usa gradient accumulation, attiva mixed precision, svuota la cache CUDA.

```python
# 1. Controlla VRAM disponibile
import torch
print(torch.cuda.memory_summary(device=None, abbreviated=True))

# 2. Gradient accumulation: simula batch più grandi con meno VRAM
accumulation_steps = 4
optimizer.zero_grad()
for i, (inputs, targets) in enumerate(loader):
    with autocast(dtype=torch.bfloat16):
        loss = criterion(model(inputs), targets) / accumulation_steps
    loss.backward()
    if (i + 1) % accumulation_steps == 0:
        optimizer.step()
        optimizer.zero_grad()

# 3. Svuota cache tra run (es. in notebook)
torch.cuda.empty_cache()

# 4. Attiva mixed precision per dimezzare la VRAM
# (vedi sezione Mixed Precision Training)
```

---

### Scenario 3 — Overfitting (train acc alta, val acc bassa)

**Sintomo**: la training accuracy sale sopra al 95% mentre la validation accuracy si ferma o peggiora dopo qualche epoch. Gap crescente tra train loss e val loss.

**Causa**: modello troppo complesso rispetto ai dati disponibili, o dati di training insufficienti/non variati.

**Soluzione**: aumenta il dropout, aggiungi weight decay, usa data augmentation, riduci la capacità del modello.

```python
# 1. Aumenta dropout
nn.Dropout(p=0.5)  # default 0.1-0.3 → prova 0.4-0.5

# 2. Weight decay più aggressivo nell'optimizer
optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4, weight_decay=0.1)

# 3. Data augmentation per immagini (torchvision.transforms)
from torchvision import transforms
augment = transforms.Compose([
    transforms.RandomHorizontalFlip(),
    transforms.RandomCrop(32, padding=4),
    transforms.ColorJitter(brightness=0.2, contrast=0.2),
    transforms.RandomRotation(15),
])

# 4. Early stopping (vedere training loop nella sezione 7)
# → il checkpoint salva il miglior val_acc prima che inizi il degrado
```

---

### Scenario 4 — GPU sottoutilizzata (utilizzo < 50%)

**Sintomo**: `nvidia-smi` mostra GPU utilization bassa (< 50%) durante il training; training più lento del previsto.

**Causa**: il data loading è il collo di bottiglia (CPU-bound), batch size troppo piccolo, o operazioni frequenti CPU↔GPU.

**Soluzione**: aumenta i worker del DataLoader, abilita `pin_memory`, usa `prefetch_factor`, o aumenta il batch size.

```bash
# Monitora GPU in tempo reale
watch -n 1 nvidia-smi

# Profila il training con PyTorch Profiler
```

```python
# 1. Più worker per il DataLoader
loader = DataLoader(
    dataset,
    batch_size=256,          # batch più grande → più lavoro per GPU
    num_workers=8,           # parallelizza il data loading su CPU
    pin_memory=True,         # trasferimento CPU→GPU più veloce
    prefetch_factor=2,       # precarica 2 batch in anticipo
    persistent_workers=True  # evita overhead di riavvio worker
)

# 2. Profiling dettagliato
with torch.profiler.profile(
    activities=[torch.profiler.ProfilerActivity.CPU,
                torch.profiler.ProfilerActivity.CUDA],
    record_shapes=True
) as prof:
    for i, batch in enumerate(loader):
        if i >= 10: break
        train_step(batch)

print(prof.key_averages().table(sort_by="cuda_time_total", row_limit=10))
```

## Riferimenti

- [PyTorch Documentation](https://pytorch.org/docs/stable/) — Documentazione ufficiale
- [Deep Learning (Goodfellow, Bengio, Courville)](https://www.deeplearningbook.org/) — Il testo di riferimento teorico
- [fast.ai Practical Deep Learning](https://course.fast.ai/) — Approccio top-down pratico
- [CS231n — Convolutional Neural Networks (Stanford)](http://cs231n.stanford.edu/) — CNN per visione artificiale
- [Mixed Precision Training (NVIDIA)](https://docs.nvidia.com/deeplearning/performance/mixed-precision-training/index.html) — Guida ufficiale
