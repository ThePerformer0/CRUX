"""BFS Control-Flow Lockset Analyzer.

Performs BFS dataflow analysis on function CFGs to track held locksets at every instruction.
Features conservative lockset intersection joins at CFG convergence points,
handles `pthread_cond_wait` (net effect 0), and collects path conditions for SMT validation.

Fixpoint convergence is computed on the lockset ONLY (finite lattice, guaranteed termination).
Path conditions are collected per-path for SMT validation but never block convergence.
"""

import re
from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Set, FrozenSet, Optional, Tuple, Deque
from src.frontend.cfg_builder import CFG, BasicBlock
from src.frontend.parser import LLVMInstruction, TERMINATOR_BR_COND
from src.analysis.alias_resolver import AliasResolver

# Maximum number of path conditions retained per site.
# Beyond this threshold we remain conservative: the SMT validator receives
# a subset of conditions but lockset correctness is not affected.
MAX_PATH_CONDITIONS: int = 32

LOCK_FUNCTIONS: Set[str] = {
    # POSIX Threads
    "pthread_mutex_lock", "pthread_mutex_trylock", "pthread_mutex_timedlock",
    "pthread_rwlock_rdlock", "pthread_rwlock_wrlock", "pthread_rwlock_tryrdlock", "pthread_rwlock_trywrlock",
    "pthread_spin_lock", "pthread_spin_trylock",
    # C11 Threads
    "mtx_lock", "mtx_timedlock", "mtx_trylock",
    # Linux Kernel
    "mutex_lock", "mutex_lock_interruptible", "mutex_lock_killable", "mutex_trylock",
    "spin_lock", "spin_lock_irq", "spin_lock_irqsave", "spin_lock_bh", "spin_trylock",
    "raw_spin_lock", "raw_spin_lock_irq", "raw_spin_lock_irqsave",
    "down_read", "down_read_trylock", "down_write", "down_write_trylock",
    "read_lock", "read_lock_irqsave", "write_lock", "write_lock_irqsave",
    # PostgreSQL
    "LWLockAcquire", "LWLockAcquireOrWait", "LWLockConditionalAcquire",
    "SpinLockAcquire", "s_lock",
    # SQLite3
    "sqlite3_mutex_enter", "sqlite3_mutex_try",
    # NGINX
    "ngx_thread_mutex_lock", "ngx_shmtx_lock", "ngx_shmtx_trylock",
    "ngx_rwlock_wrlock", "ngx_rwlock_rdlock", "ngx_spinlock",
    # OpenMPI / OPAL
    "opal_mutex_lock", "opal_mutex_trylock", "opal_atomic_lock",
    "opal_rwlock_rdlock", "opal_rwlock_wrlock",
    # RocksDB & LevelDB (C++ mangled & demangled)
    "_ZN7rocksdb4port5Mutex4LockEv", "_ZN7rocksdb4port5Mutex7TryLockEv",
    "_ZN7rocksdb4port7RWMutex6ReadLockEv", "_ZN7rocksdb4port7RWMutex7WriteLockEv",
    "_ZN7rocksdb17InstrumentedMutex4LockEv", "_ZN7rocksdb17InstrumentedMutex7TryLockEv",
    "_ZN7rocksdb19InstrumentedRWMutex6ReadLockEv", "_ZN7rocksdb19InstrumentedRWMutex7WriteLockEv",
    "_ZN7rocksdb9SpinMutex4lockEv", "_ZN7rocksdb9SpinMutex8try_lockEv",
    "_ZN7leveldb4port5Mutex4LockEv",
    # Apache HTTPD / APR
    "apr_thread_mutex_lock", "apr_thread_mutex_trylock", "apr_thread_mutex_timedlock",
    "apr_proc_mutex_lock", "apr_proc_mutex_trylock", "apr_proc_mutex_timedlock",
    "apr_thread_rwlock_rdlock", "apr_thread_rwlock_wrlock", "apr_thread_rwlock_tryrdlock", "apr_thread_rwlock_trywrlock",
    "apr_global_mutex_lock", "apr_global_mutex_trylock",
    # HAProxy
    "_ha_rwlock_wrlock", "_ha_rwlock_rdlock", "_ha_spinlock_lock", "pl_take",
    "HA_SPIN_LOCK", "HA_RWLOCK_WRLOCK", "HA_RWLOCK_RDLOCK",
    # Varnish Cache
    "Lck_Lock", "Lck_LockHdl", "Lck_Trylock",
    # GLib / GObject
    "g_mutex_lock", "g_mutex_trylock", "g_rec_mutex_lock", "g_rec_mutex_trylock",
    "g_rw_lock_reader_lock", "g_rw_lock_reader_trylock", "g_rw_lock_writer_lock", "g_rw_lock_writer_trylock",
    # librdkafka
    "rd_kafka_rdlock", "rd_kafka_wrlock", "rd_kafka_toppar_lock",
    # Xen Hypervisor
    "_spin_lock", "_spin_lock_irq", "_spin_lock_irqsave", "_spin_lock_cb", "_spin_trylock",
    "spin_lock_recursive", "_read_lock", "_read_lock_irq", "_read_lock_irqsave", "_read_trylock",
    "_write_lock", "_write_lock_irq", "_write_lock_irqsave", "_write_trylock",
    "percpu_read_lock", "percpu_write_lock", "grant_read_lock", "grant_write_lock",
    # C++ std::mutex & std::shared_mutex (mangled)
    "_ZNSt5mutex4lockEv", "_ZNSt5mutex8try_lockEv",
    "_ZNSt10timed_mutex4lockEv", "_ZNSt10timed_mutex8try_lockEv",
    "_ZNSt15recursive_mutex4lockEv", "_ZNSt15recursive_mutex8try_lockEv",
    "_ZNSt11unique_lockISt5mutexE4lockEv",
    "_ZNSt14shared_timed_mutex11lock_sharedEv", "_ZNSt14shared_timed_mutex4lockEv",
    "_ZNSt12shared_mutex11lock_sharedEv", "_ZNSt12shared_mutex4lockEv",
    # Poco C++
    "_ZN4Poco9FastMutex4lockEv", "_ZN4Poco5Mutex4lockEv",
}

