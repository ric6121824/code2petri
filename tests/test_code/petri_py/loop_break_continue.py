def loop_break_continue_func():
    i = 0
    while i < 10:
        i = i + 1
        if i == 5:
            continue
        if i == 8:
            break
    return i
