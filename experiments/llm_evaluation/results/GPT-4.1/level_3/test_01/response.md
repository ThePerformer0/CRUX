**Result:** **NECESSARY**

**Justification:**

The mutex `metrics_lock` in `metrics.c` is **required for correctness** and is neither logically nor semantically useless.

Here’s the detailed reasoning:

---

### 1. Shared mutable state accessed by multiple threads

* `processed_requests` is a `static long` with global lifetime.
* It is **modified** in `metrics_on_request_processed()`.
* It is **read** in `metrics_get_processed()`.

Both functions are called by **multiple threads concurrently**:

* `metrics_on_request_processed()` is invoked by every worker thread inside `handle_request()`.
* `metrics_get_processed()` is called after all worker threads complete.

This is classic shared mutable state.

---

### 2. `processed_requests++` is not atomic

* The increment operation:

  ```c
  processed_requests++;
  ```

  expands to:

  * load
  * increment
  * store
* Without a mutex (or atomics), concurrent increments would cause **lost updates** due to data races.

This would result in an incorrect final count.

---

### 3. Mutex ensures mutual exclusion and data race freedom

The mutex guarantees:

* Only one thread modifies `processed_requests` at a time.
* Reads in `metrics_get_processed()` see a consistent value.
* The program remains **well-defined** under the C memory model.

Removing the mutex would introduce **undefined behavior**.

---

### 4. Lock scope is minimal and appropriate

* The critical sections are very small (single increment / single read).
* The mutex protects exactly the data it should, no more and no less.
* There is no over-synchronization or redundant locking.

---

### 5. Why this is not “semantically useless”

A mutex would be semantically useless if:

* The data were immutable
* Each thread had its own private copy
* Or the operations were already atomic or single-threaded

None of those conditions apply here.

---

### 6. No alternative implicit synchronization

* The threads run concurrently for the entire workload.
* Thread joins happen **after** all increments.
* `pthread_join()` does not serialize access to `processed_requests`.

Thus, there is no other mechanism that accidentally provides safety.

---

### Conclusion

The mutex `metrics_lock` is **necessary** to prevent data races and ensure correctness of the processed request counter in a multithreaded environment.

✔ **Correct synchronization**
✔ **Prevents undefined behavior**
✔ **Not redundant**
✔ **Not misleading**

**Final verdict:** **NECESSARY**
