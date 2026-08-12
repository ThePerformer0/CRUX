"""Control Flow Graph (CFG) Builder.

Constructs basic blocks and successor/predecessor relationships for each
parsed LLVM function, parsing control flow branch/switch instructions and phi nodes.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from src.frontend.parser import (
    LLVMInstruction,
    parse_instruction,
    TERMINATOR_BR_UNCOND,
    TERMINATOR_BR_COND,
    TERMINATOR_SWITCH,
    TERMINATOR_INVOKE,
    FUNC_DEF_PATTERN,
)


@dataclass
class BasicBlock:
    """Represents a basic block in an LLVM IR function."""
    name: str
    instructions: List[LLVMInstruction] = field(default_factory=list)
    successors: List[str] = field(default_factory=list)
    predecessors: List[str] = field(default_factory=list)


@dataclass
class CFG:
    """Represents the Control Flow Graph of a single LLVM function."""
    function_name: str
    entry_block: str
    blocks: Dict[str, BasicBlock] = field(default_factory=dict)

    def get_block(self, name: str) -> Optional[BasicBlock]:
        """Returns the BasicBlock with the given name."""
        return self.blocks.get(name)


LABEL_PATTERN = re.compile(r"^\s*([a-zA-Z0-9_$.]+):\s*(?:;\s*<label>:\d+)?")


def build_cfgs(llvm_ir_text: str) -> Dict[str, CFG]:
    """Parses LLVM IR text and builds CFGs for all defined functions.

    Args:
        llvm_ir_text: The complete textual LLVM IR string (.ll).

    Returns:
        Dictionary mapping function name -> CFG instance.
    """
    cfgs: Dict[str, CFG] = {}
    lines = llvm_ir_text.splitlines()

    i = 0
    num_lines = len(lines)

    while i < num_lines:
        line = lines[i]
        def_match = FUNC_DEF_PATTERN.search(line)

        if def_match:
            func_name = def_match.group(1)
            blocks: Dict[str, BasicBlock] = {}
            current_block_name = "entry"
            current_instructions: List[LLVMInstruction] = []

            i += 1
            while i < num_lines and lines[i].strip() != "}":
                curr_line = lines[i]
                clean = curr_line.strip()

                if not clean or clean.startswith(";"):
                    i += 1
                    continue

                label_match = LABEL_PATTERN.match(curr_line)
                if label_match:
                    # Save current basic block if it has instructions or was previously created
                    if current_block_name not in blocks:
                        blocks[current_block_name] = BasicBlock(
                            name=current_block_name,
                            instructions=current_instructions,
                        )
                    else:
                        blocks[current_block_name].instructions.extend(current_instructions)

                    current_block_name = label_match.group(1)
                    current_instructions = []
                    i += 1
                    continue

                # Accumulate multi-line switch instructions
                if "switch " in clean and "[" in clean and "]" not in clean:
                    accumulated = [clean]
                    i += 1
                    while i < num_lines and "]" not in lines[i]:
                        accumulated.append(lines[i].strip())
                        i += 1
                    if i < num_lines:
                        accumulated.append(lines[i].strip())
                    curr_line = " ".join(accumulated)

                inst = parse_instruction(curr_line, line_number=i + 1)
                current_instructions.append(inst)
                i += 1

            # Save the final block of the function
            if current_block_name not in blocks:
                blocks[current_block_name] = BasicBlock(
                    name=current_block_name,
                    instructions=current_instructions,
                )
            else:
                blocks[current_block_name].instructions.extend(current_instructions)

            # Determine entry block name (first created block in order)
            entry_name = "entry"
            if "entry" not in blocks and blocks:
                entry_name = next(iter(blocks.keys()))

            cfg = CFG(function_name=func_name, entry_block=entry_name, blocks=blocks)
            _compute_cfg_edges(cfg)
            cfgs[func_name] = cfg

        i += 1

    return cfgs


def _compute_cfg_edges(cfg: CFG) -> None:
    """Computes successors and predecessors for all BasicBlocks in a CFG."""
    for block_name, block in cfg.blocks.items():
        if not block.instructions:
            continue

        last_inst = block.instructions[-1]
        raw_last = last_inst.raw.strip()

        # 1. Unconditional branch: br label %target
        uncond_match = TERMINATOR_BR_UNCOND.match(raw_last)
        if uncond_match:
            block.successors.append(uncond_match.group(1))
            continue

        # 2. Conditional branch: br i1 %cond, label %true_b, label %false_b
        cond_match = TERMINATOR_BR_COND.match(raw_last)
        if cond_match:
            block.successors.append(cond_match.group(2))
            block.successors.append(cond_match.group(3))
            continue

        # 3. Invoke: invoke ... to label %normal unwind label %unwind
        invoke_match = TERMINATOR_INVOKE.search(raw_last)
        if invoke_match:
            block.successors.append(invoke_match.group(1))
            block.successors.append(invoke_match.group(2))
            continue

        # 4. Switch instruction: switch i32 %val, label %default [ ... ]
        if last_inst.opcode == "switch":
            targets = TERMINATOR_SWITCH.findall(raw_last)
            for target in targets:
                if target not in block.successors:
                    block.successors.append(target)
            continue

    # Compute predecessors from successors
    for block_name, block in cfg.blocks.items():
        for succ_name in block.successors:
            if succ_name in cfg.blocks:
                succ_block = cfg.blocks[succ_name]
                if block_name not in succ_block.predecessors:
                    succ_block.predecessors.append(block_name)
