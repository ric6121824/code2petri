# 26 — Display Current File in Viewer

**What to build:** The viewer prominently displays the source file currently being viewed in the bottom-right information panel, providing immediate context of the active model across both the Python CLI serialization pipeline and the frontend HTML/JS template.

**Blocked by:** None — can start immediately

**Status:** resolved

- [x] The CLI serialization pipeline propagates the analyzed source file path or name into the HTML generator.
- [x] The HTML viewer template renders the filename clearly in the bottom-right information panel.
- [x] Automated tests verify that generating HTML output with `code2petri` embeds and displays the source filename.

## Answer

1. **CLI Serialization Pipeline**:
   - Updated `code2petri` in `code2petri/engine.py` to forward `source_file=source_path` in `serializer_kwargs` when serializing to HTML (`ext == "html"`).
   - Updated `generate_html` in `code2petri/viewer/__init__.py` to accept `source_file: Optional[str] = None` and `filename: Optional[str] = None`. It embeds `"source_file": full_source_path` and `"filename": file_display` into `payload` (`code2petri-data` JSON) for both `fold` and `no-fold` modes, and performs template string substitutions for `{{SOURCE_FILE}}`, `{{FILENAME}}`, and `{{FILE_BOX_STYLE}}`.

2. **HTML Viewer Template**:
   - In `code2petri/viewer/template.html`, relocated `#info-panel` to the bottom-right (`bottom: 20px; right: 20px;`).
   - Added `#info-file-box` containing `.info-file-label` (`File:`) and `#info-filename` with title tooltip set to `{{SOURCE_FILE}}`.
   - Added CSS styling for `.info-file-box`, `.info-file-label`, and `.info-filename` (monospaced blue typography).
   - In the client-side JavaScript initialization, synchronized `#info-filename` text content and tooltip with `payload.filename` and `payload.source_file`, displaying the file box when present or hiding it cleanly when omitted.

3. **Automated Verification**:
   - Added `test_generate_html_embeds_source_file_and_filename`, `test_generate_html_without_source_file`, and `test_info_panel_bottom_right_layout` in `TestHTMLViewerGenerator`.
   - Added `test_cli_engine_embeds_source_filename_in_html` and `test_cli_main_embeds_source_filename_in_html` in `TestCLIEngineHTMLIntegration`.
   - All 364 tests across the entire test suite pass.

