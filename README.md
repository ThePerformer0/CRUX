# CRUX — Concurrent Resource Unused eXtractor

CRUX is a static analysis tool designed to detect unnecessary synchronization locks (mutexes, spinlocks, rwlocks) in C/C++ programs by operating on LLVM IR (`.ll` / `.bc`).

## Features & Pipeline

1. **Call Graph Builder**: Interprocedural Call Graph construction with Class Hierarchy Analysis (CHA) for indirect calls.
2. **CFG Builder**: Control Flow Graph extraction per function.
3. **Alias Analyzer**: Field-Based Alias Analysis using Union-Find to map memory registers to canonical IDs.
4. **Lockset Analyzer**: BFS-based CFG analysis calculating held locks per instruction and handling `pthread_cond_wait`.
5. **Site Characterizer**: Extracts lock/unlock boundaries, direct/transitive reads & writes, path conditions, and lockset at entry.
6. **Lock Site Graph (LSG) Builder**: NetworkX graph representation with `SHARE`, `NEST`, and `HB` edges.
7. **Classifier**: Evaluates 6 anti-patterns (`EMPTY_CS`, `LOCAL_VARS`, `READ_ONLY`, `REDUNDANT`, `SINGLE_THREAD`, `THREAD_LOCAL`) with safety guards.
8. **SMT Validator**: Z3 SMT solver integration to prune dead path false positives.
9. **Scorer & Reporter**: Confidence scoring and structured JSON reporting with fix recommendations.

## Usage

```bash
python crux.py <path_to_llvm_ir.ll> --output report.json
```

## Running Tests

```bash
pytest tests/ -v --tb=short
```
