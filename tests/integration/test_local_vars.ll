define void @worker(i8* %mutex) {
entry:
    %local = alloca i32, align 4
    call i32 @pthread_mutex_lock(i8* %mutex)
    store i32 42, i32* %local, align 4
    %val = load i32, i32* %local, align 4
    call i32 @pthread_mutex_unlock(i8* %mutex)
    ret void
}

declare i32 @pthread_mutex_lock(i8*)
declare i32 @pthread_mutex_unlock(i8*)
