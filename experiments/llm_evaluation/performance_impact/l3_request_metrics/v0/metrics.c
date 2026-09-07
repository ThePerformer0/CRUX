#include "metrics.h"

static long processed_requests = 0;

void metrics_on_request_processed(void) {
    processed_requests++;
}

long metrics_get_processed(void) {
    return processed_requests;
}
