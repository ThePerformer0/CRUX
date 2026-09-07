#ifndef MONITOR_H
#define MONITOR_H

#include <time.h>

void monitor_update_heartbeat(void);
time_t monitor_get_last_activity(void);

#endif
