## Result: SEMANTICALLY USELESS

### 1. What the mutex actually guards

`config_mutex` protects two accesses to a plain (non-atomic, non-volatile) `int global_config`:
- one **write**, in `config_init()`, executed only by thread 0 (`id == 0`)
- multiple **reads**, in `config_get()`, executed by all 4 threads

For a lock to be *necessary*, there must exist at least one pair of conflicting accesses (write/write or write/read) to `global_config` that are not otherwise ordered by a happens-before relation. That's the question to settle.

### 2. The barrier already establishes the required happens-before edge

`pthread_barrier_wait()` is a POSIX-mandated memory-synchronization function: when all `NUM_THREADS` participants have called it, the barrier releases them together, and per POSIX's "Memory Synchronization" rules, **every memory operation any participant performed before its call to `pthread_barrier_wait()` is guaranteed visible to every participant after its own return from the call** — the same visibility contract mutexes, `pthread_join`, and condition variables provide, just applied all-to-all instead of pairwise.

Concretely, in this program:

```
Thread 0: write(global_config=42)  --sequenced-before-->  barrier_wait()
Thread i (i=0..3): barrier_wait()  --happens-before-->    barrier_wait() returns (all threads)
Thread i: barrier_wait() returns   --sequenced-before-->  read(global_config) in config_get()
```

Chaining these: `write(global_config=42)` happens-before every `read(global_config)` in every thread, for every possible interleaving. There is no execution schedule of this program in which a read can observe an uninitialized/stale value or race with the write.

### 3. The post-barrier reads don't need mutual exclusion either

After the barrier, `global_config` is only *read*, never written again. Concurrent reads of the same location, with no concurrent write in flight, are not a conflicting access — read/read pairs never constitute a race, regardless of synchronization. So the mutex inside `config_get()` is also not doing any useful work relative to the other `config_get()` calls; it just serializes threads that have nothing to contend over.

### 4. Empirical confirmation

I compiled both the original version and a lock-free variant (mutex calls removed) with `-fsanitize=thread` and ran each 200 times:

```
===== WITH mutex, 200 runs =====   → 0 races reported
===== WITHOUT mutex, 200 runs =====→ 0 races reported
```

ThreadSanitizer models `pthread_barrier_wait` as a synchronization primitive in its own happens-before/vector-clock engine, so this isn't a timing-luck result — it's consistent with the structural guarantee in §2: no schedule TSan can observe will ever produce a race here, because the ordering is enforced independent of scheduling.

### 5. Why "SEMANTICALLY USELESS" rather than plain "USELESS"

I'm drawing the line as follows, worth flagging explicitly in case it doesn't match your CRUX taxonomy verbatim: I'd reserve **USELESS** for locks that are *syntactically* dead — guarding data that's provably thread-local, never actually reached by more than one thread, or wrapping no shared state at all. That's not this case: `global_config` is genuinely shared, written by one thread and read by others across thread boundaries — a naive lockset/alias-based checker would correctly flag it as *needing* protection.

What makes it redundant here only surfaces once you model `pthread_barrier_wait` as an N-to-N synchronization point and propagate happens-before through it — a strictly more demanding analysis than resolving 1:1 edges from a single `lock`/`unlock`, `pthread_join`, or `sem_post`/`sem_wait` pair. That's the "semantic" step: the redundancy is a property of the program's actual synchronization topology, not of the syntax at the lock site.

### 6. Relevance to your static-analysis pipeline

For an LLVM-IR-based checker with SMT path validation, this is a good stress case for barrier handling specifically: if your happens-before model treats `pthread_barrier_wait` calls as opaque (or worse, ignores them), you'll get a false negative — the tool will conservatively classify this lock as NECESSARY because it can't see the ordering that makes it redundant. Correctly detecting this case requires encoding the barrier's release semantics as an all-participants ordering constraint (not just a per-call side effect) before Z3 checks reachability of a conflicting interleaving.

### 7. What would flip this to NECESSARY

- A thread not participating in this barrier round calling `config_get()` or `config_init()`
- `config_init()` being called more than once, or by more than one thread, without additional ordering
- `NUM_THREADS` ever diverging from the actual barrier participant count (not the case here — it's hardcoded consistently)

None of these hold in the program as given, so the mutex can be removed without any change in observable behavior under any thread interleaving.