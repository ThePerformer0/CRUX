**Result:** SEMANTICALLY USELESS

**Justification:**
The mutex protects a shared variable, but given the program’s semantics, that protection is unnecessary.

Detailed reasoning:

* `shared_value` is a **shared global variable**, accessed by multiple threads.
* It is **written exactly once** in `main`, **before** any threads are created.
* After thread creation, `shared_value` is **never modified again**.
* Both `reader` threads only **read** the value.

Key semantic points:

* The write `shared_value = 42` happens-before:

  * `pthread_create(&t1, ...)`
  * `pthread_create(&t2, ...)`
* POSIX guarantees that memory writes performed before `pthread_create` are **visible to the newly created thread**.
* Concurrent **read-only access** to shared data does **not** constitute a data race.

Effect of the mutex:

* The lock enforces mutual exclusion, but:

  * There are no concurrent writes
  * No invariant to protect
  * No ordering ambiguity to resolve
* Removing the mutex:

  * Does **not** introduce a data race
  * Does **not** change program behavior
  * Does **not** affect correctness

Why this is *semantically* useless:

* The mutex appears logically motivated (shared data, multiple threads).
* But the **immutability of `shared_value` after thread creation** makes synchronization unnecessary.

If `shared_value` were modified by any thread after creation, the mutex would become **necessary**.
