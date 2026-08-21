# CRUX — Concurrent Resource Unused eXtractor
> **Static Analysis Framework for Detecting Superfluous Locks in Heterogeneous C/C++ Systems Software**

CRUX is an LLVM IR-level static analyzer designed to identify unnecessary and redundant synchronization primitives (mutexes, spinlocks, rwlocks) in multi-threaded C/C++ applications, libraries, hypervisors, and kernels.

---

## Key Features & Theoretical Grounding

*   **LLVM IR Level Analysis**: Operates directly on `.ll` / `.bc` representations, agnostic to high-level language syntaxes.
*   **Lock Site Graph (LSG)**: Novel multi-directed graph $G = (S, A)$ capturing data conflicts (`SHARE`), hierarchical nesting (`NEST`), and static phase ordering (`HB`).
*   **6 Formal Anti-Patterns**: Detects `EMPTY_CS`, `LOCAL_VARS`, `READ_ONLY`, `REDUNDANT`, `SINGLE_THREAD`, and `THREAD_LOCAL` (evaluated with conservative confidence scoring).
*   **4 Strict Safety Guards**: Built-in sound filtering for indirect calls, condition variables (`pthread_cond_wait`), recursive mutexes, and asynchronous/escaping locks.
*   **SMT Path Feasibility (Z3)**: Automated dead-path pruning eliminating infeasible control-flow branches.

For complete mathematical definitions, inference rules, and soundness bounds, see:
*   📖 **[Formal Specification Document (`docs/formal_specification.md`)](file:///c:/Users/performer/Desktop/Crux/docs/formal_specification.md)**

---

## Pipeline Architecture

```
[ LLVM IR (.ll / .bc) ]
         │
         ▼
 1. Call Graph Builder       ── Interprocedural call tree with CHA fallback
         │
         ▼
 2. CFG Builder              ── Flow-sensitive per-function basic block control graphs
         │
         ▼
 3. Field-Based Alias        ── Union-Find canonical memory register mapping
         │
         ▼
 4. BFS Lockset Analyzer     ── Fixed-point dataflow tracking held locks per instruction
         │
         ▼
 5. Site Characterizer       ── Direct/transitive read/write sets & path conditions
         │
         ▼
 6. LSG Builder              ── Multi-relational graph (SHARE, NEST, HB edges)
         │
         ▼
 7. Anti-Pattern Classifier  ── Evaluates 6 anti-patterns with 4 safety guards
         │
         ▼
 8. Z3 SMT Validator         ── Prunes UNSAT path condition false positives
         │
         ▼
 9. Scorer & Reporter        ── Confidence scoring [0.0 - 1.0] and structured JSON output
```

---

## Anti-Pattern Summary

| Anti-Pattern | Description | Remediation / Fix |
| :--- | :--- | :--- |
| **`EMPTY_CS`** | Critical section contains no memory accesses or function calls | Remove lock/unlock pair |
| **`LOCAL_VARS`** | Critical section accesses only stack-allocated (`alloca`) variables | Remove lock/unlock pair |
| **`READ_ONLY`** | Critical section performs purely reads with zero concurrent writes | Remove lock or convert to `rdlock` |
| **`REDUNDANT`** | Lock is already acquired under an enclosing parent lock covering all variables | Remove inner nested lock |
| **`SINGLE_THREAD`** | Lock is executed in single-threaded init/teardown phase | Remove initialization lock |
| **`THREAD_LOCAL`** | Variables accessed exhibit no observed concurrent conflict | Conservative review / remove |

---

## Installation & Requirements

```bash
pip install -r requirements.txt
```

Prerequisites:
*   Python 3.9+
*   LLVM / Clang (for bitcode compilation)
*   `z3-solver`, `networkx`, `pytest`

---

## Usage

### 1. Analyzing an LLVM IR File

```bash
python crux.py <path_to_bitcode.ll> --output report.json
```

### 2. Options

```bash
python crux.py <path_to_bitcode.ll> \
    --output report.json \
    --min-score 0.7 \
    --no-smt
```

---

## Running Test Suite

```bash
# Run all unit and integration tests
pytest tests/ -v --tb=short
```

