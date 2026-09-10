## Problem Statement

Currently, `code2petri` only analyzes a single function in an isolated source file. Any function call encountered during AST traversal is rendered as a standalone, opaque transition labeled with a string (e.g., `call: gpuEngine.step()`). The relationship between the call site and its callee definition is lost, preventing users from understanding how control flow connects across multi-file codebases.

In real-world applications such as the primary validation target ([`GameOfLife_Simulator`](file:///Users/pingchungtsai/My%20Drive%20%28ric6121824%40gmail.com%29/Digital%20Media%20MSc/Semester%204/GameOfLife_Simulator)), critical logic crosses file boundaries: `app.js` instantiates `WebGLEngine` and invokes `gpuEngine.step()`, `gpuEngine.randomize()`, and `gpuEngine.drawToScreen()` defined in `webgl-engine.js`. Without cross-file reference tracing, users cannot trace execution dependencies across files, distinguish internal project calls from external library calls, or obtain machine-readable linkages between separate Petri nets.

## Solution

Implement cross-file reference tracing infrastructure in `code2petri`. Allow users to specify a **Resolution Context** (via a `--context` CLI flag accepting files and directories) that is parsed into a multi-language symbol table. Extend the **Walker Protocol** to extract structured **Call Site** records during AST traversal and harvest file-wide **Variable Binding** mappings from constructor instantiations.

When a function is analyzed with a resolution context, `code2petri` matches call sites against the symbol table, resolving instance method invocations to their class definitions within the same language. Resolved call transitions are annotated with structured target metadata, while unresolvable or external calls are explicitly marked as unresolved. These annotations are serialized to PNML `<toolspecific>` elements, Graphviz DOT tooltips and styling, and JSON fields.

**Implementation Delay Note**: As decided during domain modeling and architectural review, **Inline Expansion** (splicing callee subnets directly into caller nets) is explicitly **delayed until Phase 2.5** alongside the interactive HTML viewer. Phase 2 delivers non-destructive reference resolution, establishing the symbol table and call-site infrastructure without risk of net explosion.

## User Stories

1. As a user, I want to provide additional source files via `--context <file...>` so that function calls in my target function can be resolved against external definitions.
2. As a user, I want to provide a directory via `--context <dir>` so that all project source files in that directory are automatically parsed for call targets without manual enumeration.
3. As a user, I want directory context scanning to automatically filter files by supported extension so that I do not need to clean non-source assets out of target directories.
4. As a user, I want call resolution to strictly match symbols within the same source language so that mixed-language directories do not produce invalid cross-language linkages.
5. As a user, I want instance method calls (e.g., `gpuEngine.step()`) to automatically resolve to their qualified class methods (e.g., `WebGLEngine.step`) when the object was instantiated via a constructor (`new WebGLEngine(...)` or `WebGLEngine(...)`) so that object-oriented calls across files are resolved accurately.
6. As a user, I want resolved call transitions in Graphviz DOT output to include tooltips and distinct visual styling (e.g., green borders) so that I can immediately identify cross-file links when viewing rendered diagrams.
7. As a user, I want resolved call transitions in PNML output to include standardized `<toolspecific>` metadata elements containing the target function name and target file path so that external Petri net modeling tools can inspect cross-references.
8. As a user, I want resolved call transitions in JSON output to include explicit `resolved_to` and `target_file` attributes so that downstream scripts can programmatically traverse the composite call topology.
9. As a user, I want calls to external libraries, browser APIs, or unresolvable targets to be explicitly annotated as `[unresolved]` in the Petri net metadata so that I can clearly distinguish internal project calls from external boundary interfaces.
10. As a user, I want diagnostics for unresolved function calls to be logged at `DEBUG` level so that normal CLI execution remains uncluttered by expected third-party library calls.
11. As a user, I want existing single-file commands without `--context` to continue working identically to Phase 1 so that backward compatibility is preserved.
12. As a user, I want to analyze functions in `app.js` and observe cross-file reference links pointing to `WebGLEngine` methods in `webgl-engine.js` so that the primary validation target is fully satisfied.
13. As a developer, I want `WalkerProtocol.walk_function` to return a `WalkResult` containing both the `PetriNet` and a list of `CallSite` records so that call extraction is strongly typed and independent of string label formatting.
14. As a developer, I want `WalkerProtocol` to define an abstract `collect_variable_bindings` method so that language-specific constructor-assignment extraction lives entirely within the respective walker.
15. As a developer, I want `Transition` to hold an optional `metadata` dictionary so that serialization formats can consume resolution annotations without mutating graph topology or violating bipartite Petri net rules.
16. As a developer, I want inline expansion to be deferred to the interactive HTML viewer phase so that Phase 2 avoids premature complexity around recursive subnet splicing and ID collision handling.

## Implementation Decisions

- **CLI Syntax & Activation**:
  - The primary source file remains the first positional argument.
  - An optional `--context` argument accepts one or more file or directory paths.
  - Supplying `--context` implicitly activates cross-file reference tracing; no explicit `--expand` flag is required in Phase 2.
- **Language Boundary Enforcement**:
  - When `--context` contains directories, files are auto-discovered and mapped by file extension.
  - Cross-file call resolution is strictly scoped to the same language as the primary source file (e.g., `.js` calls only resolve against `.js` context symbols; `.py` calls only resolve against `.py` context symbols).
- **Walker Protocol Updates**:
  - `WalkerProtocol(abc.ABC)` is updated with two signature modifications:
    1. `walk_function(ast_node: Any, func_name: str = "") -> WalkResult`: Returns a container holding both the generated `PetriNet` and extracted `CallSite` records.
    2. `collect_variable_bindings(tree: Any) -> Dict[str, str]`: Scans the complete file AST and returns a mapping of variable names to class names based on constructor instantiations.
- **Data Shapes**:
  - `CallSite` dataclass:
    ```python
    @dataclass
    class CallSite:
        caller_function: str
        caller_file: str
        callee_name: str
        callee_owner: Optional[str]
        line_number: int
        transition_id: str
    ```
  - `WalkResult` named tuple:
    ```python
    class WalkResult(NamedTuple):
        net: PetriNet
        call_sites: List[CallSite]
    ```
  - `Transition` data model:
    `Transition` gains an optional field: `metadata: Optional[Dict[str, Any]] = None`.
- **Constructor-Only Variable Resolution (ADR 0001)**:
  - Walkers implement lightweight AST harvesting for constructor assignments (`const x = new Foo(...)`, `let x = new Foo(...)`, `var x = new Foo(...)` in JavaScript; `x = Foo(...)` in Python).
  - Walkers avoid full static data-flow analysis, reference reassignment tracking, or coupling to code2flow's internal `Variable` model.
- **Symbol Table & Matching Logic**:
  - A dedicated `SymbolTable` module parses context files and indexes all discoverable functions by qualified name and language: `(language, qualified_name) -> (filepath, function_ast_node)`.
  - For each `CallSite`:
    - If `callee_owner` is present, look up `callee_owner` in the caller's variable bindings to find class `C`. Query symbol table for `C.callee_name`.
    - If `callee_owner` is absent, query symbol table for bare `callee_name` in the caller file, then across all context files of the same language.
    - If exactly one symbol matches: assign `metadata={"resolved": True, "resolved_to": target_qualified_name, "target_file": target_filepath}`.
    - If zero or multiple symbols match: assign `metadata={"resolved": False}` and log a debug message.
- **Serialization Formats**:
  - **PNML**: Emits `<toolspecific tool="code2petri" version="1.0">` containing `<resolved target="..." file="..."/>` or `<unresolved/>`.
  - **DOT**: Adds `tooltip` attributes and border styling (`color="#2e7d32"` for resolved, `color="#e65100"` for unresolved).
  - **JSON**: Inlines `resolved`, `resolved_to`, and `target_file` directly into transition dictionary representations.
- **Deferred Inline Expansion**:
  - Inline subnet splicing (`--expand=inline`), recursion depth limiting (`--max-depth`), and subnet ID prefixing are deferred to Phase 2.5 (HTML Viewer with Structural Folding).

## Testing Decisions

- **Good Test Criteria**: Tests must verify observable behavioral outcomes (graph metadata, XML structure, DOT attributes, CLI exits) rather than internal helper dictionaries or intermediate AST states.
- **Walker Unit Seam**:
  - Test `collect_variable_bindings` in Python and JavaScript walkers with top-level and function-level constructor statements.
  - Test `walk_function` to verify `CallSite` records are correctly produced with appropriate line numbers, transition IDs, and callee owner identifiers.
- **Symbol Table Seam**:
  - Test `SymbolTable` population with synthetic multi-file file sets.
  - Test resolution logic: exact match, variable-bound method match, ambiguous callee match, and unresolved third-party call.
- **Integration Seam**:
  - Multi-file CLI tests asserting output with `--context` on test fixture packages.
  - Verify PNML output contains valid `<toolspecific>` XML elements.
  - Verify DOT output contains expected tooltips and colors.
  - Verify JSON output contains resolution keys.
- **Validation Target Seam**:
  - End-to-end integration test analyzing `app.js` with `--context webgl-engine.js` (and directory context `--context ./tests/test_code/game_of_life/`).
  - Assert that calls to `gpuEngine.step()` in `loop`, `gpuEngine.randomize()` in `randomizeBoth` (invoked by `init`), and `this.drawToScreen()` in `WebGLEngine.randomize` resolve precisely to `WebGLEngine.step`, `WebGLEngine.randomize`, and `WebGLEngine.drawToScreen` in `webgl-engine.js`.
  - Assert that calls to `document.getElementById` and `gl.bindTexture` remain cleanly marked as unresolved.

## Out of Scope

- **Inline Subnet Expansion (`--expand=inline`)**: Splicing callee subnets into caller nets is deferred until Phase 2.5.
- **Global Project Analysis**: Generating nets for all functions across all files in a single pass (belongs to Phase 5).
- **Multi-File Output Generation**: Emitting a bundle of individual files for all callees in a single CLI run.
- **Complex Type Inference**: Tracking dynamic reassignments, factory method chains, reflection, or parameter passing across modules.
- **Cross-Language Resolution**: Resolving calls between different programming languages.
- **C# and C++ Walkers**: Implementation of C# (Phase 3) and C++ (Phase 4) walkers.

## Further Notes

- Respects the domain glossary in [`CONTEXT.md`](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/CONTEXT.md) for canonical terms: **Call Site**, **Resolution Context**, **Variable Binding**, **Opaque Transition**, and **Faithful Translation**.
- Conforms to Architectural Decision Record [ADR 0001: Constructor-Only Variable Resolution](file:///Volumes/SharedDrive/Documents/GitHub/code2flow/docs/adr/0001-constructor-only-variable-resolution.md).
