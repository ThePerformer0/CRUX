#include <stdio.h>
#include <stdlib.h>
#include <pthread.h>
#include <time.h>
#include <stdint.h>

#define NUM_THREADS 16
#define ITERS_PER_THREAD 5000000

typedef struct {
    void *pkey;
    size_t next_empty;
} slot_t;

typedef struct {
    pthread_mutex_t lock;
    slot_t *slots;
    size_t num_slots;
    size_t first_empty;
} keys_table_t;

keys_table_t table_base;
keys_table_t table_patched;

// Original (Baseline with useless lock on immutable table)
void* daemon_get_pkey_base(keys_table_t *tbl, size_t key_index) {
    void *pkey = NULL;
    pthread_mutex_lock(&tbl->lock);
    if (key_index < tbl->num_slots) {
        pkey = tbl->slots[key_index].pkey;
    }
    pthread_mutex_unlock(&tbl->lock);
    return pkey;
}

// Patched (Direct access without lock)
void* daemon_get_pkey_patched(keys_table_t *tbl, size_t key_index) {
    void *pkey = NULL;
    if (key_index < tbl->num_slots) {
        pkey = tbl->slots[key_index].pkey;
    }
    return pkey;
}

typedef struct {
    int thread_id;
    int mode; // 0 = base, 1 = patched
    uint64_t ops_done;
} worker_arg_t;

void* worker_func(void *arg) {
    worker_arg_t *w = (worker_arg_t*)arg;
    size_t key_index = w->thread_id % 4;
    
    if (w->mode == 0) {
        for (int i = 0; i < ITERS_PER_THREAD; i++) {
            void *p = daemon_get_pkey_base(&table_base, key_index);
            if (p) w->ops_done++;
        }
    } else {
        for (int i = 0; i < ITERS_PER_THREAD; i++) {
            void *p = daemon_get_pkey_patched(&table_patched, key_index);
            if (p) w->ops_done++;
        }
    }
    return NULL;
}

int main() {
    table_base.num_slots = 8;
    table_base.slots = malloc(sizeof(slot_t) * 8);
    pthread_mutex_init(&table_base.lock, NULL);
    for (int i = 0; i < 8; i++) table_base.slots[i].pkey = (void*)(uintptr_t)(i + 1);

    table_patched.num_slots = 8;
    table_patched.slots = malloc(sizeof(slot_t) * 8);
    pthread_mutex_init(&table_patched.lock, NULL);
    for (int i = 0; i < 8; i++) table_patched.slots[i].pkey = (void*)(uintptr_t)(i + 1);

    pthread_t threads[NUM_THREADS];
    worker_arg_t args[NUM_THREADS];

    printf("===========================================================\n");
    printf("   BENCHMARK CRUX -- H2O neverbleed TLS Key Access        \n");
    printf("   Threads: %d | Total Ops: %lu                          \n", NUM_THREADS, (uint64_t)NUM_THREADS * ITERS_PER_THREAD);
    printf("===========================================================\n");

    // 1. Run Baseline (Original)
    struct timespec start, end;
    for (int i = 0; i < NUM_THREADS; i++) {
        args[i].thread_id = i;
        args[i].mode = 0;
        args[i].ops_done = 0;
    }

    clock_gettime(CLOCK_MONOTONIC, &start);
    for (int i = 0; i < NUM_THREADS; i++) pthread_create(&threads[i], NULL, worker_func, &args[i]);
    for (int i = 0; i < NUM_THREADS; i++) pthread_join(threads[i], NULL);
    clock_gettime(CLOCK_MONOTONIC, &end);

    double time_base = (end.tv_sec - start.tv_sec) + (end.tv_nsec - start.tv_nsec) / 1e9;
    double ops_sec_base = ((double)NUM_THREADS * ITERS_PER_THREAD) / time_base / 1e6;
    printf("BASELINE (Original Lock) : Time = %.4f s | Throughput = %.2f M ops/sec\n", time_base, ops_sec_base);

    // 2. Run Patched (Lock Removed)
    for (int i = 0; i < NUM_THREADS; i++) {
        args[i].thread_id = i;
        args[i].mode = 1;
        args[i].ops_done = 0;
    }

    clock_gettime(CLOCK_MONOTONIC, &start);
    for (int i = 0; i < NUM_THREADS; i++) pthread_create(&threads[i], NULL, worker_func, &args[i]);
    for (int i = 0; i < NUM_THREADS; i++) pthread_join(threads[i], NULL);
    clock_gettime(CLOCK_MONOTONIC, &end);

    double time_patched = (end.tv_sec - start.tv_sec) + (end.tv_nsec - start.tv_nsec) / 1e9;
    double ops_sec_patched = ((double)NUM_THREADS * ITERS_PER_THREAD) / time_patched / 1e6;
    printf("PATCHED  (Lock Removed)  : Time = %.4f s | Throughput = %.2f M ops/sec\n", time_patched, ops_sec_patched);

    double gain = ((ops_sec_patched - ops_sec_base) / ops_sec_base) * 100.0;
    printf("-----------------------------------------------------------\n");
    printf("GAIN DE PERFORMANCE      : %+.2f %%\n", gain);
    printf("REDUCTION DE TEMPS       : -%.2f %%\n", (1.0 - (time_patched / time_base)) * 100.0);
    printf("===========================================================\n");

    return 0;
}
