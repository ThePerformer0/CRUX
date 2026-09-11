"""Lock Site Characterizer.

Identifies lock acquisition calls, traces critical sections to their matching unlock calls,
and computes direct/transitive memory reads, writes, indirect call flags, path conditions,
and entry locksets for each LockSite object.

Also detects SINGLE_THREAD sites: functions that are never transitively reached from a
pthread_create (or equivalent) thread-entry callback belong to the sequential phase of
the program and do not need mutual exclusion.
"""

import re
from typing import Dict, List, Set, Tuple, Optional, FrozenSet
from src.core.lock_site import LockSite
from src.frontend.cfg_builder import CFG, BasicBlock
from src.frontend.call_graph import CallGraph
from src.frontend.parser import LLVMInstruction
from src.analysis.alias_resolver import AliasResolver
from src.analysis.lockset_analyzer import LocksetAnalyzer, LOCK_FUNCTIONS, UNLOCK_FUNCTIONS, COND_WAIT_FUNCTIONS

LOAD_VAR_PATTERN = re.compile(r"load\s+.*,\s*.*?(%[a-zA-Z0-9_$.]+|@[a-zA-Z0-9_$.]+)")
STORE_VAR_PATTERN = re.compile(r"store\s+.*,\s*.*?(%[a-zA-Z0-9_$.]+|@[a-zA-Z0-9_$.]+)")
ATOMIC_VAR_PATTERN = re.compile(r"(?:atomicrmw|cmpxchg)\s+.*?(%[a-zA-Z0-9_$.]+|@[a-zA-Z0-9_$.]+)")
MEMCPY_PATTERN = re.compile(r"@llvm\.mem(?:cpy|move)[a-zA-Z0-9_$.]*\s*\(\s*(?:ptr|i8\*|[a-zA-Z0-9_*]+)\s*(%[a-zA-Z0-9_$.]+|@[a-zA-Z0-9_$.]+)\s*,\s*(?:ptr|i8\*|[a-zA-Z0-9_*]+)\s*(%[a-zA-Z0-9_$.]+|@[a-zA-Z0-9_$.]+)")
MEMSET_PATTERN = re.compile(r"@llvm\.memset[a-zA-Z0-9_$.]*\s*\(\s*(?:ptr|i8\*|[a-zA-Z0-9_*]+)\s*(%[a-zA-Z0-9_$.]+|@[a-zA-Z0-9_$.]+)")
CALL_TARGET_PATTERN = re.compile(r"(?:call|invoke)\s+.*@([a-zA-Z0-9_$.]+)\s*\(")

# Thread creation APIs: the first or second argument is the thread entry function pointer.
# We scan the raw IR for these patterns to discover thread entry points.
THREAD_CREATE_FUNCTIONS: set = {
    "pthread_create",          # POSIX
    "thrd_create",             # C11 threads
    "clone",                   # Linux kernel raw clone
    "kthread_create",          # Linux kthread
    "kthread_run",             # Linux kthread helper
    "opal_thread_start",       # OpenMPI
    "uv_thread_create",        # libuv
}

THREAD_ENTRY_ARG_PATTERN = re.compile(
    r"(?:call|invoke)\s+.*@(?:" + r"|".join(THREAD_CREATE_FUNCTIONS) + r")\s*\(.*?@([a-zA-Z0-9_$.]+)"
)


