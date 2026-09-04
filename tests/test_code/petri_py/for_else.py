def for_else_func():
    items = [1, 2, 3]
    for item in items:
        if item == 2:
            break
    else:
        item = 0
    return item
