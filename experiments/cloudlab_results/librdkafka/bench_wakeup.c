#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "src/tinycthread.h"

#define NUM_BROKERS 16

typedef struct {
    int rkb_state;
    mtx_t rkb_lock;
} mock_broker_t;

typedef struct {
    mock_broker_t brokers[NUM_BROKERS];
    mtx_t rk_lock;
} mock_rk_t;

int all_brokers_wakeup_base(mock_rk_t *rk, int min_state) {
    int cnt = 0;
    mtx_lock(&rk->rk_lock);
    for (int i = 0; i < NUM_BROKERS; i++) {
        mock_broker_t *rkb = &rk->brokers[i];
        int do_wakeup;

        mtx_lock(&rkb->rkb_lock);
        do_wakeup = rkb->rkb_state >= min_state;
        mtx_unlock(&rkb->rkb_lock);

        if (do_wakeup) {
            cnt++;
        }
    }
    mtx_unlock(&rk->rk_lock);
    return cnt;
}

int all_brokers_wakeup_patched(mock_rk_t *rk, int min_state) {
    int cnt = 0;
    mtx_lock(&rk->rk_lock);
    for (int i = 0; i < NUM_BROKERS; i++) {
        mock_broker_t *rkb = &rk->brokers[i];
        int do_wakeup = rkb->rkb_state >= min_state;
        if (do_wakeup) {
            cnt++;
        }
    }
    mtx_unlock(&rk->rk_lock);
    return cnt;
}

int main() {
    mock_rk_t rk;
    mtx_init(&rk.rk_lock, mtx_plain);
    for (int i = 0; i < NUM_BROKERS; i++) {
        rk.brokers[i].rkb_state = 2; // UP
        mtx_init(&rk.brokers[i].rkb_lock, mtx_plain);
    }

    const int ITERS = 2000000;
    struct timespec t0, t1;

    // Benchmark Base
    clock_gettime(CLOCK_MONOTONIC, &t0);
    for (int i = 0; i < ITERS; i++) {
        all_brokers_wakeup_base(&rk, 1);
    }
    clock_gettime(CLOCK_MONOTONIC, &t1);
    double base_time = (t1.tv_sec - t0.tv_sec) + (t1.tv_nsec - t0.tv_nsec) * 1e-9;
    double base_mops = (ITERS / base_time) / 1e6;

    // Benchmark Patched
    clock_gettime(CLOCK_MONOTONIC, &t0);
    for (int i = 0; i < ITERS; i++) {
        all_brokers_wakeup_patched(&rk, 1);
    }
    clock_gettime(CLOCK_MONOTONIC, &t1);
    double patched_time = (t1.tv_sec - t0.tv_sec) + (t1.tv_nsec - t0.tv_nsec) * 1e-9;
    double patched_mops = (ITERS / patched_time) / 1e6;

    double gain = ((patched_mops - base_mops) / base_mops) * 100.0;

    printf("=== Micro-Benchmark rd_kafka_all_brokers_wakeup (%d iterations, %d brokers) ===\n", ITERS, NUM_BROKERS);
    printf("Base (with individual broker locks)    : %.3f s (%.2f M broadcasts/sec)\n", base_time, base_mops);
    printf("Patched (without redundant inner locks): %.3f s (%.2f M broadcasts/sec)\n", patched_time, patched_mops);
    printf("Gain de performance                    : +%.2f%%\n", gain);

    return 0;
}
