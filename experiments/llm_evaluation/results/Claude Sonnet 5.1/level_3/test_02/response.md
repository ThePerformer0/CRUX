Result: **SEMANTICALLY USELESS**

**What the lock actually protects**

`cache_store()` performs two non-atomic writes to file-scope globals (`strncpy` into `cached_key`, then `cached_value = value`). Four threads call `cache_store()` concurrently with no other synchronization between them, so without the mutex this is a textbook data race under the C11/pthreads memory model — concurrent, unsynchronized writes to the same objects are undefined behavior regardless of what values are being written.

I verified this empirically rather than just asserting it: I rebuilt the program with the mutex removed and compiled with `-fsanitize=thread`. Across 5 runs, ThreadSanitizer reported a genuine data race **every single time** (`WARNING: ThreadSanitizer: data race`, flagging concurrent writes to the same address by different threads). So this is not a case where no race exists at all — the lock is doing *something* in the formal sense.

**Why it's useless anyway**

The critical detail is *what* the threads race over. In `main.c`, all four worker threads call:
```c
cache_store("static_file_hash", 9999);
```
Identical key, identical value, every time. Because `strncpy(cached_key, key, 63)` always writes the same 63 bytes (the string plus deterministic null-padding) and `cached_value = 9999` always writes the same int, **every possible interleaving of the four racing stores produces the exact same final memory state.** There is no schedule under which the race changes the outcome — the "race" has no observable effect on correctness. This is a classic *benign race*: technically UB, practically inert.

This is confirmed by the test output: across all 5 TSan runs (each one exercising a different, sanitizer-perturbed thread interleaving), `Final cache value: 9999` was printed 100% of the time, despite a real race being flagged 100% of the time. Correctness and race-freedom were completely decoupled in this program.

The single `cache_get()` call in `main()` reinforces this: it only happens after `pthread_join()` on all four workers, and `pthread_join` is itself a full synchronization point establishing happens-before. So the read side was never actually concurrent with any writer — the mutex around `cache_get` protects against a scenario (a concurrent reader) that this program's control flow never creates.

**Why not USELESS, and why not NECESSARY**

- Not **USELESS**: that label fits code where no race is even possible (e.g., data only ever touched by one thread, or the lock is a no-op due to a bug that doesn't actually protect the shared state). Here a real, tool-detectable data race exists without the lock — removing it does introduce formal UB, which matters for portability, compiler optimizations, and any sanitizer/CI gate.
- Not **NECESSARY**: that would require some interleaving to produce a wrong result — e.g., different threads storing different keys/values (risking a `cache_get` that reads a torn/mismatched key-value pair), or a `cache_get` genuinely running concurrently with a `cache_store`. Neither happens here: the arguments are hardcoded identically across all call sites, and the only read is join-ordered after all writes.

**Caveat:** this classification is specific to the program as written. `cache_store`/`cache_get` are general-purpose functions — if `main.c` were changed so threads stored distinct keys/values, or `cache_get` were called from a thread that hadn't joined the writers, the same lock would immediately become necessary. The uselessness here is a property of this particular caller's usage pattern, not of the locking code in `cache.c` in isolation.