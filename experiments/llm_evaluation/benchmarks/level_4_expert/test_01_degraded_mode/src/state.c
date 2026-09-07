#include "state.h"
#include <pthread.h>

static int degraded_mode = 0;
static pthread_mutex_t state_lock = PTHREAD_MUTEX_INITIALIZER;

int is_degraded_mode(void) {
    pthread_mutex_lock(&state_lock);
    int v = degraded_mode;
    pthread_mutex_unlock(&state_lock);
    return v;
}

void set_degraded_mode(void) {
    pthread_mutex_lock(&state_lock);
    degraded_mode = 1;
    pthread_mutex_unlock(&state_lock);
}
