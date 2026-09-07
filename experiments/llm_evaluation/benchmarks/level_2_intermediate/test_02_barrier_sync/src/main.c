#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include "config.h"

#define NUM_THREADS 4

pthread_barrier_t barrier;

void* worker(void* arg) {
    long id = (long)arg;
    
    if (id == 0) {
        config_init(42);
    }
    
    pthread_barrier_wait(&barrier);
    
    int val = config_get();
    printf("Thread %ld read config: %d\n", id, val);
    
    return NULL;
}

int main() {
    pthread_t threads[NUM_THREADS];
    pthread_barrier_init(&barrier, NULL, NUM_THREADS);
    
    for (long i = 0; i < NUM_THREADS; i++) {
        pthread_create(&threads[i], NULL, worker, (void*)i);
    }
    
    for (int i = 0; i < NUM_THREADS; i++) {
        pthread_join(threads[i], NULL);
    }
    
    pthread_barrier_destroy(&barrier);
    return 0;
}
