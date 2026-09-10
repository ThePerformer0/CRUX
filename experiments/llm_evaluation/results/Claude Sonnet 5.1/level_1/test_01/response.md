## Result: USELESS

### Why no synchronization is needed here

The determining factor is the **happens-before edge established by `pthread_create()`**, not anything about the mutex.

**1. The only write to `shared_value` precedes both thread creations in program order.**

```c
shared_value = 42;           // (A) write, in main thread
pthread_create(&t1, ...);    // (B)
pthread_create(&t2, ...);    // (C)
```

Per POSIX (and mirrored in the C11 memory model's treatment of thread creation), a successful `pthread_create()` call synchronizes-with the start of execution of the new thread: *"The apparent order in which memory accesses occur across threads is constrained by memory synchronization operations... The pthread_create() function is such a synchronization."* Concretely, this gives a happens-before relation: **(A) → (B) → start of t1**, and **(A) → (C) → start of t2**.

So both reader threads observe `shared_value == 42` deterministically, by construction — this visibility guarantee does not depend on the mutex at all.

**2. `reader()` never writes `shared_value`.**

Both `t1` and `t2` execute:
```c
pthread_mutex_lock(&lock);
int v = shared_value;   // read only
pthread_mutex_unlock(&lock);
```

Neither thread mutates `shared_value` after the initial `main()` write. So the only concurrent accesses to `shared_value` between `t1` and `t2` are two **reads**.

**3. Two concurrent reads never constitute a data race.**

By the standard definition (C11 §5.1.2.4, and the informal POSIX equivalent), a data race requires two *conflicting* accesses — i.e., accesses to the same memory location where **at least one is a write** — that are not ordered by happens-before. Read/read pairs never conflict, regardless of synchronization. Since:
- the one and only write (A) is already ordered before both reads via (B)/(C), and
- the two reads t1/t2 perform don't conflict with each other,

there is **no data race in this program at all**, mutex or not. The critical section the lock wraps is, under every possible thread interleaving, free of any conflicting access.

### Why "USELESS" rather than "SEMANTICALLY USELESS"

This distinction matters for a classification scheme like CRUX's, so it's worth being precise about which bucket this falls into:

- **SEMANTICALLY USELESS** would fit a program where a genuine data race *does* exist under the memory model (e.g., two threads both writing to a shared variable without ordering), but analysis shows the race is *observationally inconsequential* — e.g., both writers always write the same value, or the raced-on value never influences the program's final output. There, the lock is removable only because of a value/outcome argument, not because the race is absent.
- **USELESS** (the classification here) fits a program where **no race is even reachable in the first place** — the happens-before graph induced by the synchronization primitives already used (`pthread_create`/`pthread_join`) rules out any conflicting concurrent access. The lock isn't neutralizing a race; there was never one to neutralize.

This program is squarely the second case: the mutex is redundant with a happens-before edge that already exists for free via thread creation.

### Practical consequence

Removing `pthread_mutex_lock(&lock)`/`pthread_mutex_unlock(&lock)` entirely from `reader()` (and dropping `lock` altogether) does not change the program's behavior under any scheduling — both threads will always print `read: 42`. The mutex only adds two uncontended lock/unlock syscalls (or futex fast-path calls) per thread with zero correctness benefit.

### Caveat (scope of the classification)

This verdict is specific to the code as written. It would flip to **NECESSARY** if, e.g.:
- any thread later wrote to `shared_value` after thread creation, or
- `reader()` were invoked from a thread not sequenced by `pthread_create`/`pthread_join` relative to the write (e.g., via a thread pool with a condition variable and no direct creation edge), or
- `shared_value` were widened to a type where reads/writes aren't naturally atomic and could tear under a race (irrelevant here since there's no race, but relevant if the "no race" premise breaks).