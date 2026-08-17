"""Lock Site Characterizer.

Identifies lock acquisition calls, traces critical sections to their matching unlock calls,
and computes direct/transitive memory reads, writes, indirect call flags, path conditions,
and entry locksets for each LockSite object.
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
CALL_TARGET_PATTERN = re.compile(r"(?:call|invoke)\s+.*@([a-zA-Z0-9_$.]+)\s*\(")


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

        all_sites: List[LockSite] = []
        site_counter = 1

        for func_name, cfg in cfgs.items():
            instruction_lockstates = self.lockset_analyzer.analyze_cfg(cfg)

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

        return all_sites

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

                # Record calls
                elif "call " in raw or "invoke " in raw:
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
