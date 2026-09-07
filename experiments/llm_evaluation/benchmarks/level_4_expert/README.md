# Level 4: Expert Systems Reasoning

At the Expert level, we look at the interaction between different modules and software layers. The "Uselessness" of a lock often comes from a guarantee provided by a different part of the system.

## Concepts for Novices

### Callbacks and Function Pointers
Instead of calling a function directly, code can "register" a function to be called later (a callback). This indirection makes it harder to see who is calling what and when.

### Distributed Invariants
An invariant is a rule that must always be true. A "distributed" invariant is a rule that involves multiple modules working together. For example: "Module A will only call Module B while holding Lock X."

---

## Test Breakdown

### 1. Degraded Mode Toggle ([Test 01](test_01_degraded_mode))
A flag indicates if the server is in a "degraded" state (running slowly to save resources). Because this flag only changes how the logger behaves and doesn't affect the actual logic of processing data, it's semantically useless to protect it perfectly.

### 2. Callback Serialization ([Test 02](test_02_callback_chain))
An event dispatcher calls a series of "observer" functions. The dispatcher holds a lock while doing this. If an observer also has its own internal lock, it's redundant—the dispatcher has already guaranteed that only one thread is executing the observer at a time.

### 3. Hierarchical Locking ([Test 03](test_03_hierarchical_contract))
Systems are often organized like a tree. If a "Parent" module already holds a lock to protect a whole "Branch," a "Child" module further down that branch doesn't need its own private lock. The safety is inherited from above.

---

## Final Lesson
The most efficient lock is the one that isn't there. By designing your system with clear "ownership" of data and well-defined "phases" of execution, you can write code that is both thread-safe and incredibly fast.
