"""Interprocedural Call Graph Builder.

Analyzes function call instructions (`call` and `invoke`) across LLVM IR text (.ll).
Constructs caller-callee mappings for direct calls and uses Class Hierarchy
Analysis (CHA) to resolve indirect calls conservatively. Supports transitive
callee extraction and recursion handling.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional


@dataclass
class CallGraph:
    """Represents the interprocedural Call Graph of an LLVM IR module."""
    calls: Dict[str, List[str]] = field(default_factory=dict)
    callers: Dict[str, List[str]] = field(default_factory=dict)
    call_counts: Dict[Tuple[str, str], int] = field(default_factory=dict)
    defined_functions: Set[str] = field(default_factory=set)
    function_signatures: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._transitive_cache: Dict[str, Set[str]] = {}

    def add_edge(self, caller: str, callee: str) -> None:
        """Adds a directed call edge caller -> callee, ignoring LLVM intrinsics."""
        if callee.startswith("llvm."):
            return  # Skip LLVM intrinsics

        if caller not in self.calls:
            self.calls[caller] = []
        self.calls[caller].append(callee)

        if callee not in self.callers:
            self.callers[callee] = []
        self.callers[callee].append(caller)

        pair = (caller, callee)
        self.call_counts[pair] = self.call_counts.get(pair, 0) + 1
        self._transitive_cache.clear()

    def get_callees(self, func: str) -> List[str]:
        """Returns direct callees for a given function."""
        return self.calls.get(func, [])

    def get_callers(self, func: str) -> List[str]:
        """Returns direct callers for a given function."""
        return self.callers.get(func, [])

    def get_transitive_callees(self, func: str, visited: Optional[Set[str]] = None) -> Set[str]:
        """Returns all functions transitively called by func, handling cycles/recursion iteratively."""
        if visited is None and func in self._transitive_cache:
            return self._transitive_cache[func]

        visited_nodes = set()
        if visited is not None:
            visited_nodes.update(visited)

        result: Set[str] = set()
        stack = [func]

        while stack:
            curr = stack.pop()
            if curr in visited_nodes:
                continue
            visited_nodes.add(curr)

            for callee in self.get_callees(curr):
                result.add(callee)
                if callee not in visited_nodes:
                    stack.append(callee)

        if visited is None:
            self._transitive_cache[func] = result

        return result


# Regex patterns for LLVM IR parsing
FUNC_DEF_PATTERN = re.compile(r"^\s*define\s+.*?@([a-zA-Z0-9_$.]+)\s*\((.*?)\)")
CALL_DIRECT_PATTERN = re.compile(r"(?:call|invoke)\s+.*@([a-zA-Z0-9_$.]+)\s*\(")
CALL_INDIRECT_PATTERN = re.compile(r"(?:call|invoke)\s+.*%([a-zA-Z0-9_$.]+)\s*\(")


def build_call_graph(llvm_ir_text: str) -> CallGraph:
    """Parses textual LLVM IR and constructs a CallGraph.

    Args:
        llvm_ir_text: The complete textual LLVM IR string (.ll).

    Returns:
        CallGraph object populated with caller/callee relations and transitive utilities.
    """
    cg = CallGraph()
    lines = llvm_ir_text.splitlines()

    # Step 1: Discover all defined functions and their parameter signature count
    current_func: Optional[str] = None
    indirect_call_sites: List[Tuple[str, str]] = []  # (caller, line)

    for line in lines:
        def_match = FUNC_DEF_PATTERN.search(line)
        if def_match:
            func_name = def_match.group(1)
            cg.defined_functions.add(func_name)
            cg.function_signatures[func_name] = def_match.group(2).strip()

    # Step 2: Scan for call and invoke instructions inside function definitions
    current_func: Optional[str] = None
    for line in lines:
        def_match = FUNC_DEF_PATTERN.search(line)
        if def_match:
            current_func = def_match.group(1)

        if current_func:
            # Check for direct calls/invokes
            direct_matches = CALL_DIRECT_PATTERN.findall(line)
            for callee in direct_matches:
                cg.add_edge(current_func, callee)

            # Check for indirect calls/invokes (%ptr)
            if not direct_matches and ("call " in line or "invoke " in line):
                indirect_match = CALL_INDIRECT_PATTERN.search(line)
                if indirect_match:
                    indirect_call_sites.append((current_func, line))

        if "}" in line:
            current_func = None

    # Step 3: Class Hierarchy Analysis (CHA) for indirect calls
    # Match indirect calls conservatively against defined candidate functions
    for caller, line in indirect_call_sites:
        for candidate in cg.defined_functions:
            if not candidate.startswith("llvm."):
                cg.add_edge(caller, candidate)

    return cg
