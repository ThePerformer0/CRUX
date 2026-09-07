Result: **NECESSARY**

### Justification:

The `state_lock` mutex in `state.c` is necessary for the correct operation of the multithreaded server for the following reasons:

* **Prevention of Data Races:** The variable `degraded_mode` is a shared global resource. In this application, 16 worker threads are created, each executing `handle_request`. This means multiple threads can simultaneously call `is_degraded_mode()` to read the flag or `set_degraded_mode()` to update it. Without the mutex, concurrent access (at least one being a write) to this memory location constitutes a data race under the C standard.
* **Memory Visibility:** In a multithreaded environment, there is no guarantee that a change made to a variable by one thread (setting the system to degraded mode) will be immediately visible to other threads. Mutexes act as memory barriers; `pthread_mutex_unlock` ensures the write is committed, and `pthread_mutex_lock` ensures the reader sees the most recent committed value.
* **Logical Coordination:** While the current logic in `main.c` only sends valid requests ("GET /"), which shouldn't trigger the error path, the `handle_request` function is designed to transition the system state if validation fails. If a validation error were to occur on one thread, the mutex ensures that all other threads calling `is_degraded_mode` subsequently observe the `degraded_mode = 1` state consistently.
* **Atomicity:** Although `int` access is often atomic on modern hardware, it is not guaranteed by the C language specification. The mutex ensures that the read and write operations are treated as atomic units by the CPU and the compiler.