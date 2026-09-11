# 16 — Fix Graphviz PNG Rendering for Transition Borders

**What to build:** Fix the missing colored borders (and missing rectangles) for transitions in `.png` exports without relying on `penwidth="2"`. 

*Diagnosis:* 
1. The project uses a custom `dot` shim (`/usr/local/bin/dot`) which compiles Graphviz to SVG via `@viz-js/viz`, and then converts SVG to PNG using `pymupdf`. 
2. Adding `penwidth="2"` correctly produces `stroke-width="2"` in the SVG `<polygon>` elements. However, `pymupdf`'s limited SVG parser fails to render polygons with `stroke-width="2"`, silently dropping the entire rectangle in the resulting PNG. 

*Proposed Solution:*
Option A (Design fix): Revert `penwidth="2"` and instead use `fillcolor` to indicate status (e.g. `fillcolor="#2e7d32"` for resolved, `#e65100` for unresolved) rather than relying on a thin border. 
Option B (Tooling fix): Update the `dot` shim to use a robust SVG-to-PNG renderer in Node (e.g., `@resvg/resvg-js`) instead of `pymupdf`.

Implement Option A as the primary fix, and optionally Option B for future-proofing the visualization pipeline.

**Blocked by:** None — can start immediately.

**Status:** complete

- [x] Revert `penwidth="2"` in `code2petri/model.py` to restore the transition rectangles.
- [x] Implement Option A (use `fillcolor` for status) OR Option B (replace `pymupdf` in the `dot` shim).
- [x] PNG exports generated via `dot -Tpng` clearly distinguish resolved and unresolved transitions without missing rectangles.
- [x] Existing tests still pass.
