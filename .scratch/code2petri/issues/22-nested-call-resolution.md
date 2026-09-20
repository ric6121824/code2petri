# 22 — Nested Call Resolution in Inline Expansion

**What to build:** Inner function calls within an inlined callee properly resolve against the symbol table, meaning they now render as green (resolved) rather than orange (unresolved) in the visualizer.

**Blocked by:** None — can start immediately.

**Status:** resolved

- [x] The `_get_callee_net` function (or equivalent inlining logic) accepts the `SymbolTable`.
- [x] `CallSite` records internal to the callee are explicitly resolved against the `SymbolTable` before the callee subnet is spliced into the caller net.
- [x] Visualizer integration test or manual verification proves that nested call transitions receive the `resolved = true` metadata and are styled green in DOT/HTML outputs.

## Answer
- Updated `_get_callee_net(symbol: Symbol, symbol_table: Optional[SymbolTable] = None)` in `code2petri/inline.py` to accept `symbol_table`.
- Within `_get_callee_net`, if `symbol_table is not None and callee_net is not None and callee_call_sites`, `symbol_table.resolve_call_sites(callee_net, callee_call_sites)` is invoked prior to returning.
- Passed `symbol_table=symbol_table` from `_inline_expand_recursive` when calling `_get_callee_net`.
- Splicing in `_splice_callee_net` preserves transition `resolution` and `metadata`, ensuring nested call transitions receive `fillcolor="#2e7d32"` in Graphviz DOT and `resolved: true` (styling class `resolved`) in the HTML viewer.
- Verified across Python and JavaScript test cases in `tests/test_inline_expansion.py` (`test_nested_call_resolution_resolved`, `test_nested_call_resolution_unresolved`, `test_nested_call_visualizer_rendering`, and `test_game_of_life_loop_inline`).
