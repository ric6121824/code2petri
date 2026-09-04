# 04 — Python control-flow walker — while & for loops

**What to build:** Extend the Python AST walker to handle `while` and `for` loop constructs. A `while` loop produces a condition-evaluation transition with two output arcs: one to the loop body entry place (true) and one to the exit place (false). The loop body is walked recursively, and its terminal place arcs back to the condition transition's input place, creating a cycle in the Petri net. A `for` loop is modeled identically — the "iterator has next" check is the condition transition, and iterator exhaustion exits to the exit place. The `else` clause on loops (Python-specific) is modeled as an arc from the condition's false-exit to the else body before the final exit place.

**Blocked by:** 02 — Python control-flow walker — sequential & return

**Status:** ready-for-agent

- [ ] `ast.While` nodes produce a condition transition, loop-body path, and back-edge arc creating a cycle
- [ ] The condition transition has two output arcs: true → body entry, false → exit place
- [ ] The body's terminal place arcs back to the condition's input place
- [ ] `ast.For` nodes are modeled identically to while (iterator-check as condition)
- [ ] Loop `else` clauses produce an additional path between the false-exit and the final exit place
- [ ] `break` statements produce a transition arcing directly to the loop's exit place
- [ ] `continue` statements produce a transition arcing back to the condition's input place
- [ ] Test fixture: `while_loop.py` — simple while; assert cycle exists in arc set
- [ ] Test fixture: `for_loop.py` — simple for; assert same cyclic structure as while
- [ ] Test fixture: `loop_break_continue.py` — break and continue; assert correct exit/back arcs
