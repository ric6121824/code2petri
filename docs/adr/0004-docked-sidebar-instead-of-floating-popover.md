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

We will replace the floating popover with a permanently docked `<aside>` sidebar on the right edge of the screen (Variant A). The sidebar will use a flex layout to push the canvas, dynamically narrowing the viewport rather than overlaying it.

## Consequences

- **Positive:** The canvas is never obscured by the inspector.
- **Positive:** We gain a stable, predictable surface for complex metadata and bulk action buttons (e.g., compound function folding).
- **Positive:** The UI aligns better with standard IDE paradigms (e.g., VS Code sidebar).
- **Negative:** The usable canvas width is permanently reduced by ~300px.
- **Negative:** The distance between the user's focal point (the clicked node) and the metadata/actions (the sidebar) is increased, requiring more eye movement.
