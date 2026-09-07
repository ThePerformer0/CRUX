## Expected Result

Lock: config_mutex
Status: USELESS

## Justification

While the program uses multiple threads and one thread ("the leader") writes to the shared configuration, the access pattern is strictly sequentialized by a `pthread_barrier`.

1. The leader thread initializes `global_config` before reaching the barrier.
2. No other thread attempts to read `global_config` until after the barrier.
3. Once the barrier is passed, the configuration is never modified again.

The mutex `config_mutex` is redundant because the barrier already guarantees that the write happens before all reads (Happens-Before relationship), and there are no concurrent writes.
