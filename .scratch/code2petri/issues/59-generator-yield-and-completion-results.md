# 59: Separate generator objects, yields, and completion

**What to build:** Users inspecting Python and JavaScript generators see the generator object, yielded-item types, and final completion-value types as separate information. Async-generator roles follow their language's rules, and all available evidence remains inspectable after saving and reopening.

**Blocked by:** [57 — Explain incomplete results and normal completion](./57-return-coverage-and-normal-completion.md).

**Status:** resolved

- [x] Determine generator/async-generator kind from the original function's own syntax, excluding yields inside nested functions, classes, lambdas, or callbacks. Do not classify the enclosing function from another function's body or from annotation text alone.
- [x] Separate the immediate generator object, yielded items, and final completion values. Body returns contribute completion evidence; yields contribute item evidence. A known outer object does not require knowing either contained role, and yielded and completion types must never be combined into a single result.
- [x] Use the existing bounded expression/binding rules for direct yield/return observations and the supported completion summary for final returns. Incomplete relevant evidence remains unknown with separately labeled known observations, without branch-environment merging or inference through delegated yields/unresolved calls.
- [x] Preserve Python written generator/iterator annotations and JavaScript yield/yields and return/returns documentation independently of inference. Associate tags with the correct original declaration, assigned function, or method. Map role detail only where recognized syntax establishes it; otherwise retain the raw declaration rather than inventing contained types.
- [x] For async generators, separate the immediate async-generator object and yielded values. Expose completion-value types where supported by the language; Python async-generator completion-value information is Not applicable. Do not treat an async-generator object as an ordinary coroutine/Promise result.
- [x] No normal return proven for a generator body concerns its completion behavior rather than creating the generator object. Keep per-role known/unknown states, No normal return, Not applicable, actual NoneType/undefined values, and a written source type named unknown distinct.
- [x] Shared root/function presentation clearly labels each applicable role and its declaration/inference/evidence. Compact expression-and-type notation is display text with provenance and return/yield-site meaning, without asserting a permanent variable type. Separately stored expression/type/state/evidence fields and function identities remain authoritative; never split the label on a colon or use it to rename or identify a variable, node, or function. Ticket 58 is not a prerequisite for this slice.
- [x] Preserve role metadata, declarations, observations, locations, and associations in generated HTML/public net JSON and production save/open without source access. Retain old-snapshot compatibility, safe validation, detached compact capture, active-document context, and existing folds/unfolding behavior.
- [x] Exercise the actual generation/inspection/save-open workflow in both languages with differing yielded and completion types, independently unknown roles, normal/bare completion where applicable, supported abnormal-only completion, delegated yields, async generators, source annotations/documentation, tag ownership, and nested generators. Assert unchanged topology/markings, fold results, weights/SM, and viewport.

Specification: [Phase 2.10 — Function Return Metadata](../specs/phase-2.10-function-return-metadata.md).
