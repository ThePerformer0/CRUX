#include "version.h"
#include <pthread.h>

static const char* APP_VERSION = "v1.2.3-lite";
static pthread_mutex_t version_lock = PTHREAD_MUTEX_INITIALIZER;

const char* version_get(void) {
    pthread_mutex_lock(&version_lock);
    const char* v = APP_VERSION;
    pthread_mutex_unlock(&version_lock);
    return v;
}
