function do_while_func() {
    let i = 0;
    do {
        i += 1;
    } while (i < 5);
    return i;
}

function do_while_break_continue() {
    let i = 0;
    do {
        i += 1;
        if (i === 2) {
            continue;
        }
        if (i === 4) {
            break;
        }
    } while (i < 10);
    return i;
}
