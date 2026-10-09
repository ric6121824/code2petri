# 50: Show the Root Function in the Info Panel

**What to build:** Identify the root function of the active net alongside its source file in the bottom-left info panel, so users can distinguish views of different functions from the same file.

**Blocked by:** None (can start immediately).

**Status:** resolved

- [ ] Generating and opening a viewer for a named function displays that root function next to or below its source file in the existing info panel.
- [ ] The name comes from the active document's root-function identity. Qualified method names and the canonical Global Scope name are preserved; selecting an inlined callee for inspection does not replace the root-function label.
- [ ] Missing function metadata uses a clear unavailable state rather than displaying an undefined value or guessing from a filename.
- [ ] The presentation uses the current light-theme info-panel styling, remains readable with long names or file paths, and does not overlap other controls.
- [ ] The panel renders the active document's identity rather than retaining a one-time copy of the initial label, so session restoration can refresh it through the existing metadata update behavior.
- [ ] Verification generates viewers for a named function, a qualified method, and Global Scope, checks their displayed identities, and covers missing metadata and rendering after the active document metadata changes. This ticket does not require Save/Open to be implemented first.

## Answer

Implemented root-function identity display and active-document metadata refresh, including qualified names, Global Scope, and unavailable metadata. Automated viewer tests passed in the focused suite. Manual browser verification was not run.
