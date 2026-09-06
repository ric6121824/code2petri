function try_finally_func() {
    let val = 0;
    try {
        val = riskyOperation();
    } finally {
        cleanup();
    }
    return val;
}
