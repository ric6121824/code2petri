# Phase 2.8: Viewer Interactive Enhancements

## Problem Statement

The HTML Petri net viewer lacks fluid interaction models for bulk reduction and session continuity. The current floating inspector popup obscures the canvas and is disconnected from the node it describes. Reducing a heavily nested function requires clicking every place node inside it one by one, which is tedious. Furthermore, closing the browser throws away all Live Fold reductions and camera panning done during a session; there is no way to save the interactive state to pick it up later.

## Solution

We will upgrade the viewer UI from a floating inspector popover to a docked right sidebar (Variant A) that pushes the canvas horizontally, providing a permanent home for metadata and bulk action buttons. Cytoscape box selection will be enabled, allowing users to drag-select multiple places and trigger a single-pass "Batch Place Fold". For compounds, a new "Fold Entire Function" button in the sidebar will recursively fold eligible descendant places until the compound collapses or no further progress is possible. Finally, the bottom-left info panel will surface the active `function_name` alongside the source file path.

The existing generated HTML remains the self-contained viewer, with its graph and feature code embedded. "Save Session" downloads a JSON Fold State Snapshot containing session data, including the subgraphs needed for later unfolding, without another copy of the viewer code. To resume, the user opens a generated HTML viewer with these features and uses "Open Session..." to load the snapshot. This phase retains the current offline HTML architecture; a standalone application and PNML import are deferred.

## User Stories

1. As a user, I want the node inspector to live in a docked sidebar that pushes the canvas aside, so that my view of the graph is never obscured by a floating popover.
2. As a user, I want the sidebar to maintain the production light theme, so that the viewer remains visually cohesive.
3. As a user, I want to drag a selection rectangle around multiple place nodes, so that I can select them at once using standard box selection.
4. As a user, I want to click a "Fold Selected Places" button in the sidebar when multiple places are selected, so that I can trigger a Batch Place Fold that sequentially evaluates and folds all contractible places in the selection in one pass.
5. As a user, I want to select a compound node and click a "Fold Entire Function" button in the sidebar, so that the engine recursively folds eligible places within that compound until it reaches a Collapsed Compound State or no further progress is possible.
6. As a user, I want to click a "Save Session" button in the toolbar, so that I can download a Fold State Snapshot (`.json`) containing the current net, fold state, component names, node layout, and camera viewport.
7. As a user, I want to click "Open Session..." in the generated HTML viewer and select a previously saved Fold State Snapshot, so that I can resume the same visual state and continue folding, renaming, and locally unfolding components, including components folded before saving.
8. As a user, I want the bottom-left info panel to display the source `function_name` next to the file name, so that I can immediately identify the root function of the displayed Petri net.

## Implementation Decisions

- **Variant A Docked Sidebar:** We will remove the absolute-positioned `#inspector-panel` from `template.html` and replace it with a flex-based `<aside>` sidebar on the right. The `#main-container` will become a flex row containing `#cy` (with `flex: 1`) and the sidebar (fixed width). The sidebar will inherit the light theme colors from the existing production styles.
- **Batch Place Fold (Selection):** We will set `boxSelectionEnabled: true` in the Cytoscape initialization in `template.html`. When the selection contains ≥2 `.place` nodes, the sidebar will show a "⚡ Fold Selected Places" button. Clicking it iterates through the selected places *once* in graph order, executing the appropriate fold on any place that is contractible at the moment of evaluation.
- **Fold-Entire-Function (Compound):** When a `.compound` node is selected, the sidebar will present a "⚡ Fold Entire Function" button. Clicking it triggers an unbounded loop that repeatedly queries all `.place` descendants of the compound for contractibility and folds them until a fixed point is reached (either a fully collapsed state or a state where no remaining places are contractible).
- **Session Serialization:** Use a versioned JSON format for `Fold State Snapshot`, containing:
  - `schemaVersion`: The snapshot format version, validated on open.
  - `elements`: The output of `cy.elements().jsons()`, preserving positions, function hierarchy, component names and weights, collapsed state, and all recursive `consumedSubnet` records needed for Component-Local Unfold.
  - `engine`: The `stepCounter`, folding configuration (`cfg`), and `rememberedCustomNames` serialized as key/value entries. Restore these so continued folding uses unique component IDs, the same penalties, and remembered names after unfold/re-fold.
  - `viewport`: Zoom and pan from the existing `captureViewport(cy)` export in [viewport.js](../../../code2petri/viewer/engine/viewport.js).
  - `document`: Net title, source/function identity, and the originating data needed by existing viewer controls such as Reset or playback. Loading a snapshot must not leave those controls attached to another net's embedded payload.
  - `engine.history` is currently unused. The recursive component records in `elements` provide unfold state; an empty history array is not a substitute for them.
