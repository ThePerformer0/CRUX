# CRUX Experimental Evaluation Artifacts

This directory contains the experimental artifacts, raw CRUX static analysis reports, benchmark reproduction code, per-site lock validation tables, and end-to-end application performance metrics evaluated on a dedicated **CloudLab** bare-metal server.

---

## 1. Hardware & Environment Specifications
* **Platform:** CloudLab Utah Cluster (`amd008` / `c6520`)
* **CPU:** Intel Xeon Gold 6338 (20 physical cores, 40 threads @ 2.00 GHz) / AMD EPYC
* **RAM:** 192 GB DDR4 ECC
* **OS:** Ubuntu 22.04 LTS (Linux Kernel 5.15.0-x86_64)
* **Compiler & LLVM:** Clang/LLVM 14.0.0, WLLVM 1.3.0
* **Static Analysis Tool:** CRUX 3.0 (Inter-procedural SMT-verified lock uselessness detector)

---

## 2. Directory Structure & File Purpose

Each evaluated project has its own dedicated directory containing 4 complementary files:

```text
experiments/cloudlab_results/
├── README.md                       # Comprehensive artifact guide (this file)
├── machine_specs2.txt              # Raw server hardware & environment dump
│
├── memcached/
│   ├── memcached_report.json       # [1] Raw CRUX static analysis report (218 lock sites)
│   ├── results_memcached.csv       # [2] Per-site lock validation & micro/macro measurements
│   ├── global_performance.txt      # [3] End-to-end application performance report (memtier)
│   └── bench_cache.c               # [4] Standalone multi-threaded cache benchmark harness
│
├── librdkafka/
│   ├── librdkafka_report.json      # [1] Raw CRUX static analysis report (2,831 lock sites)
│   ├── results_librdkafka.csv      # [2] Per-site lock validation table
│   ├── global_performance.txt      # [3] Global broker broadcast pipeline evaluation
│   ├── bench_wakeup.c              # [4] Multi-broker wakeup broadcast benchmark
│   └── bench_stats.c               # [4] Thread-local statistics rollover benchmark
│
├── h2o/
│   ├── h2o_report.json             # [1] Raw CRUX static analysis report (91 lock sites)
│   ├── results_h2o.csv             # [2] Per-site lock validation table
│   ├── global_performance.txt      # [3] TLS handshake engine global performance report
│   └── bench_neverbleed.c          # [4] Standalone 16-thread TLS key access benchmark
│
├── xen/
│   ├── xen_report.json             # [1] Raw CRUX static analysis report (653 lock sites)
│   ├── results_xen.csv             # [2] Per-site lock validation table
│   ├── global_performance.txt      # [3] Hardware trap interception global performance report
│   └── bench_xen_spinlock.c        # [4] Multi-core spinlock contention benchmark
│
└── [remaining_projects]/           # postgres, mysql, sqlite3, duckdb, rocksdb, openmpi...
    └── results_[project].csv
```

---

## 3. Explanation of Each Artifact Type

### A. Raw CRUX JSON Report (`*_report.json`)
Contains the complete machine-readable output produced by CRUX when analyzing the project's LLVM IR bitcode (`.ll`). It contains:
* Total number of synchronization lock sites discovered ($S$).
* Detailed list of useless lock sites ($\mathcal{U}$) with their precise LLVM IR instructions, source file, line number, enclosing function, and formal mathematical classification (`LOCAL_VARS`, `REDUNDANT`, `READ_ONLY`, `EMPTY_CS`).
* Total inter-procedural graph edges analyzed (`share` memory alias edges and `nest` lock nesting edges).
* Exact analysis execution time.

### B. Per-Site CSV Table (`results_*.csv`)
Provides a strictly one-row-per-lock-site tabular breakdown of all identified lock sites:
* `Lock_ID`: CRUX internal identifier (e.g. `s83`, `s113`).
* `File`, `Function`, `Line`: Exact source location in the C codebase.
* `Pattern`: Formal uselessness reason diagnosed by CRUX.
* `True_Positive`: Manual validation by human source inspection (`Yes`).
* `Benchmark_Tool`: Tool and configuration used to test the isolated lock site.
* `Base_Throughput` / `Patched_Throughput`: Throughput before and after removing the lock.
* `Throughput_Gain`: Percentage throughput increase.
* `Base_Latency` / `Patched_Latency`: Latency / execution time before and after patch.
* `Latency_Gain`: Positive percentage latency improvement / reduction (+%).

### C. Global Performance Report (`global_performance.txt`)
Documents the cumulative, end-to-end performance of the **entire application** when all useless lock patches are applied simultaneously:
* Describes the realistic macro-benchmark workload (e.g., `memtier_benchmark` with 200 concurrent TCP clients generating 1,000,000 network requests).
* Reports the mean $\pm$ standard deviation across **10 consecutive trials** to eliminate noise and guarantee zero crashes.
* Breaks down overall throughput, average latency, tail latency (P99), and maximum latency under peak contention.

### D. Benchmark Reproduction Code (`bench_*.c`)
Self-contained, standalone C programs that recreate the exact multi-threaded contention scenario of the identified lock functions on multi-core systems, allowing reviewers to verify the results in seconds with standard `gcc -O3 -pthread`.

---

## 4. How to Reproduce All Experiments

### Step 1: Run Micro-benchmarks (10 Consecutive Trials)
```bash
# Compile and run H2O TLS benchmark across 16 threads (10 trials)
gcc -O3 -pthread experiments/cloudlab_results/h2o/bench_neverbleed.c -o bench_neverbleed
./bench_neverbleed

# Compile and run Memcached cache alloc/free benchmark (10 trials)
gcc -O3 -pthread experiments/cloudlab_results/memcached/bench_cache.c -o bench_cache
./bench_cache

# Compile and run Xen spinlock contention benchmark (10 trials)
gcc -O3 -pthread experiments/cloudlab_results/xen/bench_xen_spinlock.c -o bench_xen_spinlock
./bench_xen_spinlock
```

### Step 2: Run End-to-End Macro-benchmark (Memcached)
```bash
# Start Memcached server with 4 worker threads and 1GB RAM
memcached -u root -p 11211 -t 4 -m 1024 &

# Launch memtier_benchmark with 200 concurrent connections (1M requests)
memtier_benchmark -s 127.0.0.1 -p 11211 -P memcache_text -t 4 -c 50 --requests 5000 --ratio 1:10
```
