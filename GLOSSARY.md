# code2petri Domain Model

The vocabulary for transforming source code control flow into executable Petri nets, bridging ASTs and Graphviz/PNML representations.

## Language

**Walker Protocol**:
The strict abstraction layer (implemented as an `abc.ABC`) that all language-specific parsers must implement to convert an AST into a Petri net.
_Avoid_: Parser interface, walker base class

**Global Scope**:
The top-level code in a file that executes outside of any function definition, addressable in the CLI as `(global)`.
_Avoid_: Main body, script scope

**Project Title**:
The human-readable name of the source project represented by a Petri net, shared across views of that project's files and functions. For example, Tic Tac Toe is the Project Title for its Global Scope and individual function views across analysis runs.
_Avoid_: Net title, output folder name, root function name (when referring to project identity)

**Synthetic Wrapper**:
A fabricated AST node created by a walker to encapsulate global-scope statements or anonymous callbacks so they can be processed like standard function bodies.
_Avoid_: Fake node, mock AST

**Opaque Transition**:
A single Petri net transition representing a function call or block of code whose internal structure is not expanded or analyzed.
_Avoid_: Black box, leaf transition

**Inline Expansion**:
The process of replacing an opaque call transition with the complete Petri net sub-graph of the called function.
_Avoid_: Unrolling, flattening

**Composite Net**:
A unified Petri net constructed by linking multiple per-function or cross-file Petri nets together.
_Avoid_: Merged graph, global net

**Faithful Translation**:
The principle of modeling the exact control flow present in the source AST, including dead ends and infinite loops, without attempting to sanitize or fix broken logic.
_Avoid_: Normalization, cleanup

**Call Site**:
A structured metadata record capturing the callee name, resolved owner, line number, and transition ID for a function call within a Petri net.
_Avoid_: Call transition info, call point

**Function Return Metadata**:
Information attached to a function's identity that describes its call result and, where applicable, awaited, yielded, or completion values for inspection without affecting Petri net control flow or Structural Folding.
_Avoid_: Return-place type, typed control-flow token

**Call Result Metadata**:
Type evidence for the normal result of a particular Call Site, with its evidence source or a reason that the result is unknown. It describes the individual call independently of the enclosing function's returned expression and the availability of the callee's source definition.
_Avoid_: Enclosing return type, guessed callee type

**Resolution Context**:
The set of source files provided via `--context` parsed to build a symbol table for cross-file call resolution, without being analysis targets.
_Avoid_: Secondary files, include paths, library files

**Variable Binding**:
A constructor-assignment mapping (`variable → class`) extracted from file scope to resolve instance method calls to their class definitions.
_Avoid_: Type inference, symbol alias

**Structural Fold**:
The reduction operation (Lassen & van der Aalst 2008, Def. 19) replacing a well-structured single-entry/single-exit (SESE) subnet with an opaque transition carrying accumulated complexity weight.
_Avoid_: Graph compression, subnet deletion, macro collapsing

**Structuredness Metric (SM)**:
The quantitative complexity metric derived from iterative structural reduction and component penalty weighting, representing the raw accumulated weight $\\tau$ upon termination.
_Avoid_: Complexity index, structuredness score normalization

**Component Penalty ($\\omega$)**:
The structural penalty score assigned to a recognized component based on its structural type and branch symmetry multiplier.
_Avoid_: Weight cost, complexity penalty points

**Transition Weight ($\\tau$)**:
The scalar complexity metric accumulated on a transition (initial = 1.0; increases as components are folded into opaque transitions).
_Avoid_: Firing cost, step weight

**Fold Config**:
A typed configuration object holding the base penalty weights ($\\rho$) for each component type.
_Avoid_: Weight options, reduction settings

**Fold Step**:
A serializable snapshot recording a single reduction operation: detected component type, consumed node IDs, created opaque transition ID, $\\omega$, $\\tau$, running SM score, and resulting net state.
_Avoid_: Intermediate net, reduction snapshot

**Single-Place Contraction**:
The fine-grained reduction operation that removes exactly one intermediate place and merges its adjacent transitions, replacing maximal chain matching to gracefully collapse AST branch anomalies.
_Avoid_: Sequence collapsing, chain reduction

**Live Fold Reduction**:
The process of executing structural folds (e.g., Single-Place Contractions) natively within the browser's JavaScript engine on the current interactive graph state, independent of Python pre-computation.
_Avoid_: Client-side folding, JS reduction

**Place-Centric Fold Trigger**:
The interaction paradigm where a user explicitly selects a single Place node to initiate a Live Fold Reduction on its immediate structural environment, ensuring fine-grained step-by-step graph simplification.
_Avoid_: Node clicking, manual reduction

**Collapsed Compound State**:
The visual state of an inlined function where its internal Petri net structure has been entirely reduced to a single transition, represented in the UI as a closed container (displaying the function name and component ID) rather than a naked opaque transition.
_Avoid_: Folder node, closed sub-graph

**Folded Component**:
An opaque transition created by Live Fold Reduction that represents a reduced subnet and retains its nodes and arcs for Component-Local Unfold. Its retained subnet may contain other Folded Components.
_Avoid_: Deleted subnet, unexpanded call (when referring to a reduced subnet)

**Component-Local Unfold**:
The restoration of the exact subnet consumed by a chosen folded component, independently of folds elsewhere. It is distinct from chronologically undoing or redoing a viewer action.
_Avoid_: Local undo, node expansion

**Viewer Action History**:
The chronological record of committed changes to the active graph's structure, component names, or node positions during one open viewer session. Each entry represents one user gesture, which may include multiple folds or unfolds.
_Avoid_: Fold playback, component restoration history

**Component Node Renaming**:
The ability for a user to assign a semantic, domain-specific label to an opaque transition (created via Live Fold Reduction) via a dedicated UI panel or modal, overriding the default generated `c_XX` identifier.
_Avoid_: Node relabeling, text edit

**Docked Sidebar**:
The inspector beside the graph that presents node metadata and available actions without covering the graph. Its shown or hidden state is separate from node selection and inspection.
_Avoid_: Floating popover, cleared inspection (when referring to sidebar visibility)

**Client-Side Export**:
The process of serializing the current interactive graph state (including any Live Fold Reductions) directly from the browser's in-memory model to a downloadable format (like PNML or DOT) without requiring a backend server.
_Avoid_: Browser download, frontend save

**Batch Place Fold**:
A single user gesture that sequentially evaluates and folds all contractible places in a selection or set, skipping non-contractible ones in a single pass.
_Avoid_: Multi-fold, mass collapse

**Fold-Entire-Function**:
A repeated reduction action within one Function Fold Scope, applying eligible elementary reductions before validated structural reductions until no further progress is possible or the compound fully collapses.
_Avoid_: Function collapse, auto-fold all

**Function Fold Scope**:
The selected function call occurrence and its contained eligible subgraphs within which function folding chooses and consumes reductions. Caller-owned entrance and exit places may anchor a reduction while remaining outside its consumed interior.
_Avoid_: Whole-net selection, lexical scope

**Fold State Snapshot**:
A saved record of a net's current fold state and viewing state, sufficient to resume Live Fold Reduction and Component-Local Unfold with its component names, weights, layout, and viewport preserved.
_Avoid_: Save file, session dump
