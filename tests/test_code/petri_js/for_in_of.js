function for_in_of_func() {
    let obj = { a: 1 };
    let arr = [1, 2];
    for (const k in obj) {
        print(k);
    }
    for (const v of arr) {
        print(v);
    }
    return 0;
}
