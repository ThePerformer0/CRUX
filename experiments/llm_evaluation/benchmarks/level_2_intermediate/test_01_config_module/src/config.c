#include "config.h"
#include <pthread.h>

static int config_value = 0;
static pthread_mutex_t config_lock = PTHREAD_MUTEX_INITIALIZER;

void config_init(void) {
    pthread_mutex_lock(&config_lock);
    config_value = 100;
    pthread_mutex_unlock(&config_lock);
}

int config_get_value(void) {
    pthread_mutex_lock(&config_lock);
    int v = config_value;
    pthread_mutex_unlock(&config_lock);
    return v;
}
