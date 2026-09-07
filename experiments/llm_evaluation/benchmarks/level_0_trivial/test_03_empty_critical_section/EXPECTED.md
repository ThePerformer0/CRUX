## Expected Result

Lock: lock  
Status: USELESS

## Justification

The critical section is empty.
The mutex does not protect any code, data, or invariant.

Removing the mutex has no effect on program behavior.
