# 17 — FoldConfig & Structural Component Detection

**What to build:** Given any `PetriNet` produced by the existing walker pipeline, a detection function identifies all well-structured single-entry/single-exit components present in the net — Sequences, Choices (XOR-split/join), and Loops (Cycles) — and returns them as a prioritized list sorted by Definition 21 (simplest first, smallest first within the same priority).

A typed `FoldConfig` dataclass holds the configurable base penalty weights ($\rho$): Sequence = 0, Choice = 1, Marked-Graph (AND-split) = 2, Loop = 3, Unstructured = 7. AND-split detection is not implemented in v1 but the weight is formally present in the config for Phase 3 extensibility.

Each detected component records: its type, the set of internal node IDs (places and transitions), the entrance node, the exit node, and the computed penalty weight $\omega$ per Definition 22 (incorporating the base $\rho$ and the symmetry multiplier `diff` for lopsided branching).

**Blocked by:** None — can start immediately.

**Status:** closed

- [x] `FoldConfig` dataclass exists with configurable $\rho$ weights for Sequence, Choice, Marked-Graph, Loop, and Unstructured, plus a factory method for loading from a JSON string or file path.
- [x] A `Component` dataclass exists recording type, internal node IDs, entrance, exit, and computed $\omega$.
- [x] A detection function accepts a `PetriNet` and `FoldConfig` and returns a list of `Component` instances sorted by Definition 21 priority (Sequence → Choice → Loop), with ties broken by smallest internal node count.
- [x] Sequence detection correctly identifies linear chains of place → transition → place with no branching.
- [x] Choice (XOR-split/join) detection correctly identifies a place splitting to multiple transitions that all converge on a single merge place.
- [x] Loop (Cycle) detection correctly identifies a cycle with a single entry place and a single exit arc.
- [x] Penalty weight $\omega$ is calculated per Definition 22 with the symmetry multiplier for Choices.
- [x] Unit tests verify detection on hand-built nets: pure sequence, single XOR-split/join, single loop, mixed net with multiple component types, and a net with no detectable components (fully unstructured).
- [x] Existing 235 tests continue to pass (no regressions).
