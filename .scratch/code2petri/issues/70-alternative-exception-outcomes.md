# 70: Preserve Alternative Exception Outcomes

**What to build:** Let an analyst inspect normal and exceptional completion as alternative control-flow outcomes before and after Inline Expansion. One completion activates only its matching caller continuation, and an uncaught exception remains exceptional after a normally completing finally block.

**Blocked by:** None (can start immediately).

**Status:** resolved

- [x] Within an active try context, a potentially raising operation has competing normal and exceptional outcomes; an explicit raise or throw has only an exceptional outcome.
- [x] Function nets and Inline Expansion preserve distinct normal and exceptional exits, bipartite arcs, and call metadata in the previously verified cases without finally routing.
- [x] Reachable-marking checks cover normal completion, caught and uncaught raises, nested handlers, and inlined callee completions without activating both caller continuations in the previously verified cases.
- [x] Python and JavaScript share the alternative-outcome behavior; exception-type matching and unsupported completion modes are explicitly bounded and documented.
- [x] A fresh Dots & Boxes export routes the inspected called function's normal and exceptional completions to their matching caller continuations, with no completion activating both.
- [x] An uncaught exception executes its finally cleanup and, when cleanup completes normally, reaches the exceptional function exit rather than normal completion or a following ordinary statement.
- [x] After normally completing cleanup, a pending exception reaches an enclosing handler when one is modeled; nested finally blocks preserve that pending outcome and execute cleanup in the correct order.
- [x] Inline Expansion preserves the same exception-through-finally behavior at the caller interface, including a caller that catches the propagated exception. Reachable-marking or execution-trace checks fail before and pass after the repair.
- [x] Normal completion and a handled exception that completes normally retain their normal continuation through finally. An explicit raise in cleanup remains exceptional. Python and JavaScript regressions exercise these outcomes through their production translation paths.
- [x] The representation and evidence distinguish supported normal/exception propagation through finally from still-unsupported completion modes, including return, break, and continue overrides. Broader limitations do not permit a pending uncaught exception to be silently reported as successful completion.

Specification: [Phase 2.8 — Viewer Interactive Enhancements](../specs/phase-2.8-viewer-interactive-enhancements.md). Origin: [Ticket 66](./66-function-scoped-structural-folding.md), [Round 05 inspection](../reviews/phase-2.8-ticket-66-round-05.md). Representation: [ADR 0006](../../../docs/adr/0006-alternative-exception-outcomes.md).

## Comments

### 2026-10-20 — Original implementation and verification

Implemented on 2026-10-20. The shared builder now creates competing normal/exception transitions for operations in an active `try` context, with a shared input place. Explicit `raise`/`throw` transitions have only an exceptional destination. Function nets create an exceptional boundary when needed, and Inline Expansion maps normal and exceptional exits to their corresponding caller continuations while retaining call metadata.

The bounded contract is intentionally explicit: exception matching remains type-agnostic, completion modes through `finally` are not modeled precisely, and ordinary operations outside an active `try` are treated as non-raising unless an explicit raise or an inlined callee supplies an exceptional exit. Unknown external calls outside a `try` context are not inferred to raise.

The original exception-outcome tests cover normal completion, caught and nested raises, uncaught raises, Python/JavaScript builder behavior, and inline normal/exception propagation. The generated Dots & Boxes export has SHA-256 `1a4aee112ebe6b9c0d0e6cee13289e15b5013ff487eef67fb1b1a2b05cc24c14`; its inspected called-function scope routes three explicit raises to the handler entry and its inlined normal return to the normal continuation, with no transition targeting both. Focused results and the final full-suite disposition are recorded in the linked Round 05 report.

- 2026-10-20: The selected representation uses competing transitions with a shared preset and separate function exits. Handler arms remain type-agnostic alternatives; exception-type matching and precise `finally` propagation are not implied.

### 2026-10-20 — Reopened after Round 06

The original implementation was recorded as resolved. The [Round 06 review](../reviews/phase-2.8-ticket-66-round-06.md) then identified a P1 exception-through-finally defect: an explicit uncaught raise followed by normally completing cleanup reaches normal completion and produces no exceptional boundary. An independent source-to-net reachable-marking check reproduced that result at commit `e401ee5e6233782f13db3397df1ab5349ccd4b69`.

Reopened as ready for agent work. The unchecked criteria above define the remaining end-to-end outcome repair; the checked criteria preserve the earlier implementation evidence. Implementation guidance and verification steps sit beneath the findings in Round 06. This is one existing vertical slice from source translation through Inline Expansion to observable completion outcomes; no additional ticket or blocking dependency is introduced.

The generated-viewer browser/session acceptance belongs to Ticket 66 and remains separately pending. Reversing Inline Expansion to restore an opaque call with multiple alternative exits, score-display/accounting questions, and concurrency recognition remain distinct work; they are not prerequisites for correcting this exception-routing defect.

### 2026-10-20 — Finally propagation repair

The shared builder now preserves pending exceptional completion through cleanup by translating the `finally` body on separate normal and exceptional paths. Normally completing cleanup on the exceptional path relays to the enclosing handler or `exception_end`; a cleanup exception overrides the pending outcome. Exceptions in handlers and `else` bodies also run this try statement's cleanup before propagating outward. Cleanup call sites have distinct transition IDs on each path so Inline Expansion can preserve the same alternatives.

The new production-path regressions first failed against `e401ee5`: the uncaught-finally case had no exceptional boundary and a non-final try path fired the following statement. They now pass, together with controls for normal/handled completion, nested cleanup ordering, cleanup raises, JavaScript throw/finally, and a caller that catches the inlined exception. See the [Round 06 implementation follow-up](../reviews/phase-2.8-ticket-66-round-06.md#implementation-follow-up) for the targeted suite and full-suite disposition. Call-level refolding and Ticket 66's browser/session acceptance remain separate.
