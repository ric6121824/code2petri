# 40 — Viewer: Component-Local Unfold

**What to build:**
Enable non-linear local undo. Right-clicking an opaque transition or a Collapsed Compound Node restores the exact sub-graph consumed during that fold without undoing unrelated folds elsewhere.

**Blocked by:** 39 — Viewer: Collapsed Compound State

**Status:** ready-for-agent

- [ ] Right-clicking an opaque transition or collapsed compound extracts its serialized consumed nodes and edges
- [ ] Removes the component node and re-inserts the original elements back into the Cytoscape graph
- [ ] External arc connections to the boundary places/transitions are rewired to the restored elements
- [ ] Other folded components on the canvas retain their folded state intact
- [ ] Retains selection focus on the restored sub-graph
