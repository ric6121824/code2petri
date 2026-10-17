# code2petri

> **Attribution & Lineage:** `code2petri` is a mathematical Petri net modeling tool heavily modified and evolved from the [code2flow](https://github.com/scottrogowski/code2flow) project created by Scott Rogowski. While `code2flow` generates visual call graphs, `code2petri` structurally transforms that foundation to output formal, executable Petri nets for advanced control-flow analysis and game loop modeling.

`code2petri` statically analyzes source code (currently **Python** and **JavaScript**) and translates its exact control flow into **Petri nets**. 

Unlike standard call graphs, Petri nets mathematically model execution states (places), operations (transitions), and control flow (arcs). This allows `code2petri` to faithfully translate complex logical structures like `try/catch/finally` boundaries, `switch` fallthroughs, and recursive game loops (`requestAnimationFrame`).

## Features

- **Formal Petri Net Translation**: Maps sequential statements, XOR-splits (`if/else`, `switch`), and cycles (`while`, `for`, `do..while`) into rigorous Petri net structures.
- **Cross-File Reference Tracing**: Ingests context files and directories via `--context`, indexing function definitions across files to resolve calls and method invocations (via constructor variable bindings) with rich annotations in PNML, DOT, and JSON.
- **Game-Loop Detection**: Automatically detects recursive animation/game loops (e.g., `requestAnimationFrame`) and wires them as mathematical cycles back to the function start place.
- **Synthetic Global Scope**: Analyzes not just functions and methods, but top-level script execution using a synthetic `(global)` target.
- **Multiple Output Formats**: Generates standardized XML `PNML` (ISO/IEC 15909 compliant), Graphviz `.dot`, `.svg`, `.png`, and structured `.json`.
- **High-Fidelity Labels**: Retains exact byte-sliced source code text for transition labels instead of lossy AST unparsing.

## Installation

```bash
# Clone the repository
git clone https://github.com/ric6121824/code2petri.git
cd code2petri

# Install dependencies (requires Python 3.7+)
pip install -r requirements.txt
```

## Basic Usage

You can target a specific function, a class method, or the global scope of a file, optionally supplying context files or directories for cross-file call resolution.

```bash
# Analyze a global execution script
code2petri app.js --target-function="(global)" -o global_net.svg

# Analyze a specific function in Python
code2petri main.py --target-function="calculate_path" -o path.dot

# Analyze a class method in JavaScript (e.g., a Game Engine step)
code2petri webgl-engine.js --target-function="WebGLEngine.step" -o engine_step.png

# Analyze a function with cross-file context resolution (e.g., Game of Life loop referencing WebGLEngine)
code2petri app.js --target-function="loop" --context webgl-engine.js -o loop.dot
```

## Domain Model & Architecture

`code2petri` is built on a strict, decoupled abstraction layer:
- **Walker Protocol (`WalkerProtocol`)**: An `abc.ABC` interface that all language-specific AST parsers must implement, returning `WalkResult(net, call_sites)`.
- **Control Flow Builder (`ControlFlowBuilder`)**: A composed graph-building layer that manages places, transitions, and context stacks (`try_stack`, `loop_stack`), ensuring architecture consistency across languages.
- **Symbol Table & Call Resolution (`SymbolTable`)**: Indexes functions across context files and resolves method calls using constructor-only variable bindings ([ADR 0001](docs/adr/0001-constructor-only-variable-resolution.md)).
- **Faithful Translation**: The engine models the exact control flow present in the source AST, including dead ends and infinite loops, without attempting to sanitize or fix broken logic.

## Roadmap & Grand Plan

The project is actively being developed to analyze large-scale game engine codebases. 
- **Phase 1 (Completed)**: Core infrastructure, Python & JavaScript AST walkers, `WalkerProtocol`, game-loop recursive detection.
- **Phase 2 (Completed)**: Cross-File Reference Tracing (resolving function and method calls across multiple files with constructor variable bindings, symbol indexing, and PNML/DOT/JSON serialization).
- **Phase 2.5 (Completed)**: Structural Component Folding & Structuredness Metric (SM) computation per Lassen & van der Aalst (2008), inline expansion engine (`inline.py`), and standalone Cytoscape.js HTML viewer.
- **Phase 2.6 (Completed)**: ProM reduction algorithm port (Single-Place Contraction, Atomic Choice Collapse, SESE reachability), nested call resolution, interactive client-side compound subnet expansion, and canvas viewport controls (middle/right drag pan, scroll wheel zoom, node dragging).
- **Phase 2.7 (Implemented)**: Live Fold Reduction, component-local unfold, component renaming, client-side PNML export, boot-to-composite startup, viewport preservation, extended zoom-out, and repeating green/blue/purple expanded-compound colors by nesting depth.
- **Phase 2.8 (Implemented)**: Docked inspector with a near-top hide/recall edge tab, Batch Place Fold, function-scoped elementary and validated structural folding, versioned session snapshot save/open, and Project/File/Function identity in the info panel.
- **Phase 2.9 (Implemented)**: Compact, lossless nested restoration records, legacy snapshot compatibility, and independent bounded Save Session download lifetimes.
- **Phase 2.10 (Implemented)**: Python/JavaScript Function Return Metadata, bounded list-expression inference, and separate per-call results for ten Python built-ins with supported import aliases and specific Unknown reasons.
- **Phase 2.8.1 (Implemented; browser acceptance remains open)**: [Viewer Search and Action History](.scratch/code2petri/specs/phase-2.8.1-viewer-search-and-action-history.md), including nested hidden-node search, explicit Reveal, and session-only Undo/Redo. The user confirmed Undo/Redo in the browser; remaining viewer checks stay documented in the original tickets.
- **Verification still recorded separately**: Browser download/rendering and generated-viewer session acceptance gaps remain documented in the [grand plan](.scratch/code2petri/grand_plan.md). Implementation completion does not mark those checks passed.
- **Planned language work — Phase 3**: **C# / Unity** support, including Unity lifecycle modeling. Phase 4 (**C++ / Unreal Engine**) remains planned.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. (Inherited from the original `code2flow` project).
