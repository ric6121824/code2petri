# 05 — Python control-flow walker — try/except/finally

**What to build:** Extend the Python AST walker to handle `try`, `except`, and `finally` blocks. The try body is walked normally as a sequential chain. An additional "exception" transition is added from each statement-transition in the try body, arcing to the matching except handler's entry place. Multiple except handlers produce parallel paths (one per handler). The finally block, if present, is appended as a mandatory convergence path — both the normal completion of the try body and all except handler completions must pass through it before reaching the exit place. Bare `except:` (catch-all) and typed `except TypeError:` are both handled; the walker does not distinguish exception types.

**Blocked by:** 02 — Python control-flow walker — sequential & return

**Status:** ready-for-agent

- [ ] `ast.Try` nodes walk the try body as a normal sequential chain
- [ ] Each transition in the try body gets an additional "exception" arc to the except entry place
- [ ] Multiple `except` handlers produce parallel paths from the exception entry
- [ ] The `finally` block is walked as a mandatory path that both normal and exception flows converge into
- [ ] `try` without `finally` merges the normal and exception paths into a shared exit place
- [ ] `else` clause on try (runs if no exception) is modeled as a path from the try body's normal exit to the else body before the finally/exit
- [ ] Test fixture: `try_except.py` — simple try/except; assert exception arcs from try body transitions
- [ ] Test fixture: `try_except_finally.py` — try/except/finally; assert finally is on both normal and exception paths
- [ ] Test fixture: `try_multi_except.py` — multiple except handlers; assert parallel exception paths
