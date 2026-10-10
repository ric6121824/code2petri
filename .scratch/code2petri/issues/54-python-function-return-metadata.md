# 54: Inspect Python Function Return Metadata

**What to build:** Users can generate a self-contained viewer for an ordinary Python root function, inspect its written return annotation and directly known literal result separately, save a folded session, and reopen it with the same return information. This first complete slice establishes the optional metadata and shared presentation contract used by subsequent Phase 2.10 tickets; local-expression inference, conditional completion analysis, async/generator roles, and called-function inspection follow separately.

**Blocked by:** None (can start immediately).

**Status:** resolved

- [x] Extract return evidence from the original function AST before Synthetic Wrappers, net wiring, Inline Expansion, or Structural Folding can alter its representation. Nested definitions, classes, lambdas, and callbacks do not contribute evidence to their enclosing function.
- [x] Preserve ordinary Python return annotations as written, including custom names, aliases, and generics, without evaluating them. Display declared and inferred information independently, including when they differ; do not issue a type-error verdict.
- [x] Infer direct primitive-literal returns as bool, int, float, complex, str, bytes, or NoneType. A simple sequential body can distinguish an explicit bare return or supported normal fall-through from unknown evidence. Unsupported expressions/control flow remain unknown rather than retaining an unjustified result; richer coverage analysis is deferred to Ticket 57.
- [x] Global Scope is Not applicable even if its Synthetic Wrapper contains an artificial annotation. Ordinary functions with missing metadata show unknown. Do not present async/generator body values as ordinary immediate call results before their role-specific tickets are implemented.
- [x] Introduce an optional function-owned record distinguished by source file and definition identity, including qualified name/location where needed. Preserve root metadata through public walker/net contracts, cloning, public net JSON, generated HTML, and active document context without changing existing callers unnecessarily.
- [x] Store expression text, inferred type information, analysis state, evidence/provenance, result role, and available source location separately. A compact expression-and-type string is display text only: it is never a function/node ID, a renamed variable, a lookup key, or a format parsed by splitting on a colon.
- [x] The root info panel shows a concise, explicitly inferred or declared summary and available expression evidence. Shared presentation supports distinct expression/type/evidence fields and role labels so later sidebar inspection can reuse it. Source, annotation, and documentation text is rendered as text.
- [x] Explain that an inferred expression type applies at its return statement. The lowercase unknown analysis status means inference is unavailable/incomplete; it remains distinct from a written source type named unknown, NoneType, undefined, No normal return, and Not applicable. A compact unknown display includes explanatory context rather than implying a declared language type.
- [x] Save Session and Open Session retain the root record, evidence, and associations offline without rereading source or rerunning inference. Opening another root, reset, and playback use the active document's context; snapshot capture does not mutate the live session.
- [x] Keep the version-1 Fold State Snapshot container with optional metadata. Accept old valid snapshots without it, and validate recognized new metadata before replacing active state. A malformed record or root association fails through the existing safe-open behavior while preserving the active session.
- [x] Preserve Phase 2.9's compact canonical restoration data and download behavior. No full AST/source-file copies or per-fold registry duplication are introduced. Existing graph identities, topology, markings, fold results, names, weights/SM, configuration, positions, and viewport remain unchanged; PNML/DOT receive no return metadata.
- [x] Verify through actual Python source generation, embedded HTML data, the root panel, public net JSON, and the production save/open/continue-unfold workflow. Include declared-versus-inferred differences, nested-scope exclusion, literal bool versus int, missing metadata, a source type named unknown, display text containing colons, malformed metadata, and active-root replacement. Assert behavior rather than private helpers or incidental markup.

Specification: [Phase 2.10 — Function Return Metadata](../specs/phase-2.10-function-return-metadata.md).

## Comments

- 2026-10-10: Published with to-tickets after the user approved the seven-ticket split, conditional on explicit distinctions between display notation, stored metadata, declaration/inference provenance, return-site scope, and the unknown analysis status.
