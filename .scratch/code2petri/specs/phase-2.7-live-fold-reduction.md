# Phase 2.7: Live Fold Reduction and Interactive Viewer Architecture

Status: ready-for-human

Implementation: complete (Tickets 29–44, 61, and 67; updated 2026-10-16).

Ticket 67's depth palette is implemented, including shared depth-class generation and restoration refresh. Rendered colors, legacy-session interaction, and related browser acceptance remain pending as recorded in its checklist. The original problem statements below describe the motivation before delivery.

## Problem Statement

The current `code2petri` workflow strictly segregates reduction logic from the visualization layer. The Python backend fully pre-computes a linear sequence of fold steps using the Structuredness Metric (SM) rules, and the HTML Cytoscape viewer acts merely as a playback mechanism (the fold slider). Furthermore, inline function expansion is completely orthogonal to the fold process: clicking an opaque transition splices the raw callee sub-net into a compound node, but the user cannot interactively "fold" specific parts of that newly expanded logic, nor can they view the entire composite program structure in full detail upon first opening the HTML artifact. 

This leads to a rigid, top-down exploration experience. Users cannot selectively simplify messy knots, rename abstracted transitions for clarity, or export the resulting "half-folded" architecture to external tools like ProM. They are trapped on a linear undo slider that doesn't understand the localized, non-linear nature of program comprehension.

Before Ticket 67, the viewer clamped deeper expanded compound colors to orange. GameState._coerce_direction() and its parent GameState._edge_for_move() therefore shared that color despite different nesting depths. Orange also identifies unresolved call transitions, so expanded function boundaries could suggest unresolved status. The implemented cycle distinguishes adjacent levels without changing graph hierarchy.

## Solution

The viewer will be fundamentally rearchitected to support **Live Fold Reduction**. 

Instead of opening a collapsed graph, the viewer will boot into a fully-expanded composite view, showing all inlined functions nested within visual compound nodes right from the start. The ProM local reduction algorithms (Sequence, Choice, Loop) will be ported from Python to JavaScript. This allows the user to left-click any intermediate routing place on the canvas to trigger a "Place-Centric Fold Trigger," dynamically contracting that place and updating transition weights in real-time. 

When an entire inline expansion (a compound node) is fully folded from the inside out, it transitions into a "Collapsed Compound State" visually resembling a closed folder labeled with the function's name and component ID. Folds are fully reversible via "Component-Local Unfold" (clicking the collapsed element restores its internal nodes without affecting folds made elsewhere). Finally, the user can rename any generated component node via a sidebar and trigger a "Client-Side Export" to download the current interactive graph state as a PNML file.

Cycle expanded function compounds by nesting depth: green, blue, purple, then green again. Depth zero is green; siblings at the same depth share a color and each parent/child pair differs. Reserve orange for unresolved call transitions. Keep the existing brown/gold Collapsed Compound State distinct. Recompute presentation from the active hierarchy when loading older sessions or restoring compounds, so saved legacy color classes do not preserve the orange clamp.

## User Stories

1. As a developer, I want the HTML viewer to display the entire inline-expanded graph in maximum detail immediately upon load, so I don't have to manually click through a deep call tree to see the full picture.
2. As a developer, I want all inlined functions to be visually encapsulated inside Nested Compound Nodes by default, so I can clearly see the boundaries of each function in the global composite graph.
3. As an analyst, I want to left-click an intermediate place node to instantly collapse it (Single-Place Contraction) directly in the browser, so I can manually clean up AST routing anomalies where I choose.
4. As an analyst, I want the browser to calculate the component penalty ($\omega$) and new transition weight ($\tau$) in real-time when I perform a Live Fold Reduction, so the cognitive complexity score remains mathematically rigorous.
5. As an analyst, I want to pan the canvas by holding the right and middle mouse buttons, so left-click is freed up entirely for interacting with nodes.
6. As a developer, I want a fully folded function to appear as a Collapsed Compound Node (a closed folder) displaying `function_name (c_XX)`, so I can distinguish a collapsed function from a generic opaque transition.
7. As an analyst, I want to click on a Collapsed Compound Node or opaque transition to instantly unfold it (Component-Local Unfold), without having to use a linear global undo slider that would revert my other unrelated folds.
8. As a developer, I want to left-click a transition/component node to open a sidebar or modal, so I can view its metadata ($\tau$ weight, SM score, line number).
9. As a developer, I want to use that sidebar/modal to rename a generated component (e.g., changing `c_04` to `calculate_tax`), so the folded graph better reflects domain semantics.
10. As an analyst, I want to click an "Export PNML" button in the viewer that triggers a client-side export, so I can save my manually half-folded graph state and open it in ProM without needing a Python backend server.
11. As a user, I want expanded compounds to repeat green, blue, and purple by nesting depth, so that adjacent levels remain distinguishable in deep call trees.
12. As a user, I want siblings at the same depth to share a color, so that equal-depth functions follow a predictable convention.
13. As a user, I want orange reserved for unresolved call transitions, so that an expanded resolved function does not imply an unresolved call.
14. As a user, I want collapsed compounds to retain their brown/gold appearance, so that reduction state remains distinct from expanded nesting depth.
15. As a user, I want older saved sessions to adopt the current palette when opened, so that legacy orange classes do not retain the misleading presentation.
16. As a user, I want expansion, local unfolding, Reset, and playback to apply the same depth colors, so that graph interactions do not change the convention.
17. As a user, I want palette changes to preserve hierarchy, padding, folding behavior, and weights, so that visual clarity does not change the analysis.

