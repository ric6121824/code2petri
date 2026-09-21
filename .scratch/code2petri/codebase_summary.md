# Code2flow & Code2petri Architecture & Technical Reference

## Overview
This repository contains two sibling static analysis tools:
1. **`code2flow`**: Generates call graphs across functions, classes, and files for dynamic programming languages (Python, JavaScript, Ruby, PHP) by converting source code into ASTs and resolving function calls and references.
2. **`code2petri`**: Generates 1-safe, sound Petri nets (P/T nets) representing intra-function control flow (branches, loops, exceptions, jumps, and calls) and cross-file call references. Supports **Python** and **JavaScript** (with C# and C++ planned in upcoming phases) via a formal `WalkerProtocol`. Features cross-file call resolution via `--context` symbol indexing and serializes graphs to ISO/IEC 15909-2 PNML, Graphviz DOT, JSON, SVG, and PNG formats.

---

## Codebase Directory Structure
```
code2flow/
├── c2f                            # Executable stub wrapper for code2flow
├── setup.py                       # Packaging setup with console_scripts for `code2flow` and `code2petri`
├── code2flow/                     # Primary code2flow package directory
│   ├── __init__.py                # Package export (`from .engine import code2flow`)
│   ├── engine.py                  # Pipeline orchestrator, CLI interface, and graph filter/output generators
│   ├── model.py                   # Core abstractions (Group, Node, Call, Variable, Edge, BaseLanguage)
│   ├── python.py                  # Python AST walker using native `ast` module
│   ├── javascript.py              # JavaScript parser interface (invokes `acorn` via node)
│   ├── ruby.py                    # Ruby parser interface (invokes `ruby-parse`)
│   ├── php.py                     # PHP parser interface (invokes `PHP-Parser` via php)
│   ├── get_ast.js                 # Node.js script helper for Acorn parser
│   └── get_ast.php                # PHP script helper for PHP-Parser
├── code2petri/                    # Multi-language Petri net control-flow package
│   ├── __init__.py                # Package exports (Place, Transition, Arc, PetriNet, WalkerProtocol, PythonWalker, JavascriptWalker, SymbolTable, code2petri)
│   ├── model.py                   # Core Petri net domain model, CallResolution, & serializers (PNML, DOT, JSON)
│   ├── walker_protocol.py         # Runtime-checked WalkerProtocol(abc.ABC), CallSite, and WalkResult contracts
│   ├── control_flow_builder.py    # Shared builder composition layer (counters, stacks, routing, wiring primitives, on_trans hook)
│   ├── symbol_table.py            # Multi-file symbol indexing, variable binding resolution, & call resolution engine
│   ├── python_walker.py           # Python AST walker implementing WalkerProtocol & variable binding extraction
│   ├── javascript_walker.py       # JavaScript Acorn AST walker implementing WalkerProtocol & variable binding extraction
│   ├── fold.py                    # Structural component detection, fold reduction engine, & SM computation (Tickets 17-18)
│   ├── inline.py                  # Inline expansion engine, composite net splicing, & recursion guard (Ticket 19)
│   ├── viewer/                    # Interactive offline HTML viewer generator & embedded assets (Ticket 21)
│   │   ├── __init__.py            # HTML generator dispatch (`generate_html`)
│   │   ├── template.html          # Standalone Cytoscape.js player template with Dagre animations
│   │   └── vendor/                # Embedded minified client libraries (cytoscape.min.js, dagre.min.js, cytoscape-dagre.js)
│   └── engine.py                  # Pipeline orchestrator, CLI (`code2petri`), `--context` file discovery & Graphviz renderer
├── docs/                          # Architecture decision records and specifications
│   └── adr/
│       ├── 0001-constructor-only-variable-resolution.md # ADR on constructor-only variable binding resolution
│       ├── 0002-boundary-place-unification.md           # ADR on boundary place unification for bipartite graph integrity
│       └── 0003-adopt-prom-local-reduction-algorithm.md # ADR on adopting ProM local reduction algorithms
├── tests/                         # Comprehensive unit, integration, & validation test suites (366 passing tests)
│   ├── petri_assertions.py        # Shared structural assertion utilities for Petri nets
│   ├── test_petri_model.py        # Tests for Place, Transition, Arc, PetriNet, CallResolution, and serializers
│   ├── test_walker_protocol.py    # Contract adherence & instantiation tests for WalkerProtocol & WalkResult
│   ├── test_python_walker.py      # Python control-flow walker & variable binding unit tests
│   ├── test_javascript_walker.py  # JavaScript control-flow walker & variable binding unit & integration tests
│   ├── test_symbol_table.py       # Multi-file symbol table indexing and resolution unit tests
│   ├── test_context_pipeline.py   # CLI `--context` ingestion and multi-format serialization integration tests
│   ├── test_game_of_life_validation.py # End-to-end multi-file validation suite against GameOfLife Simulator
│   ├── test_fold_detection.py     # Structural component detection & FoldConfig tests (Ticket 17, 23, 24)
│   ├── test_fold_reduction.py     # Fold reduction engine & SM computation tests (Ticket 18, 23, 24)
│   ├── test_inline_expansion.py   # Inline expansion engine & recursion guard tests (Ticket 19, 22)
│   ├── test_cli_fold_inline.py    # CLI integration tests for --fold, --inline, and headless exports (Ticket 20)
│   ├── test_html_viewer.py        # Self-contained offline HTML viewer generation & DOM tests (Ticket 21, 25-27)
│   ├── test_petri_if_branching.py # Python if/elif/else branching tests
│   ├── test_petri_loops.py        # Python while/for loop tests
│   ├── test_petri_try.py          # Python try/except/finally tests
│   ├── test_petri_pipeline.py     # End-to-end CLI & single-file pipeline tests
│   └── test_code/                 # Test code fixtures
│       ├── petri_py/              # Python test code snippets
│       ├── petri_js/              # JavaScript test code snippets
│       └── game_of_life/          # GameOfLife_Simulator integration target (app.js, webgl-engine.js)
└── .scratch/code2petri/           # Local documentation, grand roadmap, specs, issues, and review logs
    ├── codebase_summary.md        # This document
    ├── grand_plan.md              # Grand roadmap from Phase 1 to Phase 6
    ├── issues/                    # Detailed ticket task specifications (Tickets 01–28)
    ├── specs/                     # Master phase specifications (Phases 1, 2, 2.5, 2.6)
    └── reviews/                   # Two-axis code review audit reports
```

---

## Core Data Models & Architecture

### 1. `code2flow/model.py` (Call-Graph Abstractions)
- **`BaseLanguage` (ABC)**: Interface for language AST parsers (`get_tree`, `separate_namespaces`, `make_nodes`, `make_root_node`, `make_class_group`).
- **`Group`**: Namespaces (files, classes, modules).
- **`Node`**: Functions or global script blocks with attached `Call`s and `Variable`s.
- **`Call`**: Function invocation sites (`obj.method()` or `fn()`).
- **`Variable`**: Named tokens in scope pointing to targets or constructors.
- **`Edge`**: Directed call-graph linkages between `Node` instances.

### 2. `code2petri/model.py` (Petri Net Abstractions)
- **`Place`**: Control point where execution rests. Enforces non-null `id`, optional `label`, `line_number`, and `initial_tokens` (default 0).
- **`Transition`**: Action or statement execution. Enforces non-null `id`, optional `label`, `line_number`, optional `metadata` dict, and optional `resolution` (`CallResolution`).
  - `RESERVED_METADATA_KEYS`: `{"resolved", "resolved_to", "target_file", "status"}`.
  - `add_pnml_toolspecific(parent)`: Serializes `<toolspecific tool="code2petri" version="1.0">` containing `<resolved target="..." file="..."/>` or `<unresolved/>`, plus custom `<property>` elements.
  - `get_dot_attributes()`: Emits Graphviz styling (`color="#2e7d32"` for resolved, `color="#e65100"` for unresolved) and tooltips.
  - `to_dict()`: Inlines resolution keys (`resolved`, `resolved_to`, `target_file`, and root `"status": "[unresolved]"`).
- **`CallResolution` (frozen dataclass)**: Encapsulates resolution outcome (`resolved: bool`, `resolved_to: Optional[str]`, `target_file: Optional[str]`). Includes `from_metadata(dict)` factory.
- **`Arc`**: Directed connection enforcing strict bipartite graph constraints (`Place` -> `Transition` or `Transition` -> `Place`). Has `source`, `target`, and `weight` (default 1).
- **`PetriNet`**: Container class storing `places`, `transitions`, and `arcs`.
  - `add_place(...)`, `add_transition(...)`, `add_arc(...)` factory methods.
  - `to_pnml()`: ISO/IEC 15909-2 compliant XML representation.
  - `to_dot()`: Graphviz DOT representation (places as circles, transitions as rectangles with resolution tooltips/borders).
  - `to_dict() / to_json()`: Structured JSON representation.

### 3. `code2petri/walker_protocol.py` (Walker Contract & Call Sites)
- **`CallSite` (frozen dataclass)**: Structured representation of a call site encountered during AST traversal:
  - `caller_function: str`: Name of the enclosing function.
  - `caller_file: str`: Source file containing the call.
  - `callee_name: str`: Target function or method name (e.g. `"step"` or `"foo"`).
  - `callee_owner: Optional[str]`: Target receiver variable or module (e.g. `"gpuEngine"` or `"renderer"`).
  - `line_number: int`: Source line number of the call.
  - `transition_id: str`: ID of the corresponding `Transition` in the caller's net.
- **`WalkResult` (NamedTuple)**:
  - `net: PetriNet`: The generated Petri net model.
  - `call_sites: List[CallSite]`: The extracted call site records.
- **`WalkerProtocol(abc.ABC)`**: Formal abstract base class:
  - `parse_file(filepath: str) -> Any`: Parses a source file into an AST.
  - `find_function(tree: Any, name: str) -> Optional[Any]`: Finds a target function AST node.
  - `find_all_functions(tree: Any) -> List[str]`: Discovers all targetable function names.
  - `collect_variable_bindings(tree: Any) -> Dict[str, str]`: Extracts variable-to-class bindings from constructor instantiations.
  - `walk_function(ast_node: Any, func_name: str = "", filepath: Optional[str] = None) -> WalkResult`: Builds net and call sites.
  - `get_node_lineno(ast_node: Any) -> Optional[int]`: Extracts starting line number.

### 4. `code2petri/control_flow_builder.py` (Composition Layer)
Walkers compose `ControlFlowBuilder` to manage state, counters, context stacks, and graph wiring primitives:
- Counters: `place_counter`, `trans_counter` (`new_place()`, `new_transition()`).
- Callback Hook: `on_trans(transition)` invoked whenever a transition is added, cleanly notifying walkers of transition IDs without coupling.
- Stacks: `loop_stack` (`push_loop()`, `pop_loop()`), `try_stack` (`push_try()`, `pop_try()`).
- Arc management: `add_arc()`, `has_incoming_arcs()`.
- High-level wiring primitives: `wire_sequential_statement()`, `wire_if_split()`, `wire_try_catch()`, `wire_standard_loop()`, `wire_terminal_exception()`.
- Parameter Objects: `StatementContext`, `LoopContext`, `LoopRouting`, `TryContext`.

### 5. `code2petri/symbol_table.py` (Multi-File Indexing & Call Resolution)
- **`SymbolRecord` (frozen dataclass)**: `(name, filepath, ast_node, language, is_method, class_name)`.
- **`SymbolTable`**: Indexes all functions across context files into `(language, qualified_name) -> SymbolRecord`:
  - `add_file(filepath: str)`: Parses and discovers functions in a source file using the appropriate walker.
  - `resolve_call_sites(call_sites, net, variable_bindings)`: Matches call sites against the symbol table:
    1. **Bound Method Resolution**: If `callee_owner` is bound in `variable_bindings` to class `C`, resolves to `C.callee_name`.
    2. **Direct Class Receiver Fallback**: If receiver matches an indexed class directly, resolves to `ClassName.callee_name`.
    3. **Same-File Bare Call Resolution**: Matches unowned calls to non-method functions defined in the caller's file.
    4. **Cross-File Bare Call Resolution**: Matches unowned calls to unique non-method functions in context files of the same language.
    5. **Unresolved Fallback**: If 0 or >1 matches found, marks transition as `[unresolved]`.

---


### 6. `code2petri/fold.py` (Structural Folding & SM Complexity Computation)
Implements structural component recognition and iterative reduction per Lassen & van der Aalst (2008):
- **`Component`**: Abstract base dataclass with `component_type`, `node_ids`, `entry_place_id`, `exit_place_id`, and `priority`.
  - Subtypes: `SequenceComponent`, `ChoiceComponent`, `LoopComponent`, `UnstructuredComponent`.
- **`FoldConfig`**: Configurable penalty weights $\\rho$ (defaults: Sequence=0, Choice=1, Marked-Graph=2, Loop=3, Unstructured=7).
  - `load(path_or_json)`: Loads config overrides from JSON file or literal JSON string.
- **Detection Functions**:
  - `detect_sequences`: Identifies maximal unbranched linear chains ($p \\to t \\to p \\to \\dots$).
  - `detect_choices`: Identifies XOR-split/join diamonds sharing single entry and merge places ($|T_C| \\ge 2$).
  - `detect_loops`: Identifies elementary cycles with single entry place and single exit arc.
  - `detect_components`: Aggregates all components sorted by Definition 21 priority and size.
- **Symmetry Multipliers & Penalties**:
  - `calculate_symmetry_multiplier`: Computes $\\text{diff}(X) = ||\\{x \\in X \\mid |x*| > 1\\}| - |\\{x \\in X \\mid |*x| > 1\\}|| + 1$ on subnet projection $PN|C$.
  - Component penalty $\\omega = \\rho \\times \\text{diff}(X)$.
- **Reduction Loop (`fold_reduction`)**:
  - Greedily collapses simplest components into opaque transitions ($t_{C1}, t_{C2}, \\dots$).
  - Boundary places unified, internal places/transitions removed, accumulated weight $\\tau$ updated on opaque transition.
  - Unstructured fallback folds remaining irreducible nodes with $\\rho = 7$.
  - Returns `FoldResult` with snapshots (`FoldStep`), `final_sm`, and `fully_reducible`.

### 7. `code2petri/inline.py` (Inline Expansion & Composite Net Construction)
Splices resolved callee subnets into caller Petri nets at the data-model level:
- **`CallFrame` (frozen dataclass)**: Identifies invocation frame `(file_path, function_name, is_method, class_name)`. Generates candidate `variants()` to match caller/callee signatures.
- **Boundary Place Unification ([ADR 0002](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/docs/adr/0002-boundary-place-unification.md))**:
  - Callee source place is unified into caller call transition preset place; callee sink place is unified into caller call transition postset place.
  - Preserves bipartite graph validity ($F \\subseteq (P \\times T) \\cup (T \\times P)$) without illegal place-to-place arcs.
- **Recursion Guard**:
  - Maintains vertical call-stack set during recursive descent.
  - Halts expansion when callee frame is present in active stack, marking call transition with `metadata={"recursive_cycle": True}`.
  - Honors `CallSite.is_callback_loop` to halt browser game loops (`requestAnimationFrame`).
- **Depth Capping**: Configurable via `--inline-depth=N` (defaults to 1).

### 8. `code2petri/viewer/` (Self-Contained Offline HTML Viewer)
Generates single-file standalone interactive visualization using Cytoscape.js and Dagre layout:
- **`generate_html(net_or_fold, title)`**: Inlines HTML template, minified vendor JS (`cytoscape.min.js`, `dagre.min.js`, `cytoscape-dagre.js`), and pre-computed JSON snapshots into a zero-dependency `.html` document.
- **Interactive Controls**: Bidirectional step playback (`Fold`, `Unfold`, `Reset`), slider navigation, step counter, live SM score display, and contextual step inspection panel (`#info-panel`).
- **Morphing Animations**: Configured with 350ms Dagre layout transitions preserving node coordinates across step snapshots for smooth visual collapse/expansion.

---

## Control-Flow Walkers

### 1. Python Control-Flow Walker (`code2petri/python_walker.py`)
Translates Python native `ast` nodes into 1-safe, sound P/T nets:
- **Parser Foundation**: `code2flow.python.Python.get_tree()`.
- **Variable Bindings**: `collect_variable_bindings` inspects `ast.Assign` and `ast.AnnAssign` nodes for constructor calls (`x = Foo()` / `x: Foo = Foo()`), extracting variable-to-class mappings.
- **Call Site Harvesting**: Traverses statement ASTs for `ast.Call` nodes, hooking into `on_trans` to record `CallSite` entries.
- **Function Discovery**:
  - Standard functions (`ast.FunctionDef`, `ast.AsyncFunctionDef`).
  - Qualified class methods (`ClassName.methodName`).
  - Top-level script statements via synthetic `(global)` wrapper node.
- **Label Generation**: Python AST expression unparsing.

#### Semantic Rules
| Python AST Construct | Petri Net Mapping Structure |
|---|---|
| **Start / Entry** | `p_start` (initial token = 1) → `t_entry` (`def func_name(...)`) → `p1` |
| **Sequential Stmts** | `p_in` → `t_stmt` (labeled with statement code/line) → `p_out` |
| **Call Statements** | Labeled as opaque transition with `CallSite` registered: `call: func_name()` |
| **Return** (`ast.Return`) | `current_place` → `t_return` → `end_place` |
| **If / Elif / Else** | **XOR-split / XOR-join**: condition transition splits to true and false entry places; branches walk independently and converge on a single merge place. |
| **While / For Loops** | **Cycle**: `head_place` → loop transition → body → back-arc to `head_place`. Exit transition arcs to `exit_place` (or `else` block). |
| **Break / Continue** | `break` jumps to enclosing loop's exit place; `continue` jumps to loop's head place. |
| **Try / Except / Finally** | `t_try` enters try body; transitions in try body emit exception arcs to `except_entry`. Handlers compete from `except_entry`. Both normal and handler exits converge into mandatory `finally` block (or shared exit). |
| **Raise** | Routes to active `except_entry` or terminal exception place. |

---

### 2. JavaScript Control-Flow Walker (`code2petri/javascript_walker.py`)
Translates Acorn JSON AST nodes into 1-safe, sound P/T nets:
- **Parser Foundation**: `code2flow.javascript.Javascript.get_tree()` (invokes Node.js + Acorn with `source_type="script"`).
- **Variable Bindings**: `collect_variable_bindings` inspects `VariableDeclaration` and `AssignmentExpression` nodes for `NewExpression` calls (`const x = new Foo()`, `x = new Foo()`), extracting variable-to-class mappings via `_extract_new_class_name`.
- **Call Site Harvesting**: Traverses statement ASTs for `CallExpression` nodes, hooking into `on_trans` to record `CallSite` entries.
- **Function Discovery**:
  - Function declarations (`FunctionDeclaration`).
  - Qualified class methods (`ClassName.methodName` from `MethodDefinition`).
  - Named arrow functions and function expressions (`VariableDeclarator`).
  - Anonymous callbacks and event handlers via synthetic parenthetical notation (`ParentFunction.(anonymous@LineNumber)`).
  - Top-level script statements via synthetic `(global)` wrapper node.
- **Label Generation**: Direct raw source text slicing using Acorn's `start` and `end` byte offsets, preserving exact source formatting.

#### Semantic Rules
| JavaScript AST Construct | Petri Net Mapping Structure |
|---|---|
| **Sequential Stmts** | `p_in` → `t_stmt` (sliced source string) → `p_out` |
| **Call Statements** | Labeled as opaque transition with `CallSite` registered: `call: func_name()` |
| **Return** | `current_place` → `t_return` → `end_place` |
| **If / Else If / Else** | **XOR-split / XOR-join**: condition transition to true/false entry places; converges on single merge place. |
| **While / For / For..In / For..Of** | **Cycle**: loop head place, body transition, back-arc, exit transition to exit place. |
| **Do...While** | **Cycle with post-condition**: body executes first from head place, then condition transition evaluates and arcs back to body head. |
| **Switch / Case / Default** | **Multi-way XOR-split**: condition place forks into separate case transitions converging to a shared merge place; handles default branches and empty-case fallthrough. |
| **Break / Continue** | `break` jumps to loop exit place; `continue` jumps to loop head place. |
| **Try / Catch / Finally** | Body transitions emit exception arcs to catch entry; both paths converge on mandatory `finally` block. |
| **Throw** | Arcs to enclosing `catch_entry` or terminal exception place. |
| **Game-Loop Cycle (`requestAnimationFrame`)** | Detects recursive calls where `requestAnimationFrame(loop)` passes the enclosing function name; converts the call transition into a back-arc cycle to `p_start`. |

---

## Execution Pipelines & CLI

### `code2petri` CLI
```bash
code2petri <source_file> -t <target_function> [--context <context_path...>] [-o output_file] [--fold | --no-fold] [--weights <path_or_json>] [--inline] [--inline-depth <N>] [--list-functions] [--verbose] [--quiet]
```

#### Language Dispatch
`code2petri.symbol_table` and `code2petri.engine` route dynamically based on file extension:
```python
SUPPORTED_WALKERS = {
    '.py': PythonWalker,
    '.js': JavascriptWalker,
}
```

#### CLI Flags
- `<source_file>`: Primary source file containing the target function.
- `-t / --target-function`: Name of the function, qualified method, or synthetic scope to analyze.
- `--context`: One or more context files or directories parsed to build the `SymbolTable` for cross-file call resolution. Directories are recursively scanned for supported files (skipping macOS `._*` resource forks).
- `-o / --output`: Destination path. Format determined by extension (`.pnml`, `.dot`, `.gv`, `.json`, `.png`, `.svg`, `.html`).
- `--fold`: Enables structural fold reduction and Structuredness Metric (SM) computation. Automatically enabled for `.html` output.
- `--no-fold`: Disables structural fold reduction, outputting raw unreduced nets even for `.html`.
- `--weights`: Path to a JSON configuration file or raw JSON string specifying custom base penalties $\\rho$.
- `--inline`: Recursively splices resolved callee Petri nets into the caller net at call site boundaries.
- `--inline-depth`: Maximum recursion depth for inline expansion (default: 1).
- `--list-functions`: Lists all discoverable functions in the primary file and exits.
- `--verbose`: Enables detailed debug logging (including symbol indexing and resolution diagnostics).

#### Output Formats Supported by `code2petri`
- `.html`: Self-contained interactive offline viewer embedding Cytoscape.js, Dagre layout, live SM score display, animated fold/unfold playback controls, interactive compound subnet expansion on resolved calls, filename badge, dual-button viewport panning (right & middle click), scroll wheel zoom, and left-click node repositioning.
- `.pnml`: Standard ISO/IEC 15909-2 Petri net exchange XML with `<toolspecific>` metadata elements. When `--fold` is active, outputs the penultimate fold state.
- `.dot` / `.gv`: Graphviz DOT syntax with tooltips and color-coded borders. When `--fold` is active, renders the penultimate fold state with the SM score in the graph title.
- `.json`: Structured schema. When `--fold` is active, serializes full `FoldResult` schema (initial net, ordered fold steps, final SM, and reducibility flag).
- `.svg` / `.png`: Rendered visual diagrams generated automatically via Graphviz `dot` (renders penultimate fold state when `--fold` is active).

---

## Inter-Module Integration & Design Principles

1. **Shared Parser Foundation**: Walkers leverage `code2flow`'s established AST parsing frontends (`code2flow.python` and `code2flow.javascript`).
2. **Composition over Inheritance**: Walkers compose `ControlFlowBuilder` rather than subclassing a base walker, eliminating tight inheritance coupling.
3. **Constructor-Only Variable Resolution ([ADR 0001](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/docs/adr/0001-constructor-only-variable-resolution.md))**: Lightweight, sound variable binding extraction targeting constructor instantiations (`x = Foo()` / `const x = new Foo()`) without full dynamic dataflow analysis.
4. **Strict Language Boundary Enforcement**: Call resolution only links symbols between source files of the same programming language.
5. **Non-Destructive Reference Serialization**: Cross-file references enrich Petri net transitions with metadata and visual styling without modifying underlying bipartite graph topology.
6. **Bipartite Graph Integrity via Boundary Place Unification ([ADR 0002](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/docs/adr/0002-boundary-place-unification.md))**: Inline expansion fuses caller and callee boundary places rather than creating illegal place-to-place arcs, strictly preserving $F \subseteq (P \times T) \cup (T \times P)$ and 1-safe sound firing semantics.
7. **ProM Local Reduction Algorithms ([ADR 0003](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/docs/adr/0003-adopt-prom-local-reduction-algorithm.md))**: Employs fine-grained Single-Place Contraction ($1 \to 1 \to 1$), Atomic Choice Collapse (1.5x penalty), and bidirectional SESE reachability to naturally fold AST-generated branching routing places without spurious unstructured penalties.
8. **Interactive Client-Side Subnet Expansion**: HTML viewer embeds pre-computed callee payloads and dynamically expands green resolved calls into Cytoscape compound nodes with boundary place rewiring and independent fold slider operations.
9. **Self-Contained Offline Visualization**: HTML viewer operates without external CDNs or network connections, embedding minified layout engines, full callee net payloads, and pre-computed fold snapshots directly into the document.
10. **Comprehensive Verification**: Validated by **366 automated unit, integration, and cross-file validation tests**, including end-to-end multi-file tests against the [`GameOfLife_Simulator`](file:///Users/pingchungtsai/My%20Drive%20%28ric6121824%40gmail.com%29/Digital%20Media%20MSc/Semester%204/GameOfLife_Simulator) validation target (`app.js` and `webgl-engine.js`).
