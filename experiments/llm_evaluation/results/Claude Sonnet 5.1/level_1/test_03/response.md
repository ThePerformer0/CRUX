Result: SEMANTICALLY USELESS

**Why not "NECESSARY":**

The mutex protects a genuinely shared object (`value`) that is written by one thread and read by another — syntactically this is exactly the pattern a naive detector should flag as legitimate synchronization. But `main()`'s orchestration removes any possibility of concurrent access:

```c
pthread_create(&t1, NULL, writer, NULL);
pthread_join(t1, NULL);      // <-- t1 fully terminates before t2 exists
pthread_create(&t2, NULL, reader, NULL);
pthread_join(t2, NULL);
```

`t2` is not even created until after `pthread_join(t1, ...)` has returned. Since `writer` and `reader` never coexist as live threads, there is exactly one possible interleaving — there is no schedule under which both critical sections could race.

**Why "SEMANTICALLY" rather than plain "USELESS":**

This isn't a trivially-detectable case (e.g., a lock guarding a stack-local variable, a mutex only ever touched by one thread, or dead code) — those are syntactically/locally redundant and don't require reasoning about program order. Here, proving redundancy requires chaining the POSIX happens-before edges across two separate synchronization primitives:

1. Thread termination synchronizes-with the corresponding `pthread_join` return: `value = 10` happens-before `pthread_join(t1, NULL)` returns in `main`.
2. `pthread_create` establishes a happens-before edge from the creator's prior actions to the new thread's first action: the `pthread_join(t1, ...)` return happens-before `pthread_create(&t2, ...)`, which happens-before `reader`'s body begins.

Composing these gives a **total order** — not just a race-free partial order — between the write and the read: `value = 10` → (join) → (create) → `printf("value = %d\n", value)`. This is provable at the level of the C11/pthread memory model, independent of scheduling; it's not "unlikely to race," it's structurally impossible to race. Removing both `pthread_mutex_lock`/`unlock` calls entirely would not introduce a data race and would not change the program's observable behavior (it deterministically prints `10`).

Detecting this class requires building the happens-before graph induced by `pthread_create`/`pthread_join` edges across function boundaries — you can't decide it by inspecting `writer` or `reader` in isolation, since each function, read alone, is the textbook-correct way to guard `value`. That's the distinguishing trait of the "semantically useless" class versus a syntactically-useless one.

**Note on fragility:** this classification is order-dependent. If the two `pthread_create` calls were issued before either `pthread_join` (e.g., `create(t1); create(t2); join(t1); join(t2);`), the happens-before chain above breaks, both threads could run concurrently, and the lock would flip to **NECESSARY**. A detector should be careful to key this pattern specifically on the join-before-create serialization in `main`, not on any superficial property of `writer`/`reader` themselves — worth calling out explicitly if this is going into CRUX's test corpus, since it's a good adversarial example against purely intra-procedural analyses.