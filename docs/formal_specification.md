# Formal Problem Specification of CRUX
### Mathematical Modeling, Uselessness Definition, Anti-Patterns, and Lock-Site Graph (LSG)
*Reference Specification Document — CRUX (Concurrent Resource Unused eXtractor)*

---

## 1. Introduction and Objective

This document formalizes the theoretical foundations, mathematical modeling, and inference rules of the **CRUX** static analysis framework.

CRUX targets the sound identification of **superfluous synchronization operations** (mutexes, spinlocks, read-write locks) in multi-threaded C/C++ systems software. Its decision logic operates under the foundational principle of **Presumption of Intent**: *under the slightest semantic ambiguity, synchronization is conservatively preserved*.

---

## 2. Concurrent Program Execution Model

A concurrent program $P$ is formally modeled as a 5-tuple:

$$P = \langle \mathcal{T},\; \mathcal{V},\; \mathcal{L},\; \mathcal{S},\; \mathcal{E} \rangle$$

### 2.1 Model Components

*   **$\mathcal{T} = \{t_1, t_2, \dots, t_n\}$**: The finite set of execution threads.
*   **$\mathcal{V} = \mathcal{V}_l \uplus \mathcal{V}_s$**: The disjoint universe of memory variables, partitioned into:
    *   $\mathcal{V}_l$ (**Thread-local stack variables**): Private memory allocated on thread execution stacks via LLVM `alloca` instructions, inaccessible to other threads.
    *   $\mathcal{V}_s$ (**Shared variables**): Global memory variables (`@var`) or heap-allocated structures accessible across multiple threads.
*   **$\mathcal{L} = \{\ell_1, \ell_2, \dots, \ell_m\}$**: The set of canonical synchronization primitives (POSIX mutexes, spinlocks, read-write locks, kernel raw locks, DBMS lightweight locks).
*   **$\mathcal{S} = \{s_1, s_2, \dots, s_k\}$**: The set of **static lock acquisition sites** in the program code.
*   **$\mathcal{E} = \{e_1, e_2, \dots\}$**: The set of program execution events (memory reads `load`, memory writes `store`, function calls `call`, and synchronization operations `lock` / `unlock`).

---

## 3. Critical Section Delineation & Access Sets

For each lock acquisition site $s \in \mathcal{S}$ associated with a synchronization primitive $\ell \in \mathcal{L}$, the acquisition instruction delineates, together with its matching release instruction, a **critical section** denoted $\mathcal{CS}(s)$:

$$\mathcal{CS}(s) = \left[ e_{\text{acquire}(s, \ell)},\; e_{\text{release}(s, \ell)} \right]$$

### 3.1 Memory Access Sets

For each site $s \in \mathcal{S}$, CRUX extracts intra-procedurally and transitively along the Call Graph:

1.  **$\text{reads}(s)$**: The set of memory variables read (`load` or `memcpy` source) within $\mathcal{CS}(s)$ (directly or via callees).
2.  **$\text{writes}(s)$**: The set of memory variables modified (`store` or `memcpy` destination) within $\mathcal{CS}(s)$ (directly or via callees).
3.  **$\text{calls}(\mathcal{CS}(s))$**: The set of subroutines and functions invoked inside $\mathcal{CS}(s)$.
4.  **$\text{Vars}(\mathcal{CS}(s))$**: The total set of variables accessed within the critical section:

$$\text{Vars}(\mathcal{CS}(s)) = \text{reads}(s) \cup \text{writes}(s)$$

---

## 4. When is a Lock Considered Superfluous?

### 4.1 The Verification Challenge

In concurrent programming, detecting a **missing lock** is a counterexample search problem: finding a single concurrent race trace suffices to identify a bug.

In contrast, proving that an **existing lock is useless** is a universal verification problem: the analyzer must guarantee that across **all possible execution paths and thread interleavings**, removing the lock will never cause a data race or change the intended observable behavior of the program.

