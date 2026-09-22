# 33 — JS Fold Engine: Choice Reduction

**What to build:** The user can left-click a place node that fans out into parallel transitions (a branching point). The viewer fuses those parallel transitions into a single opaque component, retaining the split and join places, and updates the tau weight with a 1.5x choice multiplier. The place is highlighted in amber beforehand to distinguish it from a sequence candidate. (Prototype confirmed: "Idea B" whole-node fusion style.)

**Blocked by:** 32 — JS Fold Engine: Sequence (Single-Place Contraction)

**Status:** ready-for-agent

- [ ] Place nodes eligible for Choice reduction are visually coloured amber
- [ ] Left-clicking an eligible place fuses its parallel outgoing transitions into a single opaque component
- [ ] The split and join places remain on the canvas after the fold
- [ ] The resulting component displays its updated tau weight with 1.5x multiplier applied
- [ ] The JS tau and omega values for a choice fold match the Python fold engine for the same topology
- [ ] The new component stores enough information to restore the original transitions on demand
