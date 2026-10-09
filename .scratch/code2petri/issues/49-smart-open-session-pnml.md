# 49: Open Session and Resume Live Fold Reduction

**What to build:** Open a saved JSON Fold State Snapshot inside the generated, self-contained HTML viewer and continue Live Fold Reduction, Component Node Renaming, and Component-Local Unfold from the saved state.

**Blocked by:** 48 — Save Session as a Fold State Snapshot.

**Status:** resolved

- [ ] "Open Session..." in the toolbar lets the user choose a JSON Fold State Snapshot produced by Save Session and works offline. Cancelling file selection leaves the active session unchanged.
- [ ] The snapshot format version, graph and restoration records, folding state, viewport, and document context are validated before replacing the current session. Malformed or unsupported snapshots show a concise error and leave the active session intact.
- [ ] Opening restores the net, compound hierarchy and Collapsed Compound State, names, weights, Fold Config, node positions, zoom, and pan without applying a new layout.
- [ ] Continued folding allocates component IDs that do not collide with live or restorable components. Both restored components and subsequently created components support Component-Local Unfold.
- [ ] The saved document identity and existing original-net, callee, playback, and expansion context replace those of the previous document. Existing Reset/playback controls act on the loaded document, and displayed document metadata reflects its identity.
- [ ] Stale inspection and selection references are cleared; fold affordances and Structuredness Metric are refreshed against the restored graph.
- [ ] A round-trip check saves folded and renamed nested components, opens the snapshot in a viewer displaying another document, continues folding, and locally unfolds both restored and new components. It verifies topology, hierarchy, names, weights/SM, Fold Config, saved layout and viewport, document identity, and existing Reset/playback behavior where available.
- [ ] A separate round-trip check verifies that rename → unfold → save → open → re-fold retains the remembered semantic name. Repeated successful opens and rejected files do not leak state between sessions.
- [ ] The file chooser is exercised in a generated-viewer interaction check. Open accepts Fold State Snapshots only; PNML import, general JSON-net import, and a standalone application remain deferred.

## Answer

Implemented offline Open Session validation and restoration, including rollback-safe graph replacement, engine/document/playback state, viewport, and nested component continuation/unfolding. Focused coverage includes parser rejection cases, restore-state interaction, and a nested save/open/continue/unfold round trip. The chooser is wired and constrained to JSON sessions; manual browser verification was not run.

## Comments

### 2026-10-09 — Narrow Open to saved sessions

The user confirmed that the generated, self-contained HTML viewer remains the current architecture. This ticket now opens only the JSON session saved by Ticket 48. A standalone application that reads PNML/JSON and direct PNML import are deferred; the filename is retained to preserve existing ticket links.
