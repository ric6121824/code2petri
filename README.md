# code2petri

> **Attribution & Lineage:** `code2petri` is a mathematical Petri net modeling tool heavily modified and evolved from the [code2flow](https://github.com/scottrogowski/code2flow) project created by Scott Rogowski. While `code2flow` generates visual flowcharts, `code2petri` structurally transforms that foundation to output formal, executable Petri nets for advanced control-flow analysis and game loop modeling.

`code2petri` statically analyzes source code (currently **Python** and **JavaScript**) and translates its exact control flow into **Petri nets**. 

Unlike standard call graphs or basic flowcharts, Petri nets mathematically model execution states (places), operations (transitions), and control flow (arcs). This allows `code2petri` to faithfully translate complex logical structures like `try/catch/finally` boundaries, `switch` fallthroughs, and recursive game loops (`requestAnimationFrame`).

## Features

- **Formal Petri Net Translation**: Maps sequential statements, XOR-splits (`if/else`, `switch`), and cycles (`while`, `for`, `do..while`) into rigorous Petri net structures.
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

You can target a specific function, a class method, or the global script scope of a file.

```bash
# Analyze a global execution script
code2petri app.js --target-function="(global)" -o global_net.svg

# Analyze a specific function in Python
code2petri main.py --target-function="calculate_path" -o path.dot

# Analyze a class method in JavaScript (e.g., a Game Engine step)
code2petri webgl-engine.js --target-function="WebGLEngine.step" -o engine_step.png
```

## Domain Model & Architecture

`code2petri` is built on a strict, decoupled abstraction layer:
- **Walker Protocol (`WalkerProtocol`)**: An `abc.ABC` interface that all language-specific AST parsers must implement.
- **Control Flow Builder (`ControlFlowBuilder`)**: A composed graph-building layer that manages places, transitions, and context stacks (`try_stack`, `loop_stack`), ensuring architecture consistency across languages.
- **Faithful Translation**: The engine models the exact control flow present in the source AST, including dead ends and infinite loops, without attempting to sanitize or fix broken logic.

## Roadmap & Grand Plan

The project is actively being developed to analyze large-scale game engine codebases. 
- **Phase 1 (Completed)**: Core infrastructure, Python & JavaScript AST walkers, `WalkerProtocol`, game-loop recursive detection.
- **Phase 2 (In Progress)**: Cross-File Reference Tracing (expanding function calls into composite nets across multiple files).
- **Phase 2.5 (Planned)**: Interactive HTML Viewer with Lassen & van der Aalst structural folding and Strictness Measure (SM) scoring.
- **Phase 3 & 4 (Planned)**: **C# / Unity** and **C++ / Unreal Engine** support, mapping engine lifecycles (`Update`, `Tick`, `BeginPlay`) into implicit overarching Petri nets.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. (Inherited from the original `code2flow` project).
