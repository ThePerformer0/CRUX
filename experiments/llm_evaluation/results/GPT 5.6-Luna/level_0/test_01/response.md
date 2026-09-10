Result: **USELESS**

### Technical justification

The mutex `lock` is **not necessary for program correctness** in this program.

The critical section is:

```c
pthread_mutex_lock(&lock);
local_counter++;
pthread_mutex_unlock(&lock);
```

The key observation is that `local_counter` is declared **inside `worker()`**:

```c
void* worker(void* arg) {
    int local_counter = 0;
```

Therefore, `local_counter` has **automatic storage duration and thread-local instance semantics**: each invocation of `worker()` has its own independent `local_counter`. In this program, there is only one worker thread anyway.

Consequently:

1. **No shared state is protected.**
   `local_counter` cannot be accessed concurrently by another thread because it is local to the `worker()` invocation.

2. **There is no data race.**
   The increment

   ```c
   local_counter++;
   ```

   operates exclusively on the worker's private variable.

3. **Removing the mutex does not change correctness.**
   The following is semantically equivalent:

   ```c
   void* worker(void* arg) {
       int local_counter = 0;
       local_counter++;

       printf("local_counter = %d\n", local_counter);
       return NULL;
   }
   ```

   It still deterministically prints:

   ```text
   local_counter = 1
   ```

4. **`pthread_join()` does not make the mutex necessary.**
   `main()` waits for the worker using:

   ```c
   pthread_join(t, NULL);
   ```

   But the mutex has no role in coordinating this communication. The worker completes before `main()` continues.

### Why this is a useless lock rather than merely "uncontended"

The important distinction is that the lock does not merely happen to experience no contention. **There is nothing requiring mutual exclusion in the first place.**

The protected operation concerns a variable whose scope is restricted to the worker invocation:

```text
worker thread
┌─────────────────────────┐
│ local_counter = 0       │
│        ↓                │
│   lock()                │
│   local_counter++       │ ← private state
│   unlock()              │
│        ↓                │
│      printf()           │
└─────────────────────────┘
```

The mutex therefore provides no correctness guarantee.

### Classification

**`USELESS`** — the lock can be removed without introducing a race, changing the program's synchronization semantics, or affecting its observable correct behavior.

It is stronger than a merely **SEMANTICALLY USELESS** lock: the protected variable is structurally private to the thread, so the necessity of the lock can be established directly from the program's scope/ownership properties.