Result: NECESSARY

## Technical Justification

### 1. Shared Mutable State

The cache module (`cache.c`) maintains its state using static global variables (`cached_key` and `cached_value`). Because these variables reside in the data segment and are shared across the entire process, any function modifying them operates on shared mutable state.

### 2. Concurrent Execution in `main.c`

The program spawns four concurrent threads (`NUM_THREADS = 4`) via `pthread_create`, all running the `worker` routine. Each of these threads simultaneously invokes `cache_store("static_file_hash", result)`. This introduces active concurrency where multiple execution flows attempt to write to the exact same memory locations at the same time.

### 3. Prevention of Data Races and Undefined Behavior

* **Data Race Condition:** Without `cache_lock`, concurrent calls to `cache_store` would cause multiple threads to write to `cached_key` (using `strncpy`) and `cached_value` concurrently without synchronization.
* **Undefined Behavior (UB):** In the C memory model, concurrent accesses to non-atomic shared variables where at least one access is a write constitute a data race. A data race results in Undefined Behavior, which can lead to compiler optimization hazards, corrupted memory states, or torn writes across multi-byte structures.
* **Mutual Exclusion:** The mutex (`cache_lock`) serializes access to the critical section, ensuring that updates to `cached_key` and `cached_value` complete atomically relative to other cache operations.

### 4. Analysis of the Read Phase

Although `cache_get` is invoked in `main()` strictly *after* `pthread_join` (meaning there is no active concurrent read/write conflict between the worker threads and the main thread during the read), the lock is still strictly required to protect the concurrent write operations happening among the worker threads themselves.

Consequently, the locks are **necessary** to prevent data races and ensure well-defined program behavior.