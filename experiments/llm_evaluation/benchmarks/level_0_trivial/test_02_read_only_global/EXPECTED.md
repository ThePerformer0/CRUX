## Expected Result

Lock: lock  
Status: USELESS

## Justification

The shared variable `global_value` is never modified.
All accesses are read-only, and no invariant depends on synchronized access.

The mutex does not protect any mutable shared state.
