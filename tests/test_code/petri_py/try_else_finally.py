def try_else_finally_func():
    val = 0
    try:
        val = 1
    except:
        val = 2
    else:
        val = 3
    finally:
        val = 4
    return val
