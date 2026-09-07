# CRUX Experimental Results

This directory contains the experimental results and artifacts for the CRUX static analyzer evaluated on real-world multi-threaded C/C++ projects.

---

## 1. Test Environment

All benchmarks and analyses were executed on a dedicated bare-metal server on **CloudLab**:
* **CPU:** Intel Xeon Gold 6338 (20 cores, 40 threads @ 2.00 GHz)
* **RAM:** 192 GB DDR4
* **OS:** Ubuntu 22.04 LTS (Kernel 5.15.0-x86_64)
* **Compiler:** Clang 14.0.0 with WLLVM 1.3.0
* **Compilation Flags:** `-O0 -g -fno-inline` (unoptimized IR, full debug symbols, no inlining)
---

## 2. Directory Layout

Each project folder contains the following files:

```text
experiments/cloudlab_results/
├── README.md                  # This file
├── machine_specs2.txt         # Server hardware details
└── <project>/                 # Project results directory
    ├── <project>_report.json  # Raw CRUX static analysis report
    ├── results_<project>.csv  # Table of detected lock sites
    ├── global_performance.txt # 10-run performance benchmark comparison (where applicable)
    └── bench_<name>.c         # Standalone C reproduction benchmark (where applicable)
```

---

## 3. File Descriptions

* **`*_report.json`:** JSON output from CRUX with total lock count, useful/useless lock breakdown, bitcode size in bytes, and execution time.
* **`results_*.csv`:** CSV table listing each useless lock site, source file, line number, pattern (`LOCAL_VARS`, `READ_ONLY`, `REDUNDANT`), and speedup metrics.
* **`global_performance.txt`:** Macro and micro performance numbers averaged across 10 consecutive trials ($\mu \pm \sigma$).
* **`bench_*.c`:** Standalone C benchmarks used to measure performance with and without the detected useless locks (`gcc -O3 -pthread`).
