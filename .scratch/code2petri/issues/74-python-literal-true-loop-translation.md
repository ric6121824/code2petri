# 74 — Preserve the control flow of Python literal-true loops

**What to build:** Generate a faithful graph for Python `while True`. At the loop head, execution enters the body. A real operation in the body can still fail and reach its handler, and a real `break` can still leave the loop. Apply the fix from the Python walker through the normal export path, so newly generated Pong graphs show the actual loop semantics.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] The Python Boolean literal `True` produces a body-entry transition with source location and has neither a false-condition exit nor an exception alternative from the loop head.
- [ ] Ordinary iteration and `continue` return to the loop head. A fresh graph for a loop with no route past it does not make following statements reachable.
- [ ] A real `break` reaches the loop continuation and bypasses `while … else`. Existing `return` and `raise` destinations in the body are preserved.
- [ ] A body call under `try` can still follow its ordinary path or take a separate exception path to the active handler. An ordinary condition such as `while ready()` keeps its existing alternatives.
- [ ] The source-to-HTML regression checks observable graph reachability on a self-contained Pong-shaped fixture. A fresh Pong global export shows the loop cycle at line 136 and the body-to-handler route from `win.update()` at line 137 to the handler at line 177.

**Roadmap placement:** Original Python walker foundation, Tickets 01–06. Follow-up to [Ticket 04](./04-walker-while-for-loops.md). The [spec addendum](../specs/python-walker-literal-true-loops.md) records the approved scope and test plan.
