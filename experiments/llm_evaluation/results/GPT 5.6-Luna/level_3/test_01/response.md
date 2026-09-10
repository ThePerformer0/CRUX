Result: **NECESSARY**

The mutex `metrics_lock` is **strictly necessary for program correctness** because `processed_requests` is a shared mutable variable accessed concurrently by all 8 worker threads.

### Technical justification

The critical operation is:

```c
processed_requests++;
```

This is a read-modify-write operation. Conceptually, it behaves like:

```text
tmp = processed_requests;
tmp = tmp + 1;
processed_requests = tmp;
```

Without the mutex, two threads can interleave these operations:

```text
Thread A: read processed_requests = 10
Thread B: read processed_requests = 10
Thread A: write 11
Thread B: write 11
```

Two requests were processed, but the counter increased only once. This is a classic **lost-update race**.

With 8 threads, each executing `handle_request()` 10,000 times, the intended result is:

```text
8 × 10,000 = 80,000
```

The mutex ensures that each increment is serialized:

```c
pthread_mutex_lock(&metrics_lock);
processed_requests++;
pthread_mutex_unlock(&metrics_lock);
```

Therefore, `metrics_on_request_processed()` cannot have concurrent conflicting updates to `processed_requests`.

### Why the getter also needs the lock

`metrics_get_processed()` performs:

```c
pthread_mutex_lock(&metrics_lock);
long v = processed_requests;
pthread_mutex_unlock(&metrics_lock);
```

In this particular program, `main()` calls `metrics_get_processed()` **only after joining all worker threads**:

```c
for (int i = 0; i < 8; i++) {
    pthread_join(threads[i], NULL);
}

printf("Processed: %ld\n", metrics_get_processed());
```

Consequently, when `metrics_get_processed()` is called, no worker thread is still modifying `processed_requests`.

So there is an important distinction:

* **Lock in `metrics_on_request_processed()` → strictly necessary.**
* **Lock in `metrics_get_processed()` → not strictly necessary for this particular call pattern**, because all writers have terminated after the `pthread_join()` calls.
* However, keeping the lock in the getter is reasonable because it makes the metrics API safe if it is later called concurrently with updates.

### Are the locks logically or semantically useless?

No.

The lock around the increment is **not logically useless**: removing it can change the observable result of the program. The final count may be less than 80,000 because of lost updates.

It is also not merely **semantically useless**. The synchronization has a concrete correctness purpose: it establishes mutual exclusion around the shared state mutation.

The computation inside `handle_request()` itself does not require a lock: its local variables (`result`, `x`, and `y`) are thread-local, and the request string is a shared read-only string literal. The only clearly shared mutable state requiring synchronization is:

```c
static long processed_requests = 0;
```

**Conclusion:** the `metrics_lock` is **NECESSARY**, specifically for protecting the concurrent increment of `processed_requests`. The getter's lock is redundant under the exact synchronization structure of this program, but the mutex as a whole is essential.
