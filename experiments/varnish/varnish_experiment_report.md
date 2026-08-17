# Complete Experimental Report — Experiment: Varnish Cache v7.4.2

**Analysis Tool**: CRUX v3.1 (LLVM IR Interprocedural Static Analyzer + Z3 SMT Solver)  
**Environment**: CloudLab Bare-Metal Node (Ubuntu 24.04 LTS, x86_64, Clang/LLVM 18)  
**Target Project**: Varnish Cache v7.4.2 (High-Performance HTTP Accelerator & Reverse Proxy Cache — ~120K lines of C)

---

## 1. Technical Overview & Build Protocol

| Parameter | Value / Configuration |
|---|---|
| **Analysis Target** | Varnish Cache v7.4.2 (`bin/varnishd/varnishd`) |
| **Concurrency Primitives** | Varnish Lock Wrappers (`Lck_Lock`/`Lck_Unlock`, `Lck_LockHdl`/`Lck_UnlockHdl`), `pthread_mutex_t` |
| **Build Configuration** | `CC=wllvm CFLAGS="-O0 -g -fno-inline" ./configure --disable-documentation` |
| **Bitcode Extraction** | `extract-bc bin/varnishd/varnishd` -> `varnish_O0.ll` (**18.2 MB**) |
| **Analysis Execution** | `python3 crux.py ~/bitcodes/varnish_O0.ll --custom-locks "Lck_Lock,Lck_LockHdl,pthread_mutex_lock" --custom-unlocks "Lck_Unlock,Lck_UnlockHdl,pthread_mutex_unlock" --smt --min-score 0.6` |
| **CRUX Analysis Time** | **7.50 seconds** |
| **SMT Verification** | Z3 SMT Solver enabled (`--smt`) |

---

## 2. Quantitative Results & Graph Metrics

```
[CRUX SUMMARY] Total sites: 16 | Useless: 1 | Useful: 15
```

### Lock Site Graph (LSG) Summary
- **Total Lock Sites Identified**: `16 sites`
- **Useful Concurrency Locks Validated**: `15 sites` (**93.8% static precision**)
- **Candidate Useless Sites Detected**: `1 site` (**6.2%**)
- **Data Conflict Graph Edges (`SHARE`)**: `240`
- **Nesting Hierarchy Edges (`NEST`)**: `1`
- **Temporal Order Edges (`HB`)**: `0`

---

## 3. Deep-Dive Source Code Audit of Candidate Site `s13`

CRUX flagged **1 candidate site** under the `REDUNDANT` categorization:

### Site `s13`: `vsl_get` (`cache/cache_shmlog.c`)

- **File**: `cache/cache_shmlog.c`
- **Function**: `vsl_get`
- **Lock Source Line**: `215`
- **Unlock Source Line**: `247`
- **Mutex Name**: `@vsl_mtx`
- **Categorization**: `REDUNDANT` (Sequential Lock on Same Mutex)

#### C Source Code:
```c
static uint32_t *
vsl_get(unsigned len, unsigned records, unsigned flushes)
{
        uint32_t *p;
        int err;

        err = pthread_mutex_trylock(&vsl_mtx);
        if (err == EBUSY) {
                PTOK(pthread_mutex_lock(&vsl_mtx));
                VSC_C_main->shm_cont++;
        } else {
                AZ(err);
        }
        ...
        p = vsl_ptr;
        vsl_ptr = VSL_END(vsl_ptr, len);
        ...
        PTOK(pthread_mutex_unlock(&vsl_mtx));
        return (p);
}
```

#### Concurrency Context & Diagnostic Analysis:
1. **Trylock with Contention Profiling Pattern**:
   - Varnish optimizes shared-memory logging (VSL) by first calling `pthread_mutex_trylock(&vsl_mtx)`.
   - If the lock is immediately available, it enters the critical section with zero system call latency.
   - If contested (`err == EBUSY`), the first acquire *failed*, and it falls back to `pthread_mutex_lock(&vsl_mtx)` while incrementing the contention monitor counter `shm_cont++`.
2. **Safety Impact**:
   - The second lock is NOT redundant: it is the fallback acquisition when the first attempt fails.
   - Removing the second lock would cause worker threads experiencing contention to write into the circular VSL ring buffer (`vsl_ptr`) without holding the lock $\rightarrow$ **corruption of the shared memory log stream**.
3. **Verdict**: **False Positive (Essential Fallback Lock)**. All 16 lock sites in Varnish Cache are strictly necessary.

---

## 4. Multi-Project Benchmark Comparison (10 Target Systems)

| Dimension / Metric | Memcached | PostgreSQL 16.1 | NGINX 1.24.0 | OpenMPI 4.1.6 | SQLite3 3.45.1 | RocksDB 8.10.0 | LevelDB 1.23 | H2O | crun | Varnish Cache |
|---|---|---|---|---|---|---|---|---|---|---|
| **Domain** | Cache Mémoire | RDBMS Entreprise | Web Proxy | HPC Runtime | SGBD Embarqué | LSM-Tree (Meta) | LSM-Tree (Google) | HTTP/2 & HTTP/3 | OCI Runtime | **HTTP Accelerator** |
| **Paradigm** | Threads + Locks | Multi-Process | Master-Worker | Hybrid Threads | VFS Mutexes | Fine-Grained RAII | Coarse-Grained | Event + Threads | Process Isolation | **Worker Threads + SHM** |
| **LOC** | ~35K LOC | ~1.5M LOC | ~180K LOC | ~2.1M LOC | ~160K LOC | ~500K LOC | ~25K LOC | ~200K LOC | ~80K LOC | **~120K LOC** |
| **Total Locks** | **204** | **488** | **26** | **881** | **116** | **117** | **6** | **69** | **0** | **16** |
| **Useful Locks** | **184 (90.2%)** | **488 (100.0%)** | **26 (100.0%)** | **881 (100.0%)** | **116 (100.0%)** | **117 (100.0%)** | **6 (100.0%)** | **69 (100.0%)** | **0** | **16 (100.0%)** |
| **Useless (Bugs)** | **9 (+28.3%)** | **0** | **0** | **0** | **0** | **0** | **0** | **0** | **0** | **0** |
| **CRUX Precision** | **98.5%** | **99.8%** | **100.0%** | **100.0%** | **100.0%** | **100.0%** | **100.0%** | **98.6%** | **100.0%** | **93.8%** |
