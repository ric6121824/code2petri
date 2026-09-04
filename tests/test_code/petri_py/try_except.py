def try_except_func():
    a = 1
    try:
        b = a + 1
        c = b * 2
    except:
        c = 0
    return c
