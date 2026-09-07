#include "state.h"
#include <stdio.h>

void log_request(const char* req) {
    if (is_degraded_mode()) {
        // mock print
        volatile int x = 0;
        x++;
    } else {
        // mock print
        volatile int y = 1;
        y++;
    }
}
