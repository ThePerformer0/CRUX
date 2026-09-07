#include "manager.h"
#include "subsystem.h"
#include <pthread.h>

static pthread_mutex_t manager_lock = PTHREAD_MUTEX_INITIALIZER;
static int audit_count = 0;

void manager_init(void) {
    subsystem_init();
    audit_count = 0;
}

void manager_perform_task(void) {
    pthread_mutex_lock(&manager_lock);
    
    subsystem_increment();
    audit_count++;
    
    pthread_mutex_unlock(&manager_lock);
}

int manager_get_audit(void) {
    pthread_mutex_lock(&manager_lock);
    int c = audit_count;
    pthread_mutex_unlock(&manager_lock);
    return c;
}
