Result: **USELESS**

### Technical justification

The relevant lock is:

```c
static pthread_mutex_t dispatch_lock = PTHREAD_MUTEX_INITIALIZER;
```

It is used in both `dispatch_register_observer()` and `dispatch_event()`:

```c
void dispatch_register_observer(void (*cb)(const char*)) {
    pthread_mutex_lock(&dispatch_lock);
    g_observer = cb;
    pthread_mutex_unlock(&dispatch_lock);
}
```

and:

```c
void dispatch_event(const char* event) {
    pthread_mutex_lock(&dispatch_lock);
    if (g_observer) {
        g_observer(event);
    }
    pthread_mutex_unlock(&dispatch_lock);
}
```

#### 1. `g_observer` is initialized before concurrency begins

In `main()`:

```c
observer_init();
dispatch_register_observer(observer_callback);

pthread_create(&t1, NULL, worker, NULL);
pthread_create(&t2, NULL, worker, NULL);
```

The observer is registered **before** either worker thread is created. There is therefore no concurrent call to `dispatch_register_observer()` while `dispatch_event()` is executing.

Consequently, `g_observer` is effectively immutable during the concurrent portion of the program.

The two worker threads only perform:

```c
dispatch_event("update");
```

They never modify `g_observer`.

---

#### 2. The actual shared mutable state is already protected

The observer maintains:

```c
static int observer_count = 0;
static pthread_mutex_t observer_lock = PTHREAD_MUTEX_INITIALIZER;
```

and increments it under `observer_lock`:

```c
pthread_mutex_lock(&observer_lock);

if (strcmp(event, "update") == 0) {
    observer_count++;
}

pthread_mutex_unlock(&observer_lock);
```

Thus, when the two worker threads concurrently invoke:

```c
observer_callback("update");
```

the increment of `observer_count` is correctly serialized by `observer_lock`.

The execution is effectively:

```text
Thread 1                         Thread 2
   |                                |
dispatch_event()               dispatch_event()
   |                                |
dispatch_lock                   dispatch_lock
   |                                |
observer_callback()            observer_callback()
   |                                |
observer_lock                  waits
   |
observer_count++
   |
unlock observer_lock
                                    |
                              observer_count++
```

The `dispatch_lock` adds another level of serialization, but it does not provide the synchronization that protects the actual shared counter. `observer_lock` already does that.

---

#### 3. `dispatch_lock` unnecessarily serializes the callbacks

There is an important performance consequence.

Because `dispatch_event()` holds `dispatch_lock` **while executing the callback**:

```c
pthread_mutex_lock(&dispatch_lock);

if (g_observer) {
    g_observer(event);
}

pthread_mutex_unlock(&dispatch_lock);
```

only one thread can execute `observer_callback()` at a time.

But `observer_callback()` itself already serializes access to `observer_count`:

```c
pthread_mutex_lock(&observer_lock);
observer_count++;
pthread_mutex_unlock(&observer_lock);
```

Therefore, `dispatch_lock` creates redundant serialization:

```text
dispatch_lock
    ↓
only one callback at a time
    ↓
observer_lock
    ↓
protects observer_count
```

The second lock is unnecessary for correctness in this program.

In fact, removing `dispatch_lock` from `dispatch_event()` still leaves the program correct:

```c
void dispatch_event(const char* event) {
    if (g_observer) {
        g_observer(event);
    }
}
```

The two threads can now enter the callback concurrently, but `observer_lock` safely protects `observer_count`.

---

### Expected result

There are 2 worker threads × 10 events each:

```text
2 × 10 = 20
```

Every event is `"update"`, so the final value remains:

```text
Final Observer Count: 20
```

with or without `dispatch_lock`.

### Important qualification

`dispatch_lock` **would become necessary** if the program allowed concurrent observer registration, for example:

```text
Thread 1: dispatch_register_observer(...)
Thread 2: dispatch_event(...)
```

In that case, unsynchronized access to `g_observer` could constitute a data race, and the lock could also provide synchronization around the registration/dispatch relationship.

But **that situation does not occur in the supplied program**: registration happens-before the worker threads are created and `g_observer` is never subsequently modified.

Therefore, under the concrete program being analyzed:

> **Result: USELESS**

`dispatch_lock` does not contribute to correctness and instead imposes unnecessary lock acquisition and callback serialization. The lock that is actually required for correctness is `observer_lock`, which protects the shared `observer_count`.
