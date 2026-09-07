#include "subsystem.h"

static int sub_count = 0;

void subsystem_init(void) {
    sub_count = 0;
}

void subsystem_increment(void) {
    sub_count++;
}

int subsystem_get_val(void) {
    return sub_count;
}
