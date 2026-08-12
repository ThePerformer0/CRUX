"""Self-contained multi-threaded Memcached benchmark script for CRUX ablation studies.

Measures Throughput (QPS / ops/sec) and Latency (avg, p50, p95, p99) under heavy concurrent load.
"""

import time
import socket
import threading
import numpy as np
from typing import List


def memcached_worker(host: str, port: int, num_ops: int, thread_id: int, latencies: List[float]) -> None:
    """Worker thread performing GET and SET operations over raw TCP socket."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))

        key = f"crux_key_{thread_id}".encode("utf-8")
        val = b"x" * 128
        set_cmd = f"set crux_key_{thread_id} 0 0 128\r\n".encode("utf-8") + val + b"\r\n"
        get_cmd = f"get crux_key_{thread_id}\r\n".encode("utf-8")

        for i in range(num_ops):
            t0 = time.perf_counter()
            if i % 2 == 0:
                s.sendall(set_cmd)
                res = s.recv(128)
            else:
                s.sendall(get_cmd)
                res = s.recv(256)
            t1 = time.perf_counter()
            latencies.append((t1 - t0) * 1000.0)  # ms

        s.close()
    except Exception as e:
        print(f"[Worker Error] Thread {thread_id}: {e}")


def run_benchmark(host: str = "127.0.0.1", port: int = 11211, num_threads: int = 16, ops_per_thread: int = 5000) -> dict:
    print(f"[CRUX BENCHMARK] Running Memcached load test: {num_threads} threads, {ops_per_thread} ops/thread...")

    threads = []
    thread_latencies: List[List[float]] = [[] for _ in range(num_threads)]

    start_time = time.perf_counter()

    for i in range(num_threads):
        t = threading.Thread(target=memcached_worker, args=(host, port, ops_per_thread, i, thread_latencies[i]))
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
