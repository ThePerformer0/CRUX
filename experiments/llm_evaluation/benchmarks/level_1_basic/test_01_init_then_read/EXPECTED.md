## Expected Result

Lock: lock  
Status: USELESS

## Justification

The shared variable is written exactly once during the initialization phase,
before any thread is created.

All subsequent accesses are read-only and concurrent.
No data race or invariant violation can occur.
