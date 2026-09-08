# Code2flow & Code2petri Architecture & Technical Reference

## Overview
This repository contains two sibling static analysis tools:
1. **`code2flow`**: Generates call graphs across functions, classes, and files for dynamic programming languages (Python, JavaScript, Ruby, PHP) by converting source code into ASTs and resolving function calls and references.
2. **`code2petri`**: Generates 1-safe, sound Petri nets (P/T nets) representing intra-function control flow (branches, loops, exceptions, jumps, and calls). Supports **Python** and **JavaScript** (with C# and C++ planned in upcoming phases) via a formal `WalkerProtocol`, serializing graphs to ISO/IEC 15909-2 PNML, Graphviz DOT, JSON, SVG, and PNG formats.

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
│   ├── __init__.py                # Package exports (Place, Transition, Arc, PetriNet, WalkerProtocol, PythonWalker, JavascriptWalker, code2petri)
│   ├── model.py                   # Core Petri net domain model & format serializers (PNML, DOT, JSON)
│   ├── walker_protocol.py         # Runtime-checked WalkerProtocol(abc.ABC) contract
│   ├── control_flow_builder.py    # Shared builder composition layer (counters, stacks, routing, wiring primitives)
│   ├── python_walker.py           # Python AST walker implementing WalkerProtocol
│   ├── javascript_walker.py       # JavaScript Acorn AST walker implementing WalkerProtocol
│   └── engine.py                  # Pipeline orchestrator, CLI interface (`code2petri`), file extension router & Graphviz renderer
├── tests/                         # Comprehensive unit & integration test suites (166 passing tests)
│   ├── petri_assertions.py        # Shared structural assertion utilities for Petri nets
│   ├── test_petri_model.py        # Tests for Place, Transition, Arc, PetriNet, and serializers
│   ├── test_walker_protocol.py    # Contract adherence & instantiation tests for WalkerProtocol
│   ├── test_python_walker.py      # Python control-flow walker unit tests
│   ├── test_javascript_walker.py  # JavaScript control-flow walker unit & integration tests
│   ├── test_petri_if_branching.py # Python if/elif/else branching tests
│   ├── test_petri_loops.py        # Python while/for loop tests
│   ├── test_petri_try.py          # Python try/except/finally tests
│   ├── test_petri_pipeline.py     # End-to-end CLI & pipeline tests
│   └── test_code/                 # Test code fixtures
│       ├── petri_py/              # Python test code snippets
│       ├── petri_js/              # JavaScript test code snippets
│       └── game_of_life/          # GameOfLife_Simulator integration target (app.js, webgl-engine.js)
└── .scratch/code2petri/           # Local documentation, grand roadmap, specs, and review logs
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
- **`Transition`**: Action or statement execution. Enforces non-null `id`, optional `label`, `line_number`.
- **`Arc`**: Directed connection enforcing strict bipartite graph constraints (`Place` -> `Transition` or `Transition` -> `Place`). Has `source`, `target`, and `weight` (default 1).
- **`PetriNet`**: Container class storing `places`, `transitions`, and `arcs`.
  - `add_place(...)`, `add_transition(...)`, `add_arc(...)` factory methods.
  - `to_pnml()`: ISO/IEC 15909-2 compliant XML representation.
  - `to_dot()`: Graphviz DOT representation (places as circles, transitions as rectangles).
  - `to_dict() / to_json()`: Structured JSON representation.

### 3. `code2petri/walker_protocol.py` (Walker Contract)
- **`WalkerProtocol(abc.ABC)`**: Formal abstract base class specifying the contract that every language walker must implement:
  - `parse_file(filepath: str) -> Any`: Parses a source file into an AST.
  - `find_function(tree: Any, name: str) -> Optional[Any]`: Finds a target function AST node.
  - `find_all_functions(tree: Any) -> List[str]`: Discovers all targetable function names.
  - `walk_function(ast_node: Any, func_name: str = "") -> PetriNet`: Builds a Petri net from the AST node.
  - `get_node_lineno(ast_node: Any) -> Optional[int]`: Extracts starting line number from an AST node.

### 4. `code2petri/control_flow_builder.py` (Composition Layer)
To comply with the architectural principle of composition over inheritance, walkers do not inherit from a base walker class. Instead, they compose `ControlFlowBuilder`:
- **`ControlFlowBuilder`**: Encapsulates state, counters, context stacks, and graph wiring primitives:
  - Counters: `place_counter`, `trans_counter` (`new_place()`, `new_transition()`).
  - Stacks: `loop_stack` (`push_loop()`, `pop_loop()`), `try_stack` (`push_try()`, `pop_try()`).
  - Arc management: `add_arc()`, `has_incoming_arcs()`.
  - High-level wiring primitives: `wire_sequential_statement()`, `wire_if_split()`, `wire_try_catch()`, `wire_standard_loop()`, `wire_terminal_exception()`.
- **Parameter Objects**:
  - `StatementContext`: `(current_place, is_last, target_exit, lineno)` passed to statement dispatch handlers to decouple statement walking loops from builder plumbing.
  - `LoopContext`: `(head, exit)` tracking enclosing loop jump targets.
  - `LoopRouting`: `(head, loop_trans, exit_trans, exit_place)` encapsulating standard loop topology.
  - `TryContext`: `(except_entry, finally_entry, loop_depth)` managing exception propagation.

---

## Control-Flow Walkers

### 1. Python Control-Flow Walker (`code2petri/python_walker.py`)
Translates Python native `ast` nodes into 1-safe, sound P/T nets:
- **Parser Foundation**: `code2flow.python.Python.get_tree()`.
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
| **Call Statements** | Labeled as opaque transition: `call: func_name()` |
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
| **Call Statements** | Labeled as opaque transition: `call: func_name()` |
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

### `code2flow` CLI
```bash
code2flow <source_files...> [-o output_file] [--language py|js|ruby|php]
```

### `code2petri` CLI
```bash
code2petri <source_file> -t <target_function> [-o output_file] [--list-functions] [--verbose] [--quiet]
```

#### Language Dispatch
`code2petri.engine` selects the walker dynamically based on file extension:
```python
WALKERS = {
    '.py': PythonWalker,
    '.js': JavascriptWalker,
}
```

#### Function Targeting Options (`-t / --target-function`)
- Standard function: `-t my_func`
- Qualified class method: `-t WebGLEngine.step` or `-t MyClass.my_method`
- Anonymous callback: `-t "(anonymous@151)"` or `-t "init.(anonymous@42)"`
- Global script execution: `-t "(global)"`

#### Output Formats Supported by `code2petri`
- `.pnml`: Standard ISO/IEC 15909-2 Petri net exchange XML (compatible with PIPE, LoLA, WoPeD).
- `.dot` / `.gv`: Graphviz DOT syntax with circle places and rectangle transitions.
- `.json`: Structured schema with `places`, `transitions`, and `arcs`.
- `.svg` / `.png`: Rendered visual diagrams generated automatically via Graphviz `dot`.

---

## Inter-Module Integration & Design Principles

1. **Shared Parser Foundation**: Walkers leverage `code2flow`'s established AST parsing frontends (`code2flow.python` and `code2flow.javascript`).
2. **Composition over Inheritance**: Walkers compose `ControlFlowBuilder` rather than subclassing a base walker, eliminating tight inheritance coupling and Refused Bequest smells.
3. **Parameter Objects & Seams**: `StatementContext` parameter objects and safe property extractors decouple block traversal from state management, preventing Feature Envy and Message Chains.
4. **Cross-Language Semantic Parity**: Synthetic `(global)` scope, qualified naming, and structural soundness (initial marking = 1, single terminal sink, bipartite graph verification) are enforced across both Python and JavaScript.
5. **Comprehensive Verification**: Validated by 166 automated unit and integration tests covering language constructs and real-world multi-file targets ([`GameOfLife_Simulator`](file:///Users/pingchungtsai/My%20Drive%20%28ric6121824%40gmail.com%29/Digital%20Media%20MSc/Semester%204/GameOfLife_Simulator)).
