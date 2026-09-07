#include "dispatcher.h"
#include <pthread.h>

static void (*g_observer)(const char*) = NULL;
static pthread_mutex_t dispatch_lock = PTHREAD_MUTEX_INITIALIZER;

void dispatch_register_observer(void (*cb)(const char*)) {
    pthread_mutex_lock(&dispatch_lock);
    g_observer = cb;
    pthread_mutex_unlock(&dispatch_lock);
}

void dispatch_event(const char* event) {
    pthread_mutex_lock(&dispatch_lock);
    if (g_observer) {
        g_observer(event);
    }
    pthread_mutex_unlock(&dispatch_lock);
}
