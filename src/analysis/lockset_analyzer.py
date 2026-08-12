"""BFS Control-Flow Lockset Analyzer.

Performs BFS dataflow analysis on function CFGs to track held locksets at every instruction.
Features conservative lockset intersection joins at CFG convergence points,
handles `pthread_cond_wait` (net effect 0), and collects path conditions for SMT validation.
"""

import re
from queue import Queue
from dataclasses import dataclass, field
from typing import Dict, List, Set, FrozenSet, Optional, Tuple
from src.frontend.cfg_builder import CFG, BasicBlock
from src.frontend.parser import LLVMInstruction, TERMINATOR_BR_COND
from src.analysis.alias_resolver import AliasResolver

LOCK_FUNCTIONS: Set[str] = {
    # POSIX
    "pthread_mutex_lock", "pthread_mutex_trylock",
    "pthread_rwlock_rdlock", "pthread_rwlock_wrlock",
    "pthread_spin_lock",
    # C11
    "mtx_lock", "mtx_timedlock", "mtx_trylock",
    # Linux kernel
    "mutex_lock", "mutex_lock_interruptible",
    "spin_lock", "spin_lock_irq", "spin_lock_irqsave",
    "down_read", "down_write", "raw_spin_lock",
    # Custom / Libraries
    "rd_kafka_rdlock", "rd_kafka_wrlock", "rd_kafka_toppar_lock",
    "LWLockAcquire", "SpinLockAcquire",
    "ngx_thread_mutex_lock", "ngx_shmtx_lock",
    "sqlite3_mutex_enter",
    # C++ (mangled)
    "_ZNSt5mutex4lockEv",
}

UNLOCK_FUNCTIONS: Set[str] = {
    # POSIX
    "pthread_mutex_unlock", "pthread_rwlock_unlock", "pthread_spin_unlock",
    # C11
    "mtx_unlock",
    # Linux kernel
    "mutex_unlock", "spin_unlock", "spin_unlock_irq", "spin_unlock_irqrestore",
    "up_read", "up_write", "raw_spin_unlock",
    # Custom / Libraries
    "rd_kafka_rdunlock", "rd_kafka_wrunlock", "rd_kafka_toppar_unlock",
    "LWLockRelease", "SpinLockRelease",
    "ngx_thread_mutex_unlock", "ngx_shmtx_unlock",
    "sqlite3_mutex_leave",
    # C++ (mangled)
    "_ZNSt5mutex6unlockEv",
}

COND_WAIT_FUNCTIONS: Set[str] = {
    "pthread_cond_wait", "pthread_cond_timedwait",
}


@dataclass(frozen=True)
class LockState:
    """Represents the lock analysis state at a specific program point."""
    lockset: FrozenSet[str] = field(default_factory=frozenset)
    path_conditions: Tuple[str, ...] = field(default_factory=tuple)


# Regex to extract first argument register from call/invoke
MUTEX_ARG_PATTERN = re.compile(r"(?:call|invoke)\s+.*@(?:[a-zA-Z0-9_$.]+)\s*\(\s*(?:[^\(\),]+\s+)?(%[a-zA-Z0-9_$.]+|@[a-zA-Z0-9_$.]+)")


class LocksetAnalyzer:
    """Computes locksets per instruction across CFGs using BFS dataflow analysis."""

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

    def analyze_cfg(self, cfg: CFG) -> Dict[str, List[LockState]]:
        """Performs BFS Lockset Analysis on a single CFG.

        Args:
            cfg: CFG instance for a function.

        Returns:
            Dictionary mapping block_name -> List of LockState per instruction in that block.
        """
        block_entry_states: Dict[str, Optional[LockState]] = {b: None for b in cfg.blocks}
        instruction_states: Dict[str, List[LockState]] = {b: [] for b in cfg.blocks}

        if not cfg.blocks or cfg.entry_block not in cfg.blocks:
            return instruction_states

        worklist: Queue[Tuple[str, LockState]] = Queue()
        initial_state = LockState(lockset=frozenset(), path_conditions=())
        worklist.put((cfg.entry_block, initial_state))

        while not worklist.empty():
            block_name, incoming_state = worklist.get()

            # Join operation at CFG convergence points (Intersection of locksets)
            if block_entry_states[block_name] is not None:
                prev_state = block_entry_states[block_name]
                joined_lockset = prev_state.lockset & incoming_state.lockset
                # Combine unique path conditions
                joined_conds = tuple(dict.fromkeys(prev_state.path_conditions + incoming_state.path_conditions))
                joined_state = LockState(lockset=joined_lockset, path_conditions=joined_conds)

                if joined_state.lockset == prev_state.lockset and len(joined_conds) == len(prev_state.path_conditions):
                    continue  # Fixed point reached for this block

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
                current_state = self._transfer_function(inst, current_state)

            instruction_states[block_name] = block_inst_states

            # Propagate updated state to successors
            for succ_name in block.successors:
                worklist.put((succ_name, current_state))

        return instruction_states

    def _transfer_function(self, inst: LLVMInstruction, state: LockState) -> LockState:
        raw = inst.raw.strip()

        # Check for Lock Call
        for lock_func in self.lock_funcs:
            if f"@{lock_func}" in raw and ("call " in raw or "invoke " in raw):
                mutex_reg = self._extract_mutex_arg(raw)
                if mutex_reg:
                    canon_id = self.alias_resolver.get_canonical_id(mutex_reg)
                    new_lockset = state.lockset | {canon_id}
                    return LockState(lockset=new_lockset, path_conditions=state.path_conditions)

        # Check for Unlock Call
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
                return state  # Lockset remains unchanged after cond_wait

        # Check for Conditional Branch to collect path conditions
        cond_match = TERMINATOR_BR_COND.match(raw)
        if cond_match:
            cond_var = cond_match.group(1)
            new_conds = state.path_conditions + (cond_var,)
            return LockState(lockset=state.lockset, path_conditions=new_conds)

        return state

    def _extract_mutex_arg(self, raw_line: str) -> Optional[str]:
        match = MUTEX_ARG_PATTERN.search(raw_line)
        if match:
            return match.group(1)
        # Fallback regex matching first % or @ operand inside parentheses
        fallback = re.search(r"\(\s*(?:[^\(\),]+\s+)?(%[a-zA-Z0-9_$.]+|@[a-zA-Z0-9_$.]+)", raw_line)
        if fallback:
            return fallback.group(1)
        return None
