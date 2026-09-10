Result: **SEMANTICALLY USELESS**

### Technical justification

The mutex `config_mutex` is **not strictly necessary for correctness in this program**, even though `global_config` is shared and the code superficially looks like it requires mutual exclusion.

The key point is the **barrier** in `worker()`:

```c
if (id == 0) {
    config_init(42);
}

pthread_barrier_wait(&barrier);

int val = config_get();
```

#### 1. `config_init()` executes before the barrier

Only thread `0` calls:

```c
config_init(42);
```

Inside `config_init()`:

```c
pthread_mutex_lock(&config_mutex);
global_config = val;
pthread_mutex_unlock(&config_mutex);
```

The assignment to `global_config` therefore completes before thread 0 reaches:

```c
pthread_barrier_wait(&barrier);
```

#### 2. Every `config_get()` executes after the barrier

All four threads must reach the barrier before any of them can proceed past it.

Consequently, thread 0 cannot proceed beyond the barrier until:

```c
global_config = 42;
```

has already occurred.

Thus, after the barrier:

```text
             Thread 0
                 |
          global_config = 42
                 |
          unlock(config_mutex)
                 |
          barrier_wait()
                 |
       ====================
          barrier release
       ====================
          /    |    |    \
         /     |    |     \
      get()  get() get()  get()
```

There is no execution in which a `config_get()` can read `global_config` while `config_init()` is still modifying it.

#### 3. The `config_get()` calls cannot race with each other

After the barrier, `global_config` is only read:

```c
int val = global_config;
```

There are no subsequent writes to `global_config`.

Therefore, the four threads could safely execute:

```c
int val = global_config;
```

concurrently.

The mutex merely serializes these reads:

```text
Thread 0: lock → read → unlock
Thread 1:          lock → read → unlock
Thread 2:                   lock → read → unlock
Thread 3:                            lock → read → unlock
```

but that serialization provides no correctness benefit.

### What happens if the mutex is removed?

The implementation can effectively become:

```c
void config_init(int val) {
    global_config = val;
}

int config_get(void) {
    return global_config;
}
```

The barrier still guarantees that the initialization occurs before the reads.

The resulting behavior is therefore still:

```text
Thread 0 read config: 42
Thread 1 read config: 42
Thread 2 read config: 42
Thread 3 read config: 42
```

(up to the nondeterministic ordering of the `printf()` output).

### Why **SEMANTICALLY USELESS** rather than simply **USELESS**?

The distinction is important.

The mutex is **not inherently useless** if these functions are considered independently as a reusable configuration API. For example, if another thread could call:

```c
config_init(100);
```

concurrently with:

```c
config_get();
```

then synchronization would be necessary to prevent a data race.

But **in the concrete program given**, the surrounding program semantics impose a stronger ordering:

```text
config_init(42)
       ↓
   barrier
       ↓
 config_get()
```

The barrier makes the mutex redundant.

So the lock is **semantically useless in this particular program**, because the program's higher-level synchronization already establishes the necessary happens-before/order relationship. It is not useless merely because `global_config` is private to `config.c`; the variable is genuinely shared across threads. The redundancy comes specifically from the barrier.

**Final classification: `SEMANTICALLY USELESS`.**
