# 36 — JS Fold Engine: Marked Graph + State Machine Reductions

**What to build:** The user can trigger macro-component reductions for Marked Graph and State Machine subnets. A Marked Graph fold collapses a SESE subnet where all internal places have exactly one incoming and one outgoing arc. A State Machine fold collapses a SESE subnet where all internal transitions have exactly one incoming and one outgoing arc. Both use the SESE infrastructure from ticket 35.

**Blocked by:** 35 — JS Fold Engine: SESE Infrastructure (Bidirectional Reachability)

**Status:** ready-for-agent

- [ ] Marked Graph subnets are detected and their boundary nodes are visually highlighted to indicate eligibility
- [ ] Triggering a Marked Graph reduction collapses the subnet into a single opaque component with the correct tau and omega values
- [ ] State Machine subnets are detected and their boundary nodes are visually highlighted
- [ ] Triggering a State Machine reduction collapses the subnet into a single opaque component with the correct tau and omega values
- [ ] JS tau and omega values match the Python fold engine for the same topologies
- [ ] Each resulting component stores enough information to restore the original subnet on demand
