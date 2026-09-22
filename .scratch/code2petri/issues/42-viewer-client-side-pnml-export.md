# 42 — Viewer: Client-Side PNML Export

**What to build:**
Client-side serialization of the current Cytoscape graph state into PNML XML format, triggering a browser download to save half-folded nets for inspection in external tools like ProM.

**Blocked by:** 29 — Prefactor: Backend Composite Assembly

**Status:** ready-for-agent

- [ ] Toolbar includes an "Export PNML" button
- [ ] Export function reads active places, transitions, initial tokens, and arcs from Cytoscape
- [ ] Serializes graph elements into standard PNML XML syntax
- [ ] Generates a client-side Blob URL and triggers file download without requiring server calls
