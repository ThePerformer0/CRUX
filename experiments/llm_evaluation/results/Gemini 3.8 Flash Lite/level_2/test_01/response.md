Result: USELESS

---

### Technical Justification

The mutex (`config_lock`) and its associated locking/unlocking operations in `config.c` are entirely redundant for several architectural and concurrency reasons:

* **Happens-Before Relationship via Thread Creation:** In `main.c`, `config_init()` is called synchronously in the main thread *before* any worker threads (`t1` and `t2`) are created using `pthread_create`. According to the POSIX threads and C memory models, `pthread_create` establishes a **happens-before** edge. This guarantees that all memory writes performed prior to thread creation (including the initialization of `config_value = 100`) are fully visible to the newly spawned threads without requiring explicit synchronization.
* **Read-Only Access Post-Initialization:** Once `config_init()` completes, `config_value` is never modified again for the remainder of the program's lifecycle. It effectively functions as an immutable constant.
* **Absence of Data Races:** The worker threads exclusively invoke `config_get_value()`, which only reads `config_value`. In C, concurrent read-only access to a shared variable by multiple threads is completely safe and does not constitute a data race.

Because initialization occurs strictly before concurrent execution begins, and subsequent accesses are strictly read-only, the mutex provides zero protective benefit and is logically useless.