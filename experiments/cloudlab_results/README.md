# CRUX Experimental Results & Benchmarks

This directory contains the experimental results, reports, evaluated patches, and standalone reproduction benchmarks for the **CRUX** static analyzer across real-world multi-threaded C/C++ production software.

---

## 1. Test Environment

All benchmarks and static analyses were executed on a dedicated bare-metal server on **CloudLab**:
* **CPU:** AMD EPYC 7402P (24 physical cores, 48 vCPUs @ 2.80 GHz)
* **RAM:** 128 GB DDR4
* **OS:** Ubuntu 22.04 LTS (Kernel 5.15.0-x86_64)
* **Compiler:** Clang 14.0.0 with WLLVM 1.3.0
* **Compilation Flags:** `-O0 -g -fno-inline` (unoptimized IR, full debug symbols, no inlining)

*(See `machine_specs2.txt` for the complete hardware dump).*

---

## 2. Identified Sites & Evaluated Patches

For a comprehensive catalog of the identified lock sites, exact line numbers, and concrete code diffs for **Linux Kernel**, **Xen Hypervisor**, **PostgreSQL**, and **Memcached**, refer to:
* 📄 **[`PATCHES_AND_SITES.md`](PATCHES_AND_SITES.md)** — Detailed line-by-line patches and concurrency pattern explanations.

---

## 3. Directory Layout

Each project folder contains the following files:

```text
experiments/cloudlab_results/
├── README.md                  # This file
├── PATCHES_AND_SITES.md       # Detailed lines, sites, and diffs for evaluated patches
├── machine_specs2.txt         # Bare-metal server hardware dump
└── <project>/                 # Project results directory (17 target projects)
    ├── <project>_report.json  # Raw CRUX static analysis report
    ├── results_<project>.csv  # Table of detected lock sites, lines, and patterns
    ├── global_performance.txt # 10-run performance benchmark comparison (where applicable)
    └── bench_<name>.c         # Standalone C reproduction benchmark (where applicable)
```

---

## 4. File Descriptions

* **`*_report.json`:** JSON output from CRUX with total lock count, useful/useless lock breakdown, bitcode size in bytes, and execution time.
* **`results_*.csv`:** CSV table listing each useless lock site, source file, line number, pattern (`LOCAL_VARS`, `READ_ONLY`, `REDUNDANT`, `EMPTY_CS`), and speedup metrics.
* **`global_performance.txt`:** Macro and micro performance numbers averaged across 10 consecutive trials ($\mu \pm \sigma$).
* **`bench_*.c`:** Standalone C micro-benchmarks used to measure performance under heavy multi-core contention with and without the detected useless locks.

---

## 5. Compiling and Running Reproduction Benchmarks

Each micro-benchmark is self-contained and can be compiled and executed directly using GCC:

```bash
# 1. Linux Kernel (5 lock sites elided across 16 threads)
gcc -O3 -pthread linux/bench_linux_locks.c -o bench_linux
./bench_linux

# 2. Xen Hypervisor (Spinlock read-only trap query across 16 threads)
gcc -O3 -pthread xen/bench_xen_spinlock.c -o bench_xen
./bench_xen

# 3. PostgreSQL (Shared WAL statistics snapshot across 16 backends)
gcc -O3 -pthread postgres/bench_pgstat.c -o bench_postgres
./bench_postgres

# 4. Memcached (Thread-local cache allocation across 16 threads)
gcc -O3 -pthread memcached/bench_cache.c -o bench_memcached
./bench_memcached
```

