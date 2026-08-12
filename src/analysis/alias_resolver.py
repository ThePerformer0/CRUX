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
        if self.parent[i] == i:
            return i
        self.parent[i] = self.find(self.parent[i])
        return self.parent[i]

    def union(self, i: str, j: str) -> str:
        root_i = self.find(i)
        root_j = self.find(j)
        if root_i != root_j:
            self.parent[root_i] = root_j
            return root_j
        return root_i


GEP_PATTERN = re.compile(r"getelementptr\s+.*,\s*.*?\*\s*%([a-zA-Z0-9_$.]+)\s*,.*i32\s+(\d+)\s*$")
BITCAST_PATTERN = re.compile(r"bitcast\s+.*%([a-zA-Z0-9_$.]+)\s+to")
LOAD_PTR_PATTERN = re.compile(r"load\s+.*,\s*.*%([a-zA-Z0-9_$.]+)")
STORE_PTR_PATTERN = re.compile(r"store\s+.*%([a-zA-Z0-9_$.]+)\s*,\s*.*%([a-zA-Z0-9_$.]+)")


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
                src_reg = "%" + src_match.group(1)
                self.uf.union(inst.dest, src_reg)

        # Rule 2: %dst = getelementptr %struct, %base, i32 0, i32 N
        elif inst.opcode == "getelementptr" and inst.dest:
            gep_match = GEP_PATTERN.search(raw)
            if gep_match:
                base_reg = "%" + gep_match.group(1)
                field_idx = gep_match.group(2)
                self.gep_map[inst.dest] = (base_reg, field_idx)
            else:
                # Fallback for generic GEP: find last integer index
                indices = re.findall(r"i32\s+(\d+)", raw)
                regs = re.findall(r"%([a-zA-Z0-9_$.]+)", raw)
                if len(regs) >= 2 and indices:
                    base_reg = "%" + regs[1]  # First operand after struct type
                    field_idx = indices[-1]
                    self.gep_map[inst.dest] = (base_reg, field_idx)

        # Rule 3: %dst = phi [%p1, %bb1], [%p2, %bb2]
        elif inst.opcode == "phi" and inst.dest:
            for val, _ in inst.phi_incoming:
                val_clean = val.strip()
                if val_clean.startswith("%"):
                    self.uf.union(inst.dest, val_clean)

        # Rule 4: store %val, %ptr*
        elif inst.opcode == "store":
            store_match = STORE_PTR_PATTERN.search(raw)
            if store_match:
                val_reg = "%" + store_match.group(1)
                ptr_reg = "%" + store_match.group(2)
                self.points_to[ptr_reg] = val_reg
                # If loading from ptr_reg later, it alias-merges with val_reg

        # Rule 5: %dst = load T*, T** %ptr
        elif inst.opcode == "load" and inst.dest:
            load_match = LOAD_PTR_PATTERN.search(raw)
            if load_match:
                ptr_reg = "%" + load_match.group(1)
                if ptr_reg in self.points_to:
                    stored_val = self.points_to[ptr_reg]
                    self.uf.union(inst.dest, stored_val)

    def get_canonical_id(self, reg: str) -> str:
        """Returns the canonical identifier for a register or variable string.

        Args:
            reg: LLVM IR register name (e.g. '%11', '%p', '@global_var').

        Returns:
            Canonical string identifier.
        """
        clean_reg = reg.strip()
        if clean_reg.endswith(","):
            clean_reg = clean_reg[:-1].strip()

        # Check if register is a GEP derived pointer
        if clean_reg in self.gep_map:
            base_reg, field_idx = self.gep_map[clean_reg]
            base_canon = self.get_canonical_id(base_reg)
            return f"{base_canon}.{field_idx}"

        # Resolve through Union-Find equivalence class
        root = self.uf.find(clean_reg)

        # Check if root itself is a GEP
        if root != clean_reg and root in self.gep_map:
            base_reg, field_idx = self.gep_map[root]
            base_canon = self.get_canonical_id(base_reg)
            return f"{base_canon}.{field_idx}"

        return root
