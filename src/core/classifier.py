"""Crux Anti-Pattern Classifier.

Evaluates LockSite nodes in the Lock Site Graph against the 6 anti-patterns:
- EMPTY_CS: critical section contains no memory operations.
- LOCAL_VARS: critical section operates strictly on stack-local variables (alloca).
- READ_ONLY: critical section only reads shared variables, with zero global writes in the program.
- REDUNDANT: lock is acquired under an enclosing parent lock covering the same variables.
- SINGLE_THREAD: lock is acquired in a single-threaded execution context.
- THREAD_LOCAL: variables are thread-local and unshared across threads.

Enforces strict safety guards (indirect calls, cond_wait, recursive mutexes).
"""
