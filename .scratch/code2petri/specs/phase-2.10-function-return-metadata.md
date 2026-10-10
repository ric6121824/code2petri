# Phase 2.10: Function Return Metadata

Status: needs-info

This document records the ongoing grill-with-docs design discussion. It is not yet a ready-for-agent implementation specification.

## Confirmed Scope

- Show each function's return contract as information in the viewer. Return metadata does not change Petri net execution semantics, Structural Folding, or Structuredness Metric.
- Support both currently implemented source languages: Python and JavaScript.
- Extract declarations/documentation and perform bounded inference within the function. Use Unknown when evidence is incomplete; project-wide inference is outside this phase.
- Display return metadata in the root-function info panel and the selected-function sidebar. Canvas return-type badges are outside the initial scope.
- Describe what calling the function returns, and separately describe awaited or yielded values when known for async functions and generators.
- Use the domain term [Function Return Metadata](../../../GLOSSARY.md).
- Keep the separately reported called-function boundary-folding defect in [Phase 2.8 Ticket 53](../issues/53-called-function-fold-boundary-trigger.md); it is not a prerequisite for extracting return metadata.

## Current Codebase Facts

- Python function discovery retains return annotations in the AST, but the walker does not extract them into the net or viewer.
- JavaScript parsing retains source text and AST function nodes but does not currently collect JSDoc comments. Declared/documented JavaScript return information needs explicit collection and association with the correct function.
- There is no common function-return metadata record. Root document identity, call-site resolution, and compound identity travel through different paths.
- Compound boundaries may belong to the caller after Inline Expansion; function metadata cannot rely exclusively on a callee entrance or exit place remaining visible.
- Snapshot element data can preserve ordinary metadata, but root document capture/restoration selects fields explicitly. Root return metadata therefore needs an intentional Save/Open path.
- Neither walker has a reusable expression-type or ordered local-assignment analysis. Existing Variable Bindings resolve constructor-owned calls across the file; they are not return-type evidence for a function-local analyzer.
- The original function AST is the appropriate extraction source. Nested definitions must not contribute their returns/yields to their enclosing function, and expression-bodied JavaScript arrows must be treated as implicit returns.
- Generated net topology cannot prove normal-return coverage: [standard loop wiring](../../../code2petri/control_flow_builder.py) creates an exit regardless of a literal condition, and returns route through active finally blocks. Unsupported control-flow cases require conservative evidence handling rather than interpreting graph reachability as a type proof.
- Python async return annotations describe the awaited result, while generator annotations can separately describe yielded and completion values. Preserve annotation text without evaluation; source declarations and syntax-derived kinds do not prove a dynamically decorated callable's runtime contract. See [Python generator/coroutine annotations](https://docs.python.org/3/library/typing.html#annotating-generators-and-coroutines).
- JavaScript JSDoc collection must associate comments with the owning declaration, including variable-assigned arrows and methods. Existing function-node start offsets alone are insufficient; `@returns`/`@return` and `@yields`/`@yield` are separate evidence. See [Acorn comment collection](https://github.com/acornjs/acorn/blob/master/acorn/README.md), [JSDoc returns](https://jsdoc.app/tags-returns), and [JSDoc yields](https://jsdoc.app/tags-yields).
- Browser PNML export currently writes weights and opaque-node properties; carrying return metadata in that format would be additional scope. Existing parser limitations, such as BigInt AST transport, are not implicitly expanded by this phase.

## Open Design Decisions

1. The exact bounded-inference boundary: literals/simple expressions versus tracking local assignments, and treatment of unresolved variables/calls.
2. Multiple return paths, implicit fall-through, exceptions/non-returning paths, and presentation of known evidence alongside Unknown.
3. Conflicting declared/inferred evidence and provenance; the feature's boundary with type checking.
4. Generator completion values in addition to call-result and yielded-value information; combined async/generator cases.
5. Function identity and ownership across unresolved/resolved calls, compounds, arbitrary folded components, expansion, and Component-Local Unfold.
6. Metadata persistence, older snapshots, export formats, and supported unknown/not-applicable states.
7. Acceptance fixtures, final shared-understanding confirmation, and implementation tickets after the design is confirmed.

## Existing Constraints

Respect the existing lightweight analysis boundary in [ADR 0001](../../../docs/adr/0001-constructor-only-variable-resolution.md), [boundary place unification](../../../docs/adr/0002-boundary-place-unification.md), the [structural reduction semantics](../../../docs/adr/0003-adopt-prom-local-reduction-algorithm.md), and the [docked inspector](../../../docs/adr/0004-docked-sidebar-instead-of-floating-popover.md). Broader inference would require an explicit scope decision rather than silently extending constructor-only variable resolution.

## Discussion Record

### 2026-10-10 — Round 1

The user selected return-contract inspection as the goal (rather than data-flow tracing or type-error detection) and confirmed Python and JavaScript coverage. Extraction/inference scope and presentation remain open.

### 2026-10-10 — Round 2

The user selected Q3 B, Q4 A, and Q5 A:

- Declarations/documentation plus simple within-function inference, with Unknown when evidence is incomplete.
- Root-function info panel and selected-function sidebar, without initial canvas badges.
- Call-result information with separate awaited/yielded information when known.

The next frontier concerns the precise inference boundary, incomplete or conflicting evidence, generator completion values, which selected function representations expose metadata, and export/persistence scope. No runtime implementation is authorized by this ongoing design interview.

### 2026-10-10 — Round 3 frontier (awaiting answers)

These are proposals, not confirmed decisions:

| Question | Decision | Recommendation |
| --- | --- | --- |
| Q6 | Infer only direct literals/simple expressions, also straightforward local assignments, or branch-dependent local bindings? | Also straightforward local assignments; unresolved expressions/reassignments and ambiguous branches degrade to Unknown without extending cross-file call resolution. |
| Q7 | When the overall inferred result is Unknown, also show known observed types or show Unknown alone? | Show Unknown plus observed types, explicitly distinguished from a complete result. |
| Q8 | When declarations and body evidence differ, show them separately or use declarations alone whenever present? | Show separate declared/documented and inferred evidence; no type-error verdict or runtime guarantee. |
| Q9 | For generators, expose only call result/yielded values, or also a separate completion value when known? | Include completion separately, without treating yielded items as the function's final return value. |
| Q10 | Show metadata only for root/functions compounds, also on resolved call transitions, or on arbitrary folded components listing represented functions? | Root, function compounds including collapsed compounds, and unambiguously resolved call transitions. |
| Q11 | Preserve metadata in generated HTML, net JSON, and Fold State Snapshots, or additionally extend PNML/DOT exports? | HTML/net JSON/snapshots initially; reopening older snapshots without metadata must remain valid and display Unknown or Not applicable as appropriate. |

After these answers, define the exact supported-expression/control-flow list, language-specific display examples, identity/persistence acceptance fixtures, and any remaining decisions before requesting final shared-understanding confirmation.
