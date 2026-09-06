function throw_func(x) {
    if (x < 0) {
        throw new Error("negative");
    }
    return x;
}

function throw_in_try() {
    try {
        throw new Error("fail");
    } catch (err) {
        return -1;
    }
}
