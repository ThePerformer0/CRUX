#include <pthread.h>

void handle_request(const char* req);

void* worker(void* arg) {
    handle_request("GET /");
    return NULL;
}

int main() {
    pthread_t threads[16];

    for (int i = 0; i < 16; i++) {
        pthread_create(&threads[i], NULL, worker, NULL);
    }

    for (int i = 0; i < 16; i++) {
        pthread_join(threads[i], NULL);
    }

    return 0;
}
