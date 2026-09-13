# Phase 2.5 Discussion Progress & Architectural Blueprint

**Document Purpose**: This document records the progress, resolved decisions, design rationale, and open questions from the Phase 2.5 grilling session. It serves as the foundation for the next conversation to finalize the Phase 2.5 specification and ticket breakdown.

---

## 1. Context & Baseline (Post-Phase 2)

- **Phase 2 Complete & Verified**:
  - `WalkerProtocol` returns strongly typed `WalkResult(net, call_sites)`.
  - Walkers implement `collect_variable_bindings(tree)` for constructor assignments (`x = Foo()` / `const x = new Foo()`).
  - `SymbolTable` resolves cross-file method invocations to class definitions within the same language.
  - `--context` flag supports multi-file and directory discovery with file-extension filtering.
  - Call transitions are annotated with `CallResolution` metadata and serialized into PNML `<toolspecific>`, Graphviz DOT tooltips/fillcolors (`#2e7d32` resolved, `#e65100` unresolved), and JSON.
  - Verified on [`GameOfLife_Simulator`](file:///Users/pingchungtsai/My%20Drive%20%28ric6121824%40gmail.com%29/Digital%20Media%20MSc/Semester%204/GameOfLife_Simulator) (`app.js` + `webgl-engine.js`), with 235 automated tests passing and 0 hard review violations.

---

## 2. Phase 2.5 Core Objective

Phase 2.5 bridges the gap between raw graph generation and human-readable, quantitatively measured architectural complexity. It implements:
1. **Structural Component Folding & Structuredness Metric (SM)** computation based on Lassen & van der Aalst (2008), *Complexity Metrics for Workflow Nets* (Definitions 17–23).
2. **Interactive HTML Viewer** providing progressive graph simplification (folding/unfolding playback) and interactive call-site inline expansion.

---

## 3. Decisions Resolved in Current Grilling Session

### Decision 1: Deliverable Priority (Folding Engine First, Viewer Second)
- **Resolution**: The structural folding algorithm and SM score computation (`code2petri/fold.py`) is the analytical priority and comes first. The HTML viewer (`code2petri/viewer/`) acts as the presentation and playback layer consuming pre-computed fold data.
- **Rationale**: The SM score is the thesis contribution needed to compare structural game code complexity. Decoupling the calculation from the frontend ensures algorithmic correctness and enables headless CLI analysis and batch scoring across games before viewer polish.

### Decision 2: Configurable Component Weights ($\omega$ / $\rho$)
- **Resolution**: Component penalty weights $\omega$ must be publicly configurable via both a typed Python configuration class (`FoldConfig`) and a CLI option (`--weights <json_string_or_filepath>`).
- **Base Penalties (Lassen & van der Aalst 2008 baseline)**:
  - Sequence: $\rho = 0$
  - Choice (XOR-split/join): $\rho = 1$
  - While / Loop (Cycle): $\rho = 3$
  - Marked-Graph (AND-split): $\rho = 2$ (included in taxonomy; see Decision 6)
  - Unstructured / Irreducible: $\rho = 7$

### Decision 3: Viewer Capabilities (Folding + Inline Expansion)
- **Resolution**: The HTML viewer must support two distinct structural operations:
  1. **Structural Folding/Unfolding**: Collapsing recognized well-structured components into weighted dummy transitions ($t_C$), updating the SM score live.
  2. **Call-Site Inline Expansion**: Expanding opaque call transitions by embedding the callee's full Petri net subgraph directly into the larger net.

### Decision 4: Scope of Folding (Isolated Net vs Composite Net)
- **Resolution**: Both modes are supported, with **isolated function net folding as the default**.
  - Default: Fold runs on the target function's isolated net where unresolved and resolved calls remain opaque transitions. This provides the standard unit of comparison across functions/games.
  - Opt-in (`--inline`): Calls are inline-expanded first to produce a composite net, and the fold algorithm reduces the composite net to measure whole-program/cross-file complexity.

### Decision 5: Handling Non-Single-Exit Constructs (`break`, `continue`, `exceptions`)
- **Resolution**: **Strict Lassen & van der Aalst for v1**. Non-single-entry/single-exit patterns (e.g., `while` with `break` or `continue`, early `return`, cross-boundary exception arcs) remain **irreducible** in v1.
- **Scoring**: Irreducible subnets are treated as unstructured components and penalized with the unstructured weight ($\rho = 7$).
- **Future Extension**: Extended component definitions (e.g., "Loop-with-Break", "Try-Catch Block") will be introduced in future iterations to provide specialized weights without treating them as pure spaghetti flow.

### Decision 6: AND-Split Concurrency & Future Extensions
- **Resolution**: Marked-graph (AND-split) is formally included in the `FoldConfig` model with default $\rho = 2$.
- **Language Reality**: Python and JavaScript control-flow ASTs are inherently single-threaded and do not produce AST-level AND-splits. AST concurrency recognition (e.g., `asyncio.gather`, `Promise.all`) is **deferred** to Phase 3.
- **Future Extension**: Phase 3 will introduce natural AND-splits when modeling C# Unity coroutines (`StartCoroutine`) and multi-`MonoBehaviour` lifecycle execution order.

### Decision 7: Viewer Architecture (Hybrid Stepper & Extensible Model)
- **Resolution**: **Hybrid model**.
  - v1 ships a deterministic **player/stepper** in the HTML viewer stepping through pre-computed Python fold snapshots (sorted by Def. 21 priority: simplest component first).
  - The raw net JSON and component metadata are embedded into the HTML file to allow future client-side selective folding.
  - Inline expansion of call transitions operates independently of the fold step player.

---

## 4. Open Topics — RESOLVED (2026-09-14 Continuation Session)

All five open topics from Section 4 have been resolved. The full spec has been published to `.scratch/code2petri/specs/phase-2.5-structural-folding-and-viewer.md`.

### Decision 8: Inline Expansion Implementation Seam
- **Resolution**: **Python-level Graph Splicing (Option A)** with `--inline-depth=1` default and recursion guard.
- **Rationale**: Splicing in Python before serialization gives all output formats (PNML, DOT, JSON, HTML) instant composite net support. The fold engine can then operate on the composite net headlessly. A call-stack-based recursion guard prevents infinite expansion on self-scheduling patterns like `requestAnimationFrame`.
- **ID Collision Handling**: Callee nodes are cloned with a namespace prefix (`inline_<callee_id>__<original_id>`).

### Decision 9: Irreducible Reduction & Final SM Score
- **Resolution**: Treat the entire remaining irreducible block as a **single Unstructured Component** with $\rho = 7$. Fold it into a final dummy transition. The SM score is the raw, unnormalized scalar $\tau$ on that final transition.
- **Rationale**: Preserves the unbounded metric as defined in Lassen & van der Aalst (2008). No 0.0–1.0 normalization — raw scores enable direct cross-function comparison within and across games.

### Decision 10: HTML Viewer Technology Stack & Bundling
- **Resolution**: **Cytoscape.js with Dagre layout**, bundled as a **100% self-contained offline HTML file**.
- **Rationale**: Dagre enforces strict hierarchical top-to-bottom directed layouts matching Graphviz conventions. Inlining the minified libraries (~1 MB overhead) ensures the file works offline. Alternatives considered: d3-graphviz (strong but requires WASM bundling at 3–5 MB), Vis.js (physics-based, unstable layouts), Mermaid.js (too rigid for interactive playback).

### Decision 11: CLI Flags & Output Extensions
- **Resolution**: `--fold` as opt-in analytical flag. `.html` auto-activates `--fold` (overridable with `--no-fold`).
- **Static output with `--fold`**: Renders the **penultimate** fold state — well-structured components folded into dummies, irreducible nodes fully exposed. Final SM score printed to stderr and embedded in graph title.
- **JSON with `--fold`**: Switches schema to `FoldResult` array (initial net + fold steps + final SM).
- **Additional flags**: `--weights <path_or_json>`, `--inline`, `--inline-depth <N>`.

### Decision 12: Ticket Slicing
- **Resolution**: Deferred to the spec review cycle. Proposed 5-ticket breakdown (Tickets 17–21) to be finalized after spec approval.

---

## 5. Domain Glossary Additions (Candidate Terms for `CONTEXT.md`)

- **Structural Fold**: The reduction operation (Def. 19) that replaces a well-structured single-entry/single-exit subnet with a weighted dummy transition ($t_C$) and rewires boundary arcs.
- **Dummy Transition ($t_C$)**: A synthetic transition representing a folded component, carrying accumulated complexity weight $\tau$.
- **Structuredness Metric (SM)**: A quantitative complexity metric derived from iterative structural reduction and component penalty weighting.
- **Component Penalty ($\omega$)**: The penalty score assigned to a recognized component based on its structural type and branch symmetry.
- **Transition Weight ($\tau$)**: The accumulated complexity score stored on a transition (initial = 1; grows as components are swallowed into dummy transitions).
- **Fold Config**: A typed configuration object holding the base penalty weights ($\rho$) for each component type.
- **Fold Step**: A snapshot recording a single reduction operation: which component was detected, which nodes were consumed, and the resulting net state.

