# CRUX False Positive Study: Empirical Audit of 60 Candidate Sites

## Executive Summary

To rigorously evaluate the precision of the CRUX static detection engine on candidate superfluous critical sections, an empirical audit was conducted on a sample of **60 candidate sites** drawn across 7 production C codebases (*Linux Kernel*, *Xen Hypervisor*, *PostgreSQL*, *Memcached*, *librdkafka*, *H2O*, and *OpenMPI*).

Each site was investigated with extreme rigor by inspecting the full source code (exact versions and clean checkouts), cross-referencing commit histories, call graphs, concurrency architectures, IRQ contexts, and multithreaded design patterns.

### Key Quantitative Findings

- **Total Sites Evaluated:** 60
- **True Positives (CRUX correctly detected a genuinely superfluous lock):** **8 / 60 (13.3%)**
- **False Positives (CRUX flagged a necessary lock as superfluous):** **52 / 60 (86.7%)**
- **Overall False Positive Rate:** **86.7%**

---

## 1. Metrics Breakdown

### 1.1 Breakdown by Pattern

| Pattern | Sample Size | True Positives (TP) | False Positives (FP) | False Positive Rate |
| :--- | :---: | :---: | :---: | :---: |
| **`EMPTY_CS`** | 8 | 2 | 6 | **75.0%** |
| **`READ_ONLY`** | 16 | 1 | 15 | **93.8%** |
| **`REDUNDANT`** | 16 | 4 | 12 | **75.0%** |
| **`LOCAL_VARS`** | 20 | 1 | 19 | **95.0%** |
| **Total** | **60** | **8** | **52** | **86.7%** |

### 1.2 Breakdown by Project

| Project | Total Sites | TP | FP | FP Rate (%) | Primary Concurrency Pitfalls for CRUX |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **`librdkafka`** | 11 | 5 | 6 | **54.5%** | Handshake locks, re-entrancy wrappers |
| **`linux`** | 22 | 2 | 20 | **90.9%** | Drain barriers, IRQ-safety, hardware MMIO/Port I/O, shared readers |
| **`xen`** | 9 | 1 | 8 | **88.9%** | Per-CPU distinct lock migration, SMP memory barriers |
| **`h2o`** | 3 | 0 | 3 | **100.0%** | Hash table resizing / pointer stability under `realloc` |
| **`memcached`** | 10 | 0 | 10 | **100.0%** | Cross-thread stats scraping of worker context structures |
| **`openmpi`** | 3 | 0 | 3 | **100.0%** | Mutex as thread memory barrier & pipeline completion publish |
| **`postgres`** | 2 | 0 | 2 | **100.0%** | `LW_SHARED` reader protection against concurrent `LW_EXCLUSIVE` writers |

---

## 2. Taxonomy of False Positive Root Causes

The audit reveals **6 fundamental architectural limitations** of static LLVM-based analyses when evaluating lock necessity in systems software:

### 1. Temporal Drain & Handshake Barriers (`EMPTY_CS` False Positives)
- **CRUX Assumption:** A lock acquired and immediately released with no intervening instructions is a no-op that wastes CPU cycles.
- **Reality:** Empty critical sections are standard idioms in systems programming used as **completion barriers** or **thread startup handshakes**:
  - *Startup Handshake:* In `librdkafka` (`rdkafka_broker.c:4914`), a parent thread acquires the lock before spawning a broker thread; the broker thread locks and unlocks the same mutex at startup to ensure the parent has finished initialization.
  - *Drain Barrier against Use-After-Free:* In `linux` (`drivers/block/loop.c:794` & `1343`), the loop driver holds `loop_validate_mutex` during partition validation. When tearing down a loop device, another thread acquires and releases `loop_validate_mutex` with an empty body to wait for all in-flight validations to drain before invoking `fput()`. Removing the lock creates a live kernel UAF panic.
  - *Subsystem Teardown Barrier:* In `linux` (`net/core/net_namespace.c:625`), `net_ns_barrier()` acquires and releases `net_sem` with an empty body to flush out in-flight namespace-lookup readers before freeing namespace structures.

### 2. Multi-Process Shared Readers vs. Concurrent Writers (`READ_ONLY` False Positives)
- **CRUX Assumption:** If a critical section contains only read instructions (`load` / `memcpy` from shared memory) and no `store`, locking is superfluous because reads are idempotent.
- **Reality:** Reader locks prevent **torn reads** and data inconsistencies caused by concurrent writers running on other cores:
  - In `postgres` (`pgstat_slru.c:75` and `pgstat_wal.c:69`), worker processes hold `LWLockAcquire(..., LW_SHARED)` while copying cumulative stats structs via `memcpy`. Backend writers continuously modify these 64-bit counters with `LW_EXCLUSIVE`. Removing `LW_SHARED` results in 64-bit torn reads and corrupted monitoring metrics across PostgreSQL backends.
  - In `linux` (`kernel/sys.c:1270`), `down_read(&uts_sem)` protects concurrent access to `utsname()` fields while another process might invoke `sethostname()` or `setdomainname()`.

### 3. Hardware I/O & Bus Serialization (`READ_ONLY` & `EMPTY_CS` False Positives)
- **CRUX Assumption:** Locks only protect memory locations identified via alias analysis.
- **Reality:** In OS kernels and hypervisors, locks serialize access to **unmapped physical hardware ports** (I/O bus):
  - In `linux` (`arch/x86/kernel/bootflag.c:54`), `rtc_lock` serializes access to legacy CMOS ports `0x70` and `0x71` via `inb()` / `outb()`. Standard static analyses see no memory writes and assume the lock is useless, whereas removing it causes hardware bus conflicts.
  - In `linux` (`drivers/video/console/vgacon.c:309`), `vga_lock` protects access to VGA controller hardware registers.

