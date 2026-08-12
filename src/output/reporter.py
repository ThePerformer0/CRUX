"""JSON Report Generator.

Formats analysis results, summary statistics, flagged lock sites, and warnings into
the standardized JSON report structure.
"""

import json
from typing import Dict, List, Any
from src.core.lock_site import LockSite
from src.core.lsg import LockSiteGraph, EdgeKind
from src.output.scorer import compute_confidence_score, suggest_fix


def generate_report(sites: List[LockSite], lsg: LockSiteGraph,
                    llvm_ir_file: str, analysis_time: float,
                    smt_enabled: bool = True, min_score: float = 0.0) -> Dict[str, Any]:
    """Generates the standardized Crux analysis report dictionary.

    Args:
        sites: List of evaluated LockSite objects.
        lsg: LockSiteGraph instance.
        llvm_ir_file: Name/path of analyzed LLVM IR file.
        analysis_time: Duration of analysis in seconds.
        smt_enabled: Whether Z3 SMT validation was enabled.
        min_score: Minimum confidence score threshold for reported useless sites.

    Returns:
        Structured dictionary matching Crux JSON report schema.
    """
    total_sites = len(sites)
    useless_candidates = [s for s in sites if s.is_useless]

    # Calculate confidence scores and fixes
    for site in useless_candidates:
        site.confidence_score = compute_confidence_score(site, lsg)
        site.suggested_fix = suggest_fix(site)

    # Filter candidates above min_score threshold
    reported_useless = [s for s in useless_candidates if s.confidence_score >= min_score]
    useful_count = total_sites - len(reported_useless)

    # Count graph edge types
    share_edges = 0
    nest_edges = 0
    hb_edges = 0

    for _, _, data in lsg.graph.edges(data=True):
        kind = data.get("kind")
        if kind == EdgeKind.SHARE:
            share_edges += 1
        elif kind == EdgeKind.NEST:
            nest_edges += 1
        elif kind == EdgeKind.HB:
            hb_edges += 1

    # Format useless site entries
    useless_list: List[Dict[str, Any]] = []
    for s in reported_useless:
        useless_list.append({
            "id": s.site_id,
            "confidence_score": s.confidence_score,
            "mutex_name": s.mutex_name,
            "mutex_canonical_id": s.mutex_canonical_id,
            "function": s.function,
            "source_file": s.source_file,
            "lock_source_line": s.lock_source_line,
            "unlock_source_lines": s.unlock_source_lines,
            "reasons": s.reasons,
            "reads": sorted(list(s.reads)),
            "writes": sorted(list(s.writes)),
            "transitive_reads": sorted(list(s.transitive_reads)),
            "transitive_writes": sorted(list(s.transitive_writes)),
            "share_edges_count": 1 if lsg.has_share_edge(s.site_id) else 0,
            "smt_path_feasible": s.smt_confirmed,
            "suggested_fix": s.suggested_fix,
        })

    warnings: List[str] = []
    indirect_site_count = sum(1 for s in sites if s.has_indirect_calls)
    if indirect_site_count > 0:
        warnings.append(f"{indirect_site_count} sites contain unresolved indirect calls (CHA fallback applied).")

    report: Dict[str, Any] = {
        "metadata": {
            "tool": "crux",
            "version": "3.0",
            "llvm_ir_file": llvm_ir_file,
            "analysis_time_seconds": round(analysis_time, 2),
            "alias_analysis": "field-based",
            "interprocedural": True,
            "smt_enabled": smt_enabled,
        },
        "summary": {
            "total_sites": total_sites,
            "useless_sites": len(reported_useless),
            "useful_sites": useful_count,
            "edges": {
                "share": share_edges,
                "nest": nest_edges,
                "hb": hb_edges,
            },
        },
        "useless_sites": useless_list,
        "warnings": warnings,
    }

    return report
