#include "observer.h"
#include <pthread.h>
#include <string.h>

static int observer_count = 0;
static pthread_mutex_t observer_lock = PTHREAD_MUTEX_INITIALIZER;

void observer_init(void) {
    observer_count = 0;
}

void observer_callback(const char* event) {
    pthread_mutex_lock(&observer_lock);
    if (strcmp(event, "update") == 0) {
        observer_count++;
    }
    pthread_mutex_unlock(&observer_lock);
}

int observer_get_count(void) {
    pthread_mutex_lock(&observer_lock);
    int c = observer_count;
    pthread_mutex_unlock(&observer_lock);
    return c;
}
