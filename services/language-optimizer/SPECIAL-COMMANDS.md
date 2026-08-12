# GraalVM Auto-Optimizer — Special Setup Commands Reference

These are one-time or non-standard commands that are NOT part of the regular
`docker compose up / build` workflow. Keep this document — these commands are
easy to lose and hard to reconstruct.

---

## BankingPOC — Local Maven Build Required

### Why
GraalVM CE 22.3.3 is not on Maven Central. The Docker build could not download
it automatically. The solution was to build the JAR locally first, then copy it
into the Docker build context.

### Command
```powershell
cd C:\GreenSoftware\BankingPOC
mvn clean package -DskipTests
```

This produces `target/banking-poc-1.0-SNAPSHOT.jar` which the Dockerfile then
copies in rather than downloading.

### When to Re-Run
- After any changes to Java source files in BankingPOC
- After changing pom.xml dependencies
- After a clean checkout of the repo

---

## GraalVM Component Installation (Inside Docker)

### Why
GraalVM CE 22.3.3 requires `gu` (GraalVM Updater) to install the LLVM runtime.
These are separate components — NOT included in the base GraalVM download.

### Commands (handled automatically in Dockerfile, listed here for reference)
```bash
gu install llvm
gu install llvm-toolchain
```

### Important Note
GraalVM CE 22.3.3 is the LAST version with a working `gu` tool.
Later versions removed `gu` in favour of standalone distributions.
Do not upgrade GraalVM without testing the gu installation first.

---

## CodeBERT Model Download (Windows, One-Time)

### Why
The local classifier (Tier 2) uses CodeBERT embeddings for training.
Model weights must be downloaded once to your Windows machine.

### Commands
```powershell
# Create model directory
mkdir C:\GreenSoftware\models\codebert

# Install dependencies
pip install transformers torch sentencepiece tokenizers

# Download model weights (~450MB)
python -c "
from transformers import AutoModel, AutoTokenizer
AutoTokenizer.from_pretrained('microsoft/codebert-base', cache_dir='C:/GreenSoftware/models/codebert')
AutoModel.from_pretrained('microsoft/codebert-base', cache_dir='C:/GreenSoftware/models/codebert')
print('Done')
"
```

### Where Files Land
```
C:\GreenSoftware\models\codebert\
└── models--microsoft--codebert-base\
    └── snapshots\
        └── 3b0952feddeffad0063f274080e3c23d75e7eb39\
            ├── config.json
            ├── pytorch_model.bin   ← 450MB weights
            ├── tokenizer.json
            └── vocab.json
```

### Current Status
CodeBERT is NOT being used at runtime (Docker SSL blocks pytorch.org).
The weights are only used during training if you switch back to CodeBERT.
See TODO-POST-V1.md for how to re-enable CodeBERT.

---

## SLE'17 Classifier Training (Windows, One-Time + After Adding Examples)

### Why
The Tier 2 local classifier must be trained before the optimizer can use it.
Training produces `sle17_classifier.pkl` which is loaded by Docker at runtime.

### Command
```powershell
cd C:\GreenSoftware\AILanguageOptimization
python scripts/train_classifier.py
```

### Output
```
C:\GreenSoftware\models\codebert\sle17_classifier.pkl
```

### When to Re-Run
- After adding new training examples to `analyzer/training_data.py`
- After changing the feature extraction in `analyzer/local_classifier.py`
- After changing SVM hyperparameters in `scripts/train_classifier.py`
- After switching from hand-crafted features back to CodeBERT embeddings

### Dependencies
```powershell
pip install scikit-learn numpy
# If using CodeBERT embeddings (currently disabled):
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install transformers sentencepiece tokenizers
```

---

## UI Rebuild (Required After Any UI File Change)

### Why
The React UI is pre-built locally and copied into Docker.
Docker does NOT run `npm install` or `npm run build` (hangs in Docker).

### Command
```powershell
cd C:\GreenSoftware\AILanguageOptimization\ui
npm run build
cd ..
docker compose down
docker compose up --build
```

### When to Re-Run
- After ANY change to files in `ui/src/`
- After changing `ui/package.json`

### Files That Trigger This
- `ui/src/App.jsx`
- `ui/src/EnergyDashboard.jsx`
- Any new component added to `ui/src/`

---

## C Bitcode Compilation (Inside Polyglot Package)

