# 58: Separate async call and awaited results

**What to build:** Users can inspect Python and JavaScript async functions and distinguish the immediate coroutine/Promise object from the value obtained by awaiting it. Written and inferred evidence stays attached to the correct role and remains available after saving and reopening a folded session.

**Blocked by:** [57 — Explain incomplete results and normal completion](./57-return-coverage-and-normal-completion.md).

**Status:** resolved

- [x] Detect ordinary async-function kind from its own original syntax, excluding nested functions' yields and treating async generators as a distinct kind reserved for Ticket 59. Syntax is evidence about the source function, without proving dynamic decorators/wrappers preserve its runtime contract.
- [x] Display the immediate Python coroutine or JavaScript Promise wrapper separately from the awaited result. A known wrapper may coexist with an unknown awaited value; do not present a body return's primitive type as the immediate call-result type.
- [x] Python async return annotations describe the awaited value. Preserve JavaScript documented promise types as written and extract role detail only from recognized unambiguous wrapper syntax, without evaluating annotations or expanding custom aliases. Declared/documented and inferred evidence remain separate even when they differ.
- [x] Apply existing bounded expression and completion analysis to the awaited-result role, including local assignments, direct-return unions, known observations with unknown coverage, and implicit results where supported. No normal return from an explicit abnormal-only body applies to the awaited role rather than coroutine/Promise creation.
- [x] Returned-expression evidence refers to that expression at the return site and to its awaited-result role, without asserting a permanent variable type. Expression/type/state/provenance remain separate stored fields. Compact text is display shorthand that identifies inference; never split it on a colon or use it as a renamed variable or function/node identity. The unknown analysis status remains distinct from a written source type named unknown.
- [x] Use the shared root/function presentation for role-specific labels and evidence. Root summaries remain readable; any available called-function sidebar uses the same role-aware presentation rather than requiring separate inference. No canvas badges or additional data-flow/type-checking behavior is introduced.
- [x] Role records, written declarations, observations, source evidence, and function identity survive generation, cloning, public net JSON, self-contained HTML, and production save/open. Missing old metadata remains accepted; malformed recognized role data cannot replace active state. Keep compact capture/history and document reset/playback behavior.
- [x] Verify through Python and JavaScript source generation, actual role displays, and save/open/continue-unfold fixtures with a known wrapper and differing awaited type, unknown awaited value, conflicting declaration/inference, branch-dependent locals, explicit abnormal-only async bodies, and a nested generator that must not reclassify its parent. Graph identities/topology, markings, folds, weights/SM, and viewport remain unchanged.

Specification: [Phase 2.10 — Function Return Metadata](../specs/phase-2.10-function-return-metadata.md).
