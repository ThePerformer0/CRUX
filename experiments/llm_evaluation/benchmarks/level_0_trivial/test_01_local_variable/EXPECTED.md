## Expected Result

Lock: lock  
Status: USELESS

## Justification

The variable `local_counter` is local to the thread stack.
Each thread has its own private copy, and no shared state is accessed
inside the critical section.

Removing the mutex cannot introduce any data race or semantic violation.