### 4.2 Presumption of Intent & Soundness Guarantee

Developers generally add synchronization for a reason. Therefore, CRUX operates under the conservative principle of **Presumption of Intent**:
* A lock is declared useless **only if** its critical section strictly matches one of the six structural patterns described below, proving that the lock provides no correctness benefit.
* If there is **any semantic ambiguity** (such as dynamic function pointers, condition variables, or interaction with hardware interrupts), CRUX errs on the side of caution and **systematically preserves the lock**.

---

## 5. The Six Structural Anti-Patterns of Useless Locks

A lock site $s \in \mathcal{S}$ is classified as superfluous if its critical section $\mathcal{CS}(s)$ strictly satisfies one of the following six formal patterns:

### 1. Empty Critical Section (`EMPTY_CS`)
The critical section contains zero memory operations and invokes no external functions:

$$\text{Vars}(\mathcal{CS}(s)) = \emptyset \quad \land \quad \text{calls}(\mathcal{CS}(s)) = \emptyset$$

*Remediation:* Safely elide the `lock` and `unlock` instructions.

### 2. Thread-Confined Local Variables (`LOCAL_VARS`)
All variables accessed within $\mathcal{CS}(s)$ are strictly allocated on the local thread execution stack ($\mathcal{V}_l$ via LLVM `alloca`), rendering them private by lexical construction:

$$\forall v \in \text{Vars}(\mathcal{CS}(s)), \quad v \in \mathcal{V}_l$$

*Remediation:* Safely elide the synchronization operations.

### 3. Pure Read-Only Accesses (`READ_ONLY`)
The critical section executes solely memory reads, and **no other site in the entire program ever writes to these variables**:

$$\text{writes}(s) = \emptyset \quad \land \quad \forall s' \in \mathcal{S} \setminus \{s\},\; \text{writes}(s') \cap \text{reads}(s) = \emptyset$$

*Remediation:* Elide the exclusive lock or convert to a lightweight shared reader lock (`pthread_rwlock_rdlock`).

### 4. Redundant Nested Lock (`REDUNDANT`)
A parent lock $p$ is already actively held in the incoming lockset upon reaching $s$, and $p$ protects a superset of the variables accessed by child lock $s$:

$$\text{held}(\text{mutex}(p), s) \quad \land \quad \text{Vars}(\mathcal{CS}(s)) \subseteq \text{Vars}(\mathcal{CS}(p))$$

*Remediation:* Safely elide the inner child lock acquisition and release.

### 5. Single-Threaded Phase (`SINGLE_THREAD`)
The lock executes exclusively during the sequential execution phases of the program (prior to parallel thread creation or following complete thread joining):

$$\forall e \in \mathcal{CS}(s), \quad \text{active\_threads}(e) = \{t_{\text{main}}\}$$

*Remediation:* Elide initialization/teardown locking.

### 6. Uncontested Thread-Confined Data (`THREAD_LOCAL`)
Variables residing in shared memory ($\mathcal{V}_s$) or heap allocations accessed by thread $t$ in $\mathcal{CS}(s)$ are never accessed by any concurrent thread $t' \neq t$:

$$\forall v \in (\text{Vars}(\mathcal{CS}(s)) \cap \mathcal{V}_s), \quad \forall t' \in \mathcal{T} \setminus \{t\}, \quad v \notin \text{Vars}(t')$$

*Distinction between `LOCAL_VARS` and `THREAD_LOCAL`:* Under `LOCAL_VARS`, variables reside on the thread's local execution stack (LLVM `alloca`), making them private by lexical structure. Under `THREAD_LOCAL`, data reside in global memory ($\mathcal{V}_s$) as explicit thread-local storage (`__thread`, `_Thread_local`, or LLVM IR `thread_local`) or on the heap without observed concurrent accesses, validated via inter-procedural alias and call graph analysis.

---

## 6. The Lock Site Graph (LSG): $G = (\mathcal{S}, \mathcal{A})$

