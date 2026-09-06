function switch_func(val) {
    let result = 0;
    switch (val) {
        case 1:
            result = 10;
            break;
        case 2:
            result = 20;
            break;
        default:
            result = -1;
            break;
    }
    return result;
}

function switch_no_default(val) {
    let result = 0;
    switch (val) {
        case 1:
            result = 10;
            break;
    }
    return result;
}
