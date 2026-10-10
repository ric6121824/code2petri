# 56: Infer returned locals and simple expressions

**What to build:** Users inspecting Python and JavaScript functions can see the type of a returned local value or supported simple expression, rather than only literal returns. Straightforward assignments yield useful evidence such as x: int in Python or x: number in JavaScript; unresolved values remain explicitly unknown. This evidence survives generated exports and saved sessions.

**Blocked by:** [55 — Inspect JavaScript Function Return Metadata](./55-javascript-function-return-metadata.md).

**Status:** resolved

- [x] Track direct straight-line local assignments, reassignments, and copies from already known local names in source order within each function. Unsupported assigned expressions invalidate the binding instead of preserving its earlier known type.
- [x] A local assigned the integer literal 1 and returned as x produces an inferred function result of int in Python and number in JavaScript, with separately stored returned expression x, inferred type, return-site location, and local-assignment evidence.
- [x] Present available evidence in the existing return view using explicit fields such as Returned expression, Inferred type at this return, and Evidence. A compact x: int (inferred) is optional display shorthand; x remains the original variable name, and the label is never an identity or parsing contract. Where called-function inspection is already available, the same shared presentation displays the new evidence there.
- [x] Names dependent on assignments across branches or loops remain unknown when returned. Do not merge local environments into unions, use constructor Variable Bindings as type evidence, or retain a stale type after an unsupported construct may change the binding.
- [x] Infer Python list, dict, tuple, and set and JavaScript Array and object as outer types only, including empty containers and containers with unknown elements. Preserve richer written annotations/documentation independently; no element or field-shape inference is added. Expressions that cannot be classified safely remain unknown.
- [x] Infer Python f-strings as str and JavaScript template literals as string. Support an explicit static whitelist of numeric unary signs, logical negation, numeric addition/subtraction/multiplication/division, and string addition only for known primitive operands with unambiguous language-specific result rules.
- [x] Unsupported, overloaded, or coercion-dependent operators and calls, parameters, properties, indexing, delegated yields, and other unsupported value expressions remain unknown. Never execute source or infer through another function's return metadata.
- [x] Distinguish unknown as an unavailable/incomplete analysis state from an actual written source type named unknown. Preserve declarations and inference separately and limit the assertion to the returned expression at that source site; do not create a general variable inspector or a permanent variable-type claim.
- [x] The richer observations appear in generated HTML/public net JSON and survive production save/open, fold continuation, and local unfolding without source access or fresh inference. Keep metadata validation, detached capture, and compact restoration behavior intact; graph identities, topology, markings, weights/SM, and viewport remain unchanged.
- [x] Use source-to-viewer/session fixtures in both languages covering known assignment/copy, reassignment to a different known type, reassignment to an unknown value, branch/loop invalidation, supported and unsupported operators, empty/populated containers, interpolation, differing declarations, and expressions containing colons. Assert displayed provenance and separately persisted fields instead of matching or parsing a compact colon string.

Specification: [Phase 2.10 — Function Return Metadata](../specs/phase-2.10-function-return-metadata.md).
