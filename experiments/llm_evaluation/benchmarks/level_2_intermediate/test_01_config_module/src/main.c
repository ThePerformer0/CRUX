#include <pthread.h>
#include "config.h"

void* worker(void* arg);

int main() {
    config_init();

    pthread_t t1, t2;
    pthread_create(&t1, NULL, worker, NULL);
    pthread_create(&t2, NULL, worker, NULL);

    pthread_join(t1, NULL);
    pthread_join(t2, NULL);
    return 0;
}
