#include <pthread.h>
#include <stdio.h>
#include "dispatcher.h"
#include "observer.h"

void* worker(void* arg) {
    for (int i = 0; i < 10; i++) {
        dispatch_event("update");
    }
    return NULL;
}

int main() {
    pthread_t t1, t2;
    
    observer_init();
    dispatch_register_observer(observer_callback);
    
    pthread_create(&t1, NULL, worker, NULL);
    pthread_create(&t2, NULL, worker, NULL);
    
    pthread_join(t1, NULL);
    pthread_join(t2, NULL);
    
    printf("Final Observer Count: %d\n", observer_get_count());
    return 0;
}
