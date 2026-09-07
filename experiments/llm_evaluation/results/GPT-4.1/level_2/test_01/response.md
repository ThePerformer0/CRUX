**Result:** SEMANTICALLY USELESS

**Justification:**
The mutex is used consistently and correctly, but given the program’s semantics, it provides no additional safety or correctness.

Step-by-step reasoning:

* `config_value` is a shared global variable with internal linkage (`static` in `config.c`).
* It is **written exactly once** in `config_init()`.
* `config_init()` is called in `main` **before any threads are created**.
* After initialization:

  * `config_value` is **never modified again**
  * All worker threads only **read** it via `config_get_value()`

Memory-ordering guarantees:

* POSIX guarantees that all memory writes performed **before `pthread_create`** are visible to the newly created threads.
* Therefore, both worker threads are guaranteed to observe `config_value == 100`, even without any mutex.

Effect of the mutex:

* In `config_init()`:

  * The lock is unnecessary because no other thread exists yet.
* In `config_get_value()`:

  * The lock protects a **read-only** variable.
  * Concurrent reads of immutable data are race-free.

Removing `config_lock` entirely:

* Does **not** introduce a data race
* Does **not** change observable behavior
* Does **not** weaken correctness or visibility guarantees

Why this is *semantically* useless (not just useless):

* The mutex is logically well-placed and suggests future extensibility.
* But under the **current program semantics** (write-once, read-many after initialization), synchronization is redundant.

When it would become **necessary**:

* If `config_value` could be modified after threads start
* If `config_init()` could run concurrently with readers
* If hot reconfiguration were introduced

As written, the mutex is **semantically useless**.
