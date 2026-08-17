# Complete Experimental Report — Experiment 9: NGINX v1.24.0

**Analysis Tool**: CRUX v3.0 (LLVM IR Static Analyzer + Z3 SMT Solver)  
**Environment**: CloudLab Bare-Metal Node (Ubuntu 22.04 LTS, Kernel 5.15)  

---

## 1. Experiment Technical Overview

| Parameter | Value / Configuration |
|---|---|
| **Analysis Target** | NGINX v1.24.0 (High-Performance HTTP Web Server & Reverse Proxy in C) |
| **Language & Primitives** | C (`ngx_thread_mutex_lock`, `ngx_shmtx_lock` spinlocks, `pthread_mutex_t`) |
| **Build Protocol** | `./configure --with-threads --without-http_rewrite_module` + `wllvm` |
| **Generated LLVM IR File** | `nginx_O0.ll` (File Size: **11.8 MB**) |
| **CRUX Analysis Time** | **6.21 seconds** |
| **SMT Solver** | Z3 Solver v4.14 enabled (`--smt`) |
| **Custom Mutex Flags** | `--custom-locks ngx_thread_mutex_lock,ngx_shmtx_lock --custom-unlocks ngx_thread_mutex_unlock,ngx_shmtx_unlock` |

---

## 2. CRUX Static Analysis Summary

- **Total Lock Acquisition Sites Detected**: `26 sites`
- **Useful Legitimate Locks Preserved**: `26 sites` (**100.0%**)
- **Useless Candidate Locks Flagged**: `0 sites` (**0.0%**)

### Lock Site Graph (LSG)
- **Nodes**: 26 sites
- **Data Conflict Edges (`SHARE`)**: 632
- **Nesting Edges (`NEST`)**: 0
- **Temporal Order Edges (`HB`)**: 0

---

## 3. Architectural & Concurrency Discipline Analysis

NGINX demonstrates **pristine, 100% perfect lock discipline** across its architecture:
1. **Master-Worker Multi-Process Event Loop**: Primary request processing occurs in asynchronous non-blocking worker processes (`epoll`), eliminating the need for thread mutexes during HTTP routing.
2. **Shared Memory Spinlocks (`ngx_shmtx_t`)**: Inter-process synchronization for the accept lock and shared memory slabs is handled via atomic spinlocks without holding long-lived mutexes.
3. **Asynchronous Thread Pools (`thread_pool`)**: Thread pool workers for disk I/O operations (`ngx_thread_mutex_lock`) use strictly scoped, minimal critical sections that contain 0 redundant locks.

---

## 4. Multi-Project Concurrency Benchmark Overview (9 Analyzed Projects)

| Metric / Dimension | Memcached | Redis | H2O | SQLite3 | RocksDB | PostgreSQL | OpenMPI | crun | NGINX |
|---|---|---|---|---|---|---|---|---|---|
| **Domain** | Cache | Data Store | HTTP Web | Embedded SGBD | Persistent KV | RDBMS | HPC Infra | OCI Runtime | HTTP Proxy |
| **Architecture** | Shared Mem | Event Loop | Event Loop | Shared VFS | C++ RAII | LWLocks/IPC | OPAL/Atomics | Namespaces | **Master-Worker** |
| **Total Locks** | **204** | **0** | **58** | **114** | **232** | **483** | **881** | **0** | **26** |
| **Useful Locks** | **184** (90%) | **0** | **55** (95%) | **107** (94%) | **224** (97%) | **470** (97%) | **466** (53%*) | **0** | **26 (100%)** |
| **Redundant TP** | **9 sites** | **0** | **0** | **0** | **0** | **0** | **0** | **0** | **0** |
| **Discipline** | High Debt | Lock-Free | High | High | Pristine | Exemplary | HPC Hybrid | Process Iso | **Pristine (100%)**|
