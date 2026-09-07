#include <pthread.h>
#include <stdio.h>

int shared_value = 0;
pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;

void* reader(void* arg) {
    pthread_mutex_lock(&lock);
    int v = shared_value;
    pthread_mutex_unlock(&lock);

    printf("read: %d\n", v);
    return NULL;
}

int main() {
    shared_value = 42;

    pthread_t t1, t2;
    pthread_create(&t1, NULL, reader, NULL);
    pthread_create(&t2, NULL, reader, NULL);

    pthread_join(t1, NULL);
    pthread_join(t2, NULL);
    return 0;
}
