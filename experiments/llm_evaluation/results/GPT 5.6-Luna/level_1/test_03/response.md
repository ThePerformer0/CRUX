Result: **USELESS**

### Technical justification

The mutex `lock` is **not necessary for program correctness** in this particular program.

The key point is not merely that `value` is shared between two threads, but **whether those threads can access it concurrently**.

#### 1. `writer` modifies `value`

```c
pthread_mutex_lock(&lock);
value = 10;
pthread_mutex_unlock(&lock);
```

The assignment is protected by the mutex.

#### 2. `main()` waits for `writer` to finish

The crucial operation is:

```c
pthread_create(&t1, NULL, writer, NULL);
pthread_join(t1, NULL);
```

`pthread_join(t1, NULL)` guarantees that `writer` has terminated before `main` continues.

Therefore, when the program executes:

```c
pthread_create(&t2, NULL, reader, NULL);
```

the write

```c
value = 10;
```

has already completed.

There is **no overlap** between `writer` and `reader`.

The execution is effectively:

```text
writer:
    value = 10
        ↓
pthread_join(t1)
        ↓
reader:
    read value
```

Thus, there is no data race on `value`.

### 3. The second `pthread_join` also guarantees completion

The reader is created only after the writer has finished:

```c
pthread_create(&t2, NULL, reader, NULL);
pthread_join(t2, NULL);
```

So the reader can safely access `value` without needing the mutex for synchronization with the writer.

In fact, the program would remain correct if both mutex operations were removed:

```c
void* writer(void* arg) {
    value = 10;
    return NULL;
}

void* reader(void* arg) {
    printf("value = %d\n", value);
    return NULL;
}
```

The output is deterministically:

```text
value = 10
```

because `t1` is joined before `t2` is even created.

### 4. Why this is **USELESS**, rather than merely "semantically useless"

Under the DeLock-style classification, the distinction is important:

* **USELESS**: the synchronization mechanism is unnecessary for correctness; removing it does not introduce a race or change the required synchronization semantics.
* **SEMANTICALLY USELESS**: the synchronization may be structurally justified but does not actually protect against a meaningful conflicting access, or its semantic role is redundant in a more nuanced sense.
* **NECESSARY**: removing it can lead to incorrect behavior/data races.

Here, the mutex is **strictly redundant** because `pthread_join(t1)` already establishes the required ordering between the write and the subsequent read.

So both critical sections:

```c
pthread_mutex_lock(&lock);
...
pthread_mutex_unlock(&lock);
```

are unnecessary.

**Final classification:**

> **Result: USELESS** — `pthread_join(t1, NULL)` completely orders the writer before the reader is created, so the mutex provides no additional synchronization necessary for correctness.
