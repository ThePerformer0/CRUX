Result: **NECESSARY**

The program contains **three lock acquisition sites**, and they do not all have the same necessity. The important distinction is between the `manager_lock` protecting `audit_count` and the `sub_lock` protecting `sub_count`.

### 1. `manager_lock` in `manager_perform_task()` — **NECESSARY**

```c
pthread_mutex_lock(&manager_lock);

subsystem_increment();
audit_count++;

pthread_mutex_unlock(&manager_lock);
```

Two worker threads execute:

```c
manager_perform_task();
```

50 times each, so `audit_count++` is concurrently executed by both threads.

Without `manager_lock`, the increment:

```c
audit_count++;
```

is a read-modify-write operation. The two threads can interleave their accesses:

```text
Thread 1: read audit_count = 10
Thread 2: read audit_count = 10
Thread 1: write 11
Thread 2: write 11
```

The expected final value is **100**, but without synchronization the program has a data race on `audit_count`, resulting in undefined behavior under the C memory model.

Therefore:

**`manager_lock` around `manager_perform_task()` is strictly necessary for correctness.**

---

### 2. `sub_lock` in `subsystem_increment()` — **logically redundant in this particular program**

```c
void subsystem_increment(void) {
    pthread_mutex_lock(&sub_lock);
    sub_count++;
    pthread_mutex_unlock(&sub_lock);
}
```

At first glance, this lock is necessary because `sub_count++` is also accessed by two worker threads.

However, every call to `subsystem_increment()` currently occurs inside:

```c
manager_lock
    ↓
subsystem_increment()
    ↓
sub_lock
```

The `manager_lock` already guarantees that only one worker can execute `subsystem_increment()` at a time.

Consequently, in this particular program:

```text
Thread 1                         Thread 2

manager_lock ──────┐
                   │
sub_lock           │
sub_count++        │
sub_unlock         │
                   │
manager_unlock ────┘

                                manager_lock
                                    ↓
                                sub_lock
                                sub_count++
                                ...
```

There is no concurrent access to `sub_count` through `subsystem_increment()`.

Thus, **the `sub_lock` is redundant given the current calling structure**. Removing it would not introduce a race in this program, because `manager_lock` already serializes all calls.

However, there is an important semantic/API distinction: `subsystem_increment()` is a public subsystem function. If another future caller invokes it concurrently **without** holding `manager_lock`, `sub_lock` would become necessary. So its redundancy is relative to the current program/call graph, not necessarily to the subsystem implementation as a reusable component.

---

### 3. `manager_lock` in `manager_get_audit()` — **unnecessary in this exact execution**

```c
int manager_get_audit(void) {
    pthread_mutex_lock(&manager_lock);
    int c = audit_count;
    pthread_mutex_unlock(&manager_lock);
    return c;
}
```

In `main()`:

```c
pthread_join(t1, NULL);
pthread_join(t2, NULL);

printf("Manager Audit Result: %d\n", manager_get_audit());
```

Both `pthread_join()` calls complete before `manager_get_audit()` is called.

Therefore, there are no worker threads still modifying `audit_count` when it is read.

The lock around:

```c
int c = audit_count;
```

is consequently **not required for correctness in this particular program**.

It would become necessary if `manager_get_audit()` could be called concurrently with `manager_perform_task()`.

---

### Final classification

| Lock site                                 | Classification                          | Reason                                           |
| ----------------------------------------- | --------------------------------------- | ------------------------------------------------ |
| `manager_lock` → `manager_perform_task()` | **NECESSARY**                           | Protects concurrent `audit_count++`              |
| `sub_lock` → `subsystem_increment()`      | **USELESS / redundant in this program** | Already serialized by `manager_lock`             |
| `manager_lock` → `manager_get_audit()`    | **USELESS in this execution**           | `pthread_join()` guarantees no concurrent writer |

### Why the overall result is **NECESSARY**

If the question is whether **the locks as a whole are strictly necessary for program correctness**, the answer is **NECESSARY**, because removing the `manager_lock` from `manager_perform_task()` introduces a data race on `audit_count` and can make the final result incorrect.

The interesting DeLock finding is therefore:

> **The program contains a necessary outer lock (`manager_lock`) and a redundant nested lock (`sub_lock`).**

The `sub_lock` is a particularly good example of a **redundant lock caused by higher-level synchronization**: the subsystem protects `sub_count` independently, but the caller has already established mutual exclusion before entering the subsystem.
