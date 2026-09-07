#include "subsystem.h"
#include <pthread.h>

static int sub_count = 0;
static pthread_mutex_t sub_lock = PTHREAD_MUTEX_INITIALIZER;

void subsystem_init(void) {
    sub_count = 0;
}

void subsystem_increment(void) {
    pthread_mutex_lock(&sub_lock);
    sub_count++;
    pthread_mutex_unlock(&sub_lock);
}

int subsystem_get_val(void) {
    pthread_mutex_lock(&sub_lock);
    int v = sub_count;
    pthread_mutex_unlock(&sub_lock);
    return v;
}
