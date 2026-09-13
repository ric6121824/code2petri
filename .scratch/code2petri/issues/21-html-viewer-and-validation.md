# 21 — Offline HTML Viewer & GameOfLife Validation

**What to build:** A user can run `code2petri app.js -t stepCpu -o net.html` and receive a single, 100% self-contained HTML file that opens in any browser without an internet connection. The viewer renders the Petri net using Cytoscape.js with Dagre hierarchical layout and provides interactive fold playback controls.

Viewer features:
- **Fold/Unfold/Reset controls**: Step forward (fold the next component), step backward (unfold the last), and reset to the initial net.
- **Step counter**: Displays "Step N / Total" updating with each action.
- **Live SM score**: Displays the current accumulated SM score, updating with each fold/unfold.
- **Visual conventions**: Places as circles, transitions as filled rectangles, dummy transitions ($t_C$) as distinctly styled rectangles with a visible $\tau$ badge. Call resolution colors preserved: `#2e7d32` (resolved), `#e65100` (unresolved).
- **`--no-fold` mode**: Produces a static interactive HTML view (pan/zoom, no fold controls).

The Cytoscape.js and Dagre layout plugin libraries are inlined as minified JavaScript directly into the HTML file (no CDN references). The fold step snapshots and raw initial net are embedded as inline `<script>` JSON data blocks.

End-to-end validation against the GameOfLife Simulator confirms the entire Phase 2.5 pipeline works on real game source code.

**Blocked by:** 20 — CLI Integration & Headless Fold/Inline Output.

**Status:** ready-for-agent

- [ ] An HTML template exists that inlines minified Cytoscape.js and Dagre layout plugin source.
- [ ] A Python generator function accepts a `FoldResult` (or raw `PetriNet` for `--no-fold`) and produces a complete HTML string with the data blocks and library source embedded.
- [ ] `.html` output extension in the CLI triggers fold analysis automatically (implicit `--fold`) and invokes the HTML generator.
- [ ] `--no-fold` with `.html` output produces a static interactive view (pan/zoom, graph rendering) with no fold controls or step data.
- [ ] The generated HTML file contains zero external resource references (no CDN links, no external CSS/JS files).
- [ ] The viewer renders places as circles and transitions as filled rectangles using Dagre hierarchical top-to-bottom layout.
- [ ] Dummy transitions are visually distinct (different border style or shape) and display their accumulated $\tau$ weight as a badge.
- [ ] Resolved call transitions render with `#2e7d32` fill; unresolved with `#e65100` fill.
- [ ] Fold button advances one step, collapsing the next component.
- [ ] Unfold button reverses one step, restoring the previous state.
- [ ] Reset button returns to the initial un-folded net.
- [ ] Step counter displays "Step N / Total" and updates on each action.
- [ ] SM score display updates on each fold/unfold action.
- [ ] GameOfLife validation: `code2petri app.js -t stepCpu --fold -o net.html` with `--context <game_of_life_dir>` produces a valid HTML file with non-zero SM score and fold steps.
- [ ] GameOfLife validation: `code2petri app.js -t loop --inline --context <game_of_life_dir> -o composite.html` produces a Composite Net HTML with inlined `WebGLEngine.step` subnet nodes visible.
- [ ] Generated HTML file size is > 0 bytes and passes basic HTML validity checks (contains `<html>`, `<script>`, and the Cytoscape data blocks).
- [ ] Existing tests continue to pass.
