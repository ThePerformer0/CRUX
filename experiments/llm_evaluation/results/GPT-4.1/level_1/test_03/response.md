**Result:** SEMANTICALLY USELESS

**Justification:**
Although the mutex protects a shared variable that is both written and read, the program’s execution order makes the lock unnecessary.

Detailed reasoning:

* `value` is a shared global variable.
* It is **written** by `writer` and **read** by `reader`.
* However, the threads are **not concurrent**:

  * `writer` is created and fully completed (`pthread_join(t1)`)
  * Only after that does `reader` get created

Key ordering guarantees:

* `pthread_join(t1)` establishes a **happens-before** relationship:

  * All writes performed by `writer` (including `value = 10`) are visible to the main thread after the join.
* `pthread_create(t2, ...)` occurs **after** the join, so the `reader` thread will necessarily observe the updated value.

Consequences:

* There is **no overlap** between:

  * The write to `value`
  * The read of `value`
* No data race is possible, even without a mutex.
* Removing the mutex:

  * Does **not** change program behavior
  * Does **not** weaken correctness or visibility guarantees

Why this is *semantically* useless:

* The mutex appears logically required (shared read/write).
* But the **sequential thread lifecycle** already enforces the needed ordering.

If `writer` and `reader` could run concurrently, the mutex would become **necessary**.
