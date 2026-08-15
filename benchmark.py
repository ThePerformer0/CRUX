"""High-Eviction Multi-Threaded Memcached Benchmark Script for CRUX Ablation Experiments.

Specifically designed to force intensive LRU eviction activity, calling
lru_total_bumps_dropped() on every request to measure the isolated impact of site s58.
"""

import time
import socket
import threading
import numpy as np
from typing import List


def memcached_eviction_worker(host: str, port: int, num_ops: int, thread_id: int, latencies: List[float]) -> None:
    """Worker thread performing continuous SET operations with large payloads to force LRU evictions."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))

        payload = b"X" * 32768  # 32 KB payload per item to fill 64 MB RAM quickly

        for i in range(num_ops):
            key = f"crux_evict_t{thread_id}_k{i}".encode("utf-8")
            set_cmd = f"set crux_evict_t{thread_id}_k{i} 0 0 32768\r\n".encode("utf-8") + payload + b"\r\n"

            t0 = time.perf_counter()
            s.sendall(set_cmd)
            res = s.recv(128)
            t1 = time.perf_counter()

            latencies.append((t1 - t0) * 1000.0)  # ms

        s.close()
    except Exception as e:
        print(f"[Worker Error] Thread {thread_id}: {e}")


def run_benchmark(host: str = "127.0.0.1", port: int = 11211, num_threads: int = 16, ops_per_thread: int = 2500) -> dict:
    print(f"[CRUX EVICTION BENCHMARK] Running Memcached LRU Eviction load test: {num_threads} threads, {ops_per_thread} ops/thread (32KB payloads)...")

    threads = []
    thread_latencies: List[List[float]] = [[] for _ in range(num_threads)]

    start_time = time.perf_counter()

    for i in range(num_threads):
        t = threading.Thread(target=memcached_eviction_worker, args=(host, port, ops_per_thread, i, thread_latencies[i]))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    total_time = time.perf_counter() - start_time
    all_latencies = [lat for t_lats in thread_latencies for lat in t_lats]

    total_ops = len(all_latencies)
    qps = total_ops / total_time if total_time > 0 else 0

    p50 = np.percentile(all_latencies, 50) if all_latencies else 0
    p95 = np.percentile(all_latencies, 95) if all_latencies else 0
    p99 = np.percentile(all_latencies, 99) if all_latencies else 0
    avg_lat = sum(all_latencies) / len(all_latencies) if all_latencies else 0

    results = {
        "total_ops": total_ops,
        "total_time_sec": round(total_time, 3),
        "qps": round(qps, 2),
        "avg_latency_ms": round(avg_lat, 3),
        "p50_latency_ms": round(p50, 3),
        "p95_latency_ms": round(p95, 3),
        "p99_latency_ms": round(p99, 3),
    }

    print("================ CRUX BENCHMARK RESULTS ================")
    print(f"Total Operations : {results['total_ops']}")
    print(f"Elapsed Time     : {results['total_time_sec']} s")
    print(f"Throughput (QPS) : {results['qps']} ops/sec")
    print(f"Avg Latency      : {results['avg_latency_ms']} ms")
    print(f"p50 Latency      : {results['p50_latency_ms']} ms")
    print(f"p95 Latency      : {results['p95_latency_ms']} ms")
    print(f"p99 Latency      : {results['p99_latency_ms']} ms")
    print("========================================================")

    return results


if __name__ == "__main__":
    run_benchmark()
