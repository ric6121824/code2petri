# 42 — Viewer: Client-Side PNML Export

**What to build:** An "Export PNML" button in the viewer toolbar lets the user download the current state of the canvas as a standard PNML file. The exported file reflects the graph exactly as it appears on screen — including any folds the user has applied and any component nodes they have renamed — so it can be opened directly in an external tool such as ProM.

**Blocked by:** 29 — Prefactor: Backend Composite Assembly

**Status:** ready-for-agent

- [ ] An "Export PNML" button is visible in the viewer toolbar
- [ ] Clicking the button triggers a browser file download of a `.pnml` file
- [ ] The exported PNML contains the places, transitions, arcs, and initial token markings of the graph as currently displayed (respecting any live fold reductions applied)
- [ ] Component nodes that have been renamed export with the user-assigned label, not the auto-generated `c_XX` ID
- [ ] The exported PNML is valid and can be imported into ProM without errors
- [ ] No server or Python process is required to perform the export
