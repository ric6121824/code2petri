# 34 — JS Fold Engine: While Loop Reduction

**What to build:** The user can left-click a place node that forms the head of a while loop (a 2-in/2-out place with a self-looping transition). The viewer folds the loop into the entry transition and updates the tau weight with a 2.0x loop multiplier. The place is highlighted in purple beforehand to distinguish it from sequence and choice candidates.

**Blocked by:** 33 — JS Fold Engine: Choice Reduction

**Status:** ready-for-agent

- [ ] Place nodes eligible for while loop reduction are visually coloured purple
- [ ] Left-clicking an eligible loop head place folds the loop into an opaque component at the entry transition
- [ ] The resulting component displays its updated tau weight with 2.0x multiplier applied
- [ ] The JS tau and omega values for a while loop fold match the Python fold engine for the same topology
- [ ] The new component stores enough information to restore the original nodes on demand