UNLOCK_FUNCTIONS: Set[str] = {
    # POSIX Threads
    "pthread_mutex_unlock", "pthread_rwlock_unlock", "pthread_spin_unlock",
    # C11 Threads
    "mtx_unlock",
    # Linux Kernel
    "mutex_unlock", "spin_unlock", "spin_unlock_irq", "spin_unlock_irqrestore", "spin_unlock_bh",
    "raw_spin_unlock", "raw_spin_unlock_irq", "raw_spin_unlock_irqrestore",
    "up_read", "up_write",
    "read_unlock", "read_unlock_irqrestore", "write_unlock", "write_unlock_irqrestore",
    # PostgreSQL
    "LWLockRelease", "LWLockReleaseClearParticipant",
    "SpinLockRelease", "s_unlock",
    # SQLite3
    "sqlite3_mutex_leave",
    # NGINX
    "ngx_thread_mutex_unlock", "ngx_shmtx_unlock", "ngx_rwlock_unlock",
    # OpenMPI / OPAL
    "opal_mutex_unlock", "opal_atomic_unlock", "opal_rwlock_unlock",
    # RocksDB & LevelDB (C++ mangled & demangled)
    "_ZN7rocksdb4port5Mutex6UnlockEv",
    "_ZN7rocksdb4port7RWMutex8ReadUnlockEv", "_ZN7rocksdb4port7RWMutex9WriteUnlockEv",
    "_ZN7rocksdb17InstrumentedMutex6UnlockEv",
    "_ZN7rocksdb19InstrumentedRWMutex8ReadUnlockEv", "_ZN7rocksdb19InstrumentedRWMutex9WriteUnlockEv",
    "_ZN7rocksdb9SpinMutex6unlockEv",
    "_ZN7leveldb4port5Mutex6UnlockEv",
    # Apache HTTPD / APR
    "apr_thread_mutex_unlock", "apr_proc_mutex_unlock", "apr_thread_rwlock_unlock", "apr_global_mutex_unlock",
    # HAProxy
    "_ha_rwlock_wrunlock", "_ha_rwlock_rdunlock", "_ha_spinlock_unlock", "pl_drop",
    "HA_SPIN_UNLOCK", "HA_RWLOCK_WRUNLOCK", "HA_RWLOCK_RDUNLOCK",
    # Varnish Cache
    "Lck_Unlock", "Lck_UnlockHdl",
    # GLib / GObject
    "g_mutex_unlock", "g_rec_mutex_unlock", "g_rw_lock_reader_unlock", "g_rw_lock_writer_unlock",
    # librdkafka
    "rd_kafka_rdunlock", "rd_kafka_wrunlock", "rd_kafka_toppar_unlock",
    # Xen Hypervisor
    "_spin_unlock", "_spin_unlock_irq", "_spin_unlock_irqrestore",
    "spin_unlock_recursive", "_read_unlock", "_read_unlock_irq", "_read_unlock_irqrestore",
    "_write_unlock", "_write_unlock_irq", "_write_unlock_irqrestore",
    "percpu_read_unlock", "percpu_write_unlock", "grant_read_unlock", "grant_write_unlock",
    # C++ std::mutex & std::shared_mutex (mangled)
    "_ZNSt5mutex6unlockEv", "_ZNSt10timed_mutex6unlockEv", "_ZNSt15recursive_mutex6unlockEv",
    "_ZNSt11unique_lockISt5mutexE6unlockEv",
    "_ZNSt14shared_timed_mutex13unlock_sharedEv", "_ZNSt14shared_timed_mutex6unlockEv",
    "_ZNSt12shared_mutex13unlock_sharedEv", "_ZNSt12shared_mutex6unlockEv",
    # Poco C++
    "_ZN4Poco9FastMutex6unlockEv", "_ZN4Poco5Mutex6unlockEv",
}

