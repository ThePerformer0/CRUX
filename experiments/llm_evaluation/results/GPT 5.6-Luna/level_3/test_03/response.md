Result: **NECESSARY**

The `monitor_lock` is **strictly necessary for program correctness** under the C/POSIX memory model because `last_activity` is a shared variable accessed concurrently by multiple threads, with both reads and writes occurring without any other synchronization.

### Technical justification

The shared state is:

```c
static time_t last_activity = 0;
static pthread_mutex_t monitor_lock = PTHREAD_MUTEX_INITIALIZER;
```

Two operations access `last_activity`:

* `monitor_update_heartbeat()` **writes** to it.
* `monitor_get_last_activity()` **reads** it.

The two worker threads repeatedly execute:

```c
monitor_update_heartbeat();
```

while the main thread concurrently executes:

```c
monitor_get_last_activity();
```

Therefore, there are concurrent accesses to the same memory location, including **writes**.

#### 1. The mutex establishes synchronization

The update operation is:

```c
pthread_mutex_lock(&monitor_lock);
last_activity = time(NULL);
pthread_mutex_unlock(&monitor_lock);
```

and the read operation is:

```c
pthread_mutex_lock(&monitor_lock);
time_t t = last_activity;
pthread_mutex_unlock(&monitor_lock);
```

The same mutex protects both accesses.

Consequently, the mutex establishes the required happens-before relationship between conflicting accesses. A completed update performed while holding `monitor_lock` becomes visible to a subsequent reader that acquires the same mutex.

Without the mutex, the program would contain concurrent conflicting accesses to `last_activity`:

```text
worker 1 ── write ──┐
worker 2 ── write ──┼──> last_activity
main    ── read  ───┘
```

The writes and read are not otherwise synchronized.

#### 2. Removing the mutex introduces a data race

If the code were changed to:

```c
void monitor_update_heartbeat(void) {
    last_activity = time(NULL);
}

time_t monitor_get_last_activity(void) {
    return last_activity;
}
```

the main thread could read `last_activity` while one of the worker threads is modifying it.

In standard C, this constitutes a **data race** because `last_activity` is a non-atomic object concurrently accessed, with at least one access being a write, and there is no appropriate synchronization.

A data race results in **undefined behavior** under the C memory model. Therefore, the lock is not merely an optimization or a mechanism for avoiding occasional inconsistent output—it is required to make the concurrent program well-defined.

#### 3. The fact that `time_t` is usually a machine-sized integer does not make the lock unnecessary

One might argue that `time_t` is commonly an integer type and that a read/write is likely to be performed atomically by the hardware.

That is insufficient for this classification.

The correctness question is governed by the **C memory model**, not merely by whether a particular CPU happens to perform the load/store atomically. Even if every individual `time_t` access happened to compile to one atomic machine instruction, unsynchronized conflicting accesses would still constitute a C data race.

If atomicity were intentionally desired, the appropriate alternative would be an atomic object, e.g. an appropriately chosen `_Atomic` representation—not simply removing the mutex.

### What about the two worker threads?

The two workers both call:

```c
monitor_update_heartbeat();
```

but they are serialized by `monitor_lock`:

```text
Worker 1: LOCK → write → UNLOCK
                         ↓
Worker 2:           LOCK → write → UNLOCK
```

This prevents their writes from occurring as unsynchronized conflicting operations.

However, the mutex's more important role is protecting the **writer–reader interaction** between the workers and `main()`.

### Semantic usefulness

The lock is also **semantically useful**, not merely technically required.

The function is called:

```c
monitor_update_heartbeat()
```

and `monitor_get_last_activity()` is intended to provide a consistent observation of the shared heartbeat state. The mutex gives the monitor a clear synchronization boundary:

> updates and observations of `last_activity` occur as mutually exclusive, synchronized operations.

There is one subtle point: because `time(NULL)` normally has one-second resolution, multiple heartbeat updates can produce the same value. That does **not** make the mutex useless. It only means that the value itself may not distinguish individual heartbeat events.

### Classification

**Result: NECESSARY**

The lock protects a shared mutable `time_t` accessed concurrently by multiple threads. Removing it without replacing it with another synchronization mechanism creates a C data race and therefore undefined behavior. The mutex is consequently necessary for program correctness and is also semantically justified by the monitor's shared-state design.
