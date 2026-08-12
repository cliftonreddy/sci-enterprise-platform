# ⚡ GraalVM Auto-Optimizer

Paste **any program** in any language → AI analyzes each function → splits hot functions into optimal native languages → stitches back via GraalVM Polyglot → you run it **the same way as before**.

---

## What It Does

```
You paste:   python binary_trees.py 10
             ↓
AI Analysis: make_tree()   → C++ (binary-trees benchmark, pool allocator)
             check_tree()  → C++ (recursive traversal, ~25% saving)
             get_argchunks → C   (simple iteration, ~52% saving)
             main()        → keep in Python (orchestrator)
             ↓
Generated:   binary_trees.py      ← modified Python orchestrator
             native/native_cpp.cpp ← C++ hot functions
             native/native_c.c     ← C hot functions
             build.sh              ← compile native modules
             run.sh                ← drop-in replacement
             Dockerfile            ← containerized GraalVM runtime
             ↓
You run:     ./run.sh 10           ← same as python binary_trees.py 10
         or: docker compose run graalvm-optimizer 10
```

---

## Supported Input Languages

| Language | Detected by | Orchestrator runtime |
|---|---|---|
| Python | `.py` / imports | GraalPy / CPython |
| Java | `.java` / class | GraalVM JDK |
| JavaScript / Node.js | `.js` / require | GraalJS / Node |
| Ruby | `.rb` / def/end | TruffleRuby |
| R | `.r` / function() | FastR |

## Native Target Languages (hot functions)

| Target | Used for | GraalVM runtime |
|---|---|---|
| C | Loops, sorting, sieve, iteration | Sulong (LLVM bitcode) |
| C++ | Trees, deep recursion, allocators | Sulong (LLVM bitcode) |
| JavaScript | I/O, string ops, regex | GraalJS |

---

## Quick Start

### Option 1 — Docker (recommended, no install needed)

```bash
# 1. Copy your API key
cp .env.example .env
# Edit .env → ANTHROPIC_API_KEY=sk-ant-...

# 2. Start the service
docker compose up --build

# 3. Open the web UI
open http://localhost:8000/app

# 4. Paste your code, click Analyze, then Download Package
```

### Option 2 — CLI (Python 3.8+ required)

```bash
pip install -r requirements.txt

# Analyze and generate package
python optimize.py my_program.py

# Or with explicit API key
python optimize.py my_program.py --api-key sk-ant-...

# Report only (no file generation)
python optimize.py my_program.py --report-only
```

---

## Generated Package Structure

```
optimized/my_program/
├── my_program.py          ← modified orchestrator (drop-in replacement)
├── native/
│   ├── native_cpp.cpp     ← C++ hot functions
│   ├── native_cpp.bc      ← LLVM bitcode (GraalVM loads this)
│   ├── native_cpp.so      ← shared lib (ctypes fallback)
│   ├── native_c.c         ← C hot functions
│   ├── native_c.bc
│   └── native_c.so
├── build.sh               ← compile native modules
├── run.sh                 ← run exactly like original
├── Dockerfile             ← GraalVM container for the generated program
├── docker-compose.yml
├── REPORT.md              ← optimization report
└── manifest.json          ← machine-readable package manifest
```

---

## How GraalVM Polyglot Works

The modified orchestrator uses GraalVM's Polyglot API to call native functions:

```python
# Original Python:
def make_tree(d):
    if d > 0:
        d -= 1
        return (make_tree(d), make_tree(d))
    return (None, None)

# Generated polyglot stub:
# [GraalVM → C++] binary-trees benchmark, C++ wins with pool allocator
def make_tree(d):
    return _lib_native_cpp.make_tree(d)
```

Under GraalVM, `_lib_native_cpp.make_tree()` is a **direct JIT-optimized call** into C++ — no subprocess, no IPC, no ctypes marshaling overhead. The JIT compiler sees across the language boundary and can inline the C++ function into the Python call site.

With a ctypes fallback for non-GraalVM environments, the package runs everywhere.

---

## Energy Savings Reference (SLE'17 Paper)

| Pattern | Best Language | vs Java | vs Python |
|---|---|---|---|
| Tree alloc/dealloc | C++ | 1.6× | 50× |
| Sorting / loops | C | 2.1× | 76× |
| Simple iteration | C | 2.1× | 76× |
| Deep recursion | C++ | 1.6× | 40× |
| Hash / set ops | C | 2.1× | 76× |
| String / regex / I/O | JavaScript | 1.6× | 23× |
| Orchestration | keep | — | — |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Docker Container (GraalVM Community 21)                     │
│                                                             │
│  ┌──────────────────┐    ┌─────────────────────────────┐   │
│  │  FastAPI :8000   │    │  React UI (static)          │   │
│  │  /api/analyze    │    │  /app                       │   │
│  │  /api/generate   │    └─────────────────────────────┘   │
│  └────────┬─────────┘                                       │
│           │                                                 │
│  ┌────────▼─────────┐                                       │
│  │  AI Analyzer     │──────────► Claude API (external)      │
│  │  (ai_analyzer.py)│                                       │
│  └────────┬─────────┘                                       │
│           │                                                 │
│  ┌────────▼─────────┐                                       │
│  │  Code Generator  │                                       │
│  │  - native files  │                                       │
│  │  - orchestrator  │                                       │
│  │  - Dockerfile    │                                       │
│  │  - build/run.sh  │                                       │
│  └──────────────────┘                                       │
└─────────────────────────────────────────────────────────────┘
```
