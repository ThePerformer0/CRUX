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


# Regex patterns for instruction parsing
FUNC_DEF_PATTERN = re.compile(r"^\s*define\s+.*?@([a-zA-Z0-9_$.]+)\s*\((.*?)\)")
ASSIGN_PATTERN = re.compile(r"^\s*(%[a-zA-Z0-9_$.]+)\s*=\s*([a-zA-Z0-9_.]+)\s+(.*)")
VOID_CALL_PATTERN = re.compile(r"^\s*(call|invoke)\s+(.*)")
TERMINATOR_BR_UNCOND = re.compile(r"^\s*br\s+label\s+%([a-zA-Z0-9_$.]+)")
TERMINATOR_BR_COND = re.compile(r"^\s*br\s+i1\s+([^,]+),\s*label\s+%([a-zA-Z0-9_$.]+),\s*label\s+%([a-zA-Z0-9_$.]+)")
TERMINATOR_SWITCH = re.compile(r"label\s+%([a-zA-Z0-9_$.]+)")
TERMINATOR_INVOKE = re.compile(r"to\s+label\s+%([a-zA-Z0-9_$.]+)\s+unwind\s+label\s+%([a-zA-Z0-9_$.]+)")
PHI_PAIR_PATTERN = re.compile(r"\[\s*([^,]+),\s*%([a-zA-Z0-9_$.]+)\s*\]")


def parse_instruction(raw_line: str, line_number: int = 0) -> LLVMInstruction:
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

    return LLVMInstruction(
        raw=raw_line,
        opcode=opcode,
        dest=dest,
        args=args,
        phi_incoming=phi_incoming,
        line_number=line_number,
    )
