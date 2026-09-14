## Problem Statement

Static SVG and PNG exports of Petri nets become unreadable beyond roughly 50 nodes. For game source code analysis — the thesis's primary use case — even moderately complex functions like `stepCpu()` in the GameOfLife Simulator produce dense, non-trivial nets with nested loops and branching. Users currently have no way to:

1. **Quantify** the structural complexity of a function's control flow with a single, comparable metric.
2. **Simplify** the visual representation by progressively collapsing well-structured patterns (sequences, choices, loops) into weighted summary blocks.
3. **Explore** cross-file composite nets by inlining callee subnets into caller nets at call transition boundaries.
4. **Interact** with the net in a browser — stepping through the reduction sequence, expanding call sites, and observing the complexity score update live.

Without these capabilities, `code2petri` produces accurate but flat, non-scalable graphs that cannot support the thesis goal of comparing structural game code complexity across different games and genres.

## Solution

Implement **Structural Component Folding**, **Structuredness Metric (SM) computation**, **Python-level Inline Expansion**, and an **Interactive HTML Viewer** as Phase 2.5 of the `code2petri` pipeline.

The folding engine recognizes well-structured single-entry/single-exit components in a `PetriNet` (Sequences, Choices, Loops), replaces each with a weighted Dummy Transition ($t_C$), and accumulates complexity penalties following Lassen & van der Aalst (2008), Definitions 17–23. When no further well-structured components can be found, the remaining irreducible nodes are treated as a single Unstructured Component with penalty $\rho = 7$. The final accumulated weight $\tau$ on the last dummy transition is the raw, unnormalized SM score.

Inline Expansion splices resolved callee Petri nets into caller nets at the Python data-model level, enabling composite net analysis with configurable depth capping and recursion guards.

The HTML Viewer is a 100% offline, self-contained file using Cytoscape.js with Dagre layout, providing a deterministic step-through player over pre-computed fold snapshots.

## User Stories

1. As a researcher, I want to run `code2petri app.js -t loop --fold -o net.json` and receive a JSON file containing the initial net, every fold step with its component type and penalty, and the final SM score, so that I can batch-process game functions headlessly and compare their structural complexity.
2. As a researcher, I want to run `code2petri app.js -t stepCpu -o net.html` and receive a self-contained HTML file that I can open offline in any browser, so that I can explore the net without installing additional tools or requiring an internet connection.
3. As a researcher, I want the HTML viewer to display a "Fold" button that advances one reduction step, collapsing the simplest remaining component into a dummy transition with an animation, so that I can observe how structural patterns are progressively simplified.
4. As a researcher, I want the HTML viewer to display an "Unfold" button that reverses one reduction step, so that I can navigate the fold sequence bidirectionally.
5. As a researcher, I want the HTML viewer to display the current SM score and step counter (e.g., "Step 3 / 12"), updating live with each fold/unfold action, so that I can track how each component contributes to the total complexity.
6. As a researcher, I want dummy transitions ($t_C$) in the viewer to be visually distinct from normal transitions — with a different shape or border style and a visible badge showing their accumulated $\tau$ weight — so that I can immediately identify folded components.
7. As a researcher, I want the viewer to retain Phase 2's call resolution colors (`#2e7d32` for resolved, `#e65100` for unresolved) on call transitions, so that cross-file references remain visible during fold playback.
8. As a researcher, I want to configure the component penalty weights via `--weights <filepath_or_json>` so that I can calibrate the SM formula for game-specific domains without modifying source code.
9. As a researcher, I want `--fold` on static outputs (`.dot`, `.png`, `.pnml`) to produce the **penultimate** fold state — all well-structured components collapsed into dummy transitions, but irreducible nodes fully exposed — so that I can visually inspect the unstructured "spaghetti" that prevents full reduction.
10. As a researcher, I want the final SM score printed to stderr when `--fold` is active on any output format, so that I can capture the score in scripts without parsing the output file.
11. As a researcher, I want `--no-fold` with `.html` output to produce a static, interactive HTML view of the raw un-folded net (pan/zoom but no fold controls), so that I can share readable interactive graphs even without fold analysis.
12. As a researcher, I want to run `code2petri app.js -t loop --inline --context . -o composite.html` to see the `loop` function with resolved call targets (e.g., `WebGLEngine.step`) inlined as full subnets, so that I can measure cross-file composite complexity.
13. As a researcher, I want inline expansion to default to depth 1, and support `--inline-depth=N` for deeper expansion, so that I can control how many levels of callee nesting are spliced.
14. As a researcher, I want inline expansion to detect recursive call chains (e.g., `requestAnimationFrame(loop)` cycling back to `loop`) and halt expansion at the cycle point, retaining the recursive call as an annotated opaque transition, so that the pipeline does not produce infinite graphs.
15. As a developer, I want the fold algorithm to be a pure function operating on `PetriNet` instances from `code2petri/model.py`, returning a list of `FoldStep` snapshots, so that I can unit-test fold logic independently of walkers, CLI, or serialization.
16. As a developer, I want existing commands without `--fold` or `--inline` to produce identical output to Phase 2, so that backward compatibility is preserved.

