#include "monitor.h"
#include <time.h>

static time_t last_activity = 0;

void monitor_update_heartbeat(void) {
    last_activity = time(NULL);
}

time_t monitor_get_last_activity(void) {
    return last_activity;
}
