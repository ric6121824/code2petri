function loop_break_continue_func() {
    let i = 0;
    let sum = 0;
    while (i < 10) {
        i += 1;
        if (i === 2) {
            continue;
        }
        if (i === 8) {
            break;
        }
        sum += i;
    }
    return sum;
}
