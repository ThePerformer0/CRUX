**Result: USELESS**

### Technical justification

The mutex is **not required for program correctness** in this program.

1. **`shared_value` is initialized before any threads are created**

   ```c
   shared_value = 42;

   pthread_create(&t1, NULL, reader, NULL);
   pthread_create(&t2, NULL, reader, NULL);
   ```

   The write of `42` happens in the main thread **before** `t1` and `t2` are created. Therefore, both reader threads start after the initialization has occurred.

2. **The reader threads never modify `shared_value`**

   ```c
   int v = shared_value;
   ```

   Both threads only perform a read. There is no concurrent write to `shared_value`.

3. **Consequently, there is no data race**

   A data race would require conflicting accesses from different threads, where at least one access is a write. Here the accesses after thread creation are:

   ```text
   main:   shared_value = 42     ← happens before thread creation
                                  ↓
   t1:     read shared_value
   t2:     read shared_value
   ```

   The two reads are compatible and cannot race with each other.

4. **The mutex does not provide any additional correctness guarantee**

   The critical section is:

   ```c
   pthread_mutex_lock(&lock);
   int v = shared_value;
   pthread_mutex_unlock(&lock);
   ```

   Since `shared_value` is immutable for the lifetime of the worker threads, serialization of the reads is unnecessary. The threads could simply execute:

   ```c
   int v = shared_value;
   ```

   and the program would remain correct.

5. **What about `printf`?**

   The `printf` occurs **after the mutex is released**:

   ```c
   pthread_mutex_unlock(&lock);
   printf("read: %d\n", v);
   ```

   Therefore, the mutex does not even serialize the output operations. In any case, both threads print the value `42`.

### Conclusion

The lock is **logically useless** because removing it does not change the program's correctness or observable result:

```c
void* reader(void* arg) {
    int v = shared_value;
    printf("read: %d\n", v);
    return NULL;
}
```

Both threads will read `42`, and the program remains free of data races.

**Classification: `USELESS`** — the lock protects a read-only value after its initialization, so there is no concurrent conflicting access that requires synchronization.