- **Open Session:** A hidden `<input type="file" accept=".json">` triggered by the toolbar "Open Session..." button accepts this snapshot format. Parse and validate the version, graph, and required session state before replacing the active session. Restore graph, engine, document context, and viewport using the existing `restoreViewport(cy, zoom, pan)` export; refresh the inspector, fold affordances, and SM without running a new layout. A rejected snapshot leaves the current session intact. General JSON-net import and PNML import are outside this phase.
- **Info Panel Update:** The data payload parsing in `template.html` will be updated to extract `payload.composite_net.function_name` (or similar) and bind it to a new DOM element in `#info-panel` alongside `#info-filename`.

## Testing Decisions

- **Seam 1: JavaScript Engine Tests (`tests/test_live_fold_prototype.py`):** Extend the existing Node.js subprocess tests to test the core logic of the Batch Place Fold and Fold-Entire-Function algorithms in a headless JS context. Assert that passing an array of place IDs to a new `engine.executeBatchFold(nodeIds)` correctly reduces them, skipping invalid ones.
- **Seam 2: HTML Output Validation (`tests/test_html_viewer.py`):** We will add tests to verify that the generated `template.html` correctly includes the new CSS for the docked sidebar, the `boxSelectionEnabled` flag, and the new toolbar buttons. We will use string matching (as done in `test_info_panel_layout`) to ensure the DOM structure is correct.
- **Seam 3: Session Round-Trip Tests:** Fold and rename nested components, save a snapshot, reopen it, continue folding without component-ID collisions, and locally unfold both earlier and later components. Verify topology, hierarchy, names, weights/SM, layout, and viewport. Also cover a renamed component that was unfolded before saving, document context replacement, and rejection of invalid or unsupported snapshots without changing the current session.

## Out of Scope

- Synchronizing fold states back to the Python backend. The Fold State Snapshot is purely for client-side resumption.
- A standalone application, externalizing the embedded viewer code, or changing how the CLI generates self-contained HTML.
- PNML import and general JSON-net import. Open Session reads only saved Fold State Snapshots; existing PNML export remains available.
- Complex error recovery for a corrupted or malformed snapshot; a simple `alert()` or `showToast()` error is sufficient, while preserving the active session.
- Re-theming the entire viewer to a dark mode. The new sidebar must match the existing light theme.

## Further Notes

- The terms "Batch Place Fold", "Fold-Entire-Function", and "Fold State Snapshot" have been added to the project's `GLOSSARY.md`.

## Comments

- 2026-10-09: User clarified that the generated HTML architecture should remain for now. Save/open is limited to resuming saved sessions; standalone-app work and PNML import are deferred. Tickets [48](../issues/48-save-session.md) and [49](../issues/49-smart-open-session-pnml.md) cover this workflow.
- 2026-10-10: [Ticket 53](../issues/53-called-function-fold-boundary-trigger.md) diagnoses a follow-up defect in function folding: valid function-owned Choice branches are rejected when their shared entrance or exit is a caller-owned place, and entrance-side choices lack an internal-place trigger. The follow-up permits retained caller boundaries as anchors while preserving consumption containment, existing reduction rules, and partial completion for unsupported graphs. This fix belongs to Phase 2.8, separately from Phase 2.10 return metadata.

## Delivery Record

Tickets 45–50 are resolved. The docked sidebar, selection and compound folding actions, offline Fold State Snapshot save/open flow, and root-function info panel are delivered. See the [Phase 2.8 Round 3 review report](../reviews/phase-2.8-tickets-45-50-round-03.md) for the final review outcome.
