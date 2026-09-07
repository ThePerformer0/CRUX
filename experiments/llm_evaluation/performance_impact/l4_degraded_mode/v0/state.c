#include "state.h"

static int degraded_mode = 0;

int is_degraded_mode(void) {
    return degraded_mode;
}

void set_degraded_mode(void) {
    degraded_mode = 1;
}
