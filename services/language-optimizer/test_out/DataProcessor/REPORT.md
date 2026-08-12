# GraalVM Polyglot Optimization Report
**Source:** `DataProcessor.java` (java)
**Functions analyzed:** 6
**Functions moved to native:** 4
**Average energy saving:** ~40%

## Function Breakdown

| Function | Original | → Target | Saving | Reason |
|---|---|---|---|---|
| `countWordFrequency()` | java | **Rust** | ~42% | HashMap counting pattern matches K-NUCLEOTIDE benchmark where Rust's safe hash maps provide significant energy efficiency |
| `countKmers()` | java | **Rust** | ~42% | K-mer counting is classic K-NUCLEOTIDE pattern where Rust's safe hash maps excel over Java HashMap |
| `computeTreeDepth()` | java | **Rust** | ~38% | Binary tree traversal matches BINARY-TREES benchmark where Rust's ownership model provides energy efficiency |
| `sumTreeValues()` | java | **Rust** | ~38% | Tree traversal and accumulation matches BINARY-TREES benchmark pattern where Rust excels |
| `processData()` | java | **keep (orchestrator)** | ~0% | Orchestration functions should remain in original language for coordination |
| `TreeNode()` | java | **keep** | ~0% | SLE'17 category 'trivial' detected by CodeBERT classifier (83% confidence) |

## Architecture
```
DataProcessor.java  (orchestrator — java)
  └──► native_rust  [Rust]  countWordFrequency()
  └──► native_rust  [Rust]  countKmers()
  └──► native_rust  [Rust]  computeTreeDepth()
  └──► native_rust  [Rust]  sumTreeValues()
```

## How to Run
```bash
# Build native modules
bash build.sh

# Run exactly like the original
./run.sh [original arguments]

# Or with Docker
docker compose build
docker compose run graalvm-optimizer [original arguments]
```

## Paper Reference
_Energy Efficiency Across Programming Languages_ — Pereira et al., SLE'17