#include <pthread.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>

void handle_request(const char* req);

void* worker_thread(void* arg) {
    for (int i = 0; i < 10000; i++) {
        handle_request("GET /index.html");
    }
    return NULL;
}

int main() {
    pthread_t threads[8];

    for (int i = 0; i < 8; i++) {
        pthread_create(&threads[i], NULL, worker_thread, NULL);
    }

    for (int i = 0; i < 8; i++) {
        pthread_join(threads[i], NULL);
    }

    printf("Processed: %ld\n", metrics_get_processed());
    return 0;
}
