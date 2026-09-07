#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include "manager.h"
#include "subsystem.h"

int num_threads = 1;
long iterations_per_thread = 1000000;

void* worker(void* arg) {
    for (long i = 0; i < iterations_per_thread; i++) {
        manager_perform_task();
    }
    return NULL;
}

int main(int argc, char** argv) {
    if (argc >= 2) num_threads = atoi(argv[1]);
    if (argc >= 3) iterations_per_thread = atol(argv[2]);

    manager_init();

    pthread_t* threads = malloc(num_threads * sizeof(pthread_t));

    struct timespec start, end;
    clock_gettime(CLOCK_MONOTONIC, &start);

    for (int i = 0; i < num_threads; i++) {
        pthread_create(&threads[i], NULL, worker, NULL);
    }

    for (int i = 0; i < num_threads; i++) {
        pthread_join(threads[i], NULL);
    }

    clock_gettime(CLOCK_MONOTONIC, &end);
    double elapsed = (end.tv_sec - start.tv_sec) + (end.tv_nsec - start.tv_nsec) / 1e9;

    printf("Audit: %d\n", manager_get_audit());
    printf("Time: %.6f\n", elapsed);
    printf("Throughput: %.2f\n", (double)(num_threads * iterations_per_thread) / elapsed);

    free(threads);
    return 0;
}