### Why
The generated polyglot package's Dockerfile compiles C to LLVM bitcode.
This is part of `docker compose build` for the GENERATED package (not the optimizer).

### What It Does
```bash
clang -O2 -emit-llvm -c native_c.c -o native_c.bc --target=x86_64-unknown-linux-gnu
clang++ -O2 -emit-llvm -c native_cpp.cpp -o native_cpp.bc --target=x86_64-unknown-linux-gnu
```

### Common Errors and Fixes
| Error | Fix |
|-------|-----|
| `use of undeclared identifier 'volatility'` | Bug in generated C — `volatility` used outside scope. Fixed in `_fix_common_c_issues()` |
| `ULONG_MAX` undeclared | Missing `#include <limits.h>` — fixed in `_fix_common_c_issues()` |
| `redefinition of 'z1'` | Duplicate static variable across functions — fixed in `_fix_common_c_issues()` |
| `abs()` on long type | Use `labs()` instead — warning only, not error |

---

## Python Dependencies — Full Install List

### For Running the Optimizer (Docker handles this automatically)
```powershell
pip install fastapi uvicorn requests python-multipart scikit-learn numpy
```

### For Training the Classifier (Windows only)
```powershell
pip install scikit-learn numpy
# Optional (CodeBERT, currently disabled in Docker):
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install transformers sentencepiece tokenizers
```

### For the UI
```powershell
cd C:\GreenSoftware\AILanguageOptimization\ui
npm install
```

---

## Checking What's Running

```powershell
# See all running containers
docker ps

# See optimizer logs live
docker logs graalvm-optimizer -f

# Check classifier status
curl http://localhost:8000/health

# Check BankingPOC is running
curl http://localhost:8080/api/benchmark/history

# Check generated package test suite passed during build
docker compose build 2>&1 | Select-String "PASS|FAIL|Results"
```

---

## Port Reference

| Service | Port | URL |
|---------|------|-----|
| AILanguageOptimization (optimizer UI) | 8000 | http://localhost:8000 |
| BankingPOC (benchmark target) | 8080 | http://localhost:8080 |
| PostgreSQL (BankingPOC database) | 5432 | localhost:5432 |
| Generated polyglot package | N/A | runs and exits |

---

## Rust Toolchain Installation

### Why
Rust is needed in two places:
1. Inside the optimizer Docker container — for validating Claude-generated Rust code
2. Inside the generated polyglot package Docker build — for compiling Rust to LLVM bitcode

### Optimizer Dockerfile (auto-installed during docker compose build)
```dockerfile
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable
ENV PATH="/root/.cargo/bin:$PATH"
```

### Generated Package Dockerfile (auto-generated by code_generator.py)
Same curl command added to builder stage automatically.

### Verify Rust is available in optimizer container
```powershell
docker exec graalvm-optimizer rustc --version
docker exec graalvm-optimizer which rustc
```

### Test Rust compilation inside optimizer
```powershell
docker cp test_rust.py graalvm-optimizer:/tmp/test_rust.py
docker exec graalvm-optimizer python3 /tmp/test_rust.py
```

---

## Force-Copying Files Into Running Container

When you need to update a Python file without rebuilding the entire Docker image:

```powershell
# Copy single file directly into running container
docker cp C:\GreenSoftware\AILanguageOptimization\analyzer\code_validator.py graalvm-optimizer:/app/analyzer/code_validator.py

# Restart container to pick up changes (faster than full rebuild)
docker restart graalvm-optimizer
```

### When to use this vs docker compose up --build
- Use `docker cp` + `docker restart` for: Python file changes, quick fixes
- Use `docker compose up --build` for: Dockerfile changes, requirements.txt changes, new dependencies

---

## Mixed Language Test Files

### DataProcessor.java — tests Rust recommendations
Location: Generated by Claude session, tests HashMap/tree patterns
Expected: countWordFrequency → Rust, countKmers → Rust, computeTreeDepth → Rust

### MixedOptimizer.java — tests all three languages
Location: outputs/MixedOptimizer.java
Expected:
  sortPrices          → C    (sorting)
  runSimulation       → C    (Monte Carlo)
  computeAmortization → C    (amortization)
  evaluateRisk        → C++  (deep recursion)
  countFrequency      → Rust (HashMap)
  buildIndex          → Rust (HashMap/tree)
  loadConfig          → keep (I/O)
  orchestrate         → keep (orchestration)
