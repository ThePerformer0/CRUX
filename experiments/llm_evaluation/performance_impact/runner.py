import os
import subprocess
import csv
import re

# Configuration
BENCHMARKS = [
    "l3_request_metrics",
    "l3_approximate_monitoring",
    "l4_degraded_mode",
    "l4_hierarchical_contract"
]
VARIANTS = ["v0", "v1"]
THREADS = [1, 2, 4, 8, 16, 32]
ITERATIONS = 10000000  # Default workload
REPEATS = 3
RESULTS_FILE = "results.csv"

def compile_benchmark(benchmark, variant):
    path = os.path.join(benchmark, variant)
    src_files = [f for f in os.listdir(path) if f.endswith(".c")]
    out_file = os.path.join(path, "bench")
    
    cmd = ["gcc", "-O2"] + [os.path.join(path, f) for f in src_files] + ["-o", out_file, "-lpthread"]
    print(f"Compiling {benchmark}/{variant}...")
    subprocess.run(cmd, check=True)
    return out_file

def run_benchmark(executable, threads):
    print(f"  Running with {threads} threads...")
    # Basic run for performance
    cmd = [executable, str(threads), str(ITERATIONS)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    output = result.stdout
    time_match = re.search(r"Time: ([\d.]+)", output)
    throughput_match = re.search(r"Throughput: ([\d.]+)", output)
    
    elapsed = float(time_match.group(1)) if time_match else 0.0
    throughput = float(throughput_match.group(1)) if throughput_match else 0.0
    
    # Run with strace to count futexes (system calls)
    # Note: This is only for Linux. On other OS, futex_count will be 0.
    futex_count = 0
    try:
        strace_cmd = ["strace", "-c", "-e", "trace=futex", executable, str(threads), str(ITERATIONS)]
        strace_result = subprocess.run(strace_cmd, capture_output=True, text=True)
        futex_match = re.search(r"futex\s+\d+\s+\d+\s+\d+\s+\d+\s+(\d+)", strace_result.stderr)
        if futex_match:
            futex_count = int(futex_match.group(1))
    except FileNotFoundError:
        pass # strace not found

    return elapsed, throughput, futex_count

def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    with open(RESULTS_FILE, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["benchmark", "variant", "threads", "time", "throughput", "futex_count"])
        
        for bench in BENCHMARKS:
            for var in VARIANTS:
                try:
                    exe = compile_benchmark(bench, var)
                    for t in THREADS:
                        times, throughs, futexes = [], [], []
                        for _ in range(REPEATS):
                            elapsed, throughput, futex = run_benchmark(exe, t)
                            times.append(elapsed)
                            throughs.append(throughput)
                            futexes.append(futex)
                        
                        # Average of repeats
                        avg_time = sum(times) / len(times)
                        avg_through = sum(throughs) / len(throughs)
                        avg_futex = sum(futexes) / len(futexes)
                        
                        writer.writerow([bench, var, t, avg_time, avg_through, avg_futex])
                        f.flush()
                except Exception as e:
                    print(f"Error processing {bench}/{var}: {e}")

if __name__ == "__main__":
    main()
