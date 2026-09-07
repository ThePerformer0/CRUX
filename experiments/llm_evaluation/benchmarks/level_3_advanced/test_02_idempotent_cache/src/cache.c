#include "cache.h"
#include <pthread.h>
#include <string.h>

static int cached_value = -1;
static char cached_key[64] = "";
static pthread_mutex_t cache_lock = PTHREAD_MUTEX_INITIALIZER;

void cache_store(const char* key, int value) {
    pthread_mutex_lock(&cache_lock);
    strncpy(cached_key, key, 63);
    cached_value = value;
    pthread_mutex_unlock(&cache_lock);
}

int cache_get(const char* key) {
    pthread_mutex_lock(&cache_lock);
    int v = -1;
    if (strcmp(cached_key, key) == 0) {
        v = cached_value;
    }
    pthread_mutex_unlock(&cache_lock);
    return v;
}
