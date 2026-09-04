def while_else_func():
    i = 0
    while i < 3:
        i = i + 1
        if i == 2:
            break
    else:
        i = 99
    return i
