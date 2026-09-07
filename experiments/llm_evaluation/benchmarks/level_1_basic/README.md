# Level 1: Basic Concurrency Patterns

Level 1 introduces actual multithreaded execution. Here, threads are explicitly created and interact with shared data, but the timing of these interactions makes the locks redundant.

## Concepts for Novices

### The Thread Life Cycle
Threads are created using `pthread_create` and cleaned up with `pthread_join`. `join` is a "blocking" call: the main program stops and waits until the target thread has completely finished its work.

### Happening-Before
In programming, we say event A "happens-before" event B if the system guarantees that A will always finish before B starts. If a setup step happens-before a thread starts, that thread doesn't need a lock to see the results of the setup.

---

## Test Breakdown

### 1. Initialization then Read ([Test 01](test_01_init_then_read))
The main thread sets up a value *before* it starts any other threads. Since the value never changes after that, the worker threads don't need a lock to read it safely.

### 2. Single Writer, Single Thread ([Test 02](test_02_single_writer_single_thread))
If there is only one worker thread in the entire program, it can't "race" against anyone. It's essentially a single-threaded program running in a separate context. Locks only make sense when there are at least two entities competing for the same resource.

### 3. Thread Join Ordering ([Test 03](test_03_thread_join_ordering))
Similar to initialization, if one thread finishes its work and is "joined" by the main thread, the main thread can safely access the data produced by that thread. The `pthread_join` act acts as a synchronization point.

---

## Summary for Beginners
A lock is only needed when **two or more threads** are active at the same time and **at least one of them** is modifying the data. If the "writing" happens before the "reading" starts (or after it ends), you don't need a lock.
