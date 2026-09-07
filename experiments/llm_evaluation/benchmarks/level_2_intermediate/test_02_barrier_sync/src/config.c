#include "config.h"
#include <pthread.h>

static int global_config = 0;
static pthread_mutex_t config_mutex = PTHREAD_MUTEX_INITIALIZER;

void config_init(int val) {
    pthread_mutex_lock(&config_mutex);
    global_config = val;
    pthread_mutex_unlock(&config_mutex);
}

int config_get(void) {
    pthread_mutex_lock(&config_mutex);
    int val = global_config;
    pthread_mutex_unlock(&config_mutex);
    return val;
}
