#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <time.h>

#define NUM_THREADS 16
#define ITERS_PER_THREAD 2000000

typedef struct cache_item_s {
    struct cache_item_s *next;
    char data[64];
} cache_item_t;

typedef struct {
    pthread_mutex_t mutex;
    cache_item_t *head;
    size_t bufsize;
    int freecurr;
} mock_cache_t;

void mock_cache_init(mock_cache_t *c) {
    pthread_mutex_init(&c->mutex, NULL);
    c->head = NULL;
    c->bufsize = sizeof(cache_item_t);
    c->freecurr = 0;
}

// Baseline: with mutex
void* mock_cache_alloc_base(mock_cache_t *c) {
    pthread_mutex_lock(&c->mutex);
    cache_item_t *ret = NULL;
    if (c->head) {
        ret = c->head;
        c->head = c->head->next;
        c->freecurr--;
    } else {
        ret = (cache_item_t*)malloc(c->bufsize);
    }
    pthread_mutex_unlock(&c->mutex);
    return ret;
}

void mock_cache_free_base(mock_cache_t *c, void *ptr) {
    pthread_mutex_lock(&c->mutex);
    cache_item_t *item = (cache_item_t*)ptr;
    item->next = c->head;
    c->head = item;
    c->freecurr++;
    pthread_mutex_unlock(&c->mutex);
}

// Patched: without redundant thread-local mutex
void* mock_cache_alloc_patched(mock_cache_t *c) {
    cache_item_t *ret = NULL;
    if (c->head) {
        ret = c->head;
        c->head = c->head->next;
        c->freecurr--;
    } else {
        ret = (cache_item_t*)malloc(c->bufsize);
    }
    return ret;
}

void mock_cache_free_patched(mock_cache_t *c, void *ptr) {
    cache_item_t *item = (cache_item_t*)ptr;
    item->next = c->head;
    c->head = item;
    c->freecurr++;
}

typedef struct {
    mock_cache_t cache;
    int is_patched;
    int iters;
} thread_arg_t;

void* thread_worker(void *arg) {
    thread_arg_t *t = (thread_arg_t*)arg;
    for (int i = 0; i < t->iters; i++) {
        void *p;
        if (t->is_patched) {
            p = mock_cache_alloc_patched(&t->cache);
            mock_cache_free_patched(&t->cache, p);
        } else {
            p = mock_cache_alloc_base(&t->cache);
            mock_cache_free_base(&t->cache, p);
        }
    }
    return NULL;
}

int main() {
    pthread_t threads[NUM_THREADS];
    thread_arg_t args[NUM_THREADS];
    struct timespec t0, t1;

    printf("=== Memcached Thread-Local Cache Alloc/Free Benchmark (%d threads, %d ops/thread) ===\n",
           NUM_THREADS, ITERS_PER_THREAD);

    // Baseline benchmark
    for (int i = 0; i < NUM_THREADS; i++) {
        mock_cache_init(&args[i].cache);
        args[i].is_patched = 0;
        args[i].iters = ITERS_PER_THREAD;
    }
    clock_gettime(CLOCK_MONOTONIC, &t0);
    for (int i = 0; i < NUM_THREADS; i++) {
        pthread_create(&threads[i], NULL, thread_worker, &args[i]);
    }
    for (int i = 0; i < NUM_THREADS; i++) {
        pthread_join(threads[i], NULL);
    }
    clock_gettime(CLOCK_MONOTONIC, &t1);
    double base_time = (t1.tv_sec - t0.tv_sec) + (t1.tv_nsec - t0.tv_nsec) * 1e-9;
    double total_ops = (double)NUM_THREADS * ITERS_PER_THREAD;
    double base_mops = (total_ops / base_time) / 1e6;

    // Patched benchmark
    for (int i = 0; i < NUM_THREADS; i++) {
        mock_cache_init(&args[i].cache);
        args[i].is_patched = 1;
        args[i].iters = ITERS_PER_THREAD;
    }
    clock_gettime(CLOCK_MONOTONIC, &t0);
    for (int i = 0; i < NUM_THREADS; i++) {
        pthread_create(&threads[i], NULL, thread_worker, &args[i]);
    }
    for (int i = 0; i < NUM_THREADS; i++) {
        pthread_join(threads[i], NULL);
    }
    clock_gettime(CLOCK_MONOTONIC, &t1);
    double patched_time = (t1.tv_sec - t0.tv_sec) + (t1.tv_nsec - t0.tv_nsec) * 1e-9;
    double patched_mops = (total_ops / patched_time) / 1e6;

    double gain = ((patched_mops - base_mops) / base_mops) * 100.0;
    double time_saved = ((base_time - patched_time) / base_time) * 100.0;

    printf("Base (with thread-local mutex)    : %.3f s (%.2f M ops/sec)\n", base_time, base_mops);
    printf("Patched (lock-free thread-local) : %.3f s (%.2f M ops/sec)\n", patched_time, patched_mops);
    printf("Gain de debit                     : +%.2f%%\n", gain);
    printf("Reduction temps d'execution       : -%.2f%%\n", time_saved);

    return 0;
}
