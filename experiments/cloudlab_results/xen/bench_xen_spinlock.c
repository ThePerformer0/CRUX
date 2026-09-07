#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <time.h>

#define NUM_THREADS 16
#define ITERS_PER_THREAD 1000000

typedef struct {
    pthread_spinlock_t lock;
    int irq;
    int status;
    void *desc;
} xen_mock_pirq_t;

xen_mock_pirq_t g_pirq;

// Baseline: with exclusive spinlock for read-only query
int xen_pirq_read_base(xen_mock_pirq_t *p) {
    pthread_spin_lock(&p->lock);
    int irq = p->irq;
    int status = p->status;
    pthread_spin_unlock(&p->lock);
    return irq + status;
}

// Patched: lock-free read for read-only query
int xen_pirq_read_patched(xen_mock_pirq_t *p) {
    int irq = __atomic_load_n(&p->irq, __ATOMIC_ACQUIRE);
    int status = __atomic_load_n(&p->status, __ATOMIC_ACQUIRE);
    return irq + status;
}

typedef struct {
    int is_patched;
    int iters;
    long long checksum;
} thread_arg_t;

void* worker(void *arg) {
    thread_arg_t *t = (thread_arg_t*)arg;
    long long sum = 0;
    for (int i = 0; i < t->iters; i++) {
        if (t->is_patched) {
            sum += xen_pirq_read_patched(&g_pirq);
        } else {
            sum += xen_pirq_read_base(&g_pirq);
        }
    }
    t->checksum = sum;
    return NULL;
}

int main() {
    pthread_t threads[NUM_THREADS];
    thread_arg_t args[NUM_THREADS];
    struct timespec t0, t1;

    pthread_spin_init(&g_pirq.lock, PTHREAD_PROCESS_PRIVATE);
    g_pirq.irq = 42;
    g_pirq.status = 1;

    printf("=== Xen Spinlock Contention Benchmark (%d threads, %d queries/thread) ===\n",
           NUM_THREADS, ITERS_PER_THREAD);

    // Baseline test
    for (int i = 0; i < NUM_THREADS; i++) {
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

    // Patched test
    for (int i = 0; i < NUM_THREADS; i++) {
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

    printf("Base (with contended spinlock)    : %.3f s (%.2f M queries/sec)\n", base_time, base_mops);
    printf("Patched (lock-free atomic read)  : %.3f s (%.2f M queries/sec)\n", patched_time, patched_mops);
    printf("Gain de debit                    : +%.2f%%\n", gain);
    printf("Reduction temps d'execution      : -%.2f%%\n", time_saved);

    pthread_spin_destroy(&g_pirq.lock);
    return 0;
}
