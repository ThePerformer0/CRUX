## Expected Result

Lock: lock  
Status: USELESS

## Justification

Thread execution order is explicitly enforced by pthread_join.
No concurrent access to the shared variable occurs.

The mutex does not contribute to correctness.
