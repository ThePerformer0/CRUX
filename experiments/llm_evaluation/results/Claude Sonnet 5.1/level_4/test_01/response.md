Result: SEMANTICALLY USELESS

**Justification**

**1. Tracing actual reachability, not just the textual code shape**

The locking pattern in `state.c` looks, in isolation, like a textbook correct case for a mutex: a global flag (`degraded_mode`) is written by `set_degraded_mode()` and read by `is_degraded_mode()`, and both operations run under `state_lock`. If both functions were genuinely invoked concurrently by different threads, the lock would be *necessary* — an unsynchronized concurrent read/write to a non-atomic `int` is a data race and undefined behavior under the C11/pthreads memory model, regardless of whether the underlying hardware could tear the access.

The catch is in how `main.c` actually drives the program:

```c
void* worker(void* arg) {
    handle_request("GET /");
    return NULL;
}
```

All 16 threads call `handle_request()` with the same hardcoded literal, `"GET /"`. Inside `handle_request()`:

```c
if (!validate_request(req)) {
    set_degraded_mode();
    return;
}
log_request(req);
```

and `validate_request()` is:

```c
int validate_request(const char* req) {
    return req && strlen(req) > 0;
}
```

For `req = "GET /"`, this is a non-null pointer with `strlen == 5 > 0`, so `validate_request()` **always** returns true. Consequently `!validate_request(req)` is always false, and `set_degraded_mode()` is **statically unreachable** in this program — it is dead code given the fixed call site in `worker()`. There is no path anywhere in the program (no CLI args, no I/O, no randomness) that can change this.

**2. Consequence for `degraded_mode`**

`degraded_mode` is a `static` global initialized to `0` via `PTHREAD_MUTEX_INITIALIZER`/zero-initialization before `main()` starts spawning threads. Since `set_degraded_mode()` is never called, `degraded_mode` is **never mutated after program start**. Every one of the 16 threads that reaches `log_request()` → `is_degraded_mode()` is therefore reading a value that is write-once-at-load-time and read-only for the entire concurrent phase of the program.

**3. Why this makes the lock semantically, not structurally, useless**

Per the C/pthreads data-race definition, a race requires at least one of the conflicting concurrent accesses to be a *write*. With `set_degraded_mode()` unreachable, all concurrent accesses to `degraded_mode` are reads. Concurrent reads of a variable that no thread is writing during that window are inherently race-free and well-defined *with or without* the mutex. Removing `pthread_mutex_lock/unlock` from `is_degraded_mode()` in this exact program would not introduce any UB, would not change the observable output (`printf` always takes the `"[NORMAL] %s\n"` branch, 16 times, in some interleaving), and would not affect timing-sensitive correctness in any way.

This is different from a lock being flatly **USELESS** (e.g., a mutex wrapped around a purely thread-local variable, or a lock in an inherently single-threaded program), because here the protected object genuinely *is* shared, mutable, global state, and the locking discipline (lock/unlock symmetric on both accessor functions) is the *correct pattern in general* for that kind of state. The uselessness doesn't come from the synchronization primitive being misapplied to non-shared data — it comes from the surrounding program logic (a hardcoded, always-valid request string) making the hazardous interleaving (read racing a write) unreachable. That's a semantic property of *this specific program's control flow and input domain*, not a structural property of the lock's placement — hence "semantically useless" rather than "useless."

**4. Caveat / why this isn't "NECESSARY"**

One might argue the lock should be judged as "necessary" because `state.c` is a general-purpose module whose API contract (`is_degraded_mode`/`set_degraded_mode`) must be safe for arbitrary callers. That's a reasonable defensive-engineering argument, but the question asks about necessity *for this program's correctness* as written. Since `main.c` and `request.c` together guarantee `validate_request()` never fails for the only request ever issued, the write side of the shared state is dead code, and the module's synchronization — while well-formed — is not doing any work that affects this program's correctness.

**Summary:** The mutex is correctly implemented and would become genuinely necessary the moment `handle_request()` could receive a request that fails validation (e.g., a NULL or empty string, or real external/network input instead of a hardcoded literal) concurrently with valid requests from other threads. As the program is actually written, however, that writer path is unreachable, all concurrent accesses reduce to reads of a value fixed at `0`, and the lock is therefore semantically useless — inert with respect to this program's actual observable behavior and correctness.