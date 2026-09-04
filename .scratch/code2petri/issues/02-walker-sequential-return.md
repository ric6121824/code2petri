# 02 — Python control-flow walker — sequential & return

**What to build:** A Python AST walker that accepts a function definition node and produces a `PetriNet` representing the function's control flow for the simplest constructs: sequential statements and return statements. Given a function with N sequential lines, the output is a linear chain of N transitions (one per statement) connected by N+1 places (including a start place with 1 initial token and an end place). Return statements arc to a single shared terminal place. Function calls within statements appear as opaque transitions labeled with the call expression. This establishes the baseline walker that all subsequent tickets extend.

**Blocked by:** 01 — Petri net data model & serializers

**Status:** done

- [x] `python_walker.py` module with a `walk_function(ast_node) -> PetriNet` entry point
- [x] Sequential statements produce a place→transition→place chain, one transition per statement
- [x] Transitions are labeled with a summary of the statement and include the line number
- [x] Function calls appear as transitions labeled `call: func_name()`
- [x] Return statements produce a transition arcing to a single shared terminal `end` place
- [x] The start place has `initial_tokens=1`
- [x] The walker imports `Python.get_tree()` from code2flow to parse source files
- [x] Test fixture: `sequential.py` — a function with 5 sequential statements and a return; assert correct place/transition/arc counts and connectivity
- [x] Test fixture: `multi_return.py` — a function with multiple return paths; assert all returns converge on the same terminal place
