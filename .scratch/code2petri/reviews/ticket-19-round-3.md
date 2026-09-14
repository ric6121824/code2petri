# Ticket 19: Code Review (Round 3)

**Commit:** `HEAD`
**Spec:** `.scratch/code2petri/issues/19-inline-expansion-engine.md`

You requested another review because you had self-reviewed rounds 1 and 2. It's a good thing you asked for a check, because Round 2 inadvertently introduced a critical structural flaw.

## Spec Axis Findings & Suggestions
**STATUS: FAIL (Critical Bug)**

### (c) Implemented but looks wrong [CRITICAL]
**Finding (Horizontal Recursion Guard):**
The Round 2 fix for multi-caller call stacks is fundamentally flawed. In `inline_expand()`, `initial_stack` aggregates every `caller_function` from ALL `call_sites` across the starting net simultaneously. Call stacks must be path-dependent and vertical. By pooling all callers horizontally into the `initial_stack`, a composite net with multiple starting callers will falsely trigger the recursion guard and block valid cross-function calls simply because the target function happens to exist as a parallel caller elsewhere in the net.
**Suggestion:** The recursion guard stack must be initialized per root-level expansion and strictly passed downwards vertically, not aggregated horizontally across unrelated call sites.

### (a) Partial / Deviated Requirements
**Finding (Boundary Splicing):** The spec requested wiring to the callee's source and sink places. The implementation skips cloning the boundary places and wires directly to the callee's internal transitions. 
**Suggestion:** While this deviates from the literal spec text, it is mechanically necessary to preserve the bipartite property of Petri nets (avoiding Place-to-Place arcs). Keep the implementation as-is, but note the spec deviation.

### (b) Scope Creep
**Finding (Walker Caching):** `_get_callee_net` introduces a `walker_cache` dictionary to memoize instantiated walkers and parsed AST trees.
**Suggestion:** This caching optimization was not requested by the spec. Remove the speculative caching unless it's strictly necessary for performance right now.

---

## Standards Axis Findings & Suggestions
**STATUS: FAIL**

### 1. Documented Standard Violation (Hard Violation)
**Finding:** In `tests/test_inline_expansion.py`, a comment reads `# Merge net and call sites from both`. This violates the `CONTEXT.md` standard for **Composite Net** (rule: *Avoid: Merged graph*).
**Suggestion:** Reword to `# Build composite net and combine call sites`.

### 2. Baseline Smells (Judgement Calls)
The Round 2 report claimed all Fowler baseline code smells were resolved, but several persist or were reintroduced:

* **Duplicated Code:** The `_is_start_place(place)` helper in `inline.py` duplicates the exact logic hardcoded in `PetriNet.find_boundary_places` (`[p for p in self.places if p.initial_tokens > 0 or p.label == "start"]`). Deduplicate across the modules.
* **Feature Envy:** The extracted `_mark_recursive_cycle(trans: Transition)` is a standalone function that reaches entirely into `Transition`'s internal data to mutate its metadata dictionary. This should be a method on `Transition`.
* **Primitive Obsession:** `_is_self_referencing_game_loop` still relies on string manipulation `split(".")[-1]`. This reintroduces the exact string-hacking pattern that was cited in Round 1 for causing false positives on qualified names. Use the structured `CallFrame` logic if possible, or strictly type the resolution.
