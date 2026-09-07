#include <string.h>

int validate_request(const char* req) {
    return req != NULL && strcmp(req, "GET /index.html") == 0;
}
