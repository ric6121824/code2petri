# 07 — Prefactor: Walker Protocol & Shared Infrastructure

**What to build:** The structural foundation for multi-language support. A formal `WalkerProtocol` ensures any new language parser strictly implements the required methods or fails immediately at runtime. Common Petri net bookkeeping (ID counters, loop stacks, exception stacks) is centralized so language-specific walkers can focus purely on AST reading. The existing Python walker is migrated to this new base without breaking any existing behavior, and testing assertions are cleanly separated for reuse.

**Blocked by:** None — can start immediately.

**Status:** ready-for-agent

- [x] `WalkerProtocol` is defined as an `abc.ABC` with `parse_file`, `find_function`, `find_all_functions`, `walk_function`, and `get_node_lineno` instance methods.
- [x] `ControlFlowBuilder` is created, encapsulating `place_counter`, `trans_counter`, `loop_stack`, `try_stack`, `new_place()`, and `new_transition()`.
- [x] `PythonWalker` implements `WalkerProtocol` and composes `ControlFlowBuilder`.
- [x] Python's `find_all_functions` is updated to return qualified names for class methods (e.g., `Class.method` instead of just `method`).
- [x] Shared structural assertions (e.g., `assert_has_start_and_end`) are extracted into `tests/petri_assertions.py`.
- [x] `engine.py` instantiates the walker (`walker = WALKERS[ext]()`) rather than calling static methods.
- [x] All existing Python tests pass without modification to their underlying logic.
