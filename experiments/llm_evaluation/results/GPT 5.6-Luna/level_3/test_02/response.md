Result: **NECESSARY**

### Technical justification

The mutex `cache_lock` is **strictly necessary for correctness of this C program**, even though all worker threads happen to store the same key/value pair.

#### 1. `cache_store()` performs concurrent writes to shared state

The following objects are global and shared by all threads:

```c
static int cached_value = -1;
static char cached_key[64] = "";
```

Every worker executes:

```c
cache_store("static_file_hash", 9999);
```

and therefore concurrently executes:

```c
strncpy(cached_key, key, 63);
cached_value = value;
```

Without the mutex, multiple threads can write to `cached_key` and `cached_value` simultaneously.

In the C memory model, **concurrent conflicting accesses to the same memory location, when at least one is a write and there is no appropriate synchronization, constitute a data race**. A data race produces undefined behavior.

This is true even if every thread writes exactly the same bytes and the same integer.

---

#### 2. The fact that all writes are identical does not eliminate the data race

Semantically, the operations are idempotent:

```text
cache_store(K, 9999)
cache_store(K, 9999)
cache_store(K, 9999)
cache_store(K, 9999)
```

The intended abstract state is always:

```text
cached_key   = "static_file_hash"
cached_value = 9999
```

So from a **high-level semantic perspective**, the order of the four `cache_store()` operations does not matter.

However, this does **not** make the unsynchronized implementation valid C.

For example, the writes performed by `strncpy()` modify multiple bytes of `cached_key`. The C language does not guarantee that simultaneous writes from different threads can safely overlap merely because they contain identical data.

Therefore:

> **Semantic idempotence ≠ absence of a data race.**

This distinction is important for classifying the lock.

---

#### 3. `cache_get()` also needs synchronization

The main thread eventually executes:

```c
for (int i = 0; i < NUM_THREADS; i++) {
    pthread_join(threads[i], NULL);
}

printf("Final cache value: %d\n", cache_get("static_file_hash"));
```

The `pthread_join()` calls ensure that all worker threads have terminated before `cache_get()` is called.

Thus, there is **no concurrent writer while `cache_get()` executes**. The `join()` operations provide the necessary synchronization from the workers to the main thread.

Consequently, the mutex inside `cache_get()` is arguably **redundant in this particular `main()` execution**, because:

```text
workers
   │
   ├── cache_store()
   ├── cache_store()
   ├── cache_store()
   └── cache_store()
          │
       pthread_join()
          │
          ▼
      cache_get()
```

There is no concurrent access at that point.

---

### What happens if we remove the locks?

If we remove the mutex from `cache_store()`:

```c
void cache_store(const char* key, int value) {
    strncpy(cached_key, key, 63);
    cached_value = value;
}
```

then the four worker threads concurrently modify `cached_key`.

That is enough to make the program's behavior undefined under the C memory model.

Therefore, **the lock in `cache_store()` cannot be classified as useless merely because all threads write the same value**.

The lock in `cache_get()`, however, is not necessary for the specific `main()` shown because all workers have already been joined.

### Final classification

| Lock location        | Assessment                               | Reason                                                                      |
| -------------------- | ---------------------------------------- | --------------------------------------------------------------------------- |
| `cache_store()`      | **NECESSARY**                            | Prevents concurrent unsynchronized writes/data races                        |
| `cache_get()`        | **Redundant in this specific execution** | `pthread_join()` guarantees workers have finished                           |
| Overall `cache_lock` | **NECESSARY**                            | Removing synchronization from `cache_store()` introduces undefined behavior |

So the appropriate DeLock-style classification is:

**Result: NECESSARY**

The interesting subtlety is that the workload is **semantically idempotent**, but the synchronization is still required to make the implementation conform to C's multithreading memory model.
