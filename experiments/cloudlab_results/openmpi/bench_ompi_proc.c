#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <pthread.h>
#include <time.h>
#include <unistd.h>

#define NUM_THREADS 16
#define NUM_ITERS 1000000

typedef struct proc_entry {
    uint32_t jobid;
    uint32_t vpid;
    struct proc_entry *next;
} proc_entry_t;

static proc_entry_t *g_proc_list = NULL;
static pthread_mutex_t g_proc_lock = PTHREAD_MUTEX_INITIALIZER;

static inline double get_time_sec(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec * 1e-9;
}

// Simulated ompi_proc_find (Baseline with mutex lock)
static inline proc_entry_t *ompi_proc_find_baseline(uint32_t jobid, uint32_t vpid) {
    proc_entry_t *proc, *rproc = NULL;
    pthread_mutex_lock(&g_proc_lock);
    for (proc = g_proc_list; proc != NULL; proc = proc->next) {
        if (proc->jobid == jobid && proc->vpid == vpid) {
            rproc = proc;
            break;
        }
    }
    pthread_mutex_unlock(&g_proc_lock);
    return rproc;
}

// Simulated ompi_proc_find (Patched lock-free read)
static inline proc_entry_t *ompi_proc_find_patched(uint32_t jobid, uint32_t vpid) {
    proc_entry_t *proc, *rproc = NULL;
    for (proc = g_proc_list; proc != NULL; proc = proc->next) {
        if (proc->jobid == jobid && proc->vpid == vpid) {
            rproc = proc;
            break;
        }
    }
    return rproc;
}

static int g_mode = 0; // 0 = baseline, 1 = patched

void *worker(void *arg) {
    uint32_t target_vpid = (uint32_t)(uintptr_t)arg;
    for (int i = 0; i < NUM_ITERS; i++) {
        proc_entry_t *res;
        if (g_mode == 0) {
            res = ompi_proc_find_baseline(100, target_vpid);
        } else {
            res = ompi_proc_find_patched(100, target_vpid);
        }
        if (!res) {
            fprintf(stderr, "Error finding proc\n");
        }
    }
    return NULL;
}

int main(int argc, char **argv) {
    if (argc > 1) {
        g_mode = atoi(argv[1]);
    }

    // Initialize list with 16 simulated procs
    proc_entry_t procs[NUM_THREADS];
    for (int i = 0; i < NUM_THREADS; i++) {
        procs[i].jobid = 100;
        procs[i].vpid = i;
        procs[i].next = (i < NUM_THREADS - 1) ? &procs[i + 1] : NULL;
    }
    g_proc_list = &procs[0];

    pthread_t threads[NUM_THREADS];
    double t0 = get_time_sec();
    for (int i = 0; i < NUM_THREADS; i++) {
        pthread_create(&threads[i], NULL, worker, (void *)(uintptr_t)i);
    }
    for (int i = 0; i < NUM_THREADS; i++) {
        pthread_join(threads[i], NULL);
    }
    double t1 = get_time_sec();

    double elapsed = t1 - t0;
    double total_ops = (double)NUM_THREADS * NUM_ITERS;
    double ops_per_sec = total_ops / elapsed;

    printf("Mode: %s | Time: %.6f s | Throughput: %.2f M ops/s\n",
           (g_mode == 0) ? "BASELINE" : "PATCHED", elapsed, ops_per_sec / 1e6);

    return 0;
}
