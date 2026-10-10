# 51: Compact, lossless Fold State Snapshot saves

**What to build:** Let users save a deeply folded session from the generated offline viewer as a compact JSON Fold State Snapshot, reopen it, and continue Live Fold Reduction and Component-Local Unfold with the complete original session intact. This replaces the narrower Safari-only Ticket 51; Ticket 52 covers the browser download lifecycle.

**Blocked by:** None (can start immediately).

**Status:** resolved

- [x] Save Session writes each nested component restoration record once under canonical `consumedSubnet`, before cloning or serialization could multiply legacy `consumedSubgraph` aliases. The output retains the existing version-1 snapshot type, `.json` filename rules, offline behavior, and all data needed for restoration.
- [x] Capturing and downloading use compact JSON without redundant whole-snapshot JSON copies. The resulting snapshot is detached from subsequent live edits, and saving does not alter the active graph, fold state, selection, names, metrics, layout, or viewport.
- [x] A deterministic sequence fixture of 14 places and 13 transitions, folded 12 times to three visible nodes, saves to less than 100 KiB with a minimal valid document context. Smaller depths show no recursive alias-driven growth. Record byte counts and elapsed time for this and a representative larger net; do not assert machine-specific timing thresholds.
- [x] Open Session accepts canonical-only, legacy-only, both-field, and mixed nested version-1 restoration records. Existing canonical-field precedence is retained when both fields are present. Reopening and resaving any supported legacy form produces canonical-only restoration records; malformed input is still rejected before replacing the active session.
- [x] Save → Open → unfold all 12 nested components restores the original node/edge IDs, topology, relevant metadata, and weights. Component-Local Unfold leaves unrelated folds intact. Rename → unfold → save → open → refold retains remembered names; subsequent folds use noncolliding component IDs.
- [x] Existing compound and Collapsed Compound State, Fold Config, Transition Weight, Component Penalty, Structuredness Metric behavior, document/original-net/callee/playback context, positions, zoom, and pan survive a representative round trip. A compact snapshot remains readable under the existing version-1 contract.
- [x] Automated verification uses the production Save Session and Open Session paths and checks complete downloaded JSON plus resumed behavior. Size improvement does not rely on omitting restoration history or document context. PNML export and the generated HTML architecture remain unchanged.

Specification: [Phase 2.9 — Compact and Reliable Fold State Snapshots](../specs/phase-2.9-session-snapshot-optimization.md).

## Comments

- 2026-10-10: Implemented compact canonical snapshots and compatibility resaves. The 12-level sequence fixture measured 14,888 / 17,821 / 20,802 / 23,853 bytes at depths 3 / 6 / 9 / 12, with 0–3 ms capture times in one local run. The 12-level file reopened and unfolded to the original 27 nodes and 26 edges. An equivalent synthetic size-profile fixture (849 nodes, 904 edges) measured 385,614 bytes fresh in 9 ms and 397,458 bytes after 12 folds in 10 ms. No Aeroblasters source fixture was present, so this is a documented size-equivalent profile rather than a recreation of that workload.
- Focused snapshot/download tests pass (11 tests); the full viewer module passes (134 tests).
