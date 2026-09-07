#include <pthread.h>
#include <stdio.h>
#include "cache.h"

#define NUM_THREADS 4

void* worker(void* arg) {
    int result = 9999; 
    cache_store("static_file_hash", result);
    return NULL;
}

int main() {
    pthread_t threads[NUM_THREADS];
    
    for (int i = 0; i < NUM_THREADS; i++) {
        pthread_create(&threads[i], NULL, worker, NULL);
    }
    
    for (int i = 0; i < NUM_THREADS; i++) {
        pthread_join(threads[i], NULL);
    }
    
    printf("Final cache value: %d\n", cache_get("static_file_hash"));
    return 0;
}
