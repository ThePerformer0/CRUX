# Formal Problem Specification of CRUX
### Mathematical Modeling, Uselessness Definition, Anti-Patterns, and Lock-Site Graph
*Reference Document — CRUX (Concurrent Resource Unused eXtractor)*

---

## 1. Introduction and Goal

This document defines the **formal foundations** of the **CRUX** static analysis framework. It provides the mathematical definitions, logical formulas, the Lock Site Graph (**LSG**) semantics, and the classification rules for detecting useless synchronization locks in concurrent C programs.

---

## 2. Concurrent Program Model

A concurrent program $P$ is formally modeled as a 5-tuple:

$$P = \langle \mathcal{T},\; \mathcal{V},\; \mathcal{L},\; \mathcal{S},\; \mathcal{E} \rangle$$

### 2.1 Model Components

*   **$\mathcal{T} = \{t_1, t_2, \dots, t_n\}$**: The finite set of concurrent execution threads.
*   **$\mathcal{V} = \mathcal{V}_l \uplus \mathcal{V}_s$**: The set of memory variables, divided into two categories:
    *   $\mathcal{V}_l$ (**Local variables**): Private data accessed by a single thread (stack variables or registers), inaccessible to other threads.
    *   $\mathcal{V}_s$ (**Shared variables**): Common data (global variables or heap memory) accessible by multiple threads.
*   **$\mathcal{L} = \{\ell_1, \ell_2, \dots, \ell_m\}$**: The set of canonical synchronization locks (mutexes, spinlocks, rwlocks).
*   **$\mathcal{S} = \{s_1, s_2, \dots, s_k\}$**: The set of **static lock acquisition sites**, where each site $s_i$ corresponds to an acquire instruction in the code.
*   **$\mathcal{E} = \{e_1, e_2, \dots\}$**: The set of execution events (memory reads, memory writes, function calls, and synchronization operations).

---

## 3. Critical Section Definition

For a lock site $s \in \mathcal{S}$ associated with a lock primitive $\ell \in \mathcal{L}$, the **Critical Section** denoted $\mathcal{CS}(s)$ is the sequence of instructions executed under the protection of $\ell$ between its acquisition and its release:

$$\mathcal{CS}(s) = \left[ e_{\text{acquire}(s, \ell)},\; e_{\text{release}(s, \ell)} \right]$$

### 3.1 Memory Access Sets

For each site $s$, CRUX extracts:

1.  **Direct reads**: Variables read directly within the function between acquire and release.
2.  **Direct writes**: Variables modified directly within the function between acquire and release.
3.  **Function calls**: Functions called inside the critical section.
4.  **Transitive reads**: Direct reads combined with memory reads made by called functions (callees).
5.  **Transitive writes**: Direct writes combined with memory writes made by called functions (callees).
6.  **Total accessed variables**: The union of all read and written variables (direct and transitive).

### 3.2 Simple Example

```c
void update_counter(void) {
    pthread_mutex_lock(&lock);    // <--- Lock site s1 (acquire)

    /* Critical Section CS(s1) */
    global_count++;               // Protected memory access

    pthread_mutex_unlock(&lock);  // Release
}
```

*   **Lock site $s_1$**: The `pthread_mutex_lock(&lock)` instruction.
*   **Critical section $\mathcal{CS}(s_1)$**: The instructions executed between `lock` and `unlock`.

---

## 4. The Uselessness Predicate: $\text{Useless}(s)$

### 4.1 Definition by Behavioral Equivalence

A lock site $s \in \mathcal{S}$ is formally defined as **useless** if removing it from program $P$ preserves the exact same program behavior across all possible executions:

$$\text{Useless}(s) \iff \text{Behavior}(P) = \text{Behavior}(P \setminus \{s\})$$

*In other words: if deleting the `lock()` and `unlock()` instructions at site $s$ produces no observable change in program results or memory state under any execution, the lock is formally useless.*

### 4.2 The Three Fundamental Pillars (Sufficient Conditions)

To determine uselessness statically, CRUX decomposes $\text{Useless}(s)$ into **three sufficient pillars**:

