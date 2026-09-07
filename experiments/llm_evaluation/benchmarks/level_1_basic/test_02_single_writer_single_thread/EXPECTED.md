## Expected Result

Lock: lock  
Status: USELESS

## Justification

Although the variable is global and modified, the modification
is performed by a single thread only.

There is no concurrent access to the shared variable.
