function try_catch_finally_func() {
    let val = 0;
    try {
        val = riskyOperation();
    } catch (err) {
        val = -1;
    } finally {
        cleanup();
    }
    return val;
}
