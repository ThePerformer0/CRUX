Result: **USELESS**

### Technical justification

The mutex `version_lock` in `version_get()` is **not necessary for program correctness** in this program.

The relevant function is:

```c
const char* version_get(void) {
    pthread_mutex_lock(&version_lock);
    const char* v = APP_VERSION;
    pthread_mutex_unlock(&version_lock);
    return v;
}
```

There are five worker threads, and all of them may call `version_get()` concurrently. However, the only shared object accessed inside the critical section is:

```c
static const char* APP_VERSION = "v1.2.3-lite";
```

#### 1. `APP_VERSION` is never modified

`APP_VERSION` is initialized once:

```c
static const char* APP_VERSION = "v1.2.3-lite";
```

and there is **no write to `APP_VERSION` anywhere in the program**.

Each thread only performs:

```c
const char* v = APP_VERSION;
```

This is a read-only access to the same pointer value.

Therefore, concurrent executions such as:

```text
Thread 1: read APP_VERSION
Thread 2: read APP_VERSION
Thread 3: read APP_VERSION
...
```

do not create a data race or produce inconsistent state.

#### 2. The returned string is immutable

The string literal:

```c
"v1.2.3-lite"
```

is not modified by the program. All threads receive a pointer to the same immutable string literal.

Thus, there is no shared mutable state that needs mutual exclusion.

#### 3. `pthread_join()` does not make the mutex necessary

The calls to:

```c
pthread_join(t[i], NULL);
```

ensure that `main()` waits for all workers to finish, but they are unrelated to the necessity of `version_lock`.

The workers themselves can safely execute `version_get()` concurrently.

#### 4. Removing the lock preserves correctness

The function can safely be reduced to:

```c
const char* version_get(void) {
    return APP_VERSION;
}
```

The observable behavior remains equivalent: every worker obtains the same string and prints:

```text
Software Version: v1.2.3-lite
```

The ordering of the five `printf()` calls may vary, but that is already allowed by the concurrent execution and is not controlled by `version_lock`.

### Why this is **USELESS**, not **SEMANTICALLY USELESS**

Under a distinction such as the one used in your DeLock classification:

* **USELESS** → the lock protects state that is inherently safe to access concurrently; removing it does not affect correctness.
* **SEMANTICALLY USELESS** → the protected operation may appear to involve shared state or synchronization, but its semantics make the synchronization unnecessary in a more subtle way.

Here the case is straightforward: **there is no concurrent mutation of `APP_VERSION` at all**. The mutex simply serializes multiple identical reads.

So the classification is:

> **Result: USELESS**

The mutex adds synchronization overhead—potentially involving `pthread_mutex_lock/unlock` and contention between the five threads—without providing any correctness guarantee that the program actually needs.
