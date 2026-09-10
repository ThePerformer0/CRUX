#!/usr/bin/env python3
"""Evaluates and scores LLM responses against benchmark ground truth."""

import os
import re
from pathlib import Path

BASE_DIR = Path(__file__).parent
BENCHMARKS_DIR = BASE_DIR / "benchmarks"
RESULTS_DIR = BASE_DIR / "results"

LEVEL_DIRS = [
    ("level_0_trivial", "level_0"),
    ("level_1_basic", "level_1"),
    ("level_2_intermediate", "level_2"),
    ("level_3_advanced", "level_3"),
    ("level_4_expert", "level_4"),
]

def get_expected_status(level_dir_name: str, test_num: str) -> str:
    lvl_path = BENCHMARKS_DIR / level_dir_name
    for tdir in lvl_path.iterdir():
        if tdir.is_dir() and f"test_{test_num}" in tdir.name:
            exp_file = tdir / "EXPECTED.md"
            if exp_file.exists():
                text = exp_file.read_text(encoding="utf-8")
                m = re.search(r"Status:\s*([A-Z_ ]+)", text)
                if m:
                    return m.group(1).strip()
    return "UNKNOWN"

def parse_model_result(response_path: Path) -> str:
    if not response_path.exists() or response_path.stat().st_size == 0:
        return "EMPTY"
    text = response_path.read_text(encoding="utf-8")
    m = re.search(r"Result:\s*\*{0,2}(USELESS|SEMANTICALLY USELESS|NECESSARY)", text, re.IGNORECASE)
    if m:
        return m.group(1).upper().strip()
    return "UNKNOWN"

def main():
    models = [d.name for d in sorted(RESULTS_DIR.iterdir()) if d.is_dir()]
    
    print(f"{'='*70}")
    print("CRUX / DLock - LLM BENCHMARK EVALUATION")
    print(f"{'='*70}\n")
    
    results_summary = {}
    
    for model in models:
        scores = {}
        total_correct = 0
        total_tests = 0
        empty_count = 0
        
        for lvl_name, lvl_code in LEVEL_DIRS:
            correct_in_level = 0
            tests_in_level = 0
            for test_idx in ["01", "02", "03"]:
                exp = get_expected_status(lvl_name, test_idx)
                resp_file = RESULTS_DIR / model / lvl_code / f"test_{test_idx}" / "response.md"
                pred = parse_model_result(resp_file)
                
                tests_in_level += 1
                total_tests += 1
                
                if pred == "EMPTY":
                    empty_count += 1
                elif pred == exp or (exp in ["USELESS", "SEMANTICALLY USELESS"] and pred in ["USELESS", "SEMANTICALLY USELESS"]):
                    correct_in_level += 1
                    total_correct += 1
            
            scores[lvl_code] = f"{correct_in_level}/{tests_in_level}"
            
        pct = (total_correct / total_tests) * 100 if total_tests > 0 else 0
        results_summary[model] = {
            "scores": scores,
            "total": f"{total_correct}/{total_tests}",
            "pct": f"{pct:.1f}%",
            "empty": empty_count
        }

    # Print Markdown Table
    print("| Modèle testé | N0 | N1 | N2 | N3 | N4 | Score Total | Statut |")
    print("|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|")
    for model, data in results_summary.items():
        s = data["scores"]
        status_str = f"{15 - data['empty']}/15 remplis" if data["empty"] > 0 else "Complet"
        print(f"| **{model}** | {s['level_0']} | {s['level_1']} | {s['level_2']} | {s['level_3']} | {s['level_4']} | **{data['total']}** ({data['pct']}) | {status_str} |")
    print()

if __name__ == "__main__":
    main()
