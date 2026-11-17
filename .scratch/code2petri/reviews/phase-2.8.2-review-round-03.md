# Phase 2.8.2 — Implementation Review, Round 03

- **Review date** 2026-11-17
- **Branch** `codex/phase-2.8.2-call-refolding`
- **Candidate** `fdc198ba544f21e9bb64c5cbf5bf3aa08bb79443`
- **Owner** [Ticket 71 — Call Refolding](../issues/71-call-refolding.md)
- **Prior review** [Round 02](phase-2.8.2-review-round-02.md)

## Refolded Pong `write()` calls use the ordinary gray style

The user reported that **Fold Entire Function** on `write()` in `pong_global_foldable_session_save.json` produced no gold completion box. In the saved diagram each `write()` compound contains one `pen.write()` transition. The companion `pong_global_foldable.html` from the `Pong-261116` export embeds the same reduction engine, Fold Entire Function handler, and Cytoscape stylesheet as the current checkout.

| Pong call site | Expanded compound | Refolded call | Normal continuation | Exception continuation |
| --- | --- | --- | --- | --- |
| `game.py:157` | `compound_inline_write_t67` | `t67` | `p60` | `p49` (`except_entry`) |
| `game.py:164` | `compound_inline_write_t74` | `t74` | `p66` | `p49` (`except_entry`) |

In a headless replay of the saved graph, both button actions completed one `function_singleton` reduction and restored `call: write()` as an opaque transition. Both caller routes survived, and Component-Local Unfold restored each expanded compound. The computed style was gray `#999999` with a `#111111` border. Both refolding paths set `is_call_refolded` on the restored call, but the gold style matches `collapsed-compound`. The refolded transition uses the ordinary opaque-transition style. The older scoped structural-fold test still passes through its collapsed-compound path. [Opaque style](../../../code2petri/viewer/template.html#L1837), [gold style](../../../code2petri/viewer/template.html#L1933), [browser refold](../../../code2petri/viewer/template.html#L2584), [backend refold](../../../code2petri/viewer/template.html#L2714).

## Implementation handoff

1. In `code2petri/viewer/template.html`, let `node.transition[?is_call_refolded]` share the existing gold completion styling. Use the existing data flag for both expansion paths and for restored sessions. Keep the refolded node's ordinary transition and component classes so click handling, history, and graph export keep their existing semantics.
2. Keep label mappings appropriate to each node. A structurally collapsed compound uses `data(collapsed_label)`. A refolded transition uses `data(label)` so `call: write()` and any supported custom name remain visible. One implementation is to share the gold style object, remove its `label` mapping, and put `data(collapsed_label)` in a following compound-specific rule. The transition's base style then supplies its label. Keep the collapsed-child hiding rule scoped to compound children.
3. Extend the two existing production-action refolding tests with a computed-style check using the generated viewer's stylesheet and Cytoscape with styling enabled. Assert the gold border and visible call label for both expansion paths and after save/open. Include controls for an ordinary opaque transition and a structurally collapsed compound. Keep the existing assertions for routes, score availability, and local unfold. [Browser-expanded test](../../../tests/test_viewer_action_history.py#L468), [backend-inlined test](../../../tests/test_viewer_action_history.py#L696), [singleton control](../../../tests/test_html_viewer.py#L7160).
4. Regenerate the Pong HTML, open a copy of the original save, and fold each of the two listed calls. Verify that the labeled gold box survives Save Session and Open Session, that the normal and exception connections stay distinct, and that Component-Local Unfold restores the expanded call. Record this as a browser check on the regenerated artifact.

## Verification

The repository implementation is complete. The focused suite passed 39 tests with the generated viewer stylesheet enabled for computed-style assertions:

```sh
.venv/bin/python -m unittest \
  tests.test_html_viewer.TestFoldEntireFunction \
  tests.test_viewer_action_history
```

Both production refolding paths retain the gold border and visible call label before and after session serialization. Controls confirm that ordinary opaque transitions retain their normal style and structural collapsed compounds retain the collapsed label. Route, score, history, and local-unfold assertions remain in place.

The requested regenerated-Pong browser check is still pending. The regenerated HTML and a byte-for-byte copy of the original session are available in the [commit-named export folder](../exports/phase-2.8.2/6d7d0d3f0ebd25f27ea2b67128725cf4160ec758/README.md) for the user-run check. The original reviewed export and session remain unchanged.

| Reproduction artifact | SHA-256 |
| --- | --- |
| `Pong-261116/pong_global_foldable.html` | `0aa82bc8151bf17612006c8566ab9cab074bf1118a1e7307ab4f4b49cf362fa1` |
| `Pong-261116/pong_global_foldable_session_save.json` | `75cbde30875adbd1628af905503745c8dc33f7cab5901bb606bc999bb9f75b7d` |
