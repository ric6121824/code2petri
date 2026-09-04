# 03 — Python control-flow walker — if/else/elif

**What to build:** Extend the Python AST walker to handle `if`, `else`, and `elif` branching constructs. When the walker encounters an `ast.If` node, it produces a condition-evaluation transition that forks into two places (true-branch entry, false-branch entry). Each branch is walked recursively using the existing sequential logic. Both branches' terminal places converge into a shared merge place. Elif chains are modeled as nested if/else — the false branch of the first condition leads to the next condition's evaluation transition. The resulting Petri net accurately represents all decision paths through the function.

**Blocked by:** 02 — Python control-flow walker — sequential & return

**Status:** done

- [x] `ast.If` nodes produce a condition transition with two output arcs to true-branch and false-branch entry places
- [x] True and false branches are walked recursively, producing their own place/transition chains
- [x] Both branches merge into a single merge place after their bodies complete
- [x] `elif` chains are handled as nested if/else (the false branch recurses into the next `ast.If`)
- [x] `if` without `else` produces a false-branch arc that skips directly to the merge place
- [x] Test fixture: `if_else.py` — simple if/else; assert fork, two branches, merge
- [x] Test fixture: `if_elif_else.py` — cascading elif; assert correct nesting depth and merge points
- [x] Test fixture: `if_no_else.py` — if without else; assert the false-branch skips to merge
