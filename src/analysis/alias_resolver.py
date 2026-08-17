"""Field-Based Alias Analyzer.

Uses a Field-Based Alias Analysis algorithm backed by a Disjoint-Set (Union-Find)
data structure to compute canonical IDs for LLVM IR memory registers and struct fields.
Handles bitcast, getelementptr (GEP), store, load, and phi instructions.
"""

import re
from typing import Dict, List, Optional, Tuple, Set
from src.frontend.cfg_builder import CFG, build_cfgs
from src.frontend.parser import LLVMInstruction


class UnionFind:
    """Disjoint-set / Union-Find data structure for equivalence classes."""

    def __init__(self) -> None:
        self.parent: Dict[str, str] = {}

    def find(self, i: str) -> str:
        if i not in self.parent:
            self.parent[i] = i
            return i

        curr = i
        path = []
        while self.parent.get(curr, curr) != curr:
            path.append(curr)
            curr = self.parent[curr]
            if curr in path:
                break

        for node in path:
            self.parent[node] = curr
        return curr

    def union(self, i: str, j: str) -> str:
        root_i = self.find(i)
        root_j = self.find(j)
        if root_i != root_j:
            self.parent[root_i] = root_j
            return root_j
        return root_i


GEP_PATTERN = re.compile(r"getelementptr\s+.*,\s*.*?\*\s*(%[a-zA-Z0-9_$.]+|@[a-zA-Z0-9_$.]+)\s*,.*i32\s+(\d+)\s*$")
BITCAST_PATTERN = re.compile(r"bitcast\s+.*?(%[a-zA-Z0-9_$.]+|@[a-zA-Z0-9_$.]+)\s+to")
LOAD_PTR_PATTERN = re.compile(r"load\s+.*,\s*.*?(%[a-zA-Z0-9_$.]+|@[a-zA-Z0-9_$.]+)")
STORE_PTR_PATTERN = re.compile(r"store\s+.*?(%[a-zA-Z0-9_$.]+|@[a-zA-Z0-9_$.]+)\s*,\s*.*?(%[a-zA-Z0-9_$.]+|@[a-zA-Z0-9_$.]+)")


class AliasResolver:
    """Computes canonical IDs for LLVM IR memory objects across functions."""

    def __init__(self) -> None:
        self.uf = UnionFind()
        self.gep_map: Dict[str, Tuple[str, str]] = {}  # reg -> (base_reg, field_index)
        self.points_to: Dict[str, str] = {}  # ptr_reg -> stored_val_reg

    def analyze_cfgs(self, cfgs: Dict[str, CFG]) -> None:
        """Analyzes all instructions across CFGs to populate alias equivalence classes.

        Args:
            cfgs: Dictionary of function name -> CFG instance.
        """
        for cfg in cfgs.values():
            for block in cfg.blocks.values():
                for inst in block.instructions:
                    self._process_instruction(inst)

    def analyze_ir(self, llvm_ir_text: str) -> None:
        """Utility method to parse LLVM IR text and analyze alias relations."""
        cfgs = build_cfgs(llvm_ir_text)
        self.analyze_cfgs(cfgs)

    def _process_instruction(self, inst: LLVMInstruction) -> None:
        raw = inst.raw.strip()

        # Rule 1: %dst = bitcast T* %src to U*
        if inst.opcode == "bitcast" and inst.dest:
            src_match = BITCAST_PATTERN.search(raw)
            if src_match:
                src_reg = src_match.group(1)
                self.uf.union(inst.dest, src_reg)

        # Rule 2: %dst = getelementptr ...
        elif inst.opcode == "getelementptr" and inst.dest:
            gep_idx = raw.find("getelementptr")
            gep_body = raw[gep_idx + len("getelementptr"):] if gep_idx != -1 else raw
            parts = gep_body.split(",")
            
            if len(parts) >= 2:
                # Base pointer is in parts[1]: e.g. "%struct.Pool* %p" or "ptr %p" or "ptr @arr"
                base_regs = re.findall(r"(%[a-zA-Z0-9_$.]+|@[a-zA-Z0-9_$.]+)", parts[1])
                # Indices are in remaining parts
                indices_text = ",".join(parts[2:]) if len(parts) > 2 else parts[1]
                indices = re.findall(r"(?:i8|i16|i32|i64)\s+(-?\d+)", indices_text)
                
                if base_regs:
                    base_reg = base_regs[-1]
                    if len(indices) == 2 and indices[0] == "0":
                        offset = indices[1]
                    elif indices:
                        offset = ".".join(indices)
                    else:
                        offset = "0"
                    self.gep_map[inst.dest] = (base_reg, offset)

        # Rule 3: %dst = phi [%p1, %bb1], [%p2, %bb2]
        elif inst.opcode == "phi" and inst.dest:
            for val, _ in inst.phi_incoming:
                val_clean = val.strip()
                if val_clean.startswith("%") or val_clean.startswith("@"):
                    self.uf.union(inst.dest, val_clean)

        # Rule 4: store %val, %ptr* or @ptr
        elif inst.opcode == "store":
            store_match = STORE_PTR_PATTERN.search(raw)
            if store_match:
                val_reg = store_match.group(1)
                ptr_reg = store_match.group(2)
                if ptr_reg in self.points_to:
                    self.uf.union(val_reg, self.points_to[ptr_reg])
                else:
                    self.points_to[ptr_reg] = val_reg

        # Rule 5: %dst = load T*, T** %ptr or @ptr
        elif inst.opcode == "load" and inst.dest:
            load_match = LOAD_PTR_PATTERN.search(raw)
            if load_match:
                ptr_reg = load_match.group(1)
                if ptr_reg in self.points_to:
                    stored_val = self.points_to[ptr_reg]
                    self.uf.union(inst.dest, stored_val)
                else:
                    self.points_to[ptr_reg] = inst.dest

    def get_canonical_id(self, reg: str, visited: Optional[Set[str]] = None) -> str:
        """Returns the canonical identifier for a register or variable string.

        Args:
            reg: LLVM IR register name (e.g. '%11', '%p', '@global_var').
            visited: Set of previously visited registers to prevent GEP cycles.

        Returns:
            Canonical string identifier.
        """
        if visited is None:
            visited = set()

        clean_reg = reg.strip()
        if clean_reg.endswith(","):
            clean_reg = clean_reg[:-1].strip()

        if clean_reg in visited:
            return clean_reg
        visited.add(clean_reg)

        # Check if register is a GEP derived pointer
        if clean_reg in self.gep_map:
            base_reg, field_idx = self.gep_map[clean_reg]
            base_canon = self.get_canonical_id(base_reg, visited)
            return f"{base_canon}.{field_idx}"

        # Resolve through Union-Find equivalence class
        root = self.uf.find(clean_reg)

        # Check if root itself is a GEP
        if root != clean_reg and root in self.gep_map:
            base_reg, field_idx = self.gep_map[root]
            base_canon = self.get_canonical_id(base_reg, visited)
            return f"{base_canon}.{field_idx}"

        return root
