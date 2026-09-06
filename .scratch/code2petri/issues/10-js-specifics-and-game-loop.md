# 10 — JavaScript Specifics & Game-Loop Semantic Translation

**What to build:** Advanced JavaScript support needed to accurately model real-world game code like the `GameOfLife_Simulator`. This introduces support for JS-exclusive control flow syntax, enables the discovery of inline anonymous callbacks, and accurately models the standard `requestAnimationFrame` game loop as a recursive graph cycle rather than an opaque call.

**Blocked by:** 09 — JavaScript Core Control Flow

**Status:** done

- [x] `switch / case / default` is modeled as an XOR-split (similar to `if / elif / else`).
- [x] `do...while` is modeled as a cycle where the condition check occurs after the body execution.
- [x] `throw` statements are modeled identically to Python `raise` exceptions.
- [x] Class methods are discoverable via `--list-functions` and targetable using qualified names (e.g., `WebGLEngine.step`).
- [x] Anonymous callbacks/arrow functions passed as arguments (e.g., to `addEventListener`) are discoverable and targetable via a parenthetical line-number syntax (e.g., `(anonymous@151)`).
- [x] `requestAnimationFrame(loop)` calls where the argument matches the enclosing function name are translated into a back-arc cycle in the Petri net.
- [x] Comprehensive integration tests assert the semantic structural fidelity of the graphs generated from the actual `GameOfLife_Simulator` source files (`app.js` and `webgl-engine.js`).
