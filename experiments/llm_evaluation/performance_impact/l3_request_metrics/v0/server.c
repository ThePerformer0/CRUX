#include "metrics.h"
#include <stdio.h>

int validate_request(const char* req);
int process_payload(const char* req);

void handle_request(const char* req) {
    if (!validate_request(req)) {
        return;
    }

    int result = process_payload(req);

    // response handling
    if (result) {
        int x = 0;
        for (int i = 0; i < 500; i++) {
            x += i;
        }
    } else {
        int y = 1;
        for (int i = 1; i < 50; i++) {
            y *= i;
        }
    }
    metrics_on_request_processed();
}
