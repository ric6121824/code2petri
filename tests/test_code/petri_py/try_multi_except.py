def try_multi_except_func():
    val = 0
    try:
        val = 1
    except ValueError:
        val = 2
    except TypeError:
        val = 3
    except:
        val = 4
    return val
