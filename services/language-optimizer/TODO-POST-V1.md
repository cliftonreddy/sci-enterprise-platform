# GraalVM Auto-Optimizer — Post-V1 TODO

## Priority Queue (as of 2026-04-01)

| # | Item | Notes |
|---|------|-------|
| 1 | Thread safety — `synchronized` native dispatch | Quick fix; needed before any concurrent use |
| 2 | Tab 3 Saved Benchmark Results | JSON file + 2 API endpoints + UI tab; fully spec'd below |
| 3 | CI/CD GitHub Actions | Energy delta report per commit; block regressions |
| 4 | RAPL real energy measurement | Needs bare-metal Linux or cloud VM (AWS/Azure) — not available on Windows/WSL2 |
| 5 | BankingPOC Rust implementations | 3-way Java vs C vs Rust energy comparison |

---

## V2 Local Classifier (Tier 2 Improvements)

### Current State
- Tier 2 uses hand-crafted keyword features + sklearn SVM
- 60 manually defined signals (sort, merge, gaussian, volatility etc.)
- Trained on 127 labeled examples across 11 SLE'17 categories
- CV accuracy: ~72% — adequate but not great
- Docker image: ~800MB (no torch, no nvidia)

### Why CodeBERT Was Abandoned
- Docker network policy blocks pytorch.org SSL certificate
- Fallback to PyPI downloads GPU torch → 6GB image with nvidia libraries
- CPU-only torch wheel not accessible from Docker build environment

### What Should Be Done for V2
1. **Fix Docker SSL issue** — add corporate CA certificate to Docker build context
   so pytorch.org download works:
   ```dockerfile
   COPY certs/corporate-ca.crt /usr/local/share/ca-certificates/
   RUN update-ca-certificates
   RUN pip install torch --index-url https://download.pytorch.org/whl/cpu
   ```

2. **Switch back to CodeBERT embeddings** — replace `extract_features()` in
   `local_classifier.py` with CodeBERT embedding generation. The SVM trained on
   768-dim CodeBERT embeddings achieved better semantic understanding than 60
   hand-crafted features.

3. **Retrain on CodeBERT embeddings** — run `scripts/train_classifier.py` with
   CodeBERT enabled. Expected CV accuracy: 80%+ vs current 72%.

4. **Consider pre-trained code classifiers** — instead of training our own SVM,
   use CodeT5 or StarCoder which are already fine-tuned on code tasks. These
   would give better generalization on novel patterns without any training data.

5. **Add more training examples** — current 127 examples is marginal. Target
   500+ examples per category for reliable SVM generalization. Can use Claude
   to generate synthetic variants of each category.

6. **Confidence calibration** — current threshold is 0.65. Tune this per-category
   based on precision/recall tradeoff on a held-out validation set.

---

## Rust as Target Language

### What Needs to Be Done
1. **rule_engine.py** — add Rust as target for memory-heavy patterns:
   - binary_trees → Rust (memory safety + 1.03x energy vs C)
   - hash_map operations → Rust
   - string processing → Rust

2. **ai_analyzer.py** — update prompt to tell Claude to generate Rust when
   recommended_language = "Rust". Add Rust to TARGET_LANGUAGES dict.

3. **code_generator.py** — add `_build_rust_file()` method:
   - Functions need `#[no_mangle] pub extern "C"` signatures
   - Generate Cargo.toml for the package
   - Compile with: `rustc --emit=llvm-bc -O --crate-type=cdylib file.rs`

4. **Dockerfile (generator)** — add Rust to builder stage:
   ```dockerfile
   RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
   ENV PATH="/root/.cargo/bin:$PATH"
   RUN for f in native/*.rs; do rustc --emit=llvm-bc -O --crate-type=cdylib "$f"; done
   ```

5. **TestSuite.java.template** — no changes needed (language agnostic)

6. **BankingPOC** — add Rust implementations of the 5 functions alongside C
   for benchmark comparison (paper data: Rust vs Java vs C energy)

### Key Facts
- Rust compiles to LLVM bitcode via `rustc --emit=llvm-bc`
- GraalVM Sulong loads Rust bitcode identically to C bitcode
- SLE'17: Rust = 1.03x energy vs C (essentially identical)
- No changes needed to _GraalContext.java — it loads any .bc file
- C implementation will NOT break when Rust is added (separate .bc files)

---

## Thread Safety

### Current State
- `_GraalContext` uses C-side global variables (setter/getter pattern)
- Not thread-safe — concurrent calls will corrupt each other's data
- Acceptable for single-threaded demo and paper

