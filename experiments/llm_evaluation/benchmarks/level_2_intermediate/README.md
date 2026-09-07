# Level 2: Intermediate Architecture

Level 2 moves away from simple scripts into "real-world" software architecture, where code is split across multiple files (`.c` and `.h`). It also introduces more complex synchronization tools.

## Concepts for Novices

### Multi-File Projects
In C, we use header files (`.h`) to share function signatures and constants, while the logic lives in source files (`.c`). This encapsulation often leads to "Module Locks"—a lock hidden inside a module to protect its internal state.

### Barriers (`pthread_barrier_t`)
A barrier is a synchronization point where all threads must "meet" before any of them can proceed. It's like a starting gate at a race; nobody moves until every horse is in position.

---

## Test Breakdown

### 1. Configuration Module ([Test 01](test_01_config_module))
This models a server config. The values are loaded from a "file" (simulated) at startup. Because the configuration is "read-only" for all worker threads after startup, the internal module lock is extra weight.

### 2. Barrier Synchronization ([Test 02](test_02_barrier_sync))
One thread prepares data while others wait at a barrier. Once the barrier is released, the data is ready. Beginners often add a lock "just in case," but the barrier already ensures that the setup is finished for everyone.

### 3. Legacy Constants ([Test 03](test_03_legacy_refactor))
In long-lived projects, data that used to be variable (and needed a lock) sometimes becomes static or constant over time. If a variable is marked `const`, it can never change, making its associated lock a "ghost" of a previous requirement.

---

## Pro-Tip for Systems Programming
When looking at multi-file code, track the "lifecycle" of the data. Who creates it? Who changes it? When is it considered "finished"? If modification only happens in a well-defined "setup phase," the "execution phase" can often run lock-free.
