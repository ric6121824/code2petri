# 09 — JavaScript Core Control Flow

**What to build:** Feature parity between the JavaScript walker and the Python walker for core branching and looping constructs. The walker can now accurately model JavaScript `if/else`, loops, and exception handling, representing them as XOR-splits, cycles, and exception-arcs in the generated Petri nets.

**Blocked by:** 08 — JavaScript Walker Skeleton & Basic Statements

**Status:** resolved

- [x] `if / else if / else` statements are modeled as XOR-splits and merges.
- [x] `while` and `for` (including `for...in` and `for...of`) loops are modeled as cycles.
- [x] `break` and `continue` statements correctly jump to the enclosing loop's exit or head places.
- [x] `try / catch / finally` statements are modeled with exception-arcs and standard try-exit logic.
- [x] Tests in `test_javascript_walker.py` verify all supported constructs against targeted JS fixtures using shared assertions.

## Comments

- 2026-10-16: Corrected the stale ready-for-agent state to match this ticket's already completed checklist and the delivered Phase 1 record. Ticket 08 is resolved, so its prerequisite is satisfied. No tests were rerun for this documentation update.
