# 19 — Inline Expansion Engine

**What to build:** Given a caller `PetriNet`, its `CallSite` records, and a populated `SymbolTable`, an inline expansion function splices resolved callee Petri nets directly into the caller net at the Python data-model level, producing a Composite Net.

For each resolved call transition in the caller net:
1. Walk the callee function using the existing walker infrastructure to produce the callee's `PetriNet`.
2. Clone all callee nodes with a namespace prefix (e.g., `inline_<callee_id>__<original_id>`) to prevent ID collisions.
3. Remove the opaque call transition from the caller net.
4. Wire the call transition's preset place → callee's source place, and callee's sink place → call transition's postset place.

Expansion defaults to depth 1 and is configurable. A recursion guard tracks the active expansion call stack; if a callee appears in the stack (direct or indirect recursion), expansion halts and the call transition is retained as an annotated Opaque Transition with `metadata={"recursive_cycle": True}`.

The resulting Composite Net is a standard `PetriNet` instance, directly compatible with all existing serializers (PNML, DOT, JSON) and with the fold engine from Tickets 17–18.

**Blocked by:** None — can start immediately (uses existing `SymbolTable` and `WalkerProtocol` infrastructure from Phase 2).

**Status:** ready-for-agent

- [ ] An inline expansion function accepts a `PetriNet`, a list of `CallSite` records, a `SymbolTable`, and optional `max_depth` (default 1), and returns a new `PetriNet` with resolved callees spliced in.
- [ ] Callee nodes are cloned with namespace prefixes that prevent ID collisions across multiple inlined callees.
- [ ] The opaque call transition is removed and its preset/postset arcs are rewired to the callee's source and sink places.
- [ ] The resulting Composite Net passes `assert_valid_petri_net` (bipartite, has start/end, non-empty).
- [ ] Recursion guard: a self-referencing call site (e.g., `loop` calling `requestAnimationFrame(loop)`) retains the call transition as an Opaque Transition with `{"recursive_cycle": True}` metadata instead of infinite expansion.
- [ ] Depth capping: a 3-deep call chain with `max_depth=1` expands only the first level; deeper call transitions remain opaque.
- [ ] Unresolved call transitions are left untouched (no expansion attempted).
- [ ] Unit tests verify: single callee splicing (correct node count, arc wiring, no orphaned nodes); recursive call guard; depth-1 cap on a multi-level chain; unresolved calls remain opaque.
- [ ] Existing tests continue to pass.
