**Result: NECESSARY**

**Justification:**

The mutex `monitor_lock` is **required for correctness** and is neither logically nor semantically useless.

Here’s the reasoning in detail:

---

### 1. Shared mutable state accessed concurrently

The variable:

```c
static time_t last_activity;
```

is:

* Global (static)
* Writable
* Accessed by **multiple threads**:

  * Written by both worker threads (`monitor_update_heartbeat`)
  * Read by the main thread (`monitor_get_last_activity`)

This creates a classic shared-state concurrency scenario.

---

### 2. `time_t` is not guaranteed to be atomic

Although `time_t` is often implemented as a word-sized integer, **the C standard does not guarantee atomicity** for:

* Reads
* Writes
* Concurrent read/write access

Without synchronization:

* A read may observe a partially written value
* Or an indeterminate value
* Or trigger undefined behavior due to a data race

---

### 3. Data races are undefined behavior in C

Under the C memory model:

> Any concurrent access to the same object, where at least one access is a write and there is no synchronization, results in **undefined behavior**.

This holds true **even if**:

* All writes are “simple assignments”
* The value being written is “monotonically increasing”
* The program “seems to work” in practice

The mutex establishes the required **happens-before** relationship.

---

### 4. Mutex ensures memory visibility and ordering

The lock/unlock pair guarantees:

* Writes to `last_activity` are visible to readers
* The main thread never observes stale or torn values
* The program is correct on all architectures (including weakly ordered ones)

---

### 5. The lock is not redundant or decorative

There is:

* No single-threaded access pattern
* No read-only optimization
* No atomic type or lock-free guarantee

Removing the mutex would immediately introduce a data race.

---

### Final verdict

The mutex:

* Protects shared mutable state
* Prevents undefined behavior
* Is required by the C concurrency model

✅ **The mutual exclusion mechanism is NECESSARY.**