### What Should Be Done for Production
**Option A — Synchronized methods (quick fix):**
Add `synchronized` keyword to each native dispatch call in generated Java:
```java
public static synchronized double computeRiskScore(...) { ... }
```

**Option B — ThreadLocal GraalVM Context (proper fix):**
```java
static final ThreadLocal<Context> threadCtx = ThreadLocal.withInitial(() ->
    Context.newBuilder().allowAllAccess(true).build());
```
Each thread gets its own GraalVM context with its own copy of C globals.

**Option C — Stateless C via polyglot.h (best long-term):**
Use GraalVM's polyglot.h header for zero-copy array sharing.
Requires compiling C with GraalVM's own LLVM toolchain (not system clang).
Eliminates both the setter/getter pattern and thread safety issues.

---

## Tab 3 — Saved Benchmark Results

### Current State
- Section 2 Live Benchmark calls BankingPOC at localhost:8080
- If BankingPOC is shut down, Section 2 shows no data

### What Should Be Done
Add a third tab to EnergyDashboard.jsx:
- When benchmark runs successfully, save results to optimizer's local storage
- Tab 3 shows historical results even when BankingPOC is offline
- Store in optimizer's PostgreSQL or a simple JSON file

---

## CI/CD Integration

- GitHub Actions workflow that runs optimizer on each commit
- Reports energy delta vs previous build
- Blocks merges that increase estimated energy beyond threshold

---

## Real Energy Measurement (RAPL)

- Current energy estimation uses SLE'17 power constants × wall-clock time
- RAPL (Running Average Power Limit) gives exact joule measurements
- Requires Linux kernel access — not available in Docker without `--privileged`
- For production: sidecar container with RAPL access, REST API to main container

---

## Tab 3 — Saved Benchmark Results (Energy Dashboard)

### Current State
- Section 2 Live Benchmark calls BankingPOC at localhost:8080
- If BankingPOC is shut down, Section 2 shows no data
- No persistence of past benchmark runs in the optimizer

### What Should Be Done

**Add a third tab to EnergyDashboard.jsx:**

```
Tab 1: Live Benchmark    ← calls BankingPOC (needs it running)
Tab 2: SLE'17 Estimates  ← pure calculation, always available
Tab 3: Saved Results     ← reads from optimizer's own storage
```

**Storage options (pick one):**

Option A — Simple JSON file on disk:
- When benchmark runs successfully, append results to `/app/data/benchmark_history.json`
- Tab 3 reads this file via a new API endpoint `GET /api/saved-benchmarks`
- Survives BankingPOC shutdown, Docker restarts (if volume mounted)

Option B — SQLite in the optimizer container:
- Add SQLite database to optimizer container
- Store: run_id, timestamp, function, java_ms, native_ms, energy_saving_pct, regime
- Tab 3 queries via `GET /api/saved-benchmarks`

Option C — Use existing BankingPOC PostgreSQL:
- BankingPOC already stores benchmark results
- Tab 3 reads from `localhost:8080/api/benchmark/history`
- Simple but still requires BankingPOC running

**Recommended: Option A (JSON file)**
- No new dependencies
- Add volume mount to docker-compose.yml: `- ./data:/app/data`
- New endpoint in server.py: `GET /api/saved-benchmarks`
- New endpoint in server.py: `POST /api/save-benchmark` (called after live benchmark)
- Update EnergyDashboard.jsx to save results after successful run
- Tab 3 displays saved results table with timestamps

### API Changes Needed

```python
# server.py additions

@app.get("/api/saved-benchmarks")
def get_saved_benchmarks():
    path = Path("/app/data/benchmark_history.json")
    if not path.exists():
        return {"results": []}
    with open(path) as f:
        return {"results": json.load(f)}

@app.post("/api/save-benchmark")
def save_benchmark(data: dict):
    path = Path("/app/data/benchmark_history.json")
    path.parent.mkdir(exist_ok=True)
    history = []
    if path.exists():
        with open(path) as f:
            history = json.load(f)
    history.append({**data, "savedAt": datetime.now().isoformat()})
    with open(path, "w") as f:
        json.dump(history[-100:], f)  # keep last 100 runs
    return {"ok": True}
```

### UI Changes Needed

In EnergyDashboard.jsx BenchmarkPanel:
- After successful benchmark run, call `POST /api/save-benchmark` with results
- Add Tab 3 component that calls `GET /api/saved-benchmarks`
- Display as a table: timestamp, Monte Carlo saving %, regime counts, JVM version

### docker-compose.yml Change
```yaml
volumes:
  - ./optimized:/app/optimized
  - ./data:/app/data          # ← add this
  - C:\GreenSoftware\models\codebert:/app/models/codebert:ro
```
