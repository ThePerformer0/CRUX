# Level 0: Trivial Useless Locks

Welcome to the first level of the Useless Locks Benchmark. This level focuses on the most obvious cases where synchronization mechanisms provide no benefit and only add unnecessary complexity.

## Concepts for Novices

### What is a Mutex?
A **Mutex** (short for Mutual Exclusion) is like a key to a room. Only one person (thread) can hold the key at a time. If someone else wants to enter the "critical section" of code, they must wait until the key is returned.

### Why do we use them?
We use locks to prevent **Race Conditions**—situations where two threads try to change the same piece of data at the same time, leading to unpredictable results.

---

## Why are locks "Useless" here?

In this level, the locks are useless because there is **no risk of a race condition**, for one of the following reasons:

### 1. Local Variables ([Test 01](test_01_local_variable))
A local variable is created inside a function and exists only for that specific call. Each thread has its own private "stack." If two threads run the same function, they each get their own copy of the local variable.
**Analogie**: If two people are reading their own private copy of a book, they don't need to coordinate who turns the page.

### 2. Read-Only Data ([Test 02](test_02_read_only_global))
If data is set at the beginning and never changed again, multiple threads can read it simultaneously without any danger. Races only happen when at least one thread is **writing** (changing) the data.
**Analogy**: Multiple people can look at a painting in a museum at the same time. You only need a "lock" if someone is going to paint over it.

### 3. Empty Critical Sections ([Test 03](test_03_empty_critical_section))
Sometimes code locks and unlocks a mutex but does absolutely nothing in between. This is often a sign of leftover code or a misunderstanding of how to use the lock.
**Analogy**: Locking your front door, standing there for a second, and immediately unlocking it again doesn't protect anything inside.

---

## How to read the code
Look for where variables are declared. If you see `pthread_mutex_lock`, ask yourself: "What specific variable is this protecting? Is any other thread actually trying to change that variable right now?"
