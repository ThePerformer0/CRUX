#!/usr/bin/env python3
"""Generates ready-to-copy standardized prompt files for each of the 15 benchmark test cases."""

import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
BENCHMARKS_DIR = BASE_DIR / "benchmarks"
PROMPTS_DIR = BASE_DIR / "prompts"

PROMPTS_DIR.mkdir(parents=True, exist_ok=True)

PROMPT_HEADER = """Given the following C program, determine whether the lock(s) used are strictly necessary for program correctness, or if they are useless (logically or semantically). Format your response as: Result: [USELESS | SEMANTICALLY USELESS | NECESSARY], followed by a detailed technical justification.

"""

LEVEL_MAP = {
    "level_0_trivial": "level_0",
    "level_1_basic": "level_1",
    "level_2_intermediate": "level_2",
    "level_3_advanced": "level_3",
    "level_4_expert": "level_4",
}

count = 0
for lvl_dir in sorted(BENCHMARKS_DIR.iterdir()):
    if not lvl_dir.is_dir() or lvl_dir.name not in LEVEL_MAP:
        continue
    lvl_code = LEVEL_MAP[lvl_dir.name]
    for test_dir in sorted(lvl_dir.iterdir()):
        if not test_dir.is_dir():
            continue
        test_code = test_dir.name.split("_")[1]  # '01', '02', '03'
        
        src_dir = test_dir / "src"
        if not src_dir.exists():
            continue
            
        code_blocks = []
        for fpath in sorted(src_dir.rglob("*")):
            if fpath.is_file() and fpath.suffix in [".c", ".h"]:
                rel = fpath.relative_to(src_dir)
                content = fpath.read_text(encoding="utf-8")
                code_blocks.append(f"// File: {rel}\n{content}")
                
        full_code = "\n\n".join(code_blocks)
        prompt_content = f"{PROMPT_HEADER}```c\n{full_code}\n```\n"
        
        out_file = PROMPTS_DIR / f"{lvl_code}_test_{test_code}.md"
        out_file.write_text(prompt_content, encoding="utf-8")
        count += 1

print(f"Generated {count} ready-to-use prompt files in {PROMPTS_DIR}")
