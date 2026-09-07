#include <stdio.h>
#include "config.h"

void* worker(void* arg) {
    int v = config_get_value();
    printf("config = %d\n", v);
    return NULL;
}
