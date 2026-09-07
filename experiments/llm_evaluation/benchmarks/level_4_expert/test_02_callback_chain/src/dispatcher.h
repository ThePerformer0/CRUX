#ifndef DISPATCHER_H
#define DISPATCHER_H

void dispatch_register_observer(void (*cb)(const char*));
void dispatch_event(const char* event);

#endif
