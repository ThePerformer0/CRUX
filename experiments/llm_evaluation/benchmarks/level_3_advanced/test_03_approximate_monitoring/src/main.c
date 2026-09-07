#include <pthread.h>
#include <stdio.h>
#include <unistd.h>
#include <time.h>
#include "monitor.h"

void* worker(void* arg) {
    for (int i = 0; i < 100; i++) {
        monitor_update_heartbeat();
        usleep(10000); // 10ms
    }
    return NULL;
}

int main() {
    pthread_t t1, t2;
    
    pthread_create(&t1, NULL, worker, NULL);
    pthread_create(&t2, NULL, worker, NULL);
    
    for (int i = 0; i < 5; i++) {
        sleep(1);
        printf("Current Last Activity: %ld\n", monitor_get_last_activity());
    }
    
    pthread_join(t1, NULL);
    pthread_join(t2, NULL);
    
    return 0;
}
