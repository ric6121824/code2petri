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
│   └── engine.py                  # Pipeline orchestrator, CLI (`code2petri`), `--context` file discovery & Graphviz renderer
├── docs/                          # Architecture decision records and specifications
│   └── adr/
│       └── 0001-constructor-only-variable-resolution.md # ADR on constructor-only variable binding resolution
├── tests/                         # Comprehensive unit, integration, & validation test suites (235 passing tests)
│   ├── petri_assertions.py        # Shared structural assertion utilities for Petri nets
│   ├── test_petri_model.py        # Tests for Place, Transition, Arc, PetriNet, CallResolution, and serializers
│   ├── test_walker_protocol.py    # Contract adherence & instantiation tests for WalkerProtocol & WalkResult
│   ├── test_python_walker.py      # Python control-flow walker & variable binding unit tests
│   ├── test_javascript_walker.py  # JavaScript control-flow walker & variable binding unit & integration tests
│   ├── test_symbol_table.py       # Multi-file symbol table indexing and resolution unit tests
│   ├── test_context_pipeline.py   # CLI `--context` ingestion and multi-format serialization integration tests
│   ├── test_game_of_life_validation.py # End-to-end multi-file validation suite against GameOfLife Simulator
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
    ├── issues/                    # Detailed ticket task specifications (Tickets 01–15)
    ├── specs/                     # Master phase specifications (Phase 1, Phase 2)
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
code2petri <source_file> -t <target_function> [--context <context_path...>] [-o output_file] [--list-functions] [--verbose] [--quiet]
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
- `-o / --output`: Destination path. Format determined by extension (`.pnml`, `.dot`, `.gv`, `.json`, `.png`, `.svg`).
- `--list-functions`: Lists all discoverable functions in the primary file and exits.
- `--verbose`: Enables detailed debug logging (including symbol indexing and resolution diagnostics).

#### Output Formats Supported by `code2petri`
- `.pnml`: Standard ISO/IEC 15909-2 Petri net exchange XML with `<toolspecific>` metadata elements for resolved/unresolved calls.
- `.dot` / `.gv`: Graphviz DOT syntax with tooltips and color-coded borders (`#2e7d32` for resolved calls, `#e65100` for unresolved calls).
- `.json`: Structured schema with `places`, `transitions` (with inlined resolution properties), and `arcs`.
- `.svg` / `.png`: Rendered visual diagrams generated automatically via Graphviz `dot`.

---

## Inter-Module Integration & Design Principles

1. **Shared Parser Foundation**: Walkers leverage `code2flow`'s established AST parsing frontends (`code2flow.python` and `code2flow.javascript`).
2. **Composition over Inheritance**: Walkers compose `ControlFlowBuilder` rather than subclassing a base walker, eliminating tight inheritance coupling.
3. **Constructor-Only Variable Resolution ([ADR 0001](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/docs/adr/0001-constructor-only-variable-resolution.md))**: Lightweight, sound variable binding extraction targeting constructor instantiations (`x = Foo()` / `const x = new Foo()`) without full dynamic dataflow analysis.
4. **Strict Language Boundary Enforcement**: Call resolution only links symbols between source files of the same programming language.
5. **Non-Destructive Reference Serialization**: Cross-file references enrich Petri net transitions with metadata and visual styling without modifying underlying bipartite graph topology.
6. **Comprehensive Verification**: Validated by **235 automated unit, integration, and cross-file validation tests**, including end-to-end multi-file tests against the [`GameOfLife_Simulator`](file:///Users/pingchungtsai/My%20Drive%20%28ric6121824%40gmail.com%29/Digital%20Media%20MSc/Semester%204/GameOfLife_Simulator) validation target (`app.js` and `webgl-engine.js`).
