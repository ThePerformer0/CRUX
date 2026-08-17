"""LLVM IR Text Parser.

Responsible for parsing textual LLVM IR (.ll) into structured representations:
LLVMInstruction, BasicBlock, and CFG data structures.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class LLVMInstruction:
    """Represents a single parsed LLVM IR instruction."""
    raw: str
    opcode: str
    dest: Optional[str] = None
    args: List[str] = field(default_factory=list)
    phi_incoming: List[Tuple[str, str]] = field(default_factory=list)  # [(val, block_name)]
    line_number: int = 0
    source_file: str = "unknown.c"


# Regex patterns for instruction parsing
FUNC_DEF_PATTERN = re.compile(r"^\s*define\s+.*?@([a-zA-Z0-9_$.]+)\s*\((.*?)\)")
ASSIGN_PATTERN = re.compile(r"^\s*(%[a-zA-Z0-9_$.]+)\s*=\s*([a-zA-Z0-9_.]+)\s+(.*)")
VOID_CALL_PATTERN = re.compile(r"^\s*(call|invoke)\s+(.*)")
TERMINATOR_BR_UNCOND = re.compile(r"^\s*br\s+label\s+%([a-zA-Z0-9_$.]+)")
TERMINATOR_BR_COND = re.compile(r"^\s*br\s+i1\s+([^,]+),\s*label\s+%([a-zA-Z0-9_$.]+),\s*label\s+%([a-zA-Z0-9_$.]+)")
TERMINATOR_SWITCH = re.compile(r"label\s+%([a-zA-Z0-9_$.]+)")
TERMINATOR_INVOKE = re.compile(r"to\s+label\s+%([a-zA-Z0-9_$.]+)\s+unwind\s+label\s+%([a-zA-Z0-9_$.]+)")
PHI_PAIR_PATTERN = re.compile(r"\[\s*([^,]+),\s*%([a-zA-Z0-9_$.]+)\s*\]")


def parse_debug_metadata(llvm_ir_text: str) -> Dict[str, Tuple[str, int]]:
    """Parses LLVM IR !dbg metadata to map !dbg IDs to (filename, line_number)."""
    node_pattern = re.compile(r"^!(\d+)\s*=\s*(?:distinct\s+)?!([a-zA-Z0-9_]+)\s*\((.*)\)", re.MULTILINE)
    nodes = {}
    for match in node_pattern.finditer(llvm_ir_text):
        nodes[match.group(1)] = (match.group(2), match.group(3))

    def get_file_for_scope(scope_id: str, depth: int = 0) -> str:
        if depth > 10 or scope_id not in nodes:
            return "unknown.c"
        node_type, content = nodes[scope_id]
        
        file_match = re.search(r"file:\s*!(\d+)", content)
        if file_match:
            file_id = file_match.group(1)
            if file_id in nodes and nodes[file_id][0] == "DIFile":
                filename_match = re.search(r"filename:\s*\"([^\"]+)\"", nodes[file_id][1])
                if filename_match:
                    return filename_match.group(1)
                    
        scope_match = re.search(r"scope:\s*!(\d+)", content)
        if scope_match:
            return get_file_for_scope(scope_match.group(1), depth + 1)
            
        return "unknown.c"

    debug_map = {}
    for node_id, (node_type, content) in nodes.items():
        if node_type == "DILocation":
            line_match = re.search(r"line:\s*(\d+)", content)
            scope_match = re.search(r"scope:\s*!(\d+)", content)
            if line_match and scope_match:
                line = int(line_match.group(1))
                scope_id = scope_match.group(1)
                filename = get_file_for_scope(scope_id)
                debug_map[node_id] = (filename, line)

    return debug_map


def parse_instruction(raw_line: str, line_number: int = 0, debug_map: Optional[Dict[str, Tuple[str, int]]] = None) -> LLVMInstruction:
    """Parses a single line of LLVM IR into an LLVMInstruction dataclass.

    Args:
        raw_line: Text of the instruction line.
        line_number: Source line number.

    Returns:
        LLVMInstruction instance.
    """
    clean_line = raw_line.strip()
    if ";" in clean_line:
        # Strip inline comments
        clean_line = clean_line.split(";")[0].strip()

    dest: Optional[str] = None
    opcode: str = ""
    args: List[str] = []
    phi_incoming: List[Tuple[str, str]] = []

    assign_match = ASSIGN_PATTERN.match(clean_line)
    if assign_match:
        dest = assign_match.group(1)
        opcode = assign_match.group(2)
        rest = assign_match.group(3)

        if opcode == "phi":
            pairs = PHI_PAIR_PATTERN.findall(rest)
            for val, block in pairs:
                phi_incoming.append((val.strip(), block.strip()))
        else:
            args = [arg.strip() for arg in rest.split(",") if arg.strip()]
    else:
        tokens = clean_line.split()
        if tokens:
            opcode = tokens[0]
            args = [arg.strip() for arg in clean_line[len(opcode):].split(",") if arg.strip()]

    source_file = "unknown.c"
    dbg_match = re.search(r",\s*!dbg\s*!(\d+)", clean_line)
    if dbg_match and debug_map:
        dbg_id = dbg_match.group(1)
        if dbg_id in debug_map:
            source_file, src_line = debug_map[dbg_id]
            line_number = src_line

    return LLVMInstruction(
        raw=raw_line,
        opcode=opcode,
        dest=dest,
        args=args,
        phi_incoming=phi_incoming,
        line_number=line_number,
        source_file=source_file,
    )
