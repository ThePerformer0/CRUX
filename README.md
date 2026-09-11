# CRUX — Concurrent Resource Unused eXtractor
> **Static Analysis Framework for Detecting Superfluous Locks in Heterogeneous C/C++ Systems Software**

[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)
[![LLVM IR](https://img.shields.io/badge/LLVM%20IR-14.0%2B-red.svg)](https://llvm.org/)
[![SMT Solver](https://img.shields.io/badge/SMT-Z3%20Solver-green.svg)](https://github.com/Z3Prover/z3)
[![Test Suite](https://img.shields.io/badge/Tests-Pytest%20Passing-brightgreen.svg)](tests/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Artifact Evaluation](https://img.shields.io/badge/Artifact-Ready%20for%20Review-purple.svg)](experiments/)

CRUX is an LLVM IR-level static analyzer designed to identify unnecessary, redundant, and semantically superfluous synchronization primitives (mutexes, spinlocks, rwlocks) in multi-threaded C/C++ systems software, including libraries, database engines, web servers, hypervisors, and operating system kernels.

---

## 1. Quickstart & Kick-the-Tires (2-Minute Sanity Check)

For reviewers and users evaluating the artifact, follow these steps to verify installation and run an immediate end-to-end analysis on an included LLVM IR benchmark in under two minutes:

### 1.1 Installation

```bash
# Clone the repository
git clone https://github.com/ThePerformer0/CRUX.git
cd CRUX

# Install lightweight dependencies (Python 3.9+, Z3, NetworkX, Pytest)
pip install -r requirements.txt
```

### 1.2 Sanity Check (Immediate Analysis Demo)

Run CRUX on a pre-compiled integration test fixture (`test_read_only.ll`) to inspect useless lock detection:

```bash
python crux.py tests/integration/test_read_only.ll -v
```

**Expected Console Output:**
```text
======================================================================
  CRUX Analysis Summary -- tests/integration/test_read_only.ll
======================================================================
  Total Lock Sites    : 1
  Useless Sites (Safe): 1
  Useful Sites (Kept) : 0
  Analysis Time       : ~0.02s
----------------------------------------------------------------------
  Detected Useless Locks:
    * [site_0] worker(): line 14 -> READ_ONLY (mutex: data_mutex)
======================================================================
```

### 1.3 Running the Full Test Suite

```bash
pytest tests/ -v --tb=short
```

---

## 2. Key Features & Theoretical Foundations

*   **LLVM IR Level Analysis**: Operates directly on textual `.ll` and bitcode `.bc` representations, making analysis fully language-agnostic across C and C++.
*   **Lock Site Graph (LSG)**: Constructs a novel multi-directed graph $G = (S, A)$ capturing data sharing conflicts (`SHARE`), hierarchical nesting relationships (`NEST`), and static happens-before phase orderings (`HB`).
*   **6 Formal Anti-Patterns**: Detects `EMPTY_CS`, `LOCAL_VARS`, `READ_ONLY`, `REDUNDANT`, `SINGLE_THREAD`, and `THREAD_LOCAL` using conservative confidence scoring.
*   **4 Strict Soundness Guards**: Built-in safety guards preventing unsound lock removal around indirect function calls, condition variable predicates (`pthread_cond_wait`), recursive mutexes, and asynchronous/escaping locks.
*   **SMT Path Feasibility (Z3)**: Employs symbolic path condition solving to prune dead-code false positives and prove lock unreachability.

For rigorous mathematical proofs, inference rules, and soundness bounds, refer to:
*   📖 **[Formal Specification Document (`docs/formal_specification.md`)](docs/formal_specification.md)**

---

## 3. Pipeline Architecture

```text
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

## 4. Anti-Pattern Summary & Formal Remediation

| Anti-Pattern | Description | Formal Remediation / Fix |
| :--- | :--- | :--- |
| **`EMPTY_CS`** | Critical section contains zero memory accesses and no external function calls. | Eliminate `lock` / `unlock` pair. |
| **`LOCAL_VARS`** | Critical section accesses exclusively stack-allocated (`alloca`) memory registers. | Eliminate `lock` / `unlock` pair. |
| **`READ_ONLY`** | Critical section executes purely memory reads with zero concurrent writes across all threads. | Eliminate lock or convert to reader-lock (`rdlock`). |
| **`REDUNDANT`** | Lock is acquired while an enclosing parent lock covering all accessed variables is already held. | Eliminate inner nested lock acquisition. |
| **`SINGLE_THREAD`** | Lock is invoked strictly during single-threaded boot/init or shutdown phases (`pthread_join` HB edge). | Eliminate initialization lock. |
| **`THREAD_LOCAL`** | Variables accessed exhibit zero observed conflict edges across concurrent threads in the LSG. | Conservative review or lock elision. |

---

## 5. Large-Scale Empirical Evaluation (CloudLab)

CRUX was evaluated on **17 real-world open-source C/C++ projects** deployed on a dedicated bare-metal server on **CloudLab**:
* **Hardware:** Dual Intel Xeon Gold 6338 (20 cores, 40 hardware threads @ 2.00 GHz), 192 GB DDR4 RAM.
* **OS & Toolchain:** Ubuntu 22.04 LTS (Linux Kernel 5.15), Clang 14.0.0 with WLLVM.

### Evaluated Production Systems (17 Targets)

| Domain | Systems Evaluated |
|---|---|
| **OS Kernels & Hypervisors** | Linux Kernel 5.15 (`drivers/`), Xen Hypervisor |
| **Databases & Key-Value Stores** | PostgreSQL, MySQL Server, Redis, Memcached, SQLite3, RocksDB |
| **Web Servers & Proxies** | Nginx, HAProxy, Apache HTTPD, Lighttpd, H2O, Varnish Cache |
| **HPC & Distributed Messaging** | OpenMPI, librdkafka, BusyBox |

### Hardware Scalability Impact

When redundant or useless locks remain in multi-threaded code, they cause severe cache-line bouncing and millions of kernel `futex` context switches. CloudLab hardware measurements across 1 to 32 worker threads demonstrated throughput collapses of **up to >95%** in contended workloads when useless locks are missed.

*Detailed per-project reports, CSV logs, and reproduction benchmarks are available in [`experiments/cloudlab_results/`](experiments/cloudlab_results/).*

---

## 6. Exploratory Study: Frontier LLMs & Developer Habits

Driven by the rapid adoption of AI coding assistants (e.g., GitHub Copilot, Claude, ChatGPT) in modern software engineering workflows, we conducted an exploratory study assessing whether current frontier LLMs can reliably detect useless locks in concurrent C programs.

We evaluated three state-of-the-art models across a 15-benchmark suite spanning 5 difficulty tiers (from trivial stack locks to inter-procedural invariants and relaxed memory semantics):

| Model | Level 0 | Level 1 | Level 2 | Level 3 | Level 4 | Total Accuracy |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Claude Sonnet 5.1** | 3/3 | 3/3 | 3/3 | 2/3 | 2/3 | **13 / 15 (86.7%)** |
| **Gemini 3.8 Flash Lite** | 3/3 | 3/3 | 3/3 | 0/3 | 2/3 | **11 / 15 (73.3%)** |
| **GPT 5.6-Luna** | 3/3 | 3/3 | 3/3 | 0/3 | 1/3 | **10 / 15 (66.7%)** |

### Key Insight
While frontier LLMs excel at syntax-level scoping (100% on Levels 0–2), they suffer from a **dogmatic anti-data-race bias** on advanced cases (Level 3): models reject semantically safe lock removals (e.g., idempotent cache writes, approximate monitoring counters) by treating any unsynchronized concurrent write as illegal undefined behavior. This highlights the vital complementary role of formal static analyzers like CRUX.

*For full experimental methodology, prompt templates, and raw response logs, see [`experiments/llm_evaluation/README.md`](experiments/llm_evaluation/README.md).*

---

## 7. Paper-to-Artifact Mapping (Artifact Evaluation)

To facilitate artifact evaluation by peer reviewers, the table below maps claims, tables, and figures from the research paper directly to artifacts within this repository:

| Paper Element | Description | Corresponding Repository Artifact |
|---|---|---|
| **Section 3 / Formal Model** | Mathematical definitions of LSG, inference rules, and safety guards | [`docs/formal_specification.md`](docs/formal_specification.md) |
| **Section 4 / Implementation** | Core static analysis engine (CFG, Lockset, LSG, Z3 SMT) | [`src/`](src/) and [`crux.py`](crux.py) |
| **Section 5.1 / Table 1** | Real-world static analysis results on 17 production targets | [`experiments/cloudlab_results/`](experiments/cloudlab_results/) |
| **Section 5.2 / Figure 4** | CloudLab multi-threaded throughput & scalability curves (V0 vs V1) | [`experiments/llm_evaluation/performance_impact/images/`](experiments/llm_evaluation/performance_impact/images/) |
| **Section 5.3 / Table 2** | Exploratory LLM study on 15 concurrency test cases | [`experiments/llm_evaluation/README.md`](experiments/llm_evaluation/README.md) |
| **Ground Truth Validation** | Historical production commits confirming useless lock fixes | [`experiments/commit_mining/ground_truth_index.json`](experiments/commit_mining/ground_truth_index.json) |
| **Sanity Check Fixtures** | Minimal `.ll` bitcode cases reproducing each anti-pattern | [`tests/integration/`](tests/integration/) |

---

## 8. Analyzing Custom C/C++ Code

To analyze your own C/C++ software with CRUX, compile source files into textual LLVM IR (`.ll`) using Clang:

```bash
# 1. Compile C source to LLVM IR (unoptimized, with debug symbols and no inlining)
clang -S -emit-llvm -O0 -g -fno-inline -fno-discard-value-names target.c -o target.ll

# 2. Run CRUX static analyzer
python crux.py target.ll --output report.json -v
```

### CLI Options

```bash
python crux.py <path_to_ir.ll> \
    --output report.json \
    --min-score 0.7 \
    --no-smt \
    --custom-locks "my_lock,raw_spin_lock" \
    --custom-unlocks "my_unlock,raw_spin_unlock" \
    -v
```

---

## 9. Repository Structure

```text
CRUX/
├── crux.py                  # Main CLI entrypoint for the static analyzer
├── requirements.txt         # Python dependencies (z3-solver, networkx, pytest)
├── src/                     # Core analysis engine
│   ├── frontend/            # LLVM IR parser, Call Graph, and CFG builders
│   ├── analysis/            # Alias resolver, Lockset dataflow, and site characterizer
│   ├── core/                # Lock Site Graph (LSG) and Anti-Pattern Classifier
│   ├── validation/          # Z3 SMT symbolic path feasibility checker
│   └── output/              # JSON report generator and scoring engine
├── tests/                   # Test suite
│   ├── unit/                # Unit tests for individual analysis passes
│   └── integration/         # End-to-end integration tests on synthetic .ll fixtures
├── docs/                    # Theoretical and formal documentation
│   └── formal_specification.md # Mathematical definitions and soundness proofs
├── paper/                   # LaTeX sources and assets for the research paper
└── experiments/             # Experimental evaluation suites & reproducibility
    ├── cloudlab_results/    # Reports, CSVs, and benchmarks for 17 real systems
    ├── llm_evaluation/      # Exploratory study on frontier LLMs (Claude, GPT, Gemini)
    └── commit_mining/       # Ground-truth index of mined real-world commits
```

---

## 10. Citation

If you use CRUX, its theoretical framework, or its experimental benchmarks in your research, please cite our work:

```bibtex
@inproceedings{crux2026uselesslocks,
  author    = {Anonymous Authors},
  title     = {CRUX: Sound Static Extraction of Superfluous Synchronization in Systems Software},
  booktitle = {Proceedings of the International Conference on Systems and Software},
  year      = {2026}
}
```

---

## 11. License

This project is licensed under the [Apache License 2.0](LICENSE).


