function try_catch_func() {
    let val = 0;
    try {
        val = riskyOperation();
    } catch (err) {
        val = -1;
    }
    return val;
}
