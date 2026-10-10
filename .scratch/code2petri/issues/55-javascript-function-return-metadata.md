# 55: Inspect JavaScript Function Return Metadata

**What to build:** Users receive the same basic root-function return inspection and offline save/open behavior for JavaScript, including documented return types, direct literal results, and expression-bodied arrows. Correctly associated JSDoc supplies written evidence without implying that it has been verified against runtime behavior.

**Blocked by:** [54 — Inspect Python Function Return Metadata](./54-python-function-return-metadata.md).

**Status:** resolved

- [x] Collect JSDoc from the original source and associate return/returns tags with the owning function declaration, variable-assigned arrow/function expression, or class method. Nearby unrelated comments, multiple declarations, and nested definitions must not supply another function's documentation.
- [x] Retain documented type expressions, aliases, custom names, and generics as written without evaluation or project-wide expansion. Documented and inferred evidence remain separately labeled, including disagreement, without a type-error verdict.
- [x] Infer ordinary-function primitive-literal returns as number, string, boolean, or null. Explicit bare return and supported simple normal fall-through produce undefined, independently of null and unknown. Unsupported expressions/control flow stay conservative pending the richer analysis tickets.
- [x] Treat an expression-bodied arrow as implicitly returning its original expression before any Synthetic Wrapper conversion. Block arrows and nested callbacks obey their own scope boundaries; nested returns/yields cannot change the enclosing function's evidence or kind.
- [x] Carry function identity and root metadata through generation, cloning, public net JSON, self-contained HTML, the shared root return display, and active document context. Global Scope remains Not applicable. Async/generator syntax must not cause body values to be mislabeled as ordinary immediate results before Tickets 58–59.
- [x] Reuse separate expression, type, analysis-state, provenance, role, and source-location fields. Compact notation remains display text, with an explicit inferred/documented context; do not rename identifiers or parse a colon-delimited string. An expression that contains a colon must remain intact even when its inferred type is unknown.
- [x] The lowercase unknown analysis status is visibly distinct from a written JSDoc type named unknown. Inspection describes the expression value at its return site, without claiming a permanent type for the variable.
- [x] Generated HTML and public net JSON preserve JavaScript records, and Save Session/Open Session restore them offline, including after folding. Opening another document and reset/playback replace context correctly. Old version-1 sessions remain readable; malformed recognized metadata cannot replace the active session.
- [x] Preserve compact canonical history, detached capture, topology, initial markings, existing fold behavior, names, weights/SM, layout, and viewport. Keep parser coverage and the generated offline architecture unchanged; do not add PNML/DOT metadata or TypeScript source support.
- [x] Extend the source-generation/root-panel/save-open behavioral workflow with declarations, assigned expression/block arrows, assigned function expressions, methods, return-tag aliases, wrong-owner comments, nested callbacks, null versus undefined, and an annotation-like unknown type. Exercise expression text containing an object or conditional colon without using display text as serialized structure.

Specification: [Phase 2.10 — Function Return Metadata](../specs/phase-2.10-function-return-metadata.md).
