def helper_calc(val):
    return val * 2


def mixed_pipeline_func():
    total = 0
    items = [1, 2, 3]

    for item in items:
        if item > 1:
            total += helper_calc(item)
        else:
            total += 1

    try:
        final_res = total / 2
    except ZeroDivisionError:
        final_res = -1
    finally:
        final_res += 10

    return final_res


def secondary_func():
    return 42
