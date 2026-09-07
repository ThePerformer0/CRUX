#include <pthread.h>
#include <stdio.h>
#include "version.h"

#define THREADS 5

void* worker(void* arg) {
    const char* v = version_get();
    printf("Software Version: %s\n", v);
    return NULL;
}

int main() {
    pthread_t t[THREADS];
    
    for (int i = 0; i < THREADS; i++) {
        pthread_create(&t[i], NULL, worker, NULL);
    }
    
    for (int i = 0; i < THREADS; i++) {
        pthread_join(t[i], NULL);
    }
    
    return 0;
}
