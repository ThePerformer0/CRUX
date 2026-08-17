"""CRUX — Concurrence Ressources Unused eXtractor.

Main CLI entrypoint for Crux static analyzer.
Parses command line arguments, orchestrates the 10 analysis phases,
and outputs the JSON analysis report.
"""

import os
import sys
import time
import json
import argparse
from typing import Set, Optional
from src.frontend.call_graph import build_call_graph
from src.frontend.cfg_builder import build_cfgs
from src.analysis.alias_resolver import AliasResolver
from src.analysis.lockset_analyzer import LocksetAnalyzer
from src.analysis.site_extractor import SiteExtractor
from src.core.lsg import LockSiteGraph
from src.core.classifier import Classifier
from src.validation.smt_validator import SMTValidator
from src.output.reporter import generate_report


def main() -> None:
    """Main CLI entrypoint for Crux static analysis tool."""
    parser = argparse.ArgumentParser(
        description="CRUX — Concurrence Ressources Unused eXtractor (LLVM IR Static Lock Analyzer)"
    )
    parser.add_argument("llvm_ir_file", type=str, help="Path to textual LLVM IR file (.ll)")
    parser.add_argument("-o", "--output", type=str, default="report.json", help="Path for JSON output report")
    parser.add_argument("--smt", action="store_true", default=True, help="Enable Z3 SMT path validation (default: True)")
    parser.add_argument("--no-smt", action="store_false", dest="smt", help="Disable Z3 SMT path validation")
    parser.add_argument("--min-score", type=float, default=0.0, help="Minimum confidence score threshold (0.0 to 1.0)")
    parser.add_argument("--custom-locks", type=str, default="", help="Comma-separated list of custom lock functions")
    parser.add_argument("--custom-unlocks", type=str, default="", help="Comma-separated list of custom unlock functions")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose log output")

    args = parser.parse_args()

    custom_locks: Set[str] = set(args.custom_locks.split(",")) if args.custom_locks else set()
    custom_unlocks: Set[str] = set(args.custom_unlocks.split(",")) if args.custom_unlocks else set()

    if args.verbose:
        print(f"[CRUX] Analyzing LLVM IR file: {args.llvm_ir_file}")

    start_time = time.time()

    try:
        with open(args.llvm_ir_file, "r", encoding="utf-8") as f:
            llvm_ir_text = f.read()
    except Exception as e:
        print(f"[CRUX ERROR] Failed to read file {args.llvm_ir_file}: {e}", file=sys.stderr)
        sys.exit(1)

    # Pipeline Phase 1: Call Graph
    call_graph = build_call_graph(llvm_ir_text)

    # Pipeline Phase 2: CFG Builder
    cfgs = build_cfgs(llvm_ir_text)

    # Pipeline Phase 3: Field-Based Alias Analyzer
    alias_resolver = AliasResolver()
    alias_resolver.analyze_cfgs(cfgs)

    # Pipeline Phase 4: Lockset Analyzer
    lockset_analyzer = LocksetAnalyzer(alias_resolver, custom_locks=custom_locks, custom_unlocks=custom_unlocks)

    # Pipeline Phase 5: Site Characterizer
    site_extractor = SiteExtractor(alias_resolver, call_graph, lockset_analyzer)
    sites = site_extractor.extract_sites(cfgs)

    # Pipeline Phase 6: LSG Builder
    lsg = LockSiteGraph(call_graph)
    lsg.build_graph(sites)

    # Pipeline Phase 7: Classifier
    classifier = Classifier(lsg)
    classifier.classify_all()

    # Pipeline Phase 8: SMT Validator
    if args.smt:
        smt_validator = SMTValidator()
        smt_validator.validate_sites(sites)

    elapsed_time = time.time() - start_time

    # Pipeline Phase 9: Scorer & Reporter
    report = generate_report(sites, lsg, args.llvm_ir_file, elapsed_time, smt_enabled=args.smt, min_score=args.min_score)

    if args.output:
        out_dir = os.path.dirname(args.output)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        if args.verbose:
            print(f"[CRUX] Report written to: {args.output}")
    else:
        print(json.dumps(report, indent=2, ensure_ascii=False))

    if args.verbose:
        summary = report["summary"]
        print(f"[CRUX SUMMARY] Total sites: {summary['total_sites']} | Useless: {summary['useless_sites']} | Useful: {summary['useful_sites']}")


if __name__ == "__main__":
    main()
