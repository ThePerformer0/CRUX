@counter = global i32 0, align 4

define void @writer(i8* %m) {
entry:
    call i32 @pthread_mutex_lock(i8* %m)
    %val = load i32, i32* @counter, align 4
    %inc = add nsw i32 %val, 1
    store i32 %inc, i32* @counter, align 4
    call i32 @pthread_mutex_unlock(i8* %m)
    ret void
}

define void @reader(i8* %m) {
entry:
    call i32 @pthread_mutex_lock(i8* %m)
    %val = load i32, i32* @counter, align 4
    call i32 @pthread_mutex_unlock(i8* %m)
    ret void
}

declare i32 @pthread_mutex_lock(i8*)
declare i32 @pthread_mutex_unlock(i8*)
