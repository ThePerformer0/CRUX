import pandas as pd
import matplotlib.pyplot as plt
import os

def plot_benchmark(df, benchmark, metric, ylabel):
    plt.figure(figsize=(10, 6))
    
    bench_df = df[df['benchmark'] == benchmark]
    
    for variant in bench_df['variant'].unique():
        var_df = bench_df[bench_df['variant'] == variant]
        plt.plot(var_df['threads'], var_df[metric], marker='o', label=f'Variant {variant}')
    
    plt.title(f'{benchmark.replace("_", " ").title()} - {ylabel}')
    plt.xlabel('Number of Threads')
    plt.ylabel(ylabel)
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.legend()
    
    filename = f"plot_{benchmark}_{metric}.png"
    plt.savefig(filename)
    print(f"Saved {filename}")
    plt.close()

def main():
    if not os.path.exists("results.csv"):
        print("Error: results.csv not found. Run runner.py first.")
        return

    df = pd.read_csv("results.csv")
    
    benchmarks = df['benchmark'].unique()
    metrics = [
        ('time', 'Execution Time (s)'),
        ('throughput', 'Throughput (ops/s)'),
        ('futex_count', 'Futex Syscalls')
    ]
    
    for bench in benchmarks:
        for metric, ylabel in metrics:
            plot_benchmark(df, bench, metric, ylabel)

if __name__ == "__main__":
    main()
