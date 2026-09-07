#include "state.h"

int validate_request(const char* req);
void log_request(const char* req);

void handle_request(const char* req) {
    if (!validate_request(req)) {
        // rare error path
        set_degraded_mode();
        return;
    }

    // normal processing
    log_request(req);
}
