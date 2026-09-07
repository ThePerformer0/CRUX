#include "monitor.h"
#include <pthread.h>
#include <time.h>

static time_t last_activity = 0;
static pthread_mutex_t monitor_lock = PTHREAD_MUTEX_INITIALIZER;

void monitor_update_heartbeat(void) {
    pthread_mutex_lock(&monitor_lock);
    last_activity = time(NULL);
    pthread_mutex_unlock(&monitor_lock);
}

time_t monitor_get_last_activity(void) {
    pthread_mutex_lock(&monitor_lock);
    time_t t = last_activity;
    pthread_mutex_unlock(&monitor_lock);
    return t;
}
