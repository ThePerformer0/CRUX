# AI Model Evaluation: Detecting Useless Locks in C

This directory contains an empirical study evaluating how well modern Large Language Models (LLMs) can detect useless locks in multi-threaded C programs, and measuring the performance cost when useless locks are missed.

---

## 1. Objectives

1. **Evaluate AI Capabilities:** Test if leading AI models (Claude Sonnet 4.5, GPT-4.1, Gemini 3 Flash) can identify unnecessary locks in concurrent C code.
2. **Identify Limitations:** Understand why models fail on complex multi-threaded patterns.
3. **Measure Real Impact:** Measure the exact throughput loss caused by useless locks on real multi-core hardware (CloudLab).

---

## 2. Benchmark Suite (15 Test Cases)

The benchmark contains 15 C test cases with known ground truth, organized into 5 difficulty levels:

* **Level 0 (Trivial):** Locks protecting local stack variables or empty critical sections.
* **Level 1 (Basic):** Read-only data access after thread startup (`pthread_join` synchronization).
* **Level 2 (Intermediate):** Multi-file module initialization and barrier-synchronized reads.
* **Level 3 (Advanced):** Hidden single-writer patterns and non-critical metrics (approximate monitoring).
* **Level 4 (Expert):** Hierarchical locking, callbacks, and distributed invariants across files.

---

## 3. AI Evaluation Results

Each model was given the C source code and asked whether any lock was unnecessary.

### Model Accuracy Table

| Model | Level 0 | Level 1 | Level 2 | Level 3 | Level 4 | Total Score |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **Claude Sonnet 4.5** | 3/3 | 3/3 | 3/3 | 2/3 | 3/3 | **14 / 15 (93.3%)** |
| **GPT-4.1** | 3/3 | 3/3 | 3/3 | 0/3 | 2/3 | **11 / 15 (73.3%)** |
| **Gemini 3 Flash** | 3/3 | 3/3 | 3/3 | 1/3 | 1/3 | **11 / 15 (73.3%)** |

### Key Findings

1. **AI Succeeds on Local Patterns (Levels 0–2):** All models easily find locks on local variables or simple read-after-init data.
2. **AI Fails on Complex Invariants (Levels 3–4):** Models struggle when safety is guaranteed by program architecture rather than local syntax. Because AI models strictly follow the C rule (*"any unsynchronized shared write is a data race"*), they often claim a lock is needed even when the data is idempotent or protected at an outer level.
3. **Why Formal Static Analysis (CRUX) is Needed:** Unlike AI models that rely on text heuristics, CRUX uses mathematical SMT constraint solving and inter-procedural LLVM data-flow analysis to formally prove lock redundancy without hallucinations.

---

## 4. Hardware Performance Impact (CloudLab Measurements)

To measure the cost of missed useless locks, we benchmarked the code with the useless lock (**V1**) against the corrected lock-free version (**V0**) across 1 to 32 threads on CloudLab:

| Benchmark Case | Difficulty Level | Throughput Loss | Scalability Impact |
|---|:---:|:---:|---|
| **Request Metrics** | Level 3 | **~80% loss** | Early bottleneck due to lock contention. |
| **Approximate Monitoring** | Level 3 | **~90% loss** | Heavy overhead on high-frequency paths. |
| **Degraded Mode** | Level 4 | **>95% loss** | Complete failure to scale across multi-core CPU. |
| **Hierarchical Contract** | Level 4 | **~50% loss** | Constant overhead from redundant locking. |

### Summary Takeaway

Useless locks are not harmless:
* They do not cause crashes, making them hard to notice.
* But on multi-core systems, they trigger thousands of kernel `futex` system calls and destroy multi-threaded performance (up to **>95% throughput collapse**).

---

## 5. Directory Structure

```text
experiments/llm_evaluation/
├── README.md               # This summary guide
├── benchmarks/             # 15 C benchmark source codes (Level 0 to Level 4)
├── results/                # Raw outputs and answers for Claude, GPT-4, and Gemini
└── performance_impact/     # CloudLab benchmark scripts, raw CSV data, and plots
    ├── results.csv         # Measured throughput across 1 to 32 threads
    └── images/             # Scalability comparison graphs
```
