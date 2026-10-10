# 57: Explain incomplete results and normal completion

**What to build:** Users can distinguish a complete supported normal-result summary from partial evidence, a legitimate implicit result, and a function that clearly has No normal return. Known observations remain useful beside an overall unknown result without implying complete coverage or merging branch-dependent variable types.

**Blocked by:** [56 — Infer returned locals and simple expressions](./56-infer-returned-locals-and-expressions.md).

**Status:** resolved

- [x] Use a bounded source summary of sequential blocks and supported if/else paths in both languages. Multiple direct known return expressions form a deterministic, deduplicated union only when relevant normal-completion coverage is accounted for. Do not derive coverage from generated-net reachability or transition labels.
- [x] An unknown return expression or incomplete relevant coverage makes overall inference unknown. Display known observed types separately and explicitly as partial observations, retaining their expression evidence and available source locations. Never label that list as the complete inferred result.
- [x] Branch/loop-dependent local expressions remain x: unknown even when different branch assignments individually have known types. Direct literal return paths may form a complete union; that does not authorize local-environment merging.
- [x] Bare return contributes NoneType in Python and undefined in JavaScript. Supported possible normal fall-through, including an omitted else, contributes the corresponding implicit result; unsupported control flow does not automatically imply one.
- [x] No normal return appears only when the supported summary shows every completion path ending in explicit raise/throw with no normal return/fall-through. Abnormal paths are not inserted into a union as a data type, and a written Never/NoReturn-like annotation remains separate declared evidence rather than an inference proof.
- [x] Unsupported loops, try/finally, decorators/wrappers, delegated constructs, and ambiguous paths remain conservative. Do not add general termination/path-feasibility analysis or report unsupported cases as complete or proven non-returning. Returns after a supported terminating statement do not add normal results.
- [x] Nested functions, classes, lambdas, callbacks, and their returns/yields cannot alter the enclosing function's summary or kind. Preserve the original source-scope and local-binding boundaries.
- [x] Shared return presentation keeps declared/documented evidence, inferred result/state, partial observations, and expression-site evidence separate. Compact unknown text explains inference unavailability; it remains distinct from a written type named unknown, actual NoneType/undefined, No normal return, and Not applicable.
- [x] Store expression text, type information, analysis state, provenance/evidence, and source location as separate fields. The inferred expression type applies at its return site rather than permanently to the variable. Compact notation is display text only; never split it on a colon or use it to rename or identify a variable, node, or function.
- [x] All states, observations, and provenance survive generated HTML/public net JSON and production save/open without source access. Opening another session and reset/playback use that document's summary. Preserve compact metadata, topology, markings, existing folding, weights/SM, names, and viewport.
- [x] Extend the source-to-viewer/save-open behavioral matrix with complete direct-return unions, known plus unknown results, omitted else/fall-through, bare returns, known normal returns mixed with raises/throws, clearly abnormal-only bodies, branch-dependent locals, nested scope, unreachable returns, and unsupported loop/try-finally cases. Verify both displayed completeness and restored evidence without testing private traversal details.

Specification: [Phase 2.10 — Function Return Metadata](../specs/phase-2.10-function-return-metadata.md).
