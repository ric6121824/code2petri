# 01 — Petri net data model & serializers

**What to build:** The foundational `Place`, `Transition`, `Arc`, and `PetriNet` classes that represent a Petri net in memory, plus two serialization methods: `to_pnml()` producing valid ISO/IEC 15909-2 PNML XML, and `to_dot()` producing Graphviz DOT with circles for places, filled rectangles for transitions, and directed arcs. A developer can construct a PetriNet by hand in Python, call `to_pnml()` or `to_dot()`, and get correct, parseable output. Places support `initial_tokens` for marking, and arcs enforce the bipartite constraint (Place→Transition or Transition→Place only).

**Blocked by:** None — can start immediately.

**Status:** done

- [x] `Place` class with `id`, `label`, `line_number`, `initial_tokens` attributes
- [x] `Transition` class with `id`, `label`, `line_number` attributes
- [x] `Arc` class with `source`, `target`, `weight` attributes; raises error if both endpoints are the same type (enforcing bipartite constraint)
- [x] `PetriNet` container class holding lists of places, transitions, and arcs
- [x] `PetriNet.to_pnml()` produces well-formed XML with `<pnml>`, `<net>`, `<place>`, `<transition>`, `<arc>` elements and `<initialMarking>` for tokens
- [x] `PetriNet.to_dot()` produces valid Graphviz DOT with correct shapes and `rankdir=TB`
- [x] Unit test: hand-build a small net (3 places, 2 transitions, 4 arcs), assert PNML is valid XML, assert DOT is parseable
- [x] Unit test: bipartite constraint violation raises an error
