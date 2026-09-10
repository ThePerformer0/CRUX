Result: **USELESS**

### Technical justification

The mutex `lock` is **not necessary for program correctness** in this program.

The only shared variable accessed by both worker threads is:

```c
int global_value = 42;
```

Each worker performs:

```c
pthread_mutex_lock(&lock);
int v = global_value;
pthread_mutex_unlock(&lock);
```

However, `global_value` is **never modified** after initialization. Both threads only perform a read.

Therefore:

1. **There is no concurrent write.**
   A data race requires conflicting accesses, where at least one access is a write. Here, both threads only read `global_value`.

2. **Both threads always observe the same value.**
   Since `global_value` remains `42`, each worker obtains:

   ```c
   v == 42
   ```

3. **The local variable `v` is thread-local.**
   Each invocation of `worker()` has its own stack/local copy of `v`, so there is no synchronization requirement for it.

4. **`printf()` does not make this mutex necessary.**
   The mutex is released **before** `printf()`:

   ```c
   pthread_mutex_unlock(&lock);
   printf("value = %d\n", v);
   ```

   Consequently, the lock does not even serialize the calls to `printf()`.

5. **Removing the mutex does not change the program's correctness.**

The worker can equivalently be:

```c
void* worker(void* arg) {
    int v = global_value;
    printf("value = %d\n", v);
    return NULL;
}
```

The program still has well-defined behavior with respect to `global_value`, and both threads will read `42`.

### Classification

This is a **logically useless lock**: the critical section protects a read-only value for which no competing write exists.

It is stronger than merely saying that the lock is "uncontended." Even if the two threads execute the critical section simultaneously, **mutual exclusion provides no correctness benefit** because concurrent reads are safe.

**Therefore: `USELESS`.**
