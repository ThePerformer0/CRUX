## Expected Result

Lock: config_lock  
Status: USELESS

## Justification

The configuration value is initialized once before any worker thread
is created.

After initialization, the variable is never modified.
All concurrent accesses are read-only.

The mutex does not protect any mutable shared state and does not
contribute to correctness.


This test models a realistic configuration module commonly found
in server and system software.

Although a mutex is used to protect the configuration value,
the value is only written during initialization and never modified
after threads are created.

The lock is therefore unnecessary.

