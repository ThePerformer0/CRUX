#include <pthread.h>
#include <stdio.h>

pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;

void* worker(void* arg) {
    int local_counter = 0;

    pthread_mutex_lock(&lock);
    local_counter++;
    pthread_mutex_unlock(&lock);

    printf("local_counter = %d\n", local_counter);
    return NULL;
}

int main() {
    pthread_t t;
    pthread_create(&t, NULL, worker, NULL);
    pthread_join(t, NULL);
    return 0;
}
