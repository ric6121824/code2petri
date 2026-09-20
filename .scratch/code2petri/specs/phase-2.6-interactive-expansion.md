## Problem Statement

The `code2petri` fold engine currently uses naive, maximal pattern matchers to detect Sequences, Choices, and Loops. However, the abstract syntax tree (AST) walkers for languages like Python generate intermediate routing places (e.g., `p_split -> t_if -> p_branch_entry -> t_stmt -> p_merge`). These valid but non-textbook topologies confound the maximal detectors, causing the engine to fail to recognize standard `if/else` and `while` blocks, falling back incorrectly to the Unstructured penalty.

Additionally, while the HTML Cytoscape viewer successfully plays back fold steps, it is a static viewing tool. Users cannot interactively click on a resolved function call to expand it and view its internal sub-graph within the browser. Furthermore, nested function calls inside inlined graphs lack visual resolution styling (coloring) because their internal call sites are not resolved before being spliced.

## Solution

1. **Algorithm Port (ProM):** Replace the maximal pattern matchers with a native Python port of the ProM `PNAnalysis.jar` reference implementation (from Lassen & van der Aalst 2008). This introduces Single-Place Contraction to incrementally collapse sequences, Atomic Choice Collapse, and Single-Entry Single-Exit (SESE) bidirectional reachability for fallback knots. This mathematical alignment guarantees that AST-generated branch anomalies naturally fold into canonical components.
2. **Interactive Client-Side Expansion:** Pre-calculate and embed callee subnets as a JSON lookup table within the HTML viewer template. Clicking a call transition in the viewer dynamically converts it into a Cytoscape compound node (colored light green) and splices the raw callee sub-graph inside it, operating independently of the global fold slider.
3. **Recursive Resolution:** The `SymbolTable` is passed through the inline expansion engine so that `CallSite` records internal to callees are fully resolved before splicing.

## User Stories

1. As an analyst, I want the algorithm to evaluate `if/else` branches using the formal Choice multiplier (1.5x) so that the cognitive complexity correctly reflects structured branching.
2. As an analyst, I want the algorithm to evaluate `while` loops using the formal Loop multiplier (2.0x) so that repetitive blocks correctly penalize the Structuredness Metric (SM).
3. As an analyst, I want unstructured code blocks (like those created by `goto` or unstructured loops) to be isolated into the smallest possible SESE knot, so that the Unstructured penalty only applies to the messy parts and doesn't swallow the whole file.
4. As a developer, I want my nested function calls inside an inlined callee to be colored green (resolved) or orange (unresolved) just like top-level calls.
5. As a developer using the HTML viewer, I want to click on a green function call transition to see its internal code structure expand dynamically.
6. As a developer using the HTML viewer, I want the expanded function to render inside a light green bounding box (compound node) so I can clearly see where the callee begins and ends.
7. As a developer using the HTML viewer, I want to be able to click the expanded compound node again to collapse it back into a single transition.
8. As a developer using the HTML viewer, I want the dynamic expansion to operate on the "raw" unfolded state of the callee, regardless of where the fold slider is set, so I can see the raw logic.
9. As an analyst, I want the fold slider to continue governing the outer graph even when a callee is expanded, so I can view raw callee logic in the context of a simplified outer architecture.
10. As a developer, I want the HTML output to remain a single, 100% offline, self-contained file, so I don't need a local web server to view the interactive graphs.

## Implementation Decisions

- **ProM Port (ADR 0003):** 
  - `foldSequence` will no longer search for a maximal chain. It will contract exactly one intermediate place at a time ($1 \to 1 \to 1$ topology), which inherently normalizes AST branches.
  - `foldChoice` will look for parallel transitions between the same input and output place, collapsing them atomically.
  - `foldWhile` will look for a 2-in/2-out place with a single self-looping transition.
  - SESE detection will use a bidirectional BFS ($forward == backward$).
  - **Macro-Components:** `foldMarkedGraph`, `foldStateMachine`, and `foldWellStructured` will be ported to detect the *maximal* SESE subnet satisfying their respective graph properties.
  - `foldUnstructured` will select the *minimal* SESE knot rather than the maximal one.
- **Inlining Engine Changes:** The `_get_callee_net` function will accept the `SymbolTable` as a parameter and explicitly call `symbol_table.resolve_call_sites(callee_net, callee_call_sites)` prior to returning.
- **HTML Payload Schema:** The viewer template will receive an additional template variable: `{{ callee_nets_json }}`. This will be a flat dictionary keyed by the callee's fully qualified name (e.g., `WebGLEngine.step`), containing the `places`, `transitions`, and `arcs` of the callee's Petri net.
- **Viewer Interactivity (Cytoscape.js):** 
  - An `on('tap', 'node[?resolved]')` event listener will be added.
  - When triggered, it will fetch the callee from the JSON payload.
  - The clicked node will be mutated to a compound node (`t.classes('compound')`).
  - The callee nodes will be added to the graph with their `parent` attribute set to the clicked node's ID.
  - Subnet entrance places will be dynamically rewired to the caller transition's inputs; exit places to the caller's outputs.
  - The `dagre` layout will be re-run on the entire graph to animate the expansion.
- **Fold State Independence:** The fold slider logic (`apply_fold_step`) will be updated to ignore elements that are children of a compound node, ensuring expanded subnets always render raw.

## Testing Decisions

- **Good Test Criteria:** Tests must exercise the reduction algorithms against realistic AST topologies, not just idealized textbook Petri nets.
- **Modules to Test:** The `fold.py` engine (specifically component detection and graph topology mutation) and `inline.py` (resolution behavior).
- **Test Seams:**
  1. **Detection Seam:** Create artificial Petri nets that perfectly mimic the topologies generated by `wire_if_split` and `wire_standard_loop`. Assert that `fold_net()` successfully reduces them to a single transition without ever invoking `fold_unstructured`.
  2. **Resolution Seam:** Invoke `inline_expand` with `--inline-depth=2`. Assert that call transitions originating from depth 1 have `.resolution` correctly populated.
- **Prior Art:** Existing `tests/test_fold_detection.py` uses idealized net builders (`build_choice_net`). These will be replaced or augmented with `build_ast_choice_net` which inserts the intermediate routing places to prove the new Single-Place Contraction handles them.

## Out of Scope

- Expanding recursive functions infinitely in the browser (this is strictly capped by the Python generator's `--inline-depth` to prevent payload explosion).
- Altering the AST walkers to produce cleaner control flow graphs (we adapt to the faithful translation, not vice versa).

## Further Notes

- The complete analysis of the `/Applications/prom-6.15-all-platforms/packages/pnanalysis-6.13.1/PNAnalysis.jar` ProM source code that informed the algorithmic port is documented in `.scratch/code2petri/prom-analysis-process.md`.
- The class in subject is `org.processmining.pnanalysis.plugins.PetriNetMetricsPlugin`