The **Lock Site Graph** is the central relational data structure synthesized by CRUX to model multi-threaded interactions across all synchronization sites:

$$G = (\mathcal{S},\; \mathcal{A})$$

*   **Vertices ($\mathcal{S}$):** The static lock acquisition sites in the codebase.
*   **Edges ($\mathcal{A}$):** Directed and undirected edges modeling three fundamental concurrency relationships:

### 6.1 The Three Edge Relationships

1.  **$\textsc{share}$ Edge (Data Conflict):** An undirected edge connecting two sites $s_i$ and $s_j$ whose critical sections access the same shared variable ($v \in \mathcal{V}_s$), with at least one access being a write (`store`). This identifies potential data race locations if unsynchronized.
2.  **$\textsc{nest}$ Edge (Lock Nesting):** A directed edge $s_p \to s_c$ indicating that child lock $s_c$ is acquired while parent lock $s_p$ is already actively held. This indicates candidate locks subsumed by an outer lock (`REDUNDANT`).
3.  **$\textsc{hb}$ Edge (Happens-Before Ordering):** A directed edge $s_1 \to s_2$ capturing static execution ordering (e.g., initialization before thread creation, or teardown after `pthread_join`). This guarantees that two accesses cannot occur concurrently, resolving apparent data sharing conflicts.

---

## 7. Decision Engine & Soundness Verification

### 7.1 Strict Soundness Guards (Presumption of Intent)

To guarantee that lock elision never introduces concurrency bugs, CRUX enforces four unconditional safety guards:

1.  **Indirect Function Call Guard:** If $\mathcal{CS}(s)$ contains an unresolved function pointer call (`indirect(s)`), CRUX conservatively assumes the target may mutate shared state and preserves the lock.
2.  **Condition Variable Synchronization Guard:** If a lock is associated with condition variable synchronization (`pthread_cond_wait`, `pthread_cond_signal`), it is unconditionally preserved to prevent missed wake-ups or broken wait predicates.
3.  **Asymmetric & Escaping Lock Guard:** If a lock acquisition site lacks a statically determinable release within the CFG (or escapes the local lexical scope across threads), it is preserved.
4.  **Hardware I/O & Interrupt Guard:** In operating system kernels and hypervisors, spinlocks disabling interrupts (`spin_lock_irqsave`) or protecting unmapped physical hardware ports (`inb`, `outb`, MMIO) are preserved.

### 7.2 Path Feasibility Pruning via SMT (Z3 Solver)

For each candidate site $s$, CRUX constructs the path condition $\Phi_s$ along the Control Flow Graph and queries the Z3 SMT solver:

$$\Phi_s = \bigwedge_{b \in \text{path}(\text{entry}, s)} \text{cond}(b)$$

*   $\mathrm{UNSAT}(\Phi_s) \implies$ The path to lock site $s$ is provably dead or unreachable. The candidate is discarded as a false alarm.
*   $\mathrm{SAT}(\Phi_s) \implies$ The execution path is feasible; the candidate is validated.
*   *Solver Fallback:* If $\Phi_s$ involves unsupported non-linear arithmetic or opaque external state, CRUX conservatively defaults to $\mathrm{SAT}$ under the Presumption of Intent.

---

## 8. Summary of the Verification Pipeline

CRUX integrates these theoretical foundations across three complementary layers:

1.  **Local Critical Section Analysis ($\mathcal{CS}(s)$):** Precise field-sensitive extraction of read, write, and call sets on normalized LLVM IR.
2.  **Global Relational Graph ($G = (\mathcal{S}, \mathcal{A})$):** Multi-relational Lock Site Graph modeling data conflicts ($\textsc{share}$), lock nesting ($\textsc{nest}$), and happens-before execution order ($\textsc{hb}$).
3.  **Sound Decision Logic & SMT Validation:** Direct evaluation of the six structural anti-patterns, bounded by conservative safety guards and path reachability solving in Z3 under the **Presumption of Intent**.
