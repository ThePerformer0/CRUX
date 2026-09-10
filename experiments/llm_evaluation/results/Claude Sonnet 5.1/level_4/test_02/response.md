Result: SEMANTICALLY USELESS

**Scope of the verdict:** This program contains two distinct mutexes — `dispatch_lock` in `dispatcher.c` and `observer_lock` in `observer.c`. They deserve separate treatment, because they are not equally justified. The interesting one — and the one the "SEMANTICALLY USELESS" verdict applies to — is `dispatch_lock`. `observer_lock`, by contrast, is genuinely necessary. I'll walk through both.

## `dispatch_lock` — protects `g_observer`, but never against a reachable race

`dispatch_lock` is acquired in two places: `dispatch_register_observer` (a write to `g_observer`) and `dispatch_event` (a read of `g_observer`, plus invocation of the callback). On paper this looks like a textbook reader/writer scenario over shared global state accessed from multiple threads — exactly the kind of thing that *should* need a lock.

But look at the actual call graph in `main.c`:

```c
observer_init();
dispatch_register_observer(observer_callback);   // single write, main thread

pthread_create(&t1, NULL, worker, NULL);
pthread_create(&t2, NULL, worker, NULL);
```

- `dispatch_register_observer` is called **exactly once**, synchronously, on the main thread, **before either worker thread is created**.
- Neither `worker()` nor anything it calls ever calls `dispatch_register_observer` again. The only thing the workers ever do to `g_observer` is *read* it, inside `dispatch_event`.

This matters because `pthread_create()` establishes a happens-before edge: per POSIX's memory synchronization rules (and the C11 thread model), all memory writes performed by a thread before it calls `pthread_create()` are guaranteed visible to the newly created thread once it begins executing. So the write `g_observer = cb` is guaranteed to happen-before *every* read of `g_observer` performed by `t1` or `t2` — with no lock required to establish that ordering. It's already established structurally by thread creation.

Once you subtract that write, the only remaining accesses to `g_observer` are the concurrent reads in `dispatch_event`, performed by `t1` and `t2`. Concurrent reads of the same location, with no interleaved write, are never a data race — mutual exclusion is not needed to make reads-only access safe.

So: `dispatch_lock` protects a genuine piece of shared mutable state (this isn't a nonsensical "lock around a local variable" case), but *given the specific way this program actually drives it* — register-then-spawn, never re-register, workers only read — the race it guards against never becomes reachable. If you deleted `dispatch_lock` entirely from both functions, this program's behavior would be identical under every possible thread interleaving. That's precisely what makes it **semantically** useless rather than **logically/trivially** useless: the uselessness follows from the program's control-flow semantics (ordering + read-only usage), not from the lock being a syntactic no-op on non-shared data. Had `main.c` instead allowed re-registration from another thread, or interleaved `dispatch_register_observer` calls with dispatch after thread creation, this same lock would become genuinely necessary — the lock's *design* isn't wrong, its *deployment* here is unexercised.

(Side note: holding `dispatch_lock` across the callback invocation `g_observer(event)` is also a bit of a design smell independent of this analysis — serializing calls into arbitrary external code while holding a lock risks deadlock if the callback ever tries to re-enter the dispatcher, and needlessly serializes unrelated work. It happens to have a side effect discussed next.)

## `observer_lock` — protects `observer_count`, and this one is real

`observer_callback` performs `observer_count++`, a non-atomic read-modify-write, and it's invoked from `dispatch_event`, which is called 10 times each by both `t1` and `t2` concurrently. Without synchronization, two threads racing on `observer_count++` is a textbook lost-update data race (undefined behavior in C, and in practice a wrong final count).

You could point out that, *as currently composed*, `dispatch_lock` is held for the full duration of the callback call in `dispatch_event`, so calls into `observer_callback` end up serialized as an incidental side effect — meaning `observer_lock` never actually experiences contention in this exact build. But that's a fragile, undocumented coupling between two unrelated modules: `observer.c` has no contract guaranteeing its callback is invoked under an external lock, and nothing in `observer.h` documents such a requirement. A perfectly reasonable (arguably preferable) refactor of `dispatch_event` — releasing `dispatch_lock` before invoking the callback, to avoid the deadlock/serialization risk noted above — would immediately expose a real race on `observer_count` if `observer_lock` weren't there. Because the observer module's correctness needs to hold on its own terms as a reusable, independently-callable API, `observer_lock` is **necessary**.

## Summary

| Lock | Verdict | Reason |
|---|---|---|
| `dispatch_lock` | Semantically useless | Protects `g_observer`, but the happens-before edge from `pthread_create` plus the register-once-before-spawn / read-only-after usage pattern means the guarded race is never reachable in this program |
| `observer_lock` | Necessary | Protects a genuine concurrent read-modify-write (`observer_count++`) that two threads can reach; correctness shouldn't depend on an incidental, undocumented side effect of `dispatch_lock`'s scope |

If forced to a single answer for the featured lock in `dispatcher.c` (the file the exercise centers on), it's **SEMANTICALLY USELESS**: correct-looking, protecting real shared state, but never actually preventing a reachable race given how `main.c` drives the program.