class SiteExtractor:
    """Extracts and characterizes LockSite objects across an LLVM IR module."""

    def __init__(self, alias_resolver: AliasResolver, call_graph: CallGraph,
                 lockset_analyzer: LocksetAnalyzer) -> None:
        self.alias_resolver = alias_resolver
        self.call_graph = call_graph
        self.lockset_analyzer = lockset_analyzer
        self.function_effects: Dict[str, Tuple[Set[str], Set[str]]] = {}
        self._transitive_effects_cache: Dict[str, Tuple[Set[str], Set[str]]] = {}

    def extract_sites(self, cfgs: Dict[str, CFG]) -> List[LockSite]:
        """Extracts and characterizes all LockSite instances across the given CFGs.

        Args:
            cfgs: Dictionary of function name -> CFG.

        Returns:
            List of characterized LockSite objects.
        """
        # Step 1: Compute direct memory effects (reads, writes) for every function
        self._compute_function_memory_effects(cfgs)

        # Step 2: Compute 2-pass interprocedural lockstates across all functions
        module_lockstates = self.lockset_analyzer.analyze_module(cfgs)

        all_sites: List[LockSite] = []
        site_counter = 1

        for func_name, cfg in cfgs.items():
            instruction_lockstates = module_lockstates.get(func_name, {})

            for block_name, block in cfg.blocks.items():
                for idx, inst in enumerate(block.instructions):
                    raw = inst.raw.strip()

                    # Check if this instruction is a lock acquisition call
                    if self._is_lock_call(raw):
                        mutex_name = self.lockset_analyzer._extract_mutex_arg(raw) or "%mutex"
                        canon_mutex = self.alias_resolver.get_canonical_id(mutex_name)
                        entry_state = instruction_lockstates[block_name][idx] if idx < len(instruction_lockstates[block_name]) else None
                        entry_lockset = entry_state.lockset if entry_state else frozenset()
                        path_conds = list(entry_state.path_conditions) if entry_state else []

                        site_id = f"s{site_counter}"
                        site_counter += 1

                        site = LockSite(
                            site_id=site_id,
                            mutex_canonical_id=canon_mutex,
                            mutex_name=mutex_name,
                            function=func_name,
                            source_file=inst.source_file,
                            lock_source_line=inst.line_number,
                            lockset_at_entry=entry_lockset,
                            path_conditions=path_conds,
                        )

                        # Characterize critical section window (lock -> unlock)
                        self._characterize_critical_section(site, cfg, block_name, idx, canon_mutex)
                        all_sites.append(site)

        # Step 2: Compute transitive memory effects for each LockSite via Call Graph
        for site in all_sites:
            self._compute_transitive_effects(site)

        # Step 3: Mark sites in the single-threaded execution phase
        self._mark_single_thread_sites(all_sites, cfgs)

        return all_sites

    def _mark_single_thread_sites(self, sites: list, cfgs: dict) -> None:
        """Marks LockSite objects as single-threaded if they are never reachable from
        a thread entry function passed to pthread_create or equivalent.

        Strategy:
          1. Scan ALL instructions across all CFGs for thread-creation calls.
          2. Extract the function pointer argument (the thread entry function).
          3. Compute the set of all functions transitively reachable from any thread entry.
          4. Any site whose containing function is NOT in that reachable set is single-threaded.

        Conservative assumption: if no pthread_create is found at all (e.g. single-threaded
        program compiled with pthreads), we do NOT mark any site as SINGLE_THREAD.
        """
        thread_entry_functions: set = set()

        # Pass 1: find all thread entry points
        for func_name, cfg in cfgs.items():
            for block in cfg.blocks.values():
                for inst in block.instructions:
                    raw = inst.raw.strip()
                    if not ("call " in raw or "invoke " in raw):
                        continue
                    for create_func in THREAD_CREATE_FUNCTIONS:
                        if f"@{create_func}" in raw:
                            # Extract the thread function argument (typically 3rd arg for pthread_create)
                            m = THREAD_ENTRY_ARG_PATTERN.search(raw)
                            if m:
                                thread_entry_functions.add(m.group(1))
                            # Also scan for any @function_name reference in the args
                            # (handles direct function pointer passing)
                            all_refs = re.findall(r"@([a-zA-Z0-9_$.]+)", raw)
                            for ref in all_refs:
                                if ref != create_func and ref in cfgs:
                                    thread_entry_functions.add(ref)

        # If no thread creation found, conservatively skip (all locks may be necessary)
        if not thread_entry_functions:
            return

        # Pass 2: compute all functions reachable from any thread entry point
        threaded_functions: set = set(thread_entry_functions)
        for entry in thread_entry_functions:
            reachable = self.call_graph.get_transitive_callees(entry)
            threaded_functions.update(reachable)

        # Pass 3: mark sites whose function is NOT reachable from any thread
        for site in sites:
            if site.function not in threaded_functions:
                site.is_single_thread = True

    def _is_lock_call(self, raw_line: str) -> bool:
        if "call " not in raw_line and "invoke " not in raw_line:
            return False
        for lock_func in self.lockset_analyzer.lock_funcs:
            if f"@{lock_func}" in raw_line:
                return True
        return False

    def _is_unlock_call(self, raw_line: str) -> bool:
        if "call " not in raw_line and "invoke " not in raw_line:
            return False
        for unlock_func in self.lockset_analyzer.unlock_funcs:
            if f"@{unlock_func}" in raw_line:
                return True
        return False

    def _canonicalize_var(self, raw_var: str, func_name: str) -> str:
        """Returns canonical ID, prefixing local registers with function name for sound scoping."""
        canon = self.alias_resolver.get_canonical_id(raw_var)
        if canon.startswith("@"):
            return canon
        return f"{func_name}::{canon}"

    def _compute_function_memory_effects(self, cfgs: Dict[str, CFG]) -> None:
        """Precomputes direct memory reads and writes for every function."""
        for func_name, cfg in cfgs.items():
            reads: Set[str] = set()
            writes: Set[str] = set()

            for block in cfg.blocks.values():
                for inst in block.instructions:
                    raw = inst.raw.strip()
                    if inst.opcode == "load":
                        m = LOAD_VAR_PATTERN.search(raw)
                        if m:
                            reads.add(self.alias_resolver.get_canonical_id(m.group(1)))
                    elif inst.opcode == "store":
                        m = STORE_VAR_PATTERN.search(raw)
                        if m:
                            writes.add(self.alias_resolver.get_canonical_id(m.group(1)))
                    elif inst.opcode in ("atomicrmw", "cmpxchg"):
                        m = ATOMIC_VAR_PATTERN.search(raw)
                        if m:
                            canon = self.alias_resolver.get_canonical_id(m.group(1))
                            reads.add(canon)
                            writes.add(canon)
                    elif "llvm.memcpy" in raw or "llvm.memmove" in raw:
                        m = MEMCPY_PATTERN.search(raw)
                        if m:
                            writes.add(self.alias_resolver.get_canonical_id(m.group(1)))
                            reads.add(self.alias_resolver.get_canonical_id(m.group(2)))
                    elif "llvm.memset" in raw:
                        m = MEMSET_PATTERN.search(raw)
                        if m:
                            writes.add(self.alias_resolver.get_canonical_id(m.group(1)))

            self.function_effects[func_name] = (reads, writes)

    def _characterize_critical_section(self, site: LockSite, cfg: CFG,
                                        start_block: str, start_idx: int,
                                        canon_mutex: str) -> None:
        """Traverses the CFG from lock call to matching unlock call to record CS accesses."""
        visited_blocks: Set[str] = set()
        worklist = [(start_block, start_idx + 1)]

        while worklist:
            block_name, idx = worklist.pop(0)
            if block_name not in cfg.blocks:
                continue

            block = cfg.blocks[block_name]
            num_insts = len(block.instructions)
            stopped_by_unlock = False

            for i in range(idx, num_insts):
                inst = block.instructions[i]
                raw = inst.raw.strip()

                if self._is_unlock_call(raw):
                    unlock_mutex = self.lockset_analyzer._extract_mutex_arg(raw)
                    if unlock_mutex and self.alias_resolver.get_canonical_id(unlock_mutex) == canon_mutex:
                        site.unlock_source_lines.append(inst.line_number)
                        stopped_by_unlock = True
                        break

                # Record direct reads
                if inst.opcode == "load":
                    m = LOAD_VAR_PATTERN.search(raw)
                    if m:
                        site.reads.add(self.alias_resolver.get_canonical_id(m.group(1)))

                # Record direct writes
                elif inst.opcode == "store":
                    m = STORE_VAR_PATTERN.search(raw)
                    if m:
                        site.writes.add(self.alias_resolver.get_canonical_id(m.group(1)))

                # Record atomics
                elif inst.opcode in ("atomicrmw", "cmpxchg"):
                    m = ATOMIC_VAR_PATTERN.search(raw)
                    if m:
                        canon = self.alias_resolver.get_canonical_id(m.group(1))
                        site.reads.add(canon)
                        site.writes.add(canon)

                # Record memcpy/memset
                elif "llvm.memcpy" in raw or "llvm.memmove" in raw:
                    site.has_memory_intrinsic = True
                    m = MEMCPY_PATTERN.search(raw)
                    if m:
                        site.writes.add(self.alias_resolver.get_canonical_id(m.group(1)))
                        site.reads.add(self.alias_resolver.get_canonical_id(m.group(2)))
                elif "llvm.memset" in raw:
                    site.has_memory_intrinsic = True
                    m = MEMSET_PATTERN.search(raw)
                    if m:
                        site.writes.add(self.alias_resolver.get_canonical_id(m.group(1)))

                # Record fence (memory barriers)
                elif inst.opcode == "fence":
                    site.has_memory_intrinsic = True

                # Record calls
                elif "call " in raw or "invoke " in raw:
                    if " asm " in raw:
                        site.has_inline_asm = True
                    else:
                        call_match = CALL_TARGET_PATTERN.search(raw)
                        if call_match:
                            callee = call_match.group(1)
                            if not callee.startswith("llvm.") and callee not in self.lockset_analyzer.lock_funcs and callee not in self.lockset_analyzer.unlock_funcs:
                                if callee in COND_WAIT_FUNCTIONS:
                                    site.is_cond_wait_mutex = True
                                else:
                                    site.calls.append(callee)
                        elif "%" in raw:
                            site.has_indirect_calls = True

            if not stopped_by_unlock and block_name not in visited_blocks:
                visited_blocks.add(block_name)
                for succ in block.successors:
                    worklist.append((succ, 0))

    def _compute_transitive_effects(self, site: LockSite) -> None:
        """Aggregates transitive memory reads and writes for callees in the critical section using memoization."""
        for callee in site.calls:
            if callee not in self._transitive_effects_cache:
                transitive_callees = self.call_graph.get_transitive_callees(callee)
                all_callees = {callee} | transitive_callees
                reads: Set[str] = set()
                writes: Set[str] = set()

                for c in all_callees:
                    if c in self.function_effects:
                        r, w = self.function_effects[c]
                        reads |= r
                        writes |= w
                self._transitive_effects_cache[callee] = (reads, writes)

            reads, writes = self._transitive_effects_cache[callee]
            site.transitive_reads |= reads
            site.transitive_writes |= writes