## Implementation Decisions

- **Initial Assembly:** Python's `inline.py` engine (specifically a variant or flag on `inline_expand`) will pre-assemble the entire Composite Net. It will inject hierarchy metadata (`enclosing_function` or explicit `parent` pointers) into the nodes before generating the `{{DATA_JSON}}` payload. 
- **Live Fold Reduction Engine:** The core reduction algorithms from `fold.py` (specifically `fold_single_place_contraction`, `fold_choice`, and `fold_while`) along with SESE macro folds will be implemented in JavaScript within dedicated engine modules.
- **SESE Macro Folds & Knot Isolation:**
  - **SESE Subnet Discovery:** Bidirectional reachability traversal discovers Single-Entry Single-Exit (SESE) subgraphs bounded by candidate source and sink nodes.
  - **Marked Graph Reduction:** Subnets where every place has $\le 1$ incoming and $\le 1$ outgoing arc can be contracted. Transitions acting as candidate boundary triggers are tagged with `contractible-marked-graph`.
  - **State Machine Reduction:** Subnets where every transition has $\le 1$ incoming and $\le 1$ outgoing arc can be contracted into a composite component.
  - **Well-Structured SESE Structural Fold:** Validated SESE components are contracted while preserving interface soundness. Elementary reductions are prioritized to prevent premature structural folding.
  - **Unstructured Knot Isolation:** Non-reducible cyclic or interwoven regions are detected and isolated with visual boundary styling to maintain analysis transparency.
- **Interaction Mapping:** 
  - Left-Click (Place): Trigger Place-Centric Live Fold.
  - Left-Click (Transition/Component): Open floating HUD popover for metadata inspection, running SM score display, node renaming, and explicit structural fold actions (e.g. "Contract Marked Graph").
  - Right-Click (Transition/Component): Trigger Component-Local Unfold.
  - Right/Middle Mouse Hold: Canvas Pan.
- **UI & UX Decisions (Prototype Confirmed):**
  - **UI Layout:** The final inspector interface will use "Variant B: HUD" (Floating popover HUD near selection with compact stat pills, including running SM score).
  - **Visual Affordances:** Foldability state is indicated directly via place colors (Green for Sequence, Amber for Choice, Purple for While loop) and transition styling.
  - **Choice Reduction:** Implements "Idea B" (whole-node style), fusing parallel transitions into a single component while preserving the split and join places.
  - **Focus Retention:** Folding a place successfully retains selection focus on the relevant target node, so subsequent fold states (e.g. from Choice to Sequence) are instantly displayed without re-selecting.
- **Expanded compound palette:** Ticket 67 replaces the depth-three orange clamp with the existing green, blue, and purple colors repeating at arbitrary depth. Choose the palette slot using actual nesting depth modulo three: depths zero/three/six are green, one/four/seven blue, and two/five/eight purple. Derive depth from the active compound parent hierarchy. Apply coherent background, border, and label/text-background treatment using the production light theme. This is compound presentation, distinct from type-specific foldability marks.
- **Hierarchy and state preservation:** Palette indexing must not replace or truncate semantic nesting depth, alter parent relationships, or restart depth-dependent padding. Preserve the existing brown/gold collapsed-compound override and ordinary orange unresolved-call styling. Refresh presentation during fresh viewer boot, runtime expansion, Component-Local Unfold, Reset, playback, and Open Session. Normalize active restored presentation rather than trusting saved legacy color classes; do not mutate detached snapshots, unopened input data, or stored restoration history just to recolor them. Existing session formats remain readable without source access or a schema migration.
- **Local Restoration Architecture:** The delivered Component-Local Unfold stores the consumed subnet on the created component and restores that chosen subnet independently of other folds. The original design did not provide chronological action Undo/Redo. On 2026-10-17, the user approved complementary, session-local Viewer Action History for committed graph edits, one entry per user gesture, without persisting Undo/Redo stacks in saved sessions. This explicitly amends the earlier prohibition on global state-array undo; it does not replace consumed-subnet restoration or prescribe the action-history storage mechanism. The agreed design is now owned by [Phase 2.8.1](./phase-2.8.1-viewer-search-and-action-history.md) and [ADR 0005](../../../docs/adr/0005-session-local-viewer-action-history.md). Implementation is pending in original [Ticket 68](../issues/68-viewer-action-history-undo-redo.md), followed by dependent search/Reveal Ticket 69.
- **Client-Side Export:** A new JS function will traverse the current Cytoscape elements array, convert the places, transitions, arcs, and initial tokens into standard PNML XML syntax, and construct a `Blob` URL attached to a hidden `<a download>` tag to trigger a client-side export.
- **Prototyping Strategy:** Development will begin on the `feature/live-fold-reduction-js-prototype` branch to validate the Live Fold Reduction math and the Cytoscape UI/UX feel before replacing the main Phase 2.6 infrastructure.

