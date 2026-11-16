try:
    while True:
        win.update()
except Exception:
    handle_failure()


def no_break():
    while True:
        tick()
    after_loop()


def break_and_continue():
    while True:
        if should_continue():
            continue
        if should_break():
            break
    else:
        on_exhaustion()
    after_loop()


def return_or_raise(should_return):
    while True:
        if should_return:
            return
        raise ValueError()


def ordinary_condition():
    try:
        while ready():
            tick()
    except Exception:
        handle_error()
