# 03 — Python control-flow walker — if/else/elif

**What to build:** Extend the Python AST walker to handle `if`, `else`, and `elif` branching constructs using standard Petri net choice semantics (XOR-split / conflict). When the walker encounters an `ast.If` node, the incoming place acts as a decision place connecting to two competing transitions: a true condition transition (e.g. `if condition`) leading to the true branch entry place, and an alternative/else transition leading to the false/else branch. Each branch is walked recursively using the existing sequential logic. Both branches converge into a shared merge place (XOR-join). Elif chains are modeled as nested if/else — the false transition leads to a place which serves as the decision place for the next condition. For an `if` without `else`, the false transition connects directly to the merge place, allowing the execution token to bypass the true branch. The resulting Petri net accurately represents mutually exclusive decision paths and preserves 1-safeness and soundness.

**Blocked by:** 02 — Python control-flow walker — sequential & return

**Status:** done

- [x] `ast.If` nodes produce a standard choice construct (XOR-split): the incoming decision place connects to two mutually exclusive transitions (true condition transition and false/else transition)
- [x] Firing the true condition transition enters the true branch; firing the false transition enters the else branch or skips to merge
- [x] Both branches converge into a shared merge place (XOR-join) after their bodies complete
- [x] `elif` chains are handled as nested if/else (the false transition leads to the decision place of the next `ast.If`)
- [x] `if` without `else` produces a false transition that connects directly to the merge place
- [x] Test fixture: `if_else.py` — simple if/else; assert XOR-split from decision place to true/false transitions, two branches, and convergence at merge place
- [x] Test fixture: `if_elif_else.py` — cascading elif; assert correct nesting depth, decision places, and shared merge points
- [x] Test fixture: `if_no_else.py` — if without else; assert false transition skips directly to merge place
