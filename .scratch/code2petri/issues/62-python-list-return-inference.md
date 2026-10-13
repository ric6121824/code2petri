# 62: Infer Python list-comprehension and concatenation returns

**What to build:** Users inspecting a Python function such as Tic Tac Toe's create_board see an inferred return type of list when its return expression joins a list literal to a list comprehension. The viewer retains the source expression as separate evidence, and the improved result stays associated with the correct root or called function through generation, supported folding, and offline save/open.

**Blocked by:** None (can start immediately).

**Status:** resolved

- [ ] Recognize synchronous Python list comprehensions as the outer built-in list type, including filtered/nested synchronous clauses and unknown element or iterable types. The claim concerns the result if evaluation completes; it does not establish termination or absence of exceptions. Do not execute source or infer element types, lengths, or evaluated return values.
- [ ] Infer list for addition when both operands are statically known built-in lists from supported evidence. Cover literals, supported comprehensions, chained concatenations, and the existing straight-line assignment/copy flow. The create_board shape—a sentinel list joined to a comprehension producing nine spaces—has complete list inference when it is the only return in a supported ordinary function.
- [ ] Keep unknown or incompatible additions conservative in both operand orders. One known list, a written list annotation, or another function's return contract is insufficient. Unsupported calls, parameters, properties, indexing, custom/subclass operators, other container operations, and unsupported reassignment must not produce a guessed or stale list result. Preserve existing primitive operators and JavaScript inference.
- [ ] Keep comprehension iteration variables scoped to the comprehension. The extension must not create outer local bindings or retain stale evidence if unsupported expression effects can rebind an outer name; conservative invalidation/unknown is acceptable for those effects. Preserve existing incomplete coverage, partial observations, nested-function ownership, and result-role distinctions.
- [ ] Show list as inferred evidence in the existing root return panel and called-function sidebar. Retain the returned expression, return-site location, provenance, and available local-assignment evidence as separate fields; do not call expression text a string return type, infer generic element types, or replace source text with an evaluated value. Written annotations remain independently visible.
- [ ] Preserve the new evidence and exact function associations in generated HTML, public net JSON, cloned/composite nets, and version-1 Fold State Snapshots. Repeated call occurrences, expanded/collapsed compounds, renaming, and Component-Local Unfold retain the same metadata under currently supported folds, without record duplication or source access on open.
- [ ] Existing snapshots remain compatible. A previously saved unknown result is preserved on open without reanalysis of saved expression text; newly generated output contains the improved inference. Metadata validation, detached capture, compact history, and continued folding after restore keep their existing contracts.
- [ ] Verify the complete behavior through the existing source-to-generated-viewer/session workflow using self-contained fixtures. Include the create_board shape, direct list comprehensions, empty/populated/chained list addition, local assignments/copies, unknown contents, filtered/nested clauses, unsupported operands/reassignments, and comprehension scope/effect cases. Assert displayed type/state and separately persisted expression/evidence, then save/open and inspect offline. Use an already-foldable variant for collapse/rename/unfold coverage; fixing Ticket 53 is not required.
- [ ] Keep Call Site resolution, graph identity/topology, tokens, fold eligibility/actions, Transition Weight, Component Penalty, Structuredness Metric, and viewport behavior unchanged. This ticket adds bounded Function Return Metadata inference; it does not alter called-function representation or introduce a new folding operation.

## Context

The reported function's saved metadata already contains the correct return expression. Unknown comes from two independent inference gaps: the list comprehension is not recognized as list, and list addition is outside the previous operator whitelist. Both must be addressed for the user-visible result to improve. The completed Phase 2.10 foundation provides the required inspector and persistence contracts; no separate prefactoring or blocking ticket is needed.

Specification: [Phase 2.10 — Function Return Metadata](../specs/phase-2.10-function-return-metadata.md).

## Comments

### 2026-10-12 — Published

Created as the single Phase 2.10 follow-up requested by the user. The scope is outer list inference from comprehensions and known-list concatenation, with expression evidence and offline inspection preserved. The separate Ticket 53 function-folding work remains independent.

### 2026-10-13 — Implemented

Added bounded inference for synchronous list comprehensions and concatenation of two known built-in lists, including straight-line local copies. Unknown operands and unsupported expression effects remain conservative. Verified the root/called-function metadata and offline snapshot workflow through self-contained fixtures.
