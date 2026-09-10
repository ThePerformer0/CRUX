Result: NECESSARY

---

### Technical Justification

1. **Shared State and Concurrency:**
The program creates 8 worker threads (`threads[8]`) that execute concurrently. Each thread calls `handle_request` 10,000 times, which in turn invokes `metrics_on_request_processed()`. This function modifies the static global variable `processed_requests`.
2. **Data Race Prevention:**
The operation `processed_requests++` is not atomic; it consists of three distinct machine-level steps: reading the current value into a register, incrementing it, and writing it back to memory. Because multiple threads execute this operation concurrently without synchronization, unprotected access would result in a **data race** (Undefined Behavior in C), leading to lost updates and an incorrect final count.
3. **Mutex Utility:**
The `metrics_lock` (a `pthread_mutex_t`) ensures mutual exclusion around the critical section where `processed_requests` is incremented and read. Even though `metrics_get_processed()` is called in `main` *after* all threads have been joined (meaning no concurrent access happens at the time of the read), the lock is strictly necessary during the active execution phase of the worker threads to serialize updates to `processed_requests`.

Therefore, the locks are **necessary** for thread safety, correctness, and preventing data races.