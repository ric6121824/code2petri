# 4. Docked Sidebar instead of Floating Popover

Date: 2026-10-08

## Status

Accepted

## Context

The initial HTML viewer UI utilized a floating `#inspector-panel` popover that appeared absolutely positioned near the selected node. While this kept metadata close to the locus of attention, it suffered from several drawbacks:
1. It frequently obscured adjacent nodes and edges, requiring constant manual panning to see the graph structure underneath.
2. For large graphs, positioning the popup securely within viewport bounds led to jarring visual jumps when selecting nodes near the edges.
3. The lack of a permanent UI surface made it difficult to introduce global or batch actions (like "Fold Selected Places") without cluttering the main header toolbar.

We built three prototype variants (A: Docked Sidebar, B: Floating Popover, C: Bottom Drawer) to evaluate alternatives. 

## Decision

We replace the floating popover with a docked `<aside>` sidebar on the right edge of the screen (Variant A). When shown, the sidebar uses a flex layout to push the canvas, dynamically narrowing the viewport rather than overlaying it.

Amended 2026-10-13 after the user approved optional sidebar visibility: hiding removes the entire sidebar and returns its width to the graph; recalling restores the docked sidebar. A small edge tab near the top of the sidebar's left boundary hides it; while hidden, the tab remains near the top of the graph's far-right edge to recall it. Use a right-pointing chevron to hide and a left-pointing chevron to recall, descriptive accessible labels, and no animation. This edge tab replaces the initially proposed toolbar toggle. The existing clear-inspection control retains its separate meaning, and inspecting nodes does not automatically reveal a sidebar the user has hidden. Visibility changes preserve graph layout and camera zoom/pan. This refines the original permanently-visible decision while retaining the unobscured docked layout.

New viewers and older snapshots default to shown. Fold State Snapshots retain sidebar visibility, and opening one restores its saved state; Reset preserves the current visibility choice. Hiding and immediately recalling the same inspected node preserves unfinished naming text without saving it. Selecting another node or clearing inspection follows the existing replacement/clear behavior, and unfinished text is not newly persisted in snapshots. The complete follow-up is specified in [Phase 2.8](../../.scratch/code2petri/specs/phase-2.8-viewer-interactive-enhancements.md) and [Ticket 64](../../.scratch/code2petri/issues/64-hide-recall-docked-sidebar.md).

## Consequences

- **Positive:** The canvas is never obscured by the inspector.
- **Positive:** We gain a stable, predictable surface for complex metadata and bulk action buttons (e.g., compound function folding).
- **Positive:** The UI aligns better with standard IDE paradigms (e.g., VS Code sidebar).
- **Trade-off:** The usable canvas width is reduced by ~300px while the sidebar is shown. Hiding reclaims that space, but sidebar actions then require explicit recall.
- **Negative:** The distance between the user's focal point (the clicked node) and the metadata/actions (the sidebar) is increased, requiring more eye movement.
