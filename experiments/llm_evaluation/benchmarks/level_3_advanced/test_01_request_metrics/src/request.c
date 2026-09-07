#include <string.h>
#include <stdlib.h>

int validate_request(const char* req) {
    return req != NULL && strlen(req) > 0;
}

int process_payload(const char* req) {
    // some work
    return req[0] % 2;
}
