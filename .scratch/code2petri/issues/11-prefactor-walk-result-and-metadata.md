# 11 — Prefactor: WalkResult Protocol Return Type and Transition Metadata

**What to build:** Refactor the Walker Protocol contract to prepare for structured call resolution. Currently `walk_function` returns a bare `PetriNet` and `Transition` has no slot for annotations. This ticket updates `walk_function` to return a `WalkResult` container that packages both the `PetriNet` and a list of `CallSite` records, adds an optional `metadata` mapping to `Transition`, and introduces the `collect_variable_bindings` abstract method stub to the protocol. Existing engine consumers, walkers, and test suites are updated to preserve 100% passing tests.

**Blocked by:** None — can start immediately

**Status:** closed

- [x] `CallSite` dataclass and `WalkResult` named tuple are defined in `code2petri`.
- [x] `Transition` data model supports an optional `metadata: Optional[Dict[str, Any]] = None` field, preserved across serialization formats.
- [x] `WalkerProtocol(abc.ABC)` defines abstract `walk_function(ast_node: Any, func_name: str = "") -> WalkResult` and abstract `collect_variable_bindings(tree: Any) -> Dict[str, str]`.
- [x] Both `PythonWalker` and `JavascriptWalker` implement the updated `walk_function` returning `WalkResult(net=..., call_sites=[])` and baseline `collect_variable_bindings(tree)` returning empty dicts.
- [x] `engine.py` is updated to unpack `WalkResult` from `walk_function`.
- [x] All 166 existing unit and integration tests pass without regression under the new protocol signature.
