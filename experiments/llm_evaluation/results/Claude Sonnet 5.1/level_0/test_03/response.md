Result: **USELESS**

**Justification**

**1. No concurrent thread ever exists in this program.**
The entire translation unit contains exactly one thread of control: `main()`. There is no call to `pthread_create` (or any other thread-spawning primitive) anywhere in the program. This is a purely structural, call-graph-level fact — decidable by a simple reachability query on the LLVM IR (no `CallInst` targeting `pthread_create`/`pthread_create@plt` is reachable from `main`'s entry block, and there's no dynamic dispatch, function-pointer indirection, or dlopen'd code that could hide one).

Since a second thread can never come into existence, no other execution context can ever attempt to acquire `lock` while `main` holds it. The mutex therefore never actually arbitrates between competing threads — there is no "other side" for it to synchronize with.

**2. Formal framing (relevant to your SMT-based pipeline).**
The property you'd want to falsify is something like:
> ∃ an interleaving in which thread T₂ blocks on `pthread_mutex_lock(&lock)` while thread T₁ (main) holds it.

This is UNSAT *before* you even need a solver: the existential quantifier over T₂ is vacuous, because the predicate "a second thread exists" is false in every reachable program state. This is a strictly weaker (cheaper) obligation than the points-to/aliasing reasoning your SMT-path-validation stage normally has to do — no path feasibility or shared-memory-access modeling is needed, just call-graph reachability.

**3. Independent, secondary observation: the critical section is empty.**
Even bracketing the single-threadedness argument, there is zero code between `pthread_mutex_lock` and `pthread_mutex_unlock` — no shared/global memory is read or written. So even in a counterfactual world where a second thread existed, this particular lock/unlock pair would still guard nothing.

**4. On your "USELESS" vs "SEMANTICALLY USELESS" distinction.**
I don't have your CRUX taxonomy's exact definitions on hand, so let me be explicit about the distinction I'm drawing, so you can cross-check it against your paper's definitions:

- **USELESS** (as I'm using it here): provable false-by-reachability — no second thread can ever reach the lock, full stop. Decidable by call-graph analysis alone.
- **SEMANTICALLY USELESS**: I'd reserve this for the harder case — the lock *is* reachable by ≥2 threads (real concurrency exists), but static data-flow/points-to analysis shows the guarded region touches no shared/aliased state (e.g., a mutex protecting only a thread-local variable, or two threads that never actually alias the same object despite both locking).

Under that split, this example is the *stronger* and *cheaper-to-detect* case (category 1), not the harder semantic one — the concurrency precondition itself fails, so you never even get to the "what does the critical section touch" question. If your paper defines the two labels the other way around, this example would just swap labels; the underlying argument (no thread creation ⇒ no possible contention ⇒ safe to elide) doesn't change.

**5. Correctness of removal (observational equivalence).**
Removing both calls yields a program that is behaviorally identical under every possible scheduler: `pthread_mutex_lock`/`unlock` here have no observable side effect on program state (return values discarded, no shared memory touched, no signal/cancellation interaction). This is the standard soundness argument for flagging a lock as removable — replacing it with a no-op preserves semantics for all interleavings, trivially, since the interleaving space has exactly one thread in it.

**6. Practical note for your evaluation writeup.**
Worth keeping in your slide on real-world impact: even here, the call still costs a real atomic CAS (glibc's default non-recursive, non-error-checking mutex from `PTHREAD_MUTEX_INITIALIZER`) on both lock and unlock — pure overhead with zero synchronization benefit, which is exactly the kind of pattern your detector is meant to surface at scale (e.g., in libraries that lock defensively in code paths that turn out to be single-threaded in practice).