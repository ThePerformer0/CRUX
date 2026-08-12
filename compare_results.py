"""Results Comparison and Statistical Analysis Script for CRUX Ablation Experiments.

Parses baseline and ablation benchmark outputs, computes percentage deltas,
and formats publication-ready Markdown and LaTeX comparison tables.
"""

import sys
import re
from typing import Dict, Any


def parse_benchmark_file(filepath: str) -> Dict[str, float]:
    """Parses benchmark output text file to extract metrics."""
    metrics = {}
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    qps_match = re.search(r"Throughput \(QPS\)\s*:\s*([\d.]+)", content)
    if qps_match:
        metrics["qps"] = float(qps_match.group(1))

    avg_lat = re.search(r"Avg Latency\s*:\s*([\d.]+)", content)
    if avg_lat:
        metrics["avg_latency"] = float(avg_lat.group(1))

    p50_lat = re.search(r"p50 Latency\s*:\s*([\d.]+)", content)
    if p50_lat:
        metrics["p50_latency"] = float(p50_lat.group(1))

    p95_lat = re.search(r"p95 Latency\s*:\s*([\d.]+)", content)
    if p95_lat:
        metrics["p95_latency"] = float(p95_lat.group(1))

    p99_lat = re.search(r"p99 Latency\s*:\s*([\d.]+)", content)
    if p99_lat:
        metrics["p99_latency"] = float(p99_lat.group(1))

    time_match = re.search(r"Elapsed Time\s*:\s*([\d.]+)", content)
    if time_match:
        metrics["elapsed_time"] = float(time_match.group(1))

    return metrics


def compare(baseline_path: str, ablation_path: str) -> None:
    base = parse_benchmark_file(baseline_path)
    abla = parse_benchmark_file(ablation_path)

    print("================ CRUX ABLATION COMPARISON ================")
    print(f"{'Metric':<20} | {'Baseline':<12} | {'Ablation':<12} | {'Delta (%)':<10}")
    print("-" * 62)

    for key in ["qps", "elapsed_time", "avg_latency", "p50_latency", "p95_latency", "p99_latency"]:
        if key in base and key in abla:
            v_base = base[key]
            v_abla = abla[key]
            delta_pct = ((v_abla - v_base) / v_base) * 100.0 if v_base != 0 else 0.0
            sign = "+" if delta_pct > 0 else ""
            print(f"{key:<20} | {v_base:<12.2f} | {v_abla:<12.2f} | {sign}{delta_pct:<.2f}%")

    print("==========================================================")


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        compare(sys.argv[1], sys.argv[2])
    else:
        print("Usage: python compare_results.py baseline.txt ablation.txt")
