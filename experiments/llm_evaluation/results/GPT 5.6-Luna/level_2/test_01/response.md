Result: **USELESS**

### Technical justification

The mutex `config_lock` is **not strictly necessary for program correctness** in this particular program.

The key point is the ordering established by `main()`:

1. `config_init()` is called **before** any worker thread is created.
2. `config_init()` sets:

   ```c
   config_value = 100;
   ```
3. Only after `config_init()` returns are `t1` and `t2` created.
4. Both worker threads subsequently call `config_get_value()`.
5. `config_value` is **never modified again** after initialization.

Therefore, the accesses to `config_value` made by the worker threads are only reads, and they occur after the initialization has completed.

#### Why the locks are unnecessary

The lock in `config_init()`:

```c
pthread_mutex_lock(&config_lock);
config_value = 100;
pthread_mutex_unlock(&config_lock);
```

does not protect against any concurrent access, because no worker thread exists yet.

Likewise, the locks in `config_get_value()`:

```c
pthread_mutex_lock(&config_lock);
int v = config_value;
pthread_mutex_unlock(&config_lock);
```

do not provide meaningful synchronization between the workers. Both threads only read the same immutable value.

Conceptually, the program could be reduced to:

```c
void config_init(void) {
    config_value = 100;
}

int config_get_value(void) {
    return config_value;
}
```

and the observable behavior would remain the same: both workers print `config = 100`.

### Why this is not merely "semantically useless"

Under a classification such as DeLock's, **SEMANTICALLY USELESS** would be more appropriate when a lock protects an operation that may have some synchronization/ordering role but whose critical section is semantically idempotent or otherwise does not require mutual exclusion.

Here, the mutex has **no required mutual-exclusion role at all**:

* there is no concurrent write;
* there is no concurrent read/write conflict;
* there is no shared mutable state after initialization;
* there is no lock-based ordering needed between the worker threads.

Thus the lock is **logically unnecessary**, rather than merely semantically redundant.

### One important C/POSIX nuance

This conclusion depends on the program's actual execution structure. If `config_init()` could execute concurrently with `config_get_value()`, the classification could change: the write to `config_value` and concurrent reads would constitute a data race in ordinary C, and synchronization would then be required.

But **for the program exactly as given**, `config_init()` happens-before thread creation, and the value is subsequently read-only.

**Final classification: `USELESS`.**
