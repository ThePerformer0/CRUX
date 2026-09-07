#include <pthread.h>
#include <stdio.h>
#include "manager.h"

void* worker(void* arg) {
    for (int i = 0; i < 50; i++) {
        manager_perform_task();
    }
    return NULL;
}

int main() {
    pthread_t t1, t2;
    
    manager_init();
    
    pthread_create(&t1, NULL, worker, NULL);
    pthread_create(&t2, NULL, worker, NULL);
    
    pthread_join(t1, NULL);
    pthread_join(t2, NULL);
    
    printf("Manager Audit Result: %d\n", manager_get_audit());
    return 0;
}
