#ifndef OBSERVER_H
#define OBSERVER_H

void observer_init(void);
void observer_callback(const char* event);
int observer_get_count(void);

#endif