## Implementation Decisions

- **New Module: Fold Engine**
  - A new module implements the structural fold algorithm as a pure function consuming a `PetriNet` and a `FoldConfig`, returning a `FoldResult` containing the ordered list of `FoldStep` snapshots.
  - Each `FoldStep` records: the component type detected, the set of node IDs consumed, the dummy transition ID created, the component penalty $\omega$, the accumulated weight $\tau$ on the dummy, the running SM score, and the full `PetriNet` state after the fold.

- **Component Detection Priority (Definition 21)**
  - Components are detected and folded in strict priority order: Sequence → Choice (XOR-split/join) → Loop (Cycle) → Unstructured.
  - At each iteration, the algorithm scans for the highest-priority (simplest) component first. If multiple components of the same priority exist, the smallest one (fewest internal nodes) is folded first.

- **Penalty Weights (Definition 22)**
  - Default base penalties ($\rho$): Sequence = 0, Choice = 1, Marked-Graph (AND-split) = 2, Loop = 3, Unstructured = 7.
  - The AND-split penalty is formally included in the configuration model but will not be detected in v1 (Python/JS ASTs are inherently single-threaded). It is a placeholder for Phase 3 (C#/Unity coroutines).
  - Penalty weight $\omega$ for a component is calculated per Definition 22, incorporating the base $\rho$ and the symmetry multiplier (`diff`) that penalizes lopsided branching.
  - Weights are configurable via a typed `FoldConfig` dataclass and the CLI flag `--weights <path_or_json>`.

- **Irreducible Termination**
  - When no well-structured single-entry/single-exit component can be found and multiple nodes remain, the algorithm treats the entire remaining block (excluding the global source and sink places) as a single Unstructured Component with $\rho = 7$.
  - It folds this block into a final dummy transition, yielding the terminal SM score.
  - For **static visual outputs** (`.dot`, `.png`, `.pnml`) with `--fold`, the output renders the **penultimate state** — well-structured components folded, irreducible nodes exposed — to let the researcher see the tangled logic. The final SM score is printed to stderr and embedded in the graph title.

- **SM Score Format**
  - The SM score is the raw, unnormalized scalar $\tau$ on the final dummy transition after full reduction. It is not normalized to a 0.0–1.0 range, preserving the unbounded structural complexity metric as defined in Lassen & van der Aalst (2008).

- **Dummy Transition ($t_C$) Data Model**
  - Dummy transitions are standard `Transition` instances with metadata marking them as dummies: `metadata={"dummy": True, "component_type": "sequence", "tau": 3.0}`.
  - They participate in the same bipartite arc structure as normal transitions.
  - In DOT/HTML rendering, they receive distinct visual styling (bold border, tau badge).

- **Inline Expansion (Python-Level Graph Splicing)**
  - Inline expansion is a Python pipeline step that operates on the `PetriNet` data model before serialization or folding.
  - For each resolved call transition in the target net:
    1. Walk the callee function using the existing walker infrastructure to produce the callee's `PetriNet`.
    2. Clone all callee nodes with a namespace prefix (e.g., `inline_<callee_id>__<original_id>`) to prevent ID collisions.
    3. Remove the opaque call transition from the caller net.
    4. Wire the call transition's preset place → callee's source place, and callee's sink place → call transition's postset place.
  - Default depth = 1. Configurable via `--inline-depth=N`.
  - A recursion guard tracks the active expansion call stack. If a callee appears in the stack (direct or indirect recursion), expansion halts and the call transition is retained as an annotated opaque transition with metadata `{"recursive_cycle": True}`.
  - Inline expansion requires `--context` to be active (the symbol table must be populated for callee resolution).

- **HTML Viewer Architecture**
  - The viewer is a single self-contained `.html` file generated by a Python template engine.
  - Cytoscape.js (minified) and the Dagre layout plugin (minified) are inlined directly into the HTML file via `<script>` tags containing the library source.
  - The fold step snapshots (JSON array) and raw initial net (JSON) are embedded as inline `<script>` data blocks.
  - The JavaScript stepper provides: Forward (fold), Backward (unfold), Reset, and a step counter / SM score display.
  - Places render as circles, transitions as filled rectangles, dummy transitions as distinctly styled rectangles with a tau badge.
  - Call resolution colors are preserved: `#2e7d32` (resolved), `#e65100` (unresolved).
  - Inline expansion in the viewer operates independently from fold playback — it is triggered before fold computation.

- **CLI Integration**
  - New flags: `--fold`, `--no-fold`, `--weights <path_or_json>`, `--inline`, `--inline-depth <N>`.
  - `.html` output extension implicitly activates `--fold` unless `--no-fold` is explicitly passed.
  - `.json` output with `--fold` switches the schema to the `FoldResult` structure (initial net + fold steps + final SM).
  - `.dot` / `.png` / `.pnml` with `--fold` output the penultimate fold state.
  - `--inline` is orthogonal to `--fold` and can be combined with any output format. When combined with `--fold`, inline expansion runs first, then folding operates on the resulting composite net.

- **Domain Glossary Additions (for `CONTEXT.md`)**
  - **Structural Fold**: The reduction operation (Def. 19) replacing a well-structured SESE subnet with a weighted Dummy Transition and rewiring boundary arcs.
  - **Dummy Transition ($t_C$)**: A synthetic transition representing a folded component, carrying accumulated complexity weight $\tau$.
  - **Structuredness Metric (SM)**: A quantitative complexity metric derived from iterative structural reduction and component penalty weighting.
  - **Component Penalty ($\omega$)**: The penalty score assigned to a recognized component based on its structural type and branch symmetry.
  - **Transition Weight ($\tau$)**: The accumulated complexity score stored on a transition (initial = 1; grows as components are folded).
  - **Fold Config**: A typed configuration object holding the base penalty weights ($\rho$) for each component type.
  - **Fold Step**: A snapshot recording a single reduction operation: which component was detected, which nodes were consumed, and the resulting net state.

## Testing Decisions

- **Good Test Criteria**: Tests verify externally observable outcomes — the shape, size, and metadata of the returned `PetriNet` or `FoldResult`, the content of serialized output files, and CLI exit behavior. Tests must not assert on internal algorithm state, iteration counts, or intermediate variable values.

- **Prior Art**: Existing test suites in `tests/test_petri_model.py`, `tests/test_python_walker.py`, `tests/test_petri_pipeline.py`, and `tests/test_game_of_life_validation.py` establish the patterns. The shared `tests/petri_assertions.py` module (`assert_valid_petri_net`, `assert_bipartite`, `assert_has_start_and_end`) will be extended with fold-specific assertions.

- **Fold Engine Seam (Unit)**
  - Construct small, hand-built `PetriNet` instances with known topology (a pure sequence, a single XOR-split/join, a single loop, a mixed net, and a known-irreducible net).
  - Assert that the fold algorithm produces the expected number of steps, the correct component types at each step, and the correct final SM score.
  - Assert that the penultimate state for a partially-irreducible net retains the correct number of exposed nodes.
  - Assert that `FoldConfig` weight overrides change the computed $\omega$ and final SM score.

- **Inline Expansion Seam (Unit)**
  - Construct a caller `PetriNet` with one resolved call transition and a callee `PetriNet`. Run inline expansion and assert the resulting composite net has the correct node count, correct arc wiring (caller preset → callee source, callee sink → caller postset), and no orphaned nodes.
  - Test recursion guard: construct a self-referencing call site and assert the recursive transition is retained with `{"recursive_cycle": True}` metadata.
  - Test depth capping: construct a 3-deep call chain with `--inline-depth=1` and assert only the first level is expanded.

- **CLI Integration Seam (Integration)**
  - Test `--fold` with `.json` output and assert the JSON schema matches the `FoldResult` structure.
  - Test `--fold` with `.dot` output and assert the penultimate state is rendered (irreducible nodes present, dummy transitions present).
  - Test `--no-fold` with `.html` and assert no fold controls data is embedded.
  - Test `--weights` override via a JSON string and verify the SM score changes.

- **HTML Viewer Seam (Validation)**
  - Assert that the generated `.html` file is valid HTML, contains inlined Cytoscape.js source, contains the fold step JSON data block, and is openable as a standalone file (no external resource references).

- **GameOfLife End-to-End Validation Seam**
  - Run the full pipeline on `app.js` targeting `stepCpu` with `--fold` and assert a non-zero SM score.
  - Run with `--inline --context <game_of_life_dir>` targeting `loop` and assert the composite net contains inlined `WebGLEngine.step` subnodes.
  - Generate `.html` output and assert the file size is > 0 and contains the expected data blocks.

## Out of Scope

- **Client-Side Selective Folding**: The v1 viewer is a deterministic stepper over pre-computed fold snapshots. Allowing the user to click individual components and fold them selectively (reimplementing the fold algorithm in JavaScript) is deferred to a future iteration.
- **AND-Split (Marked-Graph) Detection**: The penalty weight is formally included in `FoldConfig`, but the pattern matcher will not detect AND-splits in v1. Python and JavaScript ASTs are inherently single-threaded. Detection will be implemented in Phase 3 when C#/Unity coroutines introduce natural concurrency.
- **Extended Component Definitions**: Specialized component types for `break`-from-loop, `continue`-from-loop, or `try/catch` blocks with dedicated penalty weights are deferred. In v1, these remain irreducible and receive the flat $\rho = 7$ unstructured penalty.
- **Score Normalization**: The SM score is the raw accumulated $\tau$. Normalization to a 0.0–1.0 scale or per-node-count normalization for cross-function comparability is deferred to thesis analysis methodology, not baked into the tool.
- **C# / C++ Walkers**: Language support for C# (Phase 3) and C++ (Phase 4) is out of scope.
- **Project-Scale Analysis**: Batch analysis of entire project directories in a single CLI invocation belongs to Phase 5.

## Further Notes

- Respects the domain glossary in `CONTEXT.md` for canonical terms: **Opaque Transition**, **Inline Expansion**, **Composite Net**, **Call Site**, **Resolution Context**, **Variable Binding**, **Faithful Translation**.
- Conforms to ADR 0001 (Constructor-Only Variable Resolution) for inline expansion callee resolution.
- The folding algorithm follows Lassen & van der Aalst (2008), Definitions 17–23, as annotated in `Source Notes/Lassen and van der Aalst 2008.md` and synthesized in `Knowledge_Base/Structuredness Metrics.md` and `Knowledge_Base/Fold (Workflow Nets).md`.
- Walkers and `ControlFlowBuilder` are NOT modified by Phase 2.5. The fold engine and inline expansion operate purely on `PetriNet` instances produced by the existing Phase 2 pipeline.

## Architectural Decision Records (ADR)

### ADR 0002: Boundary Place Unification for Bipartite Graph Integrity

- **Status**: Accepted
- **Context**: In Phase 2.5, Inline Expansion splices resolved callee subnets into caller Petri nets where opaque call transitions reside. The entrance of the callee subnet must receive control flow from the caller transition's preset place, and the exit of the callee subnet must transfer control flow to the caller transition's postset place.
- **Decision**: Unify the boundary places by redirecting incoming arcs from the caller's preset place directly to the callee's entrance transitions, and redirecting outgoing arcs from the callee's exit transitions directly to the caller's postset place (boundary place unification / place fusion), rather than attempting to connect caller places to callee places via direct arcs.
- **Rationale**: Petri nets are fundamentally bipartite graphs $(P, T, F)$ where flow arcs strictly connect places to transitions or transitions to places ($F \subseteq (P \times T) \cup (T \times P)$). Connecting the caller preset place to the callee start place with a direct arc would introduce a place-to-place arc ($P \times P$), which directly violates the bipartite structural invariant and breaks reachability and token game firing semantics. By fusing boundary places, bipartite graph integrity is strictly preserved, sound token flow is maintained, and no synthetic intermediate transitions are required.
