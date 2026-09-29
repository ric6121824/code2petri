# 41 — Viewer: Component Node Renaming via HUD

**What to build:** Left-clicking a transition or component node opens a floating HUD popover near the selection. The HUD displays the node's key metrics (tau weight, component type, source line number) as compact stat pills, and includes an editable name field. Saving the new name renames the node on the canvas, replacing the auto-generated `c_XX` ID with a user-chosen semantic label. (Prototype confirmed: "Variant B: HUD" layout.)

**Blocked by:** 40 — Viewer: Component-Local Unfold

**Status:** done

- [x] Left-clicking a transition or component node opens the floating HUD popover near the selected node
- [x] The HUD displays tau weight, component type, and source line number as compact stat pills
- [x] The HUD contains an editable text field pre-filled with the node's current label
- [x] Saving a new name updates the node's displayed label on the canvas immediately
- [x] The HUD closes when the user clicks elsewhere on the canvas
- [x] A renamed component retains its custom label after being unfolded and re-folded
