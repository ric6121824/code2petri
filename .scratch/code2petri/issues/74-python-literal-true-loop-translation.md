# 74 — Preserve the control flow of Python literal-true loops

**What to build:** Generate a faithful graph for Python `while True`. At the loop head, execution enters the body. A real operation in the body can still fail and reach its handler, and a real `break` can still leave the loop. Apply the fix from the Python walker through the normal export path, so newly generated Pong graphs show the actual loop semantics.

**Blocked by:** None (can start immediately).

**Status:** resolved

- [x] The Python Boolean literal `True` produces a body-entry transition with source location and has neither a false-condition exit nor an exception alternative from the loop head.
- [x] Ordinary iteration and `continue` return to the loop head. A fresh graph for a loop with no route past it does not make following statements reachable.
- [x] A real `break` reaches the loop continuation and bypasses `while … else`. Existing `return` and `raise` destinations in the body are preserved.
- [x] A body call under `try` can still follow its ordinary path or take a separate exception path to the active handler. An ordinary condition such as `while ready()` keeps its existing alternatives.
- [x] The source-to-HTML regression checks observable graph reachability on a self-contained Pong-shaped fixture. A fresh Pong global export shows the loop cycle at line 136 and the body-to-handler route from `win.update()` at line 137 to the handler at line 177.

**Roadmap placement:** Original Python walker foundation, Tickets 01–06. Follow-up to [Ticket 04](./04-walker-while-for-loops.md). The [spec addendum](../specs/python-walker-literal-true-loops.md) records the approved scope and test plan.

## Comments

### 2026-11-16 — Implemented

- Python `while True` now has a body-entry path only. The loop body retains normal and exception outcomes; `break`, `continue`, `return`, and `raise` keep their existing destinations. Other loop conditions keep their false and exceptional outcomes.
- Added source-to-HTML reachability checks in `tests/test_python_literal_true_loops.py` using the self-contained Pong-shaped fixture at `tests/test_code/petri_py/literal_true_global.py`.
- Focused verification passed: `python -m unittest tests.test_python_literal_true_loops tests.test_petri_loops tests.test_petri_try` (35 tests). The changed Python files also passed `compileall`.
- Regenerated the Pong Global Scope HTML from Python-Games source commit `3f9b5bfab39540a056e7a7fa152b686974c20b67` with `code2petri(source_path="/Volumes/SharedDrive/Documents/GitHub/Python-Games/Pong/game.py", target_function="(global)", output_file="/private/tmp/ticket74-pong-xtz73_k4/pong_global.html")`. Its embedded graph has only `while True` at line 136 leaving the loop head, cycles from `win.update()` at line 137 back to that head, and routes the call's exception alternative to the handler at line 177. The loop head has no exception alternative.
