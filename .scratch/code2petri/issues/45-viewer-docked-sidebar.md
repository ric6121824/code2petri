# 45: Docked Sidebar Inspector

**What to build:** Inspect and rename nodes in a permanently docked right sidebar, following prototype Variant A while retaining the generated viewer's light theme. The sidebar gives metadata and folding actions a stable home without covering the graph.

**Blocked by:** None (can start immediately).

**Status:** resolved

- [x] The sidebar occupies a fixed-width area on the right and reduces the canvas width without covering graph content.
- [x] The sidebar remains visible, with an empty state when no node is being inspected.
- [x] Inspecting a node shows its ID, editable label, Transition Weight, Component Penalty, component type, source line, and Structuredness Metric as applicable; missing metadata has a clear empty value.
- [x] Inspecting another node replaces the displayed metadata and available actions. Clearing inspection restores the empty state without stale values.
- [x] Component Node Renaming updates the canvas immediately and retains existing name preservation across Component-Local Unfold and re-fold.
- [x] Existing applicable inspector actions remain available, including Marked Graph reduction and Component-Local Unfold.
- [x] Updating sidebar contents does not resize the canvas or reset its camera. Existing place-click folding, right-click unfolding, right/middle-drag panning, and wheel zoom continue to work.
- [x] Automated checks and a generated-viewer interaction check verify inspection, clearing, renaming, applicable actions, and the unobscured light-theme layout.

## Answer

Implemented the docked inspector, metadata and rename flow, plus existing reduction/unfold actions. Viewer regression tests passed as part of the 130-test focused suite. A separate manual browser session was not run.
