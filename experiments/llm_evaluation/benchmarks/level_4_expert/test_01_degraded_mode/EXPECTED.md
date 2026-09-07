## Expected Result

Lock: state_lock  
Status: SEMANTICALLY USELESS

## Justification

The degraded_mode flag is accessed concurrently and modified in a rare
execution path.

However, this flag does not influence any functional behavior of the
program. It only affects logging output.

No program invariant relies on the exact value of this flag.
Therefore, the mutex does not protect any correctness-critical state.
