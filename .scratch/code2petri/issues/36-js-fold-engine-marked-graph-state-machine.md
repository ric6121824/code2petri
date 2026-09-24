# 36 — JS Fold Engine: Marked Graph + State Machine Reductions

**What to build:** The user can trigger macro-component reductions for Marked Graph and State Machine subnets. A Marked Graph fold collapses a SESE subnet where all internal places have exactly one incoming and one outgoing arc. A State Machine fold collapses a SESE subnet where all internal transitions have exactly one incoming and one outgoing arc. Both use the SESE infrastructure from ticket 35.

**Blocked by:** 35 — JS Fold Engine: SESE Infrastructure (Bidirectional Reachability)

**Status:** complete

- [x] Marked Graph subnets are detected and their boundary nodes are visually highlighted to indicate eligibility
- [x] Triggering a Marked Graph reduction collapses the subnet into a single opaque component with the correct tau and omega values
- [x] State Machine subnets are detected and their boundary nodes are visually highlighted
- [x] Triggering a State Machine reduction collapses the subnet into a single opaque component with the correct tau and omega values
- [x] JS tau and omega values match the Python fold engine for the same topologies
- [x] Each resulting component stores enough information to restore the original subnet on demand

## Implementation Notes
- **Priority Gating (Lassen Def. 21)**: Structural SESE folds (Marked Graph & State Machine) are gated behind exhaustion of elementary reductions (`!this.hasElementaryReductions()`). This strictly adheres to Lassen & van der Aalst (2008) Definition 21 (Order of Reductions) to ensure sequences, choices, and loops are fully reduced before broader SESE components are contracted.
- **Token Emptiness Requirement**: Internal places of SESE candidate subnets must have `initial_tokens === 0`. In workflow nets, marked internal places represent active concurrent state; folding over them would violate token conservation.
- **Shared SESE Reduction Mechanics**: Both Marked Graph and State Machine contractions delegate to `_executeSESEReduction(candidate, boundaryConfigFn)`, unifying step indexing, node/edge extraction, compound pruning, and opaque node generation while cleanly isolating boundary arc reconnection semantics.
