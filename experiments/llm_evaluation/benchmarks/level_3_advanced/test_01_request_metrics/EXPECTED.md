## Expected Result

Lock: metrics_lock  
Status: SEMANTICALLY USELESS

## Justification

The shared counter is updated concurrently by multiple threads.
However, its value is never used to control program behavior or
enforce any correctness property.

The counter is used strictly for monitoring and logging purposes.
Minor inaccuracies caused by concurrent updates would not violate
any functional invariant.

The mutex therefore protects no correctness-critical invariant and
only adds synchronization overhead.
