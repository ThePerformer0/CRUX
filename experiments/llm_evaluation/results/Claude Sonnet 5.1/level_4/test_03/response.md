Result: **NECESSARY**

The program actually contains *two* independent mutexes with two different verdicts, so the analysis has to be done per-lock before giving the overall answer. I verified each claim empirically with ThreadSanitizer rather than relying purely on inspection.

## `manager_lock` (manager.c) — NECESSARY

It guards `audit_count`, a file-static `int` that both worker threads increment 50 times each (100 total non-atomic read‑modify‑write operations) with no other synchronization between them. That's a textbook data race if removed.

**Proof by removal:** I built a variant with `manager_lock` deleted (keeping `sub_lock` intact) and compiled with `-fsanitize=thread`:

```
WARNING: ThreadSanitizer: data race
  Read of size 4 ... manager_perform_task manager.c:7
  Previous write of size 4 ... manager_perform_task manager.c:7
  Location is global 'audit_count'
```
TSan flags a genuine race every run — this is undefined behavior under the C11/pthreads memory model regardless of what value ends up printed.

Interestingly, in the composed program the *observed* final count still came out correct (100, or 1,600,000 in a stress build) even without the lock. That's not evidence the lock is unneeded — it's incidental luck: `subsystem_increment()`'s own lock/unlock (for `sub_count`) happens to pace/synchronize the two threads' scheduling just enough to narrow the race window on this machine/compiler. To prove the underlying mechanism is real, I isolated a bare unprotected `counter++` race with no incidental throttling:
```
Expected: 4000000 | Got: 1587683
Expected: 4000000 | Got: 2433153
```
Massive lost updates. This confirms `manager_lock` is not "nice to have" — its absence produces real, standard-violating, platform/timing-dependent corruption; the composed program just wasn't unlucky enough to show it on this run. That's precisely the danger data races pose, and precisely why the lock is necessary rather than optional.

*(Minor aside: the lock/unlock pair inside `manager_get_audit()` specifically is technically redundant too — by the time `main()` calls it, both `pthread_join`s have already returned, and `pthread_join` establishes a happens-before edge, so no thread is concurrently touching `audit_count` at that point. It's harmless defensive consistency, not a correctness requirement. The two lock/unlock pairs *inside* `manager_perform_task`, however, are where the real necessity lives.)*

## `sub_lock` (subsystem.c) — SEMANTICALLY USELESS

`sub_count` is genuinely shared data — over the program's life it's touched from both worker threads — so at a glance `sub_lock` looks like legitimate protection. But tracing the call graph: `subsystem_increment()` has exactly **one** call site in the entire program, and it sits strictly *between* `pthread_mutex_lock(&manager_lock)` and `pthread_mutex_unlock(&manager_lock)` in `manager_perform_task()`. Since `manager_lock` is non-recursive and mutually exclusive, only one thread can ever be executing inside `manager_perform_task()` — and therefore inside `subsystem_increment()` — at any moment. `sub_lock` can never actually experience contention in this program; the outer lock has already fully subsumed it. (`subsystem_get_val()`, the only other consumer of `sub_lock`, is never called anywhere — it's dead code here.)

**Proof by removal:** I stripped `sub_lock` out of `subsystem_increment()` entirely, keeping `manager_lock` untouched, and re-ran under TSan:
```
Manager Audit Result: 100   (x5 runs, clean — zero race warnings)
```
Identical, correct results with zero synchronization warnings. Removing `sub_lock` changes nothing observable or provable about this program's correctness — that's the definition of it being redundant/subsumed rather than protective. It's not "useless" in the absolute sense (if `subsystem_increment()` were ever called concurrently from a context that *didn't* hold `manager_lock`, it would matter again — it's defensible as encapsulation in a standalone module), but **within this specific program's actual composition and call graph, it is semantically useless**: it does no synchronization work that isn't already guaranteed by the caller.

## Overall verdict

Because removing all locking (specifically `manager_lock`) provably reintroduces a data race, you cannot categorically call the locking in this program "useless" — hence **NECESSARY** as the top-line answer. But necessity is concentrated entirely in `manager_lock`'s two critical sections in `manager_perform_task`; `sub_lock` is a redundant nested lock that contributes nothing beyond what the coarser-grained `manager_lock` already guarantees, at the cost of extra (harmless but pointless) lock/unlock overhead on every call.