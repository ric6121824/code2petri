# code2petri Domain Model

The vocabulary for transforming source code control flow into executable Petri nets, bridging ASTs and Graphviz/PNML representations.

## Language

**Walker Protocol**:
The strict abstraction layer (implemented as an `abc.ABC`) that all language-specific parsers must implement to convert an AST into a Petri net.
_Avoid_: Parser interface, walker base class

**Global Scope**:
The top-level code in a file that executes outside of any function definition, addressable in the CLI as `(global)`.
_Avoid_: Main body, script scope

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
