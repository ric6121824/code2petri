# Phase 2.8.2 — Pong call-refolding browser check

This is a regenerated acceptance build for Phase 2.8.2 review round 03. It is stored under the full generator commit so the earlier reviewed Pong export remains unchanged.

## Provenance

- **Generator repository:** `code2flow`
- **Generator commit:** `6d7d0d3f0ebd25f27ea2b67128725cf4160ec758`
- **Source game:** `Python-Games/Pong/game.py`
- **Source-game commit:** `3f9b5bfab39540a056e7a7fa152b686974c20b67`
- **Target:** global graph; saved calls `t67` (`game.py:157`) and `t74` (`game.py:164`)
- **Related review:** [`phase-2.8.2-review-round-03.md`](../../../reviews/phase-2.8.2-review-round-03.md)

## Generation command

Run from the `code2flow` repository at the generator commit above:

```sh
.venv/bin/python -m code2petri.engine \
  '/Volumes/SharedDrive/Documents/GitHub/Python-Games/Pong/game.py' \
  -t '(global)' \
  -o '/private/tmp/code2petri-round03-6d7d0d3/pong_global_foldable.html'
```

The actual temporary output directory was `/private/tmp/code2petri-round03-6d7d0d3/`; the command above records the generator invocation with the output filename. The session file is a byte-for-byte copy of the pre-existing `Pong-261116/pong_global_foldable_session_save.json` and was not edited.

## SHA-256

| File | SHA-256 |
| --- | --- |
| `pong_global_foldable.html` | `ab37f296f049cc33c4ccbd08858c12c706173cb59905cafab73e4506c74cdee9` |
| `pong_global_foldable_session_save.json` | `75cbde30875adbd1628af905503745c8dc33f7cab5901bb606bc999bb9f75b7d` |

## Browser acceptance

**Pending user-run browser check.** Open `pong_global_foldable.html`, then open the copied session JSON. Use Fold Entire Function on `t67` and `t74`. Save and reopen the session, then verify each call remains a labeled gold box, its normal and exception routes remain distinct, and Component-Local Unfold restores the expanded call. Record the result in the related review or Ticket 71.