### 4. Cross-Thread Stats Scraping of "Thread-Local" Structures (`LOCAL_VARS` False Positives)
- **CRUX Assumption:** If a critical section only accesses fields within a pointer passed as a local parameter (e.g. `LIBEVENT_THREAD *t`), the data is thread-local and synchronization is unnecessary.
- **Reality:** In high-performance servers like `memcached`, threads maintain worker structures (such as `t->stats`), but **global monitoring threads or control threads periodically scrape and sum these structures across all worker threads**:
  - In `memcached` (`thread.c:1014` and `thread.c:986`), `threads[ii].stats.mutex` is acquired by external threads iterating through the `threads` array to aggregate global stats. Removing the lock in worker threads introduces live data races during stats queries (`stats` command).

### 5. Asynchronous IRQ / SoftIRQ Exclusion vs. Sleeping Mutexes (`REDUNDANT` False Positives)
- **CRUX Assumption:** If an outer lock `Mutex A` is already held throughout a function, an inner lock `Spinlock B` on the same subsystem is redundant.
- **Reality:** In kernel contexts, sleeping process-context mutexes cannot be held in interrupt service routines (ISRs):
  - In `linux` (`drivers/tty/serial/serial_core.c:1266`), `uart_get_rs485_config` is called under the TTY mutex, but acquires `uport->lock` via `spin_lock_irqsave`. The inner spinlock disables local interrupts and excludes UART interrupt handlers that update RS485 status at any instant. Removing the inner spinlock exposes the driver to immediate kernel lockup/deadlock from an interrupt.

### 6. Per-Instance / Reallocation Pointer Stability (`REDUNDANT` False Positives)
- **CRUX Assumption:** Two locks of the same type held sequentially or concurrently protect the same target.
- **Reality:** 
  - In `xen` (`arch/x86/hvm/vmx/vmx.c:266` `vmx_pi_desc_fixup`), `old_lock` and `new_lock` protect distinct per-CPU PI lists when migrating a virtual interrupt. Both must be held simultaneously during the list migration to guarantee atomic handoff.
  - In `h2o` (`lib/common/neverbleed.c:710`), `pthread_rwlock_rdlock` on `nb->daemonvars.rwlock` is essential because concurrent threads can call `realloc()` on the daemon keys table under `wrlock`. Removing the read lock causes a use-after-free or segfault if a realloc occurs concurrently.

---

## 3. Analysis of Confirmed True Positives (TPs)

Only **8 sites (13.3%)** were confirmed as genuine true positives where the lock was strictly superfluous:

1. **`linux` (`mm/vmscan.c:641` — `s1590` — `EMPTY_CS`):**
   `free_prealloced_shrinker` acquires and releases `shrinker_rwsem`. In default kernel configurations, `unregister_memcg_shrinker` inlines to a complete NOP; no shared reads or writes take place under the rwsem.
2. **`linux` (`drivers/mailbox/mailbox.c:345` — `s7325` — `EMPTY_CS`):**
   `mbox_request_channel` acquires `con_mutex` prematurely before device-tree parsing (`of_parse_phandle_with_args`). When parsing fails, it releases the lock immediately without having read or written any mailbox controller state.
3. **`xen` (`include/xen/spinlock.h:243` / `domain_soft_reset` — `s15` — `READ_ONLY`):**
   Quiesced domain state: reads `vcpu->paused_for_shutdown` flags while all vCPUs are explicitly halted and the domain is frozen for soft reset.
4. **`librdkafka` (`rdkafka_broker.c:3173` — `s271` — `REDUNDANT`):**
   Redundant logging lock: `rd_rkb_dbg` internally re-acquires `rkb_lock` while the enclosing produce/toppar execution path already guarantees the broker reference and state.
5. **`librdkafka` (`rdkafka_broker.c:5526` — `s276` — `REDUNDANT`):**
   Double lock acquisition: `rd_rkb_dbg` re-acquires `rkb_lock` at line 5526 while the enclosing function `rd_kafka_broker_add` already holds `rkb_lock` since line 5484.
6. **`librdkafka` (`rdkafka_broker.c:6353` — `s356` — `REDUNDANT`):**
   Redundant nested lock: `rd_rkb_dbg` macro re-locks `rkb` while the broker lock is already held exclusively across active toppar list management.
7. **`librdkafka` (`rdkafka_broker.c:5640` — `s374` — `REDUNDANT`):**
   Redundant nested lock: `rd_rkb_dbg` inside `rd_kafka_broker_lock`/`unlock` block at line 5638 re-acquires `rkb_lock` redundantly.
8. **`librdkafka` (`rdkafka.c:984` — `s31` — `LOCAL_VARS`):**
   Thread-confined consumer queue purge: queue is strictly private during the final consumer close sequence; no concurrent producer or consumer thread can access it.

---

## 4. Conclusion & Recommendations for the CRUX Tool

1. **Precision Rate:** The audited sample exhibits a true positive rate of **13.3%** and a false positive rate of **86.7%**.
2. **Key Enhancements Needed for CRUX:**
   - **Cross-Thread & Process Memory Escape Analysis:** Must model readers vs writers (especially in multi-process architectures like PostgreSQL).
   - **Barrier Pattern Recognition:** Recognize empty lock/unlock sequences that serve as temporal completion barriers or thread-join fences.
   - **Interrupt & Hardware Awareness:** Model IRQ disabling (`spin_lock_irqsave`) and hardware I/O instructions (`inb`, `outb`, MMIO).
   - **Global Aggregation Recognition:** Detect worker structure arrays iterated by monitoring threads before classifying locks on parameter structures as `LOCAL_VARS`.
