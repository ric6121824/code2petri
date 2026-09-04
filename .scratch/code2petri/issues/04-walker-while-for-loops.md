# 04 — Python control-flow walker — while & for loops

**What to build:** Extend the Python AST walker to handle `while` and `for` loop constructs using standard Petri net choice semantics (XOR-split / conflict). A loop's incoming place acts as a loop head decision place connecting to two competing transitions: one representing the true condition / iteration step (leading to the loop body entry place) and one representing condition false / exhaustion (leading to the exit place or loop `else` body). The loop body is walked recursively, and its terminal transition (along with any `continue` transition) arcs back to the loop head place, creating a cycle in the Petri net. A `for` loop is modeled identically — the loop head place splits between an iterator-has-next transition and an iterator-exhausted transition. The `else` clause on loops (Python-specific) is executed when the loop finishes normally, modeled as a path from the false transition through the else body to the loop exit place, whereas `break` transitions exit directly to the loop exit place.

**Blocked by:** 02 — Python control-flow walker — sequential & return

**Status:** done

- [x] `ast.While` nodes produce a standard choice construct (XOR-split) at the loop head place connecting to a loop transition and an exit transition
- [x] The loop transition enters the body; the body's terminal transition arcs back to the loop head place, creating a cycle
- [x] The loop exit transition connects to the loop exit place (or else-clause entry place)
- [x] `ast.For` nodes are modeled identically to while (iterator-next vs exhaustion as competing transitions from loop head)
- [x] Loop `else` clauses produce an additional path between the exit transition and the final loop exit place
- [x] `break` statements produce a transition arcing directly to the loop's exit place (bypassing `else`)
- [x] `continue` statements produce a transition arcing back to the loop head place
- [x] Test fixture: `while_loop.py` — simple while; assert cycle exists in arc set
- [x] Test fixture: `for_loop.py` — simple for; assert same cyclic structure as while
- [x] Test fixture: `loop_break_continue.py` — break and continue; assert correct exit/back arcs
