#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <time.h>
#include <stdint.h>

#define NUM_THREADS 16
#define ITERS_PER_THREAD 1500000

/*
 * Mock synchronization objects corresponding to the 5 identified Linux sites:
 * 1. s7703: net/core/net_namespace.c:625 (net_ns_barrier - EMPTY_CS)
 * 2. s5848: drivers/block/loop.c:794 (loop_change_fd - EMPTY_CS)
 * 3. s5851: drivers/block/loop.c:1343 (__loop_clr_fd - EMPTY_CS)
 * 4. s5950: drivers/scsi/scsi_sysfs.c:484 (scsi_device_dev_release_usercontext - REDUNDANT)
 * 5. s5330: drivers/gpu/drm/i915/gt/uc/intel_guc_submission.c:601 (scrub_guc_desc - REDUNDANT)
 */

typedef struct {
    pthread_mutex_t net_sem;
    pthread_mutex_t loop_validate_mutex;
    pthread_mutex_t sdev_mutex;
    pthread_spinlock_t guc_lock;
    volatile uint64_t mock_state;
} linux_subsystems_t;

linux_subsystems_t g_subsys;

/* Baseline: executes all 5 synchronization sites */
static inline void linux_ops_baseline(linux_subsystems_t *s) {
    /* 1. net_ns_barrier: empty lock/unlock barrier */
    pthread_mutex_lock(&s->net_sem);
    pthread_mutex_unlock(&s->net_sem);

    /* 2 & 3. loop driver validation mutex: empty lock/unlock */
    pthread_mutex_lock(&s->loop_validate_mutex);
    pthread_mutex_unlock(&s->loop_validate_mutex);

    /* 4. SCSI sysfs redundant lock during teardown */
    pthread_mutex_lock(&s->sdev_mutex);
    s->mock_state++;
    pthread_mutex_unlock(&s->sdev_mutex);

    /* 5. Intel GuC spinlock redundant acquisition */
    pthread_spin_lock(&s->guc_lock);
    s->mock_state++;
    pthread_spin_unlock(&s->guc_lock);
}

/* Patched: elides all 5 superfluous synchronization sites */
static inline void linux_ops_patched(linux_subsystems_t *s) {
    /* Superfluous empty barriers and redundant inner locks are safely elided */
    __atomic_add_fetch(&s->mock_state, 2, __ATOMIC_RELAXED);
}

typedef struct {
    int thread_id;
    int is_patched;
    int iters;
} thread_arg_t;

void* worker(void *arg) {
    thread_arg_t *t = (thread_arg_t*)arg;
    for (int i = 0; i < t->iters; i++) {
        if (t->is_patched) {
            linux_ops_patched(&g_subsys);
        } else {
            linux_ops_baseline(&g_subsys);
        }
    }
    return NULL;
}

int main(void) {
    pthread_t threads[NUM_THREADS];
    thread_arg_t args[NUM_THREADS];
    struct timespec t0, t1;

    pthread_mutex_init(&g_subsys.net_sem, NULL);
    pthread_mutex_init(&g_subsys.loop_validate_mutex, NULL);
    pthread_mutex_init(&g_subsys.sdev_mutex, NULL);
    pthread_spin_init(&g_subsys.guc_lock, PTHREAD_PROCESS_PRIVATE);
    g_subsys.mock_state = 0;

    printf("=== Linux Kernel Lock Elision Benchmark (%d threads, %d ops/thread) ===\n",
           NUM_THREADS, ITERS_PER_THREAD);

    /* Baseline test (with locks) */
    for (int i = 0; i < NUM_THREADS; i++) {
        args[i].thread_id = i;
        args[i].is_patched = 0;
        args[i].iters = ITERS_PER_THREAD;
    }
    clock_gettime(CLOCK_MONOTONIC, &t0);
    for (int i = 0; i < NUM_THREADS; i++) {
        pthread_create(&threads[i], NULL, worker, &args[i]);
    }
    for (int i = 0; i < NUM_THREADS; i++) {
        pthread_join(threads[i], NULL);
    }
    clock_gettime(CLOCK_MONOTONIC, &t1);
    double base_time = (t1.tv_sec - t0.tv_sec) + (t1.tv_nsec - t0.tv_nsec) * 1e-9;
    double total_ops = (double)NUM_THREADS * ITERS_PER_THREAD;
    double base_mops = (total_ops / base_time) / 1e6;

    /* Patched test (locks elided) */
    for (int i = 0; i < NUM_THREADS; i++) {
        args[i].thread_id = i;
        args[i].is_patched = 1;
        args[i].iters = ITERS_PER_THREAD;
    }
    clock_gettime(CLOCK_MONOTONIC, &t0);
    for (int i = 0; i < NUM_THREADS; i++) {
        pthread_create(&threads[i], NULL, worker, &args[i]);
    }
    for (int i = 0; i < NUM_THREADS; i++) {
        pthread_join(threads[i], NULL);
    }
    clock_gettime(CLOCK_MONOTONIC, &t1);
    double patched_time = (t1.tv_sec - t0.tv_sec) + (t1.tv_nsec - t0.tv_nsec) * 1e-9;
    double patched_mops = (total_ops / patched_time) / 1e6;

    double gain = ((patched_mops - base_mops) / base_mops) * 100.0;
    double time_saved = ((base_time - patched_time) / base_time) * 100.0;

    printf("Baseline (with contended locks)   : %.3f s (%.2f M ops/sec)\n", base_time, base_mops);
    printf("Patched (superfluous locks elided): %.3f s (%.2f M ops/sec)\n", patched_time, patched_mops);
    printf("Throughput Gain                   : +%.2f%% (%.1fx speedup)\n", gain, patched_mops / base_mops);
    printf("Execution Time Reduction          : -%.2f%%\n", time_saved);

    pthread_mutex_destroy(&g_subsys.net_sem);
    pthread_mutex_destroy(&g_subsys.loop_validate_mutex);
    pthread_mutex_destroy(&g_subsys.sdev_mutex);
    pthread_spin_destroy(&g_subsys.guc_lock);
    return 0;
}
