# 52: Reliable large Save Session downloads across browsers

**What to build:** Let users download complete Fold State Snapshots from the generated offline viewer in Safari, Chrome, and Firefox, including the compact nested snapshots from Ticket 51. Save Session must keep each download available long enough for the browser to consume it, clean up afterward, and leave the active session usable.

**Blocked by:** 51 — Compact, lossless Fold State Snapshot saves (provides the nested snapshot used for end-to-end browser acceptance).

**Status:** ready-for-human

- [ ] Replace Save Session's unconditional 100 ms Blob URL revocation with a bounded lifecycle supported by evidence from the target browsers. The URL remains usable while its download is being initiated/consumed, then is eventually released; temporary DOM resources are also cleaned up.
- [x] Two or more rapid Save Session actions each produce an independent, correctly named, complete JSON file. Starting or cleaning up one download does not interrupt another or leave unbounded object URLs behind.
- [x] Detectable initiation, serialization, and download-helper errors leave the active graph, fold state, selection, names, metrics, layout, and viewport intact and show a useful failure message. Do not claim to detect an operating-system/browser cancellation that the page cannot observe.
- [x] Automated regression coverage exercises the actual Save Session download helper, including object-URL creation, click, delayed cleanup, repeated saves, and failure paths. An injected replacement download callback alone is insufficient. Saved bytes parse and reopen through Open Session with folding/unfolding intact.
- [ ] With freshly generated HTML, verify a small snapshot, a representative large net, and a deeply nested compact snapshot in Safari 18.6, Chrome, and Firefox where those browsers are available. Inspect each completed file, reopen it, continue Component-Local Unfold, repeat the save, and record browser versions, file sizes, responsiveness, and any recurrence of the reported wait prompt or silent failure. Report unavailable browser coverage as a validation gap rather than a passed check.
- [x] Keep the Safari/Firefox root cause provisional until reproduced or otherwise established. The older WebKit Blob-URL reports support testing cleanup timing but do not prove this specific failure. PNML export and its download helper are outside this ticket.

Specification: [Phase 2.9 — Compact and Reliable Fold State Snapshots](../specs/phase-2.9-session-snapshot-optimization.md).

## Comments

- 2026-10-10: The production helper now keeps each Blob URL alive independently for a bounded 30-second grace period, removes its temporary anchor, and immediately cleans up detectable initiation failures. Automated helper tests verify repeated-download isolation, complete mocked bytes, and cleanup. The grace period is not treated as evidence that the browser finished writing the file.
- Browser acceptance remains unverified. Safari, Chrome, and Firefox are installed, but browser automation could not be initialized in this environment (the computer-use runtime failed before exposing browser controls). No claim is made about completed files, browser versions, or whether the reported failures recur; the browser-validation checkbox remains open as an explicit gap.
- Focused snapshot/download tests pass (11 tests); the full viewer module passes (134 tests). The observed Safari/Firefox failure cause remains provisional.
