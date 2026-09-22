# 32 — JS Fold Engine: Sequence (Single-Place Contraction)

**What to build:** The user can left-click any intermediate place node that connects two transitions in a linear sequence. The viewer immediately removes the place and merges the two adjacent transitions into a single opaque component, updating the displayed tau weight in real time. The place is visually highlighted in green beforehand to indicate it is foldable.

**Blocked by:** 31 — Viewer: Input Remapping

**Status:** ready-for-agent

- [ ] Place nodes eligible for Single-Place Contraction are visually coloured green
- [ ] Left-clicking an eligible place contracts it and replaces the two adjacent transitions with a single opaque component
- [ ] The resulting component displays its updated tau weight
- [ ] The new component stores enough information to restore the original nodes on demand (for local unfold)
- [ ] The JS tau and omega values for a sequence contraction match the output of the Python fold engine for the same topology