## Testing Decisions

- A good test for Live Fold Reduction ensures that the mathematical invariants of the Petri net (conservancy, structural soundness) are maintained after arbitrary sequences of user interactions, and that the resulting $\tau$ weights exactly match the Python reference implementation.
- **Modules to Test:** 
  1. The Python composite assembly logic (ensuring parent hierarchy metadata survives the splice).
  2. The JavaScript fold engine (via a headless JS test runner like Jest, or robust DOM tests using Playwright/Selenium).
- **Prior Art:** Since JS testing is new to this project, we will establish a pattern: we will dump a known AST-generated composite graph to JSON, run the JS fold functions on it, and assert the resulting graph topology and SM scores match the output of `pytest tests/test_fold_detection.py`.
- **Ticket 67 primary seam — generated viewer rendering and session round trip:** Reuse existing generated-viewer/browser and production snapshot/open workflows with self-contained nested-call fixtures. Assert actual rendered compound backgrounds, borders, and label readability at depths zero through at least eight, same-depth siblings, distinct adjacent levels, and no expanded orange compound. Verify the observed depth-four _coerce_direction() reproduction against its depth-three parent. Include an older snapshot carrying a legacy depth-three orange class on a deeper compound; opening it must derive current color from the active hierarchy. Cover runtime expansion, local unfold restoring legacy classes, Reset, playback, and save/open continuation. Check the brown/gold collapsed override and unchanged orange unresolved transitions. Compare topology, parent/depth metadata, nested padding, tokens, fold eligibility, names, weights/SM, viewport, and detached snapshot/history contents before and after styling. CSS string matching alone is insufficient evidence of correct rendered state; no new test seam is required.

## Out of Scope

- **Freeform Lasso Folding:** Freeform lasso selection remains out of scope. Phase 2.8 later added box selection and Batch Place Fold; component inspection and actions moved from the floating HUD to the docked sidebar.
- **Round-trip execution:** The exported PNML is one-way. We are not building a feature to re-import a half-folded PNML file back into the `code2petri` CLI.
- **Palette follow-up exclusions:** No orange slot for expanded compounds, random/per-call colors, user-customizable palettes, animation, broad theme redesign, semantic depth/parent changes, reduction-rule changes, or modification of existing exported files in place. Regenerated viewers provide the updated rendering for compatible saved sessions.

## Further Notes

- The decision tree that formed this spec is documented in the project logs, confirming the architectural shift from Python-led reduction to Browser-led interactive reduction.

## Subsequent Updates

- [Ticket 61 — Inline same-file callees in global composite HTML](../issues/61-single-file-global-composite-html.md) is resolved. Global HTML startup expands reachable same-file callees into compounds using the configured inline depth and recursion guard, extending the initial-composite behavior to single-file projects. Its recorded generated-HTML checks cover same-file and multi-file graphs; no new run is claimed here.
- Phase 2.8's final sidebar and selection decisions are recorded in [ADR 0004](../../../docs/adr/0004-docked-sidebar-instead-of-floating-popover.md) and the [Phase 2.8 spec](./phase-2.8-viewer-interactive-enhancements.md).
- Viewer viewport preservation and extended zoom-out were delivered in [Tickets 43](../issues/43-viewer-camera-viewport-preservation.md) and [44](../issues/44-viewer-extended-zoom-out-range.md).
- [Ticket 67 — Cycle Nested Compound Colors](../issues/67-cycle-nested-compound-colors.md) is implemented and ready for human verification. It repeats green/blue/purple by depth and reserves orange for unresolved transitions while retaining brown/gold collapsed compounds. Ticket 30 remains completed.
- [Ticket 66](../issues/66-function-scoped-structural-folding.md) and the [Phase 2.8 spec](./phase-2.8-viewer-interactive-enhancements.md) separately extend scoped function folding under the [ADR 0003 amendment](../../../docs/adr/0003-adopt-prom-local-reduction-algorithm.md). That action exhausts elementary reductions within the selected function before structural reductions, even if unrelated elementary folds remain elsewhere; whole-net priority is unchanged. Neither follow-up blocks the other.

## Comments

- 2026-10-13: The user approved depth-based green/blue/purple cycling, exclusion of orange to avoid unresolved-call ambiguity, equal colors for siblings, and retention of existing brown/gold collapsed-compound styling. Published with to-spec and to-tickets as Ticket 67, independently of function-fold eligibility.
- 2026-10-16: Implementation completion confirmed by the user. Commits `3d54cbb`, `96b6fb5`, and `6c37849` contain the palette and shared-helper follow-ups. The [Round 02 review](../reviews/phase-2.10-tickets-65-67-round-02.md) found no concrete palette mismatch. Ticket 67 retains its unperformed rendering/session checks; no new tests or browser acceptance were run for this documentation update.
