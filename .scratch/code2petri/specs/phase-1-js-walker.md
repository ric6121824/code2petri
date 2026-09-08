## Problem Statement

The `code2petri` tool currently only supports Python. However, the primary validation target for the project is the `GameOfLife_Simulator`, which is written in JavaScript. To analyze the simulator and prove the multi-language architecture of the tool, `code2petri` needs to be able to parse JavaScript files, extract control-flow structures, and faithfully represent them as Petri nets. Additionally, the tool lacks a formalized abstraction layer (Walker Protocol) to smoothly handle multiple languages.

## Solution

Formalize a Walker Protocol as an Abstract Base Class (ABC) to ensure all language parsers adhere to a strict contract. Implement a JavaScript Walker that uses `code2flow`'s Acorn parser to read JavaScript ASTs, including support for global scope code, class methods, and common control structures (`if`, `while`, `for`, `try/catch`, `switch`, `do...while`, `throw`). The walker will faithfully represent all control-flow oddities and capture game-loop patterns (like `requestAnimationFrame`) as Petri net cycles.

## User Stories

1. As a user, I want to pass a `.js` file to `code2petri`, so that I can generate Petri nets from JavaScript code.
2. As a user, I want the CLI to automatically detect JavaScript files by extension and route them to the correct parser, so that I don't have to specify the language manually.
3. As a user, I want to use the `--list-functions` flag on a JavaScript file, so that I can see all discoverable functions, methods, and callbacks.
4. As a user, I want to target top-level global code using `--target-function '(global)'`, so that I can analyze code executed outside of any specific function.
5. As a user, I want to target class methods using qualified names (e.g., `WebGLEngine.step`), so that I can distinguish between methods with the same name in different classes.
6. As a user, I want anonymous arrow functions and callbacks to be discoverable via synthetic names (e.g., `setupEventListeners.(anonymous@151)`), so that I can independently analyze their internal logic.
7. As a user, I want a `requestAnimationFrame(loop)` call to be translated into a back-arc cycle in the Petri net, so that standard game-loop recursion is accurately modeled.
8. As a user, I want `if/else`, `switch/case`, `while`, `do...while`, `for`, `try/catch/finally`, `throw`, `return`, `break`, and `continue` to be fully supported, so that the Petri net accurately reflects all possible control flow paths in JavaScript.
9. As a user, I want the transition labels to reflect the exact source code substring of the condition (e.g., `if (mode === 'gpu')`), so that the Petri net is highly readable.
10. As a developer, I want all language walkers to implement a strict `abc.ABC` Walker Protocol (including `parse_file`, `find_function`, `find_all_functions`, `walk_function`, and `get_node_lineno`), so that any missing methods in future walkers result in immediate runtime errors.
11. As a developer, I want common Petri net construction logic (counters, loop stacks, try stacks) to be encapsulated in a shared builder class (`ControlFlowBuilder`), so that language-specific walkers can compose it and focus purely on AST traversal.
12. As a developer, I want tests to faithfully verify the actual semantic structure of the `GameOfLife_Simulator`, so that I can be confident the tool accurately models real-world game code.

## Implementation Decisions

- **Walker Protocol**: The protocol will be enforced via `abc.ABC` for runtime safety. Walkers will expose instance methods (e.g., `walker.parse_file()`) rather than static methods to allow internal state tracking.
- **Shared Infrastructure**: A shared internal builder class (`ControlFlowBuilder`) will provide the counters, loop stacks, try stacks, and helper methods. Language-specific walkers will utilize this via composition to avoid walker base classes, focusing solely on AST dispatch logic.
- **JS Parser & Settings**: The JS walker will internally handle the requirement for `LanguageParams(source_type="script")` when communicating with `code2flow`'s Acorn parser. `parse_file(filepath)` will remain clean of language-specific arguments.
- **Global Scope**: To maintain a uniform shape for `walk_function`, requests for `(global)` scope will return a synthetic AST wrapper node that encapsulates top-level statements. For language feature parity, this synthetic `(global)` execution scope is proactively supported across both `JavascriptWalker` and `PythonWalker`.
- **Game-Loop Cycles**: For now, game-loop cycle detection is narrowly restricted to `requestAnimationFrame` where the argument matches the enclosing function name. A TODO marker will be left for extending this to `setTimeout` or `setInterval`.
- **JS Constructs**: The JS walker will implement a complete set of control-flow nodes, including `switch/case/default`, `do...while`, and `throw`, even if they aren't present in the primary validation target.
- **Method & Callback Naming**: Class methods will use qualified names (`ClassName.methodName`) across both Python and JS. Anonymous callbacks will be discoverable using parenthetical synthetic names like `ParentFunction.(anonymous@LineNumber)`.
- **Transition Labels**: JavaScript transition labels will be created by slicing the raw source string using Acorn's `start` and `end` byte offsets, rather than attempting to unparse the AST.

## Testing Decisions

- A good test isolates the semantic meaning of the control structure without being brittle to minor implementation details.
- **Unit Seam**: The walker interface will be tested by asserting on the structural integrity of the `PetriNet` objects returned by `walk_function()`.
- **Integration Seam**: The engine/CLI will be tested by verifying it correctly maps file extensions, routes execution to the JS walker, and successfully outputs graphs for the GameOfLife simulator files.
- **Separate Files & Shared Helpers**: Tests will be split into `test_python_walker.py` and `test_javascript_walker.py`. Shared assertions (e.g., `assert_has_start_and_end`) will be extracted into a `tests/petri_assertions.py` helper module.
- **Faithful Validation**: Tests on the `GameOfLife_Simulator` will be highly detailed. They will semantically verify exact structures like the `requestAnimationFrame` cycle in `loop`, the XOR-splits in `stepCpu`, and the initialization calls in `(global)`. We will not normalize or "fix" bad code structures; the graphs must reflect the exact flow present in the source files, warts and all.

## Out of Scope

- Cross-file reference tracing (resolving a function call in `app.js` to its definition in `webgl-engine.js`). This belongs to Phase 2.
- Expansion of function calls into inline subnetworks. Calls are currently treated as opaque transitions.
- C# and C++ language walkers.
- HTML viewer and visual folding capabilities.
- Support for complex ES modules (`source_type="module"`) that fail standard script parsing. Auto-detection is planned, but full module resolution is out of scope for Phase 1.

## Further Notes

- It's critical that the Python walker's class method naming is updated to be qualified (e.g., `Class.method`) to keep parity with the new JS walker behavior.
- The `code2flow` Acorn script (`get_ast.js`) is used natively by this project; ensure the dependency on the `acorn` npm package is documented or handled.
