Result: **NECESSARY**

The mutex `state_lock` in `state.c` is **strictly necessary for correctness** under the C/POSIX threading model.

### Why

The shared state is:

```c
static int degraded_mode = 0;
```

It is accessed concurrently by multiple worker threads:

* `set_degraded_mode()` **writes** `degraded_mode`.
* `is_degraded_mode()` **reads** `degraded_mode`.

Both operations are protected by the same mutex:

```c
pthread_mutex_lock(&state_lock);
...
pthread_mutex_unlock(&state_lock);
```

Thus, the mutex establishes the required synchronization between concurrent accesses.

### What happens without the lock?

Consider one thread executing the error path:

```c
void set_degraded_mode(void) {
    degraded_mode = 1;
}
```

while another executes:

```c
int is_degraded_mode(void) {
    return degraded_mode;
}
```

These accesses would constitute a **data race**: one thread writes the object while another thread reads it without synchronization.

In C, a data race on a non-atomic object results in **undefined behavior**. It is therefore not merely a question of whether the reader happens to see `0` or `1`.

The mutex prevents this:

```text
Thread A                         Thread B
--------                         --------
lock(state_lock)
degraded_mode = 1
unlock(state_lock)

                                 lock(state_lock)
                                 v = degraded_mode
                                 unlock(state_lock)
```

The unlock/lock synchronization also provides the necessary memory-ordering guarantees: once thread B acquires the mutex after thread A releases it, B can observe A's prior write.

### Is the lock logically necessary for the algorithm?

There is an important distinction here.

`degraded_mode` is a **monotonic flag**:

```text
0  ───────────────►  1
      set_degraded_mode()
```

It is never reset to `0`. Consequently, from a high-level algorithmic perspective, the program does not require complicated synchronization to maintain an invariant such as a counter or a compound data structure.

However, that does **not** make the mutex useless. The actual C implementation still has concurrent reads and writes to the same non-atomic `int`.

For example, replacing the mutex with an atomic integer would also be correct:

```c
static _Atomic int degraded_mode = 0;

int is_degraded_mode(void) {
    return atomic_load(&degraded_mode);
}

void set_degraded_mode(void) {
    atomic_store(&degraded_mode, 1);
}
```

But simply removing synchronization would not be correct.

### What about `printf()`?

The calls to:

```c
printf("[DEGRADED] %s\n", req);
printf("[NORMAL] %s\n", req);
```

are not what makes `state_lock` necessary. The mutex only protects `degraded_mode`.

There is also a separate issue: multiple worker threads call `printf()` concurrently. Standard C/POSIX I/O provides its own stream-level synchronization, so that does not justify removing or retaining `state_lock`. More importantly, `state_lock` is **not held while `printf()` executes**, so it does not serialize the log messages.

### Classification

| Property                                            | Assessment            |
| --------------------------------------------------- | --------------------- |
| Shared state                                        | `degraded_mode`       |
| Concurrent readers                                  | Yes                   |
| Concurrent writers                                  | Yes, potentially      |
| Protected by same mutex                             | Yes                   |
| Data race without mutex                             | **Yes**               |
| Mutex affects correctness                           | **Yes**               |
| Could another synchronization mechanism replace it? | Yes, e.g. C11 atomics |
| Is the current mutex useless?                       | **No**                |

**Conclusion:** `state_lock` is **NECESSARY** for the correctness of the program as written. The flag could be implemented with an atomic instead, but removing synchronization altogether would introduce a data race and undefined behavior.
