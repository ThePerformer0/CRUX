**Result: NECESSARY**

**Justification:**

The mutex `cache_lock` is **not useless**—it is genuinely required for correctness in this program.

Here’s why, step by step:

---

### 1. Shared mutable state exists

The following variables in `cache.c` are:

```c
static int cached_value;
static char cached_key[64];
```

They are:

* **Global (static)**
* **Writable**
* **Accessed by multiple threads**

This already puts us squarely in *data race territory* if no synchronization is used.

---

### 2. Writes are not atomic as a whole

Even though:

* Writing an `int` may be atomic on many platforms
* `strncpy` + `cached_value = value` is **not atomic as a combined operation**

Without a mutex, another thread could observe:

* A partially updated `cached_key`
* Or a key/value mismatch (new key with old value, or vice versa)

That’s a classic **torn state** problem.

---

### 3. Concurrent reads + writes must be synchronized

`cache_get()` does:

```c
strcmp(cached_key, key)
```

If another thread is concurrently executing:

```c
strncpy(cached_key, key, 63);
```

Then:

* `strcmp` may read `cached_key` while it is being modified
* This is **undefined behavior** under the C memory model

The mutex prevents exactly this scenario.

---

### 4. “All threads write the same value” does NOT remove the need for a mutex

It’s tempting to think:

> “All threads write the same key and same value (9999), so locking is pointless.”

But this is **not a valid optimization** in C concurrency terms:

* The C standard does **not** allow unsynchronized concurrent writes, even if values are identical
* Data races are UB *regardless of intent or apparent determinism*

Correctness must be defined by the language memory model, not by observed outcomes.

---

### 5. The mutex establishes happens-before guarantees

The lock ensures:

* Writes to `cached_key` and `cached_value` **happen-before**
* Any subsequent read in `cache_get()`

Without it, the final `printf` could legally print:

* `-1`
* Or any stale value
* Or crash in extreme cases

---

### Final verdict

The mutex:

* Protects real shared state
* Prevents data races
* Enforces memory visibility
* Avoids undefined behavior

✅ **The mutual exclusion mechanism is NECESSARY.**
