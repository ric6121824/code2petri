def try_except_finally_func():
    x = 10
    try:
        x = x + 1
    except Exception as e:
        x = -1
    finally:
        x = x * 2
    return x
