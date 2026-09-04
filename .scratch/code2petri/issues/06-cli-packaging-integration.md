# 06 — CLI, packaging & end-to-end integration

**What to build:** Wire all the pieces together into a usable command-line tool. A user can run `code2petri myfile.py --target-function=main --output net.pnml` and get a valid PNML file, or `--output net.gv` for a Graphviz DOT file, or `--output net.svg`/`net.png` for a rendered image (if Graphviz is installed). The `--list-functions` flag prints all function names found in the file and exits. The tool is installable via `pip install` with a `code2petri` console script entry point in `setup.py`. Logging is controlled via `--quiet`/`--verbose`. Clear error messages are shown when the target function is not found or the file cannot be parsed.

**Blocked by:** 03 — if/else/elif, 04 — while & for loops, 05 — try/except/finally

**Status:** ready-for-agent

- [ ] `code2petri/engine.py` with `code2petri()` top-level function and `main()` CLI entry point using argparse
- [ ] `--target-function` flag to select which function to analyze
- [ ] `--output` flag with format detection by extension (`.pnml`, `.gv`/`.dot`, `.png`/`.svg`, `.json`)
- [ ] `--list-functions` flag that prints all function names and exits
- [ ] `--quiet` and `--verbose` flags for logging control
- [ ] Clear error message when `--target-function` is not found in the file
- [ ] `setup.py` updated with `code2petri` package and `console_scripts` entry point
- [ ] `code2petri/__init__.py` exporting the `code2petri` function
- [ ] End-to-end test: a Python file with mixed constructs (if, loop, try, sequential, return), assert the full pipeline produces correct PNML and DOT output
- [ ] End-to-end test: `--list-functions` on a multi-function file prints expected names
- [ ] End-to-end test: missing target function produces a clear AssertionError
