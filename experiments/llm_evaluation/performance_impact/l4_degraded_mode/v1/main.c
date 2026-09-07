#include <pthread.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include "state.h"

int num_threads = 1;
long iterations_per_thread = 1000000;

void handle_request(const char* req);

void* worker(void* arg) {
    for (long i = 0; i < iterations_per_thread; i++) {
        handle_request("GET /index.html");
    }
    return NULL;
}

int main(int argc, char** argv) {
    if (argc >= 2) num_threads = atoi(argv[1]);
    if (argc >= 3) iterations_per_thread = atol(argv[2]);

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

    printf("Degraded: %d\n", is_degraded_mode());
    printf("Time: %.6f\n", elapsed);
    printf("Throughput: %.2f\n", (double)(num_threads * iterations_per_thread) / elapsed);

    free(threads);
    return 0;
}
