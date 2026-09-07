#include <pthread.h>

pthread_mutex_t lock = PTHREAD_MUTEX_INITIALIZER;

int main() {
    pthread_mutex_lock(&lock);
    pthread_mutex_unlock(&lock);
    return 0;
}
