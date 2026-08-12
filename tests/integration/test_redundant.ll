@shared = global i32 0, align 4

define void @nested(i8* %parent, i8* %child) {
entry:
    call i32 @pthread_mutex_lock(i8* %parent)
    call i32 @pthread_mutex_lock(i8* %child)
    store i32 1, i32* @shared, align 4
    call i32 @pthread_mutex_unlock(i8* %child)
    call i32 @pthread_mutex_unlock(i8* %parent)
    ret void
}

declare i32 @pthread_mutex_lock(i8*)
declare i32 @pthread_mutex_unlock(i8*)
