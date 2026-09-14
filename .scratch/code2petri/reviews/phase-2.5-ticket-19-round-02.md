# Ticket 19: Code Review (Round 2)

**Commit:** `HEAD`
**Spec:** `.scratch/code2petri/issues/19-inline-expansion-engine.md`

## Spec Axis Findings & Suggestions
**STATUS: PASS**

All findings from the Round 1 review and Round 2 inspection have been successfully addressed:
- **Game-Loop Cycle Detection:** `requestAnimationFrame(loop)` is checked structurally and annotated with `{"recursive_cycle": True}`, retaining the call transition as an opaque transition.
- **Multi-Caller Call Stack Tracking:** `initial_stack` aggregates all callers across `call_sites` in the caller net rather than indexing only the first call site.
- **Qualified Method Recursion Guard:** Class methods and bare function names within the same file path are unified via `CallFrame(filepath, name)` matching, preventing qualification mismatch bypasses.
- **Boundary Degeneracy Guard:** `_splice_callee_net` verifies that `callee_source_place.id != callee_sink_place.id`, ensuring source and sink boundaries do not coincide.
- **Scope Creep Removed:** Eliminated speculative net caching and unrequested `resolve_call_sites` metadata decoration on depth-capped unexpanded transitions.
- **Test Coverage:** Comprehensive tests covering single callee splicing, depth capping, mutual/direct recursion, RAF game loop, class method recursion, multi-caller initial stack, and boundary place discovery.

---

## Standards Axis Findings & Suggestions
**STATUS: PASS**

All documented standards in `CONTEXT.md` are strictly adhered to (no prohibited vocabulary, proper use of `Inline Expansion`, `Composite Net`, `Opaque Transition`, `Call Site`, `Walker Protocol`).

All Fowler baseline code smells have been addressed:
1. **Data Clumps:** Replaced raw `Tuple[str, str]` call stack tracking with dedicated immutable `CallFrame` dataclass.
2. **Feature Envy:** Moved `find_boundary_places()` onto `PetriNet` in `code2petri/model.py`.
3. **Duplicated Code:** Extracted `_mark_recursive_cycle(trans)` and `_is_start_place(place)` helpers to remove redundant dictionary initialization and start-place predicates.
4. **Clean API Boundaries:** Hidden internal recursion implementation (`_inline_expand_recursive`) behind clean, strictly typed `inline_expand(net, call_sites, symbol_table, max_depth=1)`.
