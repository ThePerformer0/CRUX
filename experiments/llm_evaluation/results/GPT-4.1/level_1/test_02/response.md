**Result:** USELESS

**Justification:**
The mutex does not provide any meaningful synchronization because no concurrent access to the shared variable ever occurs.

Detailed reasoning:

* `counter` is a shared global variable, but:

  * It is incremented by **only one worker thread**
  * It is read by `main` **after** `pthread_join`
* There is **no overlap** between:

  * The write to `counter` in `worker`
  * The read of `counter` in `main`

Key ordering guarantees:

* `pthread_join` establishes a **happens-before** relationship:

  * All writes done by `worker` are guaranteed to be visible in `main` after the join.
* Since only one thread modifies `counter`, there is:

  * No data race
  * No need for mutual exclusion

Effect of the mutex:

* The lock/unlock pair surrounds an operation that is:

  * Never executed concurrently with another access to `counter`
* Removing the mutex:

  * Does **not** change program behavior
  * Does **not** introduce a race
  * Does **not** affect correctness

This makes the mutex **logically useless**: although the variable is shared, the program structure guarantees exclusive access without any synchronization primitive.

If multiple worker threads incremented `counter`, the mutex would become **necessary**.
