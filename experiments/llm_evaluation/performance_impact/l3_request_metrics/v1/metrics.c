#include "metrics.h"
#include <pthread.h>

static long processed_requests = 0;
static pthread_mutex_t metrics_lock = PTHREAD_MUTEX_INITIALIZER;

void metrics_on_request_processed(void) {
    pthread_mutex_lock(&metrics_lock);
    processed_requests++;
    pthread_mutex_unlock(&metrics_lock);
}

long metrics_get_processed(void) {
    pthread_mutex_lock(&metrics_lock);
    long v = processed_requests;
    pthread_mutex_unlock(&metrics_lock);
    return v;
}