*   **Pillar A (Temporal Solitude)**: Site $s$ runs only in a single-threaded context (e.g., initialization before thread creation, or teardown after `join`).
*   **Pillar B (No Memory Conflict)**: Variables accessed inside $\mathcal{CS}(s)$ face no concurrent conflicting writes by other threads.
*   **Pillar C (Redundancy)**: An outer enclosing parent lock $\ell_p$ is already held when $s$ is acquired, and it already protects all variables of $s$.

---

## 5. Definition of the 6 Anti-Patterns

### 5.1 Notation

*   $\mathcal{CS}(s)$: Variables accessed in the critical section of site $s$ (reads and writes).
*   $\mathcal{V}_l$: Thread-local variables (stack).
*   $\mathcal{V}_s$: Shared or global variables.
*   $\text{writes}(s)$: Set of modified variables inside the critical section.
*   $\text{held}(m, s)$: Mutex $m$ is already held in the *lockset* upon entering $s$.
*   $\text{calls}(s)$: Functions called inside the critical section.
*   $\text{indirect}(s)$: Presence of an unresolved indirect call (function pointer).
*   $\text{is\_single\_thread}(s)$: Executed in a single-threaded context (init or cleanup).

### 5.2 Logical Formulas and Explanations

| Anti-Pattern | Logical Formula | Simple Explanation |
| :--- | :--- | :--- |
| **`EMPTY_CS`** | $\mathcal{CS}(s) = \emptyset \land \text{calls}(s) = \emptyset \land \neg \text{indirect}(s)$ | The critical section contains no memory accesses and no function calls. |
| **`LOCAL_VARS`** | $\forall v \in \mathcal{CS}(s): v \in \mathcal{V}_l$ | Only accesses thread-local stack variables. |
| **`READ_ONLY`** | $\text{writes}(s) = \emptyset$ | Only performs reads, with no memory writes. |
| **`REDUNDANT`** | $\exists p : \text{held}(\text{mutex}(p), s)$ | An outer parent lock $p$ is already held upon acquiring $s$. |
| **`SINGLE_THREAD`** | $\text{is\_single\_thread}(s) = \text{true}$ | Executed in the sequential phase of the program. |
| **`THREAD_LOCAL`** | $\mathcal{CS}(s) \cap \mathcal{V}_s \neq \emptyset$ | Global variables without observed concurrent conflicts (*weighted confidence*). |

> **Treatment of `THREAD_LOCAL`**: In C, this pattern flags unshared global variables with no observed concurrent access conflict. CRUX assigns it a weighted confidence score (`LOW / MEDIUM`) recommending manual confirmation.

---

## 6. The Lock Site Graph (LSG): $G = (S, A)$

The **Lock Site Graph** is the multi-directed graph at the core of CRUX connecting all synchronization sites:

$$G = (S,\; A)$$

### 6.1 Edge Types

1.  **`SHARE` Edge (Data Conflict)**:
    *   $s_1 \xleftrightarrow{\text{SHARE}} s_2$: Sites $s_1$ and $s_2$ access the same shared variable, with at least one write.
    *   *Role*: Indicates a potential conflict between two memory accesses.

2.  **`HB` Edge (Happens-Before / Temporal Order)**:
    *   $s_1 \xrightarrow{\text{HB}} s_2$: Site $s_1$ always executes before $s_2$ (e.g., sequential initialization before parallel execution).
    *   *Role*: Resolves a `SHARE` conflict by execution order.

3.  **`NEST` Edge (Nesting / Redundancy)**:
    *   $s_1 \xrightarrow{\text{NEST}} s_2$: The lock at site $s_1$ already encloses the lock acquisition at site $s_2$.
    *   *Role*: Triggers the `REDUNDANT` pattern for $s_2$.

---

## 7. Summary

The formal framework of **CRUX** connects three levels of analysis:

1. **Local level**: The critical section $\mathcal{CS}(s)$ captures the exact variables accessed under lock protection.
2. **Global level**: The **LSG** graph $G = (S, A)$ models relationships between sites via real conflicts (`SHARE`), execution order (`HB`), and lock nesting (`NEST`).
3. **Decision level**: The **6 anti-patterns** translate the 3 fundamental pillars (Solitude, No-Conflict, Redundancy) into formal criteria to prove lock uselessness:

$$\text{Useless}(s) \iff \text{Behavior}(P) = \text{Behavior}(P \setminus \{s\})$$

This model provides a clean, rigorous theoretical foundation to mechanically prove the safe removal of useless locks in systems software.

