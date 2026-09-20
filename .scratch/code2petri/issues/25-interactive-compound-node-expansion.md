# 25 — Interactive Compound Node Expansion

**What to build:** End-to-end interactive exploration in the browser. Users can click on a green function call to expand its raw code structure in-place as a light green bounding box, operating completely independently of the global fold playback slider.

**Blocked by:** 22 — Nested Call Resolution in Inline Expansion

**Status:** resolved

- [x] Python CLI: Pre-compute and embed all resolved callee nets (up to the requested `--inline-depth`) into a `window.CALLEE_NETS_JSON` dictionary in the HTML template.
- [x] Javascript: Add an `on('tap')` listener for resolved call transitions.
- [x] Javascript: On click, transform the clicked transition into a Cytoscape compound node (colored light green) and splice the raw callee elements inside it.
- [x] Javascript: Dynamically rewire the callee's entrance/exit places to the caller's input/output arcs, and re-run the `dagre` layout.
- [x] Javascript: Ensure the fold slider ignores the expanded raw contents (e.g., by excluding children of compound nodes from fold reductions).
- [x] Javascript: Clicking the expanded compound node collapses it back to a single transition.

## Answer

Ticket 25 delivers end-to-end interactive compound node expansion in the self-contained offline HTML Cytoscape viewer:
1. **Python Precomputation & Embedding:**
   - Implemented `precompute_callee_nets(call_sites, symbol_table, max_depth)` in `code2petri/inline.py` to traverse resolved call sites and extract raw callee Petri net dictionaries up to `--inline-depth`, guarded against recursive cycles.
   - Updated `generate_html` in `code2petri/viewer/__init__.py` to embed `window.CALLEE_NETS_JSON` without redundant payload bloat.
   - Wired `code2petri` CLI in `code2petri/engine.py` to dispatch HTML serialization through `TEXT_SERIALIZERS` and pass precomputed `callee_nets` when generating `.html` output with `--context`.
2. **Boundary Place Unification & Bipartite Net Validity (ADR-0002):**
   - Added Cytoscape styling for `node.compound, node:parent` rendering a light green bounding box (`#e8f5e9`, border `#2e7d32`, top label).
   - Implemented boundary place unification in `code2petri/viewer/template.html`: caller preset places connect directly to callee entrance transitions, and callee exit transitions connect directly to caller postset places, unifying away boundary source/sink places to prevent illegal Place -> Place arcs.
   - Preserved strict bipartite graph validity across all interactive compound nodes and transitions.
3. **Fold Slider Independence:**
   - Maintained active expansions in `expandedNodes`.
   - `renderStep(stepIndex)` applies active expansions directly onto the current step's net, allowing users to step backward and forward through outer control flow reductions while retaining raw expanded callee subnets.
4. **Interactive Tap & Collapse:**
   - Added `cy.on('tap', 'node')` to toggle expansion on green resolved call transitions and collapse on expanded compound nodes.
   - Added hover cursor feedback (`pointer`) for interactive nodes.
5. **Testing & Verification:**
   - Unit tests in `tests/test_interactive_expansion.py` verify precomputation depth, recursion guards, and execute headless Cytoscape compound expansion, boundary unification, fold independence, and collapse directly against template functions.
   - Integration tests in `tests/test_html_viewer.py` verify payload embedding and CLI HTML generation.
   - All 352 repository tests passing.
