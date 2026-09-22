# 41 — Viewer: Component Node Renaming via HUD

**What to build:**
Floating HUD popover for selected transitions/components allowing users to inspect metrics (tau, SM score, type, line number) and assign custom semantic names overriding default component IDs.

**Blocked by:** 40 — Viewer: Component-Local Unfold

**Status:** ready-for-agent

- [ ] Left-clicking a transition or component opens a floating popover HUD near the selected element
- [ ] HUD displays compact stat pills for tau weight, component type, and line number
- [ ] Editable text field allows the user to rename the component node
- [ ] Submitting the new name updates the canvas label and persists across local unfolds
