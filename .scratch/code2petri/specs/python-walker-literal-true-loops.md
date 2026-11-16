# Python walker foundation follow-up — Preserve literal-true loop control flow

**Status:** ready-for-agent

**Approved:** 2026-11-16

## Problem Statement

In the Pong export, the graph for the `while True` at line 136 lets control enter the loop body, exit normally at the loop head, or jump from the loop head to the handler at line 177. Evaluating the literal `True` always enters the body. The other two alternatives misrepresent the program and can make a nonterminating path appear to finish even when the body never exits.

## Solution

Translate a Python `while True` loop with a single body-entry path at its head. Keep the back edge for another iteration and keep the actual ways to leave from inside the loop. In Pong, a call in the body such as `win.update()` can still lead to the handler.

## User Stories

1. As a Pong analyst, I want the loop head to enter the body every time, so that the diagram accurately shows the game loop.
2. As a viewer user, I want an exception from a call in the loop body to reach the existing handler, so that I can trace how the game ends after a failure.
3. As a viewer user, I want a loop with only iteration paths to remain a cycle, so that the graph never suggests spontaneous completion.
4. As a Python developer, I want a `break` to reach the code after the loop and skip the loop’s `else` suite, so that the diagram preserves the actual exit.
5. As a Python developer, I want `continue` to return to the loop head, so that its graph matches the next iteration.
6. As a Python developer, I want a `return` or `raise` in the body to keep its existing destination, so that the literal loop condition does not erase real exits.
7. As a Python developer, I want an ordinary condition such as a call to keep its possible true, false, and exceptional outcomes, so that the special case applies only where the condition is known.
8. As a maintainer, I want the corrected graph to appear in a fresh HTML export, so that automated tests cover what users receive.

## Implementation Decisions

- Apply Faithful Translation when the Python AST contains a `while` whose condition is the Boolean literal `True`. Keep its source label and line number.
- Build the loop’s entry and repeat path through the usual loop context. Omit the false-condition transition, its path through any loop `else` suite, and the exceptional alternative associated with evaluating the literal.
- Preserve the loop continuation target for actual breaks. If the loop has no path to its continuation, it must not make statements after it reachable merely by creating an exit place. Preserve return and exception destinations supported by the existing translator.
- Keep the existing control flow for other conditions, Python `for` loops, and JavaScript callers of the shared builder. Continue to use the existing exception model for operations in the loop body.

## Testing Decisions

- Use the existing public Python source-to-HTML integration path and inspect the embedded Petri net. Reuse the loop and exception-routing tests for smaller topology and reachable-marking checks where they isolate a failure.
- In a self-contained Pong-shaped global fixture, verify that the loop head reaches the body, completion of an iteration returns to the head, and an exception from a modeled body call reaches the handler. Verify that there is no condition-false or condition-exception route at the loop head.
- Cover a loop with no break as well as a reachable break that skips `while … else` and reaches the following statement. Check `continue` and the existing return and raise routes. Use a nonliteral call condition under `try` as the control for false and exceptional outcomes.
- Regenerate the Pong global HTML as an acceptance check. Inspect the connections by source line and semantic role rather than by generated IDs or graph layout.

## Out of Scope

- General constant evaluation, `while False`, and exception-type inference.
- New behavior for JavaScript, Python iterator loops, or completion overrides through `finally`.
- Changes to the Structuredness Metric, Call Refolding, viewer layout, or saved historical artifacts.

## Further Notes

- This is a follow-up to the original Python walker foundation, which the [roadmap](../grand_plan.md#dependency-summary) lists as Tickets 01–06 before numbered Phase 1. [Ticket 04](../issues/04-walker-while-for-loops.md) owns Python loop translation. [Ticket 05](../issues/05-walker-try-except-finally.md) and [ADR 0006](../../../docs/adr/0006-alternative-exception-outcomes.md) provide the existing exception policy.
- The November 16 Pong export has one broad handler at line 177. The reported defect concerns the two impossible branches at the literal condition on line 136. Multiple body operations may still feed the same handler entry.
- A self-contained Python fixture reproduced both impossible branches through the public source-to-HTML path on the current implementation. [Ticket 74](../issues/74-python-literal-true-loop-translation.md) tracks the repair and acceptance checks.
