# Alternative Exception Outcomes in Control-Flow Nets

Date: 2026-10-20

## Status

Accepted

## Context

The shared control-flow builder previously added an exception-handler output arc directly to every transition created inside a `try` block. A normal transition therefore produced tokens both on its normal continuation and on its exception continuation. During Inline Expansion, a callee's single shared sink was also connected to every postset of the call transition, so a callee completion could activate both the normal and exception continuations.

This violates ordinary Petri-net firing semantics for source-level alternatives. In the supplied Dots & Boxes graph, `_edge_for_move()` has both a normal caller continuation and an exception-handler continuation. The problem affects the builder before inlining as well as the inliner boundary representation.

## Decision

- A potentially raising operation inside an active `try` context is represented by a normal transition and an exceptional alternative transition. Both consume the same preset place, so one firing consumes the input token along exactly one outcome path.
- An exceptional alternative inside a `try` context routes to the active handler entry. Explicit `raise`/`throw` transitions route only to the active handler or, when uncaught, the function's exceptional exit; they have no normal alternative.
- Function nets retain separate normal (`end`) and exceptional (`exception_end`) boundary places.
- Inline Expansion fuses the callee's normal exit into the call's normal continuation and its exceptional exit into the call's exceptional continuation. It removes the paired opaque-call exception alternative only when the callee supplies an explicit exceptional exit.
- Handler arms remain nondeterministic alternatives at a shared exception-entry place. The model does not infer Python exception classes, JavaScript thrown-value types, or handler matching; any modeled handler arm may be selected. This is an over-approximation, not a claim that every handler matches every exception.
- Outside an active modeled handler, ordinary operations are treated as non-raising. Explicit `raise`/`throw` and exceptional exits from inlined callees still propagate to the exceptional boundary. The model does not infer exceptions from unknown external calls outside a `try` context.

## Consequences

- A single modeled completion cannot produce tokens on both normal and exceptional paths.
- Inlined callees preserve the normal/exception distinction across boundary-place unification and remain bipartite.
- Additional transitions and an exceptional exit place change generated net size and can affect structural metrics. These are explicit control-flow nodes, not synthetic plumbing introduced only by inlining.
- Precise matching, exception propagation through `finally`, and return/break/continue completion modes through `finally` remain outside this bounded representation and must be treated conservatively.

See also [ADR 0002 — Boundary Place Unification](./0002-boundary-place-unification.md) and [Ticket 70 — Alternative Exception Outcomes](../../.scratch/code2petri/issues/70-alternative-exception-outcomes.md).
