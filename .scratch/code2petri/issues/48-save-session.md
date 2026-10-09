# 48: Save Session as a Fold State Snapshot

**What to build:** Download the current session as a JSON Fold State Snapshot from the generated, self-contained HTML viewer, retaining the information needed to resume folding and unfolding later. This slice delivers a verifiable download; Ticket 49 adds reopening.

**Blocked by:** None (can start immediately).

**Status:** resolved

- [ ] "Save Session" in the toolbar downloads a versioned JSON Fold State Snapshot while the generated viewer runs offline.
- [ ] The snapshot records the current net, compound hierarchy and Collapsed Compound State, component names, Transition Weights, Component Penalties, Fold Config, node positions, zoom, and pan.
- [ ] Complete consumed subgraphs and boundary connections are retained for Component-Local Unfold, including nested folds and consumed function containers.
- [ ] The snapshot retains component-ID allocation state and remembered semantic names, including names of components that were unfolded before saving.
- [ ] Document title, source file and root-function identity, original net, and the existing callee, playback, and expansion context are retained where applicable, so reopening can restore existing viewer controls against the saved document.
- [ ] The download contains session data without another copy of the viewer code. Its filename uses the current net title followed by the suffix "_session.json".
- [ ] Saving leaves the active graph, fold state, selection, layout, and camera unchanged.
- [ ] Verification exercises the toolbar download and compares its parsed contents with a session after folding, renaming, unfolding, and moving the camera. It checks the hidden restoration data as well as visible state and can pass before Open Session is implemented.

## Answer

Implemented versioned Fold State Snapshot serialization and the offline download action, including live elements, restoration records, engine state, viewport, and document context. Automated save and round-trip tests passed within the focused viewer suite. Manual browser verification was not run.

## Comments

### 2026-10-09 — Keep session continuity within the generated HTML viewer

The user confirmed that Phase 2.8 retains the generated, self-contained HTML architecture. Save Session downloads JSON for reopening through the viewer; a standalone application and PNML import are deferred. The snapshot records the live engine state and document context rather than relying on the unused `history` array.