COND_WAIT_FUNCTIONS: Set[str] = {
    "pthread_cond_wait", "pthread_cond_timedwait",
}


@dataclass(frozen=True)
class LockState:
    """Represents the lock analysis state at a specific program point."""
    lockset: FrozenSet[str] = field(default_factory=frozenset)
    path_conditions: Tuple[str, ...] = field(default_factory=tuple)


@dataclass
class FunctionLockSummary:
    """Interprocedural lock effect summary for a function.

    Captures net lock acquisitions (locks acquired and not released upon return)
    and net releases (locks released without prior acquisition).
    """
    net_acquires: Set[str] = field(default_factory=set)
    net_releases: Set[str] = field(default_factory=set)
    is_balanced: bool = True


# Regex to extract first argument register from call/invoke
MUTEX_ARG_PATTERN = re.compile(r"(?:call|invoke)\s+.*@(?:[a-zA-Z0-9_$.]+)\s*\(\s*(?:[^\(\),]+\s+)?(%[a-zA-Z0-9_$.]+|@[a-zA-Z0-9_$.]+)")
CALL_TARGET_WITH_ARGS_PATTERN = re.compile(r"(?:call|invoke)\s+.*@([a-zA-Z0-9_$.]+)\s*\((.*?)\)")


class LocksetAnalyzer:
    """Computes locksets per instruction across CFGs using intra- and interprocedural dataflow analysis."""

    def __init__(self, alias_resolver: AliasResolver,
                 custom_locks: Optional[Set[str]] = None,
                 custom_unlocks: Optional[Set[str]] = None) -> None:
        self.alias_resolver = alias_resolver
        self.lock_funcs = set(LOCK_FUNCTIONS)
        if custom_locks:
            self.lock_funcs.update(custom_locks)

        self.unlock_funcs = set(UNLOCK_FUNCTIONS)
        if custom_unlocks:
            self.unlock_funcs.update(custom_unlocks)

        self.cond_wait_funcs = set(COND_WAIT_FUNCTIONS)
        self.function_summaries: Dict[str, FunctionLockSummary] = {}
        self.function_entry_locksets: Dict[str, FrozenSet[str]] = {}

    def analyze_cfg(self, cfg: CFG,
                    initial_lockset: FrozenSet[str] = frozenset(),
                    function_summaries: Optional[Dict[str, FunctionLockSummary]] = None) -> Dict[str, List[LockState]]:
        """Performs BFS Lockset Analysis on a single CFG with support for initial entry locksets and summaries.

        Fixpoint criterion: lockset only (finite lattice → guaranteed termination).

        Args:
            cfg: CFG instance for a function.
            initial_lockset: Inherited lockset at function entry (top-down interprocedural context).
            function_summaries: Precomputed lock effect summaries for called functions.

        Returns:
            Dictionary mapping block_name -> List of LockState per instruction in that block.
        """
        block_entry_states: Dict[str, Optional[LockState]] = {b: None for b in cfg.blocks}
        instruction_states: Dict[str, List[LockState]] = {b: [] for b in cfg.blocks}

        if not cfg.blocks or cfg.entry_block not in cfg.blocks:
            return instruction_states

        summaries = function_summaries if function_summaries is not None else self.function_summaries

        worklist: Deque[Tuple[str, LockState]] = deque()
        initial_state = LockState(lockset=initial_lockset, path_conditions=())
        worklist.append((cfg.entry_block, initial_state))

        while worklist:
            block_name, incoming_state = worklist.popleft()

            if block_entry_states[block_name] is not None:
                prev_state = block_entry_states[block_name]

                # --- Fixpoint on LOCKSET only (finite lattice) ---
                joined_lockset = prev_state.lockset & incoming_state.lockset
                if joined_lockset == prev_state.lockset:
                    continue

                merged_conds = dict.fromkeys(
                    prev_state.path_conditions + incoming_state.path_conditions
                )
                joined_conds = tuple(list(merged_conds)[:MAX_PATH_CONDITIONS])
                joined_state = LockState(lockset=joined_lockset, path_conditions=joined_conds)
                block_entry_states[block_name] = joined_state
                incoming_state = joined_state
            else:
                block_entry_states[block_name] = incoming_state

            # Process instructions inside the block
            current_state = incoming_state
            block_inst_states: List[LockState] = []
            block = cfg.blocks[block_name]

            for inst in block.instructions:
                block_inst_states.append(current_state)
                current_state = self._transfer_function(inst, current_state, summaries)

            instruction_states[block_name] = block_inst_states

            # Propagate updated state to successors
            for succ_name in block.successors:
                if succ_name in cfg.blocks:
                    worklist.append((succ_name, current_state))

        return instruction_states

    def compute_all_summaries(self, cfgs: Dict[str, CFG], max_iterations: int = 5) -> Dict[str, FunctionLockSummary]:
        """Computes lock effect summaries for all functions using a bottom-up fixpoint algorithm.

        Args:
            cfgs: Dictionary mapping function_name -> CFG.
            max_iterations: Maximum iterations for mutual recursion convergence.

        Returns:
            Dictionary mapping function_name -> FunctionLockSummary.
        """
        summaries: Dict[str, FunctionLockSummary] = {
            f: FunctionLockSummary() for f in cfgs
        }

        for _ in range(max_iterations):
            changed = False
            for func_name, cfg in cfgs.items():
                summary = self._compute_single_function_summary(cfg, summaries)
                if (summary.net_acquires != summaries[func_name].net_acquires or
                        summary.net_releases != summaries[func_name].net_releases):
                    summaries[func_name] = summary
                    changed = True

            if not changed:
                break

        self.function_summaries = summaries
        return summaries

    def _compute_single_function_summary(self, cfg: CFG,
                                         current_summaries: Dict[str, FunctionLockSummary]) -> FunctionLockSummary:
        """Analyzes a CFG starting from an empty lockset to calculate net acquired and released locks."""
        instruction_states = self.analyze_cfg(cfg, initial_lockset=frozenset(), function_summaries=current_summaries)

        return_locksets: List[FrozenSet[str]] = []
        unpaired_releases: Set[str] = set()

        for block in cfg.blocks.values():
            for idx, inst in enumerate(block.instructions):
                raw = inst.raw.strip()
                if inst.opcode == "ret":
                    if idx < len(instruction_states.get(block.name, [])):
                        state = instruction_states[block.name][idx]
                        return_locksets.append(state.lockset)

                # Track unlock calls where the mutex was not currently held (net release)
                if self._is_unlock_call(raw):
                    mutex_arg = self._extract_mutex_arg(raw)
                    if mutex_arg:
                        canon_id = self.alias_resolver.get_canonical_id(mutex_arg)
                        current_held = instruction_states[block.name][idx].lockset if idx < len(instruction_states.get(block.name, [])) else frozenset()
                        if canon_id not in current_held:
                            unpaired_releases.add(canon_id)

        # Net acquires: locks held on ALL return paths
        if return_locksets:
            net_acquires = set(return_locksets[0])
            for ls in return_locksets[1:]:
                net_acquires &= ls
        else:
            net_acquires = set()

        is_balanced = len(net_acquires) == 0 and len(unpaired_releases) == 0

        return FunctionLockSummary(
            net_acquires=net_acquires,
            net_releases=unpaired_releases,
            is_balanced=is_balanced,
        )

    def compute_interprocedural_entry_locksets(self, cfgs: Dict[str, CFG],
                                               summaries: Optional[Dict[str, FunctionLockSummary]] = None) -> Dict[str, FrozenSet[str]]:
        """Propagates held locksets from callers to callees (Top-Down phase).

        Args:
            cfgs: Dictionary mapping function_name -> CFG.
            summaries: Precomputed function summaries.

        Returns:
            Dictionary mapping function_name -> FrozenSet of locks held across all call sites.
        """
        active_summaries = summaries or self.function_summaries
        incoming_locksets: Dict[str, List[FrozenSet[str]]] = {f: [] for f in cfgs}

        # Step 1: Collect caller lockset at every callsite
        for caller_name, cfg in cfgs.items():
            instruction_states = self.analyze_cfg(cfg, initial_lockset=frozenset(), function_summaries=active_summaries)

            for block_name, block in cfg.blocks.items():
                for idx, inst in enumerate(block.instructions):
                    raw = inst.raw.strip()
                    if "call " in raw or "invoke " in raw:
                        call_match = CALL_TARGET_WITH_ARGS_PATTERN.search(raw)
                        if call_match:
                            callee_name = call_match.group(1)
                            if callee_name in incoming_locksets:
                                current_state = instruction_states[block_name][idx] if idx < len(instruction_states[block_name]) else None
                                if current_state is not None:
                                    incoming_locksets[callee_name].append(current_state.lockset)

        # Step 2: Compute conservative intersection of held locksets across all call sites
        entry_locksets: Dict[str, FrozenSet[str]] = {}
        for func_name, lockset_list in incoming_locksets.items():
            if lockset_list:
                # If called from multiple places, intersect to be sound (must be held in all contexts)
                intersected = set(lockset_list[0])
                for ls in lockset_list[1:]:
                    intersected &= ls
                entry_locksets[func_name] = frozenset(intersected)
            else:
                entry_locksets[func_name] = frozenset()

        self.function_entry_locksets = entry_locksets
        return entry_locksets

    def analyze_module(self, cfgs: Dict[str, CFG]) -> Dict[str, Dict[str, List[LockState]]]:
        """Runs full 2-pass interprocedural analysis on all CFGs.

        1. Bottom-Up pass: computes function summaries.
        2. Top-Down pass: computes entry locksets.
        3. Final pass: computes full instruction lockstates with inherited context.

        Args:
            cfgs: Dictionary mapping function_name -> CFG.

        Returns:
            Dictionary mapping function_name -> (block_name -> List of LockState).
        """
        summaries = self.compute_all_summaries(cfgs)
        entry_locksets = self.compute_interprocedural_entry_locksets(cfgs, summaries)

        all_states: Dict[str, Dict[str, List[LockState]]] = {}
        for func_name, cfg in cfgs.items():
            initial_lockset = entry_locksets.get(func_name, frozenset())
            all_states[func_name] = self.analyze_cfg(cfg, initial_lockset=initial_lockset, function_summaries=summaries)

        return all_states

    def _transfer_function(self, inst: LLVMInstruction, state: LockState,
                           summaries: Optional[Dict[str, FunctionLockSummary]] = None) -> LockState:
        raw = inst.raw.strip()

        # Check for Direct Lock Call
        for lock_func in self.lock_funcs:
            if f"@{lock_func}" in raw and ("call " in raw or "invoke " in raw):
                mutex_reg = self._extract_mutex_arg(raw)
                if mutex_reg:
                    canon_id = self.alias_resolver.get_canonical_id(mutex_reg)
                    new_lockset = state.lockset | {canon_id}
                    return LockState(lockset=new_lockset, path_conditions=state.path_conditions)

        # Check for Direct Unlock Call
        for unlock_func in self.unlock_funcs:
            if f"@{unlock_func}" in raw and ("call " in raw or "invoke " in raw):
                mutex_reg = self._extract_mutex_arg(raw)
                if mutex_reg:
                    canon_id = self.alias_resolver.get_canonical_id(mutex_reg)
                    new_lockset = state.lockset - {canon_id}
                    return LockState(lockset=new_lockset, path_conditions=state.path_conditions)

        # Check for Cond Wait Call (Net effect = 0 on lockset)
        for cond_func in self.cond_wait_funcs:
            if f"@{cond_func}" in raw and ("call " in raw or "invoke " in raw):
                return state

        # Check for Function Calls with Precomputed Summaries (Wrappers / Helpers)
        if summaries and ("call " in raw or "invoke " in raw):
            call_match = CALL_TARGET_WITH_ARGS_PATTERN.search(raw)
            if call_match:
                callee_name = call_match.group(1)
                if callee_name in summaries and not summaries[callee_name].is_balanced:
                    summary = summaries[callee_name]
                    # Map net acquires / releases
                    new_lockset = set(state.lockset)
                    for rel in summary.net_releases:
                        new_lockset.discard(self.alias_resolver.get_canonical_id(rel))
                    for acq in summary.net_acquires:
                        new_lockset.add(self.alias_resolver.get_canonical_id(acq))
                    return LockState(lockset=frozenset(new_lockset), path_conditions=state.path_conditions)

        # Check for Conditional Branch to collect path conditions
        cond_match = TERMINATOR_BR_COND.match(raw)
        if cond_match:
            cond_var = cond_match.group(1)
            new_conds = state.path_conditions + (cond_var,)
            return LockState(lockset=state.lockset, path_conditions=new_conds)

        return state

    def _is_unlock_call(self, raw_line: str) -> bool:
        if "call " not in raw_line and "invoke " not in raw_line:
            return False
        for unlock_func in self.unlock_funcs:
            if f"@{unlock_func}" in raw_line:
                return True
        return False

    def _extract_mutex_arg(self, raw_line: str) -> Optional[str]:
        match = MUTEX_ARG_PATTERN.search(raw_line)
        if match:
            return match.group(1)
        fallback = re.search(r"\(\s*(?:[^\(\),]+\s+)?(%[a-zA-Z0-9_$.]+|@[a-zA-Z0-9_$.]+)", raw_line)
        if fallback:
            return fallback.group(1)
        return None

