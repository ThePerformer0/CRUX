@g_mutex = global i8 0
@g_data = global i32 0

define void @inner_worker() {
entry:
    call i32 @pthread_mutex_lock(i8* @g_mutex)
    store i32 100, i32* @g_data
    call i32 @pthread_mutex_unlock(i8* @g_mutex)
    ret void
}

define void @outer_task() {
entry:
    call i32 @pthread_mutex_lock(i8* @g_mutex)
    store i32 50, i32* @g_data
    call void @inner_worker()
    call i32 @pthread_mutex_unlock(i8* @g_mutex)
    ret void
}
