## Expected Result

Lock: monitor_lock
Status: SEMANTICALLY USELESS

## Justification

The `monitor_lock` protects a timestamp (`last_activity`) updated by high-frequency heartbeat signals.

In the context of health monitoring:
1. The exact sub-second timing of a heartbeat update is rarely critical.
2. If two threads update the timestamp simultaneously, the resulting value will still be a very recent timestamp (at most off by the duration of the race, which is microseconds).
3. The heartbeat's semantic contract (detecting if a process is "alive" within a window of seconds) is not violated by minor 1-second jitter or lost updates.

Since no functional invariant or correctness property depends on the absolute precision of this timestamp, the mutex is semantically useless and only introduces performance bottlenecks in a high-frequency path.
