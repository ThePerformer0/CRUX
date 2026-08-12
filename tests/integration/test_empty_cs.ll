define void @worker(i8* %mutex) {
entry:
    call i32 @pthread_mutex_lock(i8* %mutex)
    call i32 @pthread_mutex_unlock(i8* %mutex)
    ret void
}

declare i32 @pthread_mutex_lock(i8*)
declare i32 @pthread_mutex_unlock(i8*)
