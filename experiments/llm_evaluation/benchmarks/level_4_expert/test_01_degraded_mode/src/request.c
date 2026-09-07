#include <string.h>

int validate_request(const char* req) {
    return req && strlen(req) > 0;
}
