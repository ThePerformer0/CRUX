"""CloudLab Automated 15-Run Benchmark Script for Memcached Ablation Experiments.

Specifically tests 1 SINGLE LOCK SITE: s58 (items.c: lru_total_bumps_dropped).
Starts Memcached with -m 64 (64 MB RAM limit) to force continuous LRU eviction.

Automates:
1. 15 independent baseline runs of Memcached 1.6.22 (-m 64)
2. Applies CRUX patch ONLY on site s58
3. 15 independent ablation runs of patched Memcached 1.6.22 (-m 64)
4. Exports raw results to ~/results/memcached_15_runs.csv for SCP download
"""

import os
import csv
import time
import subprocess


def run_benchmark_iteration(run_id: int, run_type: str, memcached_dir: str, crux_dir: str) -> dict:
    """Launches Memcached with -m 64 (small RAM limit for LRU eviction storm), runs benchmark.py."""
    print(f"  [{run_type.upper()} Run {run_id:02d}/15] Starting Memcached (-m 64)...", end="", flush=True)

    # Kill any existing memcached instance
    subprocess.run("killall -9 memcached 2>/dev/null", shell=True)
    time.sleep(1)

    # Start Memcached server with 64MB RAM limit to force active LRU evictions
    mc_cmd = f"cd {memcached_dir} && ./memcached -t 4 -m 64 -p 11211 &"
    subprocess.run(mc_cmd, shell=True)
    time.sleep(2)

    # Run Python benchmark
    bench_cmd = f"python3 {crux_dir}/benchmark.py"
    t0 = time.time()
    res = subprocess.run(bench_cmd, shell=True, capture_output=True, text=True)
    t1 = time.time()

    # Kill Memcached server
    subprocess.run("killall -9 memcached 2>/dev/null", shell=True)

    # Parse metrics from stdout
    output = res.stdout
    metrics = {"run_id": run_id, "run_type": run_type, "qps": 0.0, "avg_lat": 0.0, "p50_lat": 0.0, "p95_lat": 0.0, "p99_lat": 0.0}

    for line in output.splitlines():
        if "Throughput (QPS)" in line:
            metrics["qps"] = float(line.split(":")[1].strip().split()[0])
        elif "Avg Latency" in line:
            metrics["avg_lat"] = float(line.split(":")[1].strip().split()[0])
        elif "p50 Latency" in line:
            metrics["p50_lat"] = float(line.split(":")[1].strip().split()[0])
        elif "p95 Latency" in line:
            metrics["p95_lat"] = float(line.split(":")[1].strip().split()[0])
        elif "p99 Latency" in line:
            metrics["p99_lat"] = float(line.split(":")[1].strip().split()[0])

    print(f" Completed! QPS: {metrics['qps']:.2f} (Time: {t1-t0:.1f}s)")
    return metrics


def apply_s58_patch(memcached_dir: str):
    """Applies CRUX ablation patch on 1 SINGLE LOCK SITE: s58 (items.c: lru_total_bumps_dropped)."""
    items_path = os.path.join(memcached_dir, "items.c")
    with open(items_path, "r", encoding="utf-8") as f:
        content = f.read()

    target = """static uint64_t lru_total_bumps_dropped(void) {
    uint64_t total = 0;
    lru_bump_buf *b;
    pthread_mutex_lock(&bump_buf_lock);
    for (b = bump_buf_head; b != NULL; b=b->next) {
        pthread_mutex_lock(&b->mutex);
        total += b->dropped;
        pthread_mutex_unlock(&b->mutex);
    }
    pthread_mutex_unlock(&bump_buf_lock);
    return total;
}"""

    replacement = """static uint64_t lru_total_bumps_dropped(void) {
    uint64_t total = 0;
    lru_bump_buf *b;
    pthread_mutex_lock(&bump_buf_lock);
    for (b = bump_buf_head; b != NULL; b=b->next) {
        /* CRUX ABLATION s58 ONLY: Redundant b->mutex removed */
        total += b->dropped;
    }
    pthread_mutex_unlock(&bump_buf_lock);
    return total;
}"""

    if target in content:
        with open(items_path, "w", encoding="utf-8") as f:
            f.write(content.replace(target, replacement))
        print("\n[PATCH SUCCESS] Patch s58 (1 SINGLE LOCK SITE) applied to items.c!")
    else:
        print("\n[PATCH NOTICE] Code target already modified or not matched.")

    # Recompile Memcached
    print("[RECOMPILE] Rebuilding Memcached with make -j$(nproc)...")
    subprocess.run(f"cd {memcached_dir} && make -j$(nproc)", shell=True)


def main():
    home = os.path.expanduser("~")
    memcached_dir = os.path.join(home, "memcached-1.6.22")
    crux_dir = os.path.join(home, "crux")
    results_dir = os.path.join(home, "results")
    os.makedirs(results_dir, exist_ok=True)

    csv_output_path = os.path.join(results_dir, "memcached_15_runs.csv")

    all_metrics = []

    print("======================================================================")
    print("      CLOUDLAB MEMCACHED 15-RUN EVICTION EXPERIMENT (SITE s58 ONLY)")
    print("======================================================================")

    # 1. BASELINE RUNS (Unpatched, -m 64)
    print("\n--- PHASE 1: Running 15 BASELINE Iterations (Unpatched, -m 64 MB) ---")
    for i in range(1, 16):
        m = run_benchmark_iteration(i, "baseline", memcached_dir, crux_dir)
        all_metrics.append(m)

    # 2. APPLY PATCH ON 1 SINGLE LOCK SITE s58
    print("\n--- PHASE 2: Applying Patch ONLY on Site s58 (items.c: lru_total_bumps_dropped) ---")
    apply_s58_patch(memcached_dir)

    # 3. ABLATION RUNS (Patched s58, -m 64)
    print("\n--- PHASE 3: Running 15 ABLATION Iterations (Patched Site s58 ONLY, -m 64 MB) ---")
    for i in range(1, 16):
        m = run_benchmark_iteration(i, "ablation", memcached_dir, crux_dir)
        all_metrics.append(m)

    # 4. EXPORT TO CSV
    fieldnames = ["run_id", "run_type", "qps", "avg_lat", "p50_lat", "p95_lat", "p99_lat"]
    with open(csv_output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_metrics)

    print("\n======================================================================")
    print(f"[SUCCESS] All 30 runs completed! Data exported to: {csv_output_path}")
    print(f"You can now copy it to your PC with:")
    print(f"  scp Jim0@amd248.utah.cloudlab.us:{csv_output_path} c:\\Users\\performer\\Desktop\\Crux\\experiments\\memcached\\")
    print("======================================================================")


if __name__ == "__main__":
    main()
