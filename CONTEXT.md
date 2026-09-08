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
