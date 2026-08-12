@global_var = global i32 100, align 4

define void @reader1(i8* %m1) {
entry:
    call i32 @pthread_mutex_lock(i8* %m1)
    %v = load i32, i32* @global_var, align 4
    call i32 @pthread_mutex_unlock(i8* %m1)
    ret void
}

define void @reader2(i8* %m2) {
entry:
    call i32 @pthread_mutex_lock(i8* %m2)
    %v = load i32, i32* @global_var, align 4
    call i32 @pthread_mutex_unlock(i8* %m2)
    ret void
}

declare i32 @pthread_mutex_lock(i8*)
declare i32 @pthread_mutex_unlock(i8*)
