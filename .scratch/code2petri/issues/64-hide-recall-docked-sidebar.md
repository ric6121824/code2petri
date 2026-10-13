# 64: Hide and Recall the Docked Sidebar

**What to build:** Users can instantly hide the right Docked Sidebar to reclaim graph space and recall it with a small tab near the top of its edge. The tab stays reachable when hidden, the graph keeps its camera/layout, inspection continues independently, and saved sessions restore the chosen sidebar visibility.

**Blocked by:** None (can start immediately).

**Status:** ready-for-human

- [x] When shown, place a small hide/recall tab near the top of the sidebar's left boundary. When hidden, retain it near the top of the graph's far-right edge at the same height. Use a right-pointing chevron to hide and a left-pointing chevron to recall, descriptive Hide Sidebar / Show Sidebar tooltips and accessible labels/state, keyboard activation, and visible focus. The tab must remain usable regardless of inspector scrolling and must not be clipped off-screen. It replaces the proposed toolbar toggle.
- [x] Hiding removes the entire sidebar from layout and returns its full width to the graph, leaving only the small recall tab. Showing restores the existing docked width and light-theme layout. Both transitions are immediate: no slide, fade, or width animation. The existing clear-inspection control retains its separate action.
- [x] Resize the canvas to the resulting layout without graph layout, fit, recentering, reset, reduction, or changes to node positions, zoom, or pan. Keep graph pointer/selection interactions correct after repeated toggles. Do not add sidebar drag resizing or an overlay inspector mode.
- [x] Keep visibility separate from inspected-node identity, node selection, and content/empty state. Inspecting another node, selection changes, background clearing, programmatic inspector refresh, and supported graph actions while hidden do not automatically reveal the sidebar. Recall displays the latest valid details and applicable actions, including Batch Place Fold availability, or the current empty state if inspection was cleared or its node was removed.
- [x] Hiding and recalling the same inspected node preserves unfinished component-name input without saving or clearing it. Selecting another node or clearing inspection retains the existing replacement/clear behavior. No per-node draft store, automatic Save Name, or new persistence for unfinished input/inspected-node identity is added.
- [x] New viewers default to shown. Save Session records optional shown/hidden viewing metadata in the existing version-1 Fold State Snapshot, without mutating the current session. Open Session restores the incoming visibility even when the host viewer has the opposite state. Older valid snapshots without it default to shown; Reset preserves the current visibility choice.
- [x] Validate recognized visibility metadata as a boolean before replacing active state. Invalid additions leave the graph, document identity, sidebar state, and camera unchanged. Establish the restored sidebar layout/canvas dimensions before restoring camera zoom/pan. Preserve existing compact, offline capture/open and fold-continuation contracts.
- [x] Hiding moves keyboard focus to the tab if it would otherwise remain in invisible sidebar contents. Hidden sidebar controls are not keyboard-focusable; recalling allows normal keyboard access to the inspector. The tab remains operable in both states without a pointer.
- [ ] Verify through actual generated-viewer interactions and production save/open: near-top edge placement, canvas width reclaim/restore, no animation, pointer and keyboard operation, repeated toggles, unchanged positions/zoom/pan, hidden inspection/selection/clear/action flows, same-node drafts and node replacement, shown/hidden session round trips into opposite-state viewers, old snapshots, Reset, and malformed-state rejection. Browser geometry/rendering checks establish spatial behavior; headless logic or source-string matching alone is insufficient. Use self-contained source/net fixtures and existing inspector/session seams.
- [x] Preserve graph/document and function identities, Project Title, return metadata, tokens, Call Site resolution, fold eligibility/results, weights/Structuredness Metric, component names/history, and unrelated controls. Sidebar actions operate normally when recalled. This ticket is independent of the Project Title and called-function folding follow-ups.

## Context

This is a Phase 2.8 follow-up to the resolved Ticket 45. The current close control deliberately clears inspection while leaving the sidebar visible. Optional visibility is a new feature and refines the original permanently-visible decision; it does not reopen Ticket 45 as defective. The agreed design retains the docked, unobscured layout when shown and uses a near-top edge tab for explicit recall, with no animation or duplicate toolbar toggle.

Specification: [Phase 2.8 — Viewer Interactive Enhancements](../specs/phase-2.8-viewer-interactive-enhancements.md).

## Comments

### 2026-10-13 — Published

The user settled all hide/recall, persistence, draft, and placement decisions through grill-with-docs/grill-me, choosing the near-top tab position and replacing the earlier toolbar-toggle proposal. Published as one complete, unblocked ticket with to-tickets after incorporating the agreements into Phase 2.8 with to-spec. The amended docked-sidebar decision and glossary capture the agreed visibility/inspection distinction.

### 2026-10-13 — Implementation

Implemented the independent hide/recall edge tab in the generated viewer. Hiding returns the sidebar width to the graph while preserving the camera, inspector state, and same-node draft; keyboard focus moves out of hidden controls. Fold State Snapshots now save and validate the optional visibility boolean, restore the sidebar layout before camera state, default older snapshots to shown, and leave Reset behavior unchanged.

Focused verification passed: `python3 -m unittest tests.test_sidebar_visibility` and the targeted sidebar, inspector, and session snapshot tests. `python3 -m compileall -q code2petri` passed. The full suite ran 566 tests and reported five existing environment/baseline issues: the prototype runner could not bind its test port; pygraphviz and pytest are unavailable; and two unrelated legacy tests fail on existing result-shape/protocol mismatches. Actual generated-viewer browser geometry, pointer, keyboard, and end-to-end session checks remain pending human verification, so the ticket remains `ready-for-human`.
