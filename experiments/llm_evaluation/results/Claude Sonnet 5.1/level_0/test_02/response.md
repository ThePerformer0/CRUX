Result: **USELESS**

**Justification**

The mutex in this program protects a critical section whose only operation is:
```c
int v = global_value;
```
No thread ever *writes* to `global_value` anywhere in the concurrent portion of the program — the sole assignment is the static initializer `int global_value = 42;`, which executes before `main()` runs and therefore strictly before either `pthread_create()` call.

**Why this is a data-race-free access pattern by construction**

Under the C11 / POSIX threads memory model, a data race requires two *conflicting* concurrent accesses to the same memory location, where "conflicting" means at least one of them is a write, and there is no happens-before ordering between them. Here:

1. **No write exists in the concurrent region.** Both `worker()` invocations only read `global_value`. Concurrent reads with zero concurrent writers can never race — there is no conflicting pair of operations to reason about, regardless of scheduling or interleaving.
2. **Visibility is already guaranteed without the lock.** `pthread_create()` establishes a happens-before edge from everything sequenced before the call in the creating thread to the start of the new thread's execution. Since the initialization of `global_value` happens-before both `pthread_create()` calls in `main()`, POSIX guarantees both worker threads observe the fully-initialized value `42` — no additional synchronization (mutex, atomic, or memory barrier) is needed to establish that visibility.
3. **No observable behavior depends on the lock.** Removing `pthread_mutex_lock`/`unlock` entirely would not change the possible outputs of the program in any execution: both threads always print `value = 42`, and the only nondeterminism (interleaving of the two `printf` calls, which are outside the critical section anyway) is unaffected by the lock's presence.

**Why this is "USELESS" rather than "SEMANTICALLY USELESS"**

This distinction matters for a detector like the one in your CRUX work, since it maps to two very different analysis costs:

- **USELESS** (this case): provable purely from a syntactic/alias write-set analysis — there is no write to the guarded location anywhere in the concurrent scope, full stop. No value-level or path-feasibility reasoning (e.g., an SMT solver proving two branches can't co-occur, or that a racing write is idempotent) is required. A simple def-use/write-set analysis over the LLVM IR (find all store instructions targeting the memory location aliased by `&global_value`, confirm the set is empty in reachable-after-`pthread_create` code) is sufficient to flag it.
- **SEMANTICALLY USELESS** would apply to a strictly harder case: a genuine race exists at the memory-model level (a write *does* execute concurrently with other accesses, unordered by happens-before), but deeper semantic reasoning shows the race is inconsequential — e.g., the racing write always stores the same value that's already there, or the interleaving where the race would produce a different observable outcome is infeasible given program invariants. That class requires path-sensitive/value-flow reasoning (your Z3-backed path validation) to establish, precisely because a naive race detector would flag it as a true positive.
- **NECESSARY** would require at least one concurrent write to `global_value` after thread creation with no ordering relative to the reads — not present here.

So for your classification scheme, this program is a clean instance of the *first, cheapest* category: a lock over a value that is write-once-before-concurrency-begins, or equivalently "effectively `const` from the perspective of the parallel region." It should be detectable by your tool without needing the SMT layer at all — a good regression/unit-test case for the syntactic pass specifically, to make sure it doesn't get incorrectly escalated to the semantic pass.