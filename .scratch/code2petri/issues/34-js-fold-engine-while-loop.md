# 34 — JS Fold Engine: While Loop Reduction

**What to build:**
Client-side implementation of while loop reduction. Left-clicking a loop place matching the 2-in/2-out self-loop pattern folds it into the loop's entry transition.

**Blocked by:** 33 — JS Fold Engine: Choice Reduction

**Status:** ready-for-agent

- [ ] Place nodes qualifying for while loop reduction are visually styled (purple affordance)
- [ ] Left-clicking an eligible place folds the loop transition into the entry transition
- [ ] Loop penalty with 2.0x multiplier and updated tau weight are calculated accurately
- [ ] Consumed nodes and edges are stored in the resulting component for local undo
