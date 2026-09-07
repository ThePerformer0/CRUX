#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <time.h>
#include <stdint.h>

#define NUM_BACKENDS 16
#define ITERS_PER_BACKEND 2000000

// PostgreSQL mock WAL stats structure
typedef struct {
    uint64_t wal_records;
    uint64_t wal_fpi;
    uint64_t wal_bytes;
    uint64_t wal_buffers_full;
    uint64_t wal_write;
    uint64_t wal_sync;
    uint64_t wal_write_time;
    uint64_t wal_sync_time;
} PgStat_WalStats;

typedef struct {
    pthread_rwlock_t lock;
    PgStat_WalStats stats;
} PgStatShared_Wal;

PgStatShared_Wal g_shared_wal;

// Baseline: with LW_SHARED rwlock acquisition for stats snapshot
void pgstat_wal_snapshot_base(PgStat_WalStats *dst) {
    pthread_rwlock_rdlock(&g_shared_wal.lock);
    memcpy(dst, &g_shared_wal.stats, sizeof(PgStat_WalStats));
    pthread_rwlock_unlock(&g_shared_wal.lock);
}

// Patched: Lock-free snapshot read
void pgstat_wal_snapshot_patched(PgStat_WalStats *dst) {
    memcpy(dst, &g_shared_wal.stats, sizeof(PgStat_WalStats));
}

typedef struct {
    int backend_id;
    int is_patched;
    int iters;
    PgStat_WalStats local_snapshot;
} backend_arg_t;

void* backend_worker(void *arg) {
    backend_arg_t *b = (backend_arg_t*)arg;
    for (int i = 0; i < b->iters; i++) {
        if (b->is_patched) {
            pgstat_wal_snapshot_patched(&b->local_snapshot);
        } else {
            pgstat_wal_snapshot_base(&b->local_snapshot);
        }
    }
    return NULL;
}

int main() {
    pthread_t threads[NUM_BACKENDS];
    backend_arg_t args[NUM_BACKENDS];
    struct timespec t0, t1;

    pthread_rwlock_init(&g_shared_wal.lock, NULL);
    memset(&g_shared_wal.stats, 0xAB, sizeof(PgStat_WalStats));

    printf("=== PostgreSQL Stats Snapshot Benchmark (%d backends, %d snapshots/backend) ===\n",
           NUM_BACKENDS, ITERS_PER_BACKEND);

    // 1. Baseline Test
    for (int i = 0; i < NUM_BACKENDS; i++) {
        args[i].backend_id = i;
        args[i].is_patched = 0;
        args[i].iters = ITERS_PER_BACKEND;
    }
    clock_gettime(CLOCK_MONOTONIC, &t0);
    for (int i = 0; i < NUM_BACKENDS; i++) pthread_create(&threads[i], NULL, backend_worker, &args[i]);
    for (int i = 0; i < NUM_BACKENDS; i++) pthread_join(threads[i], NULL);
    clock_gettime(CLOCK_MONOTONIC, &t1);

    double base_time = (t1.tv_sec - t0.tv_sec) + (t1.tv_nsec - t0.tv_nsec) * 1e-9;
    double total_ops = (double)NUM_BACKENDS * ITERS_PER_BACKEND;
    double base_mops = (total_ops / base_time) / 1e6;

    // 2. Patched Test
    for (int i = 0; i < NUM_BACKENDS; i++) {
        args[i].backend_id = i;
        args[i].is_patched = 1;
        args[i].iters = ITERS_PER_BACKEND;
    }
    clock_gettime(CLOCK_MONOTONIC, &t0);
    for (int i = 0; i < NUM_BACKENDS; i++) pthread_create(&threads[i], NULL, backend_worker, &args[i]);
    for (int i = 0; i < NUM_BACKENDS; i++) pthread_join(threads[i], NULL);
    clock_gettime(CLOCK_MONOTONIC, &t1);

    double patched_time = (t1.tv_sec - t0.tv_sec) + (t1.tv_nsec - t0.tv_nsec) * 1e-9;
    double patched_mops = (total_ops / patched_time) / 1e6;

    double gain = ((patched_mops - base_mops) / base_mops) * 100.0;
    double time_saved = ((base_time - patched_time) / base_time) * 100.0;

    printf("Base (with LWLock shared lock)     : %.3f s (%.2f M snapshots/sec)\n", base_time, base_mops);
    printf("Patched (lock-free snapshot read) : %.3f s (%.2f M snapshots/sec)\n", patched_time, patched_mops);
    printf("Gain de debit                     : +%.2f%%\n", gain);
    printf("Reduction temps d'execution       : -%.2f%%\n", time_saved);

    pthread_rwlock_destroy(&g_shared_wal.lock);
    return 0;
}
