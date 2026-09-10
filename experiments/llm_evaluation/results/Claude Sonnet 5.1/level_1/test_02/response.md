Result: **USELESS**

**Justification**

**1. Thread topology.** `main` spawns exactly one worker thread via a single, non-looped call to `pthread_create`. `counter` is touched at exactly two program points:
- a write (`counter++`) inside `worker`, executed by the child thread, and
- a read (inside `printf`) inside `main`, executed by the parent thread, **strictly after** `pthread_join(t, NULL)` returns.

No other thread, and no other code path, ever touches `counter`.

**2. Happens-before via `pthread_join`.** Per the POSIX threads memory model (and equivalently the C11 `<threads.h>` model), thread join is a synchronization point: all memory effects performed by a thread *before its termination* are guaranteed visible to, and ordered-before, the corresponding `pthread_join()` call's return in the joining thread. Formally, if `W` is the write `counter++` in `worker` and `R` is the read in `main`'s `printf`:

```
W (in worker, before return)  --happens-before-->  worker terminates
worker terminates             --happens-before-->  pthread_join(t, ...) returns
pthread_join(t, ...) returns  --happens-before-->  R (printf)
```

By transitivity, `W happens-before R`. This edge exists **independently of the mutex** — it's a property of `pthread_create`/`pthread_join` alone.

**3. No data race exists, with or without the lock.** A data race is defined as two conflicting accesses (at least one a write) on different threads that are *not* ordered by happens-before. Here, the only two accesses to `counter` are `W` and `R`, and step 2 shows they're already ordered. There is no third access competing for the same window. Hence removing `pthread_mutex_lock`/`unlock` cannot introduce a race — the program's behavior (including the exact value printed, `counter = 1`) is byte-for-byte identical with or without the lock.

**4. Non-atomicity of `counter++` is irrelevant here.** `counter++` is a non-atomic read-modify-write at the machine level, which normally matters only when *multiple* threads can interleave on it. Since exactly one thread ever executes it, and no concurrent observer exists during that window, atomicity is moot — there's nothing to interleave with.

**5. Contrast case (sharpens the boundary).** If `pthread_create(&t, NULL, worker, NULL)` were inside a loop spawning N ≥ 2 threads that all call `worker` before any join, the lock becomes **NECESSARY**: now multiple threads can execute `counter++` concurrently with no happens-before edge between them prior to their respective joins, and the mutex is what supplies that edge. The single-thread case here has no such competing writers, which is exactly what makes the lock vacuous.

**6. Note on terminology.** I'm treating **USELESS** as "provably unnecessary from the happens-before/thread-topology graph alone, with no dependence on the specific values or logic of the guarded computation" — as opposed to what I'd call **SEMANTICALLY USELESS**: a lock that *does* guard a reachable, topologically-real race, but where the guarded computation's actual semantics (dead value, idempotent write, value never observed, etc.) make the race's outcome immaterial to the program's observable behavior. This example falls squarely in the first bucket — the redundancy is structural, not value-dependent. If your formal taxonomy in CRUX draws this line differently, flag it and I'll re-classify accordingly.

This is also a clean case for the SMT-validation half of your pipeline: encoding "∃ a reachable interleaving where an access to `counter` is unordered by happens-before" and checking satisfiability under Z3 would return **UNSAT** given the `create`/`join` edges alone — giving a formal certificate for the classification above rather than just a heuristic one.