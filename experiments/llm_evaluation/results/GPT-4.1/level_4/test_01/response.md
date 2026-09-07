Result: **NECESSARY**

Justification:
The mutex `state_lock` is **not useless**, neither logically nor semantically.

Here’s why:

* `degraded_mode` is a shared global variable accessed by **multiple threads**:

  * Written in `set_degraded_mode()` (error path in `handle_request`)
  * Read in `is_degraded_mode()` (called by `log_request`)
* These accesses can occur **concurrently** across worker threads.

Without the mutex:

* You would have a **data race**: at least one write and one read of `degraded_mode` without synchronization.
* In C, data races result in **undefined behavior**, even for a simple `int`.
* There is no guarantee of visibility: one thread may never observe the update made by another.

With the mutex:

* Mutual exclusion ensures **atomicity** of access to `degraded_mode`.
* The mutex provides a **happens-before relationship**, guaranteeing visibility of the write to all readers.
* The behavior becomes well-defined and portable.

Important nuance:

* While the mutex may be **overkill** from a performance or design perspective (an `atomic_int` or `atomic_bool` would be more lightweight), that does **not** make it useless.
* “Semantically useless” would mean removing it does not change correctness or behavior — which is **not true** here.

So:

* The mutex is **functionally required** for correctness.
* It enforces necessary synchronization and memory ordering.
* Therefore, it is **NECESSARY**, not useless.
