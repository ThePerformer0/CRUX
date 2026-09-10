**Result: USELESS**

The mutex is **not strictly necessary for program correctness in this particular program**.

### Technical justification

The shared variable is:

```c
int counter = 0;
```

The only modification to `counter` occurs in `worker()`:

```c
pthread_mutex_lock(&lock);
counter++;
pthread_mutex_unlock(&lock);
```

At first glance, `counter++` is a classic data-race candidate because it is a read-modify-write operation. However, we need to consider the **actual thread lifetime and synchronization structure**.

#### 1. There is only one worker thread

`main()` creates exactly one worker:

```c
pthread_create(&t, NULL, worker, NULL);
```

No other thread executes `counter++`.

Therefore, there cannot be two concurrent executions of:

```c
counter++;
```

that interfere with each other.

The increment is effectively:

```text
counter = 0
    |
    v
worker thread
    |
    +-- counter++  → counter = 1
```

There is no competing writer.

#### 2. `pthread_join()` already provides the required synchronization

After creating the worker, `main()` executes:

```c
pthread_join(t, NULL);
```

The `join` waits until the worker has terminated before continuing to:

```c
printf("counter = %d\n", counter);
```

Consequently, the `printf()` cannot execute concurrently with the worker's modification of `counter`.

The relevant ordering is:

```text
Worker thread:                 Main thread:

counter++ 
    |
    v
worker terminates
    |
    | pthread_join
    v
                              pthread_join returns
                                    |
                                    v
                              printf(counter)
```

Thus, the mutex is not needed to establish the ordering between the worker and `main`; `pthread_join()` already does that.

#### 3. Removing the mutex preserves the program's behavior

The worker can therefore be simplified to:

```c
void* worker(void* arg) {
    counter++;
    return NULL;
}
```

The program still deterministically produces:

```text
counter = 1
```

There is no possibility of two threads simultaneously modifying `counter`.

### Why this is `USELESS`, rather than `SEMANTICALLY USELESS`

For this classification, the distinction is important:

* **USELESS**: the synchronization mechanism is unnecessary at the logical/concurrency level.
* **SEMANTICALLY USELESS**: the lock may guard something that is technically concurrent, but the protected operation has semantics that make the synchronization unnecessary, such as an idempotent or otherwise semantically harmless operation.

Here, the simpler situation applies: **there is no competing concurrent access that requires mutual exclusion at all**.

The mutex does not contribute to correctness because:

1. only one worker modifies `counter`;
2. `main` reads `counter` only after `pthread_join()` completes;
3. therefore, no conflicting accesses to `counter` occur concurrently.

### Final classification

**Result: USELESS**

The lock introduces synchronization overhead without providing any correctness benefit. `pthread_join()` is the synchronization primitive that matters here; the mutex around `counter++` can safely be removed.
