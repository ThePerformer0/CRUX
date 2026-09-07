#include "state.h"
#include <stdio.h>

void log_request(const char* req) {
    if (is_degraded_mode()) {
        printf("[DEGRADED] %s\n", req);
    } else {
        printf("[NORMAL] %s\n", req);
    }
}
