#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "src/tinycthread.h"

typedef struct {
    int ra_type;
    int ra_enabled;
    long long ra_v;
    mtx_t ra_lock;
} rd_avg_mock_t;

void rd_avg_rollover_base(rd_avg_mock_t *dst, rd_avg_mock_t *src) {
    mtx_lock(&src->ra_lock);
    mtx_init(&dst->ra_lock, mtx_plain);
    dst->ra_type = src->ra_type;
    dst->ra_v = src->ra_v;
    mtx_unlock(&src->ra_lock);
    mtx_destroy(&dst->ra_lock);
}

void rd_avg_rollover_patched(rd_avg_mock_t *dst, rd_avg_mock_t *src) {
    mtx_lock(&src->ra_lock);
    dst->ra_type = src->ra_type;
    dst->ra_v = src->ra_v;
    mtx_unlock(&src->ra_lock);
}

int main() {
    rd_avg_mock_t src;
    memset(&src, 0, sizeof(src));
    src.ra_enabled = 1;
    src.ra_v = 12345;
    mtx_init(&src.ra_lock, mtx_plain);

    const int ITERS = 10000000;
    struct timespec t0, t1;

    // Benchmark Base
    clock_gettime(CLOCK_MONOTONIC, &t0);
    for (int i = 0; i < ITERS; i++) {
        rd_avg_mock_t dst;
        rd_avg_rollover_base(&dst, &src);
    }
    clock_gettime(CLOCK_MONOTONIC, &t1);
    double base_time = (t1.tv_sec - t0.tv_sec) + (t1.tv_nsec - t0.tv_nsec) * 1e-9;
    double base_mops = (ITERS / base_time) / 1e6;

    // Benchmark Patched
    clock_gettime(CLOCK_MONOTONIC, &t0);
    for (int i = 0; i < ITERS; i++) {
        rd_avg_mock_t dst;
        rd_avg_rollover_patched(&dst, &src);
    }
    clock_gettime(CLOCK_MONOTONIC, &t1);
    double patched_time = (t1.tv_sec - t0.tv_sec) + (t1.tv_nsec - t0.tv_nsec) * 1e-9;
    double patched_mops = (ITERS / patched_time) / 1e6;

    double gain = ((patched_mops - base_mops) / base_mops) * 100.0;

    printf("=== Micro-Benchmark rd_avg_rollover (%d iterations) ===\n", ITERS);
    printf("Base (with stack mtx_init/destroy) : %.3f s (%.2f M ops/sec)\n", base_time, base_mops);
    printf("Patched (without stack mutex)     : %.3f s (%.2f M ops/sec)\n", patched_time, patched_mops);
    printf("Gain de performance               : +%.2f%%\n", gain);

    mtx_destroy(&src.ra_lock);
    return 0;
}
