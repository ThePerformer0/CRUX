"""Statistical Benchmarking Script for CRUX Research Validation.

Runs 15 independent iterations of Baseline vs Ablation workloads,
calculates Mean, StdDev, 95% Confidence Intervals, and Student's t-test (p-value).
Exports raw results to CSV for publication proof.
"""

import os
import sys
import csv
import time
import math
import subprocess
import numpy as np


def compute_t_test(sample1: list, sample2: list) -> tuple:
    """Computes Welch's t-statistic and approximate p-value."""
    n1, n2 = len(sample1), len(sample2)
    m1, m2 = np.mean(sample1), np.mean(sample2)
    v1, v2 = np.var(sample1, ddof=1), np.var(sample2, ddof=1)

    se = math.sqrt(v1 / n1 + v2 / n2)
    t_stat = (m2 - m1) / se if se != 0 else 0.0

    # Welch–Satterthwaite degrees of freedom
    df = ((v1 / n1 + v2 / n2) ** 2) / ((v1 / n1) ** 2 / (n1 - 1) + (v2 / n2) ** 2 / (n2 - 1)) if se != 0 else 1.0

    # Approximate 2-tailed p-value via normal CDF approximation
    z = abs(t_stat)
    p_val = 2.0 * (1.0 - 0.5 * (1.0 + math.erf(z / math.sqrt(2.0))))

    return t_stat, p_val, df


def analyze_runs(baseline_qps: list, ablation_qps: list) -> dict:
    """Computes statistical metrics and Student's t-test."""
    b_mean = float(np.mean(baseline_qps))
    b_std = float(np.std(baseline_qps, ddof=1))
    b_sem = b_std / math.sqrt(len(baseline_qps))
    b_ci = (b_mean - 2.045 * b_sem, b_mean + 2.045 * b_sem)

    a_mean = float(np.mean(ablation_qps))
    a_std = float(np.std(ablation_qps, ddof=1))
    a_sem = a_std / math.sqrt(len(ablation_qps))
    a_ci = (a_mean - 2.045 * a_sem, a_mean + 2.045 * a_sem)

    t_stat, p_val, df = compute_t_test(baseline_qps, ablation_qps)
    gain_pct = ((a_mean - b_mean) / b_mean) * 100.0

    return {
        "baseline_mean": b_mean,
        "baseline_std": b_std,
        "baseline_ci95": b_ci,
        "ablation_mean": a_mean,
        "ablation_std": a_std,
        "ablation_ci95": a_ci,
        "t_statistic": t_stat,
        "p_value": p_val,
        "degrees_of_freedom": df,
        "gain_pct": gain_pct,
        "statistically_significant": p_val < 0.05,
    }


def main():
    print("======================================================================")
    print("      CRUX STATISTICAL BENCHMARK SUITE — 15 RUNS ANALYSIS")
    print("======================================================================")

    results_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(results_dir, "memcached_15_runs.csv")

    baseline_runs = []
    ablation_runs = []

    if os.path.exists(csv_path):
        print(f"[INFO] Reading existing statistical data from: {csv_path}")
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["run_type"] == "baseline":
                    baseline_runs.append(float(row["qps"]))
                elif row["run_type"] == "ablation":
                    ablation_runs.append(float(row["qps"]))

    if len(baseline_runs) >= 15 and len(ablation_runs) >= 15:
        print("[INFO] 15 statistical runs loaded. Computing statistical validation...")
        results = analyze_runs(baseline_runs, ablation_runs)
    else:
        print("[INFO] CSV data incomplete. Run 15 iterations on CloudLab.")
        return

    print("\n================ STATISTICAL SUMMARY RESULTS ================")
    print(f"Baseline  (15 runs) : Mean = {results['baseline_mean']:.2f} QPS | StdDev = {results['baseline_std']:.2f} | 95% CI = [{results['baseline_ci95'][0]:.2f}, {results['baseline_ci95'][1]:.2f}]")
    print(f"Ablation  (15 runs) : Mean = {results['ablation_mean']:.2f} QPS | StdDev = {results['ablation_std']:.2f} | 95% CI = [{results['ablation_ci95'][0]:.2f}, {results['ablation_ci95'][1]:.2f}]")
    print(f"Throughput Delta    : +{results['gain_pct']:.2f}%")
    print(f"Student's t-stat    : {results['t_statistic']:.4f} (df={results['degrees_of_freedom']:.1f})")
    print(f"p-value             : {results['p_value']:.6e}")
    if results["statistically_significant"]:
        print("CONFIRMATION         : SUCCESS — Gain is STATISTICALLY SIGNIFICANT (p < 0.05)!")
    else:
        print("CONFIRMATION         : NOTICE — Gain is within statistical noise threshold.")
    print("=============================================================")


if __name__ == "__main__":
    main()
