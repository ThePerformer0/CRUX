Result: **USELESS**

**What the lock actually protects**

`version_lock` guards the body of `version_get()`, which touches exactly one piece of shared state: the static pointer `APP_VERSION` in `version.c`. The local variable `v` inside `version_get()` (and the `v` inside `worker()`) is stack-allocated per call — it is never shared across threads and is not a synchronization concern at all.

**Write-set analysis of `APP_VERSION`**

`APP_VERSION` is written exactly once, at its declaration:

```c
static const char* APP_VERSION = "v1.2.3-lite";
```

This is a static-storage-duration object with a constant initializer. Per the C standard, initialization of objects with static storage duration is completed before `main()` begins executing — i.e., before any `pthread_create` call happens. There is no other assignment to `APP_VERSION` anywhere in the translation unit (it is `static`, so it has internal linkage and cannot be written from any other file). After program startup, every access to `APP_VERSION` — across all 5 worker threads — is a **read**.

**Why no race is possible, lock or no lock**

A data race requires two conflicting accesses (at least one a write) that are not ordered by a happens-before relation. Here:

- The single write (static initialization) happens-before `main()`, which happens-before every `pthread_create()`, which in turn happens-before the corresponding thread's execution (POSIX guarantees `pthread_create` synchronizes-with the start of the new thread). So the write is transitively ordered before *every* read in every worker thread.
- After that point, all accesses from all threads are reads. Concurrent reads never race with each other, regardless of interleaving.

This means the property "no race on `APP_VERSION`" holds under **every possible thread schedule**, and it's provable purely from the program's write-set being empty in the post-initialization/concurrent phase — no interleaving exploration or SMT path validation is even needed here; a simple def-use / points-to pass over the LLVM IR showing zero write instructions to `APP_VERSION` outside of the global initializer would suffice. That's what puts this in the plain **USELESS** bucket rather than **SEMANTICALLY USELESS**: the latter would apply to a case where a genuine concurrent write *does* exist but is provably inconsequential to observable behavior (e.g., idempotent or dead writes, requiring the Z3-based equivalence reasoning your pipeline does); here there isn't even a candidate race to reason about semantically.

**One tangential point, for completeness**

`printf` itself is internally thread-safe (glibc serializes access to `FILE*` streams via its own internal per-stream lock), so interleaved calls from the 5 workers won't corrupt output — but this has nothing to do with `version_lock`, since the mutex's critical section ends before `printf` is ever called.

**Conclusion**

Removing `pthread_mutex_lock`/`pthread_mutex_unlock` from `version_get()` changes nothing about program correctness under any scheduling: `APP_VERSION` is fully initialized and immutable for the entire lifetime of the concurrent region. The lock only adds acquisition/release overhead and (under contention with more threads/frequent calls) unnecessary serialization and cache-line traffic on `version_lock`'s internal state, with zero correctness benefit. It is a clean example of a structurally/logically provable **USELESS** lock — the kind your write-set analysis should be able to flag without needing path-sensitive interleaving checks.