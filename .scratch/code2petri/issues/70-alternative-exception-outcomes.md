# 70: Preserve Alternative Exception Outcomes

**What to build:** Preserve the distinction between normal completion and exceptional completion in control-flow nets and across Inline Expansion, so one operation or callee completion cannot activate both caller continuations.

**Blocked by:** None.

**Status:** resolved

- [x] Within an active `try` context, model a potentially raising operation as normal and exceptional alternatives that share its input place; explicit `raise`/`throw` has only an exceptional outcome.
- [x] Give function nets separate normal and exceptional exits, and inline each exit into its matching caller continuation while preserving bipartite arcs and call metadata.
- [x] Cover normal return, caught raise, uncaught raise, nested handler routing, and inlined callee completions with reachable markings; assert that one completion cannot activate both continuations.
- [x] Inspect both Python and JavaScript walkers because they share the builder. Keep exception-type matching and completion modes through `finally` explicitly bounded and documented.
- [x] Export a fresh Dots & Boxes graph and verify `_edge_for_move()`'s normal and exception continuations remain alternatives after inlining.

Specification: [Phase 2.8 — Viewer Interactive Enhancements](../specs/phase-2.8-viewer-interactive-enhancements.md). Origin: [Ticket 66](./66-function-scoped-structural-folding.md), [Round 05 inspection](../reviews/phase-2.8-ticket-66-round-05.md). Representation: [ADR 0006](../../../docs/adr/0006-alternative-exception-outcomes.md).

## Answer

Implemented on 2026-10-20. The shared builder now creates competing normal/exception transitions for operations in an active `try` context, with a shared input place. Explicit `raise`/`throw` transitions have only an exceptional destination. Function nets create an exceptional boundary when needed, and Inline Expansion maps normal and exceptional exits to their corresponding caller continuations while retaining call metadata.

The bounded contract is intentionally explicit: exception matching remains type-agnostic, completion modes through `finally` are not modeled precisely, and ordinary operations outside an active `try` are treated as non-raising unless an explicit raise or an inlined callee supplies an exceptional exit. Unknown external calls outside a `try` context are not inferred to raise.

`tests.test_exception_outcome_routing` covers normal completion, caught and nested raises, uncaught raises, Python/JavaScript builder behavior, and inline normal/exception propagation. The generated Dots & Boxes export has SHA-256 `1a4aee112ebe6b9c0d0e6cee13289e15b5013ff487eef67fb1b1a2b05cc24c14`; its `_edge_for_move()` scope routes three explicit raises to `except_entry` and its inlined normal return to `try_exit`, with no transition targeting both. Focused results and the final full-suite disposition are recorded in the linked Round 05 report.

## Comments

- 2026-10-20: The selected representation uses competing transitions with a shared preset and separate function exits. Handler arms remain type-agnostic alternatives; exception-type matching and precise `finally` propagation are not implied.
