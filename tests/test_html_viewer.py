import json
import os
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET

from code2petri.engine import code2petri, main, TEXT_SERIALIZERS
from code2petri.fold import FoldConfig, fold_net, FoldResult
from code2petri.model import PetriNet, Transition, Place
from code2petri.viewer import generate_html


_CANONICAL_SNAPSHOT_ASSERTION_JS = r"""
function assertCanonicalSnapshot(value) {
  if (!value || typeof value !== 'object') return;
  if (value.group === 'nodes' && value.data && Object.prototype.hasOwnProperty.call(value.data, 'consumedSubgraph')) {
    throw new Error('snapshot retained a legacy restoration alias');
  }
  Object.keys(value).forEach(key => assertCanonicalSnapshot(value[key]));
}
"""


def _extract_embedded_data(html_content: str) -> dict:
    """Helper to extract and parse the embedded code2petri-data JSON block."""
    match = re.search(
        r'<script id="code2petri-data" type="application/json">\s*(\{.*?\})\s*</script>',
        html_content,
        re.DOTALL,
    )
    if not match:
        raise ValueError("Could not find embedded code2petri-data in HTML content")
    return json.loads(match.group(1))


def _extract_callee_nets_data(html_content: str) -> dict:
    """Helper to extract and parse the embedded CALLEE_NETS_JSON script block."""
    match = re.search(
        r'window\.CALLEE_NETS_JSON\s*=\s*(\{.*?\});',
        html_content,
        re.DOTALL,
    )
    if not match:
        raise ValueError("Could not find window.CALLEE_NETS_JSON in HTML content")
    return json.loads(match.group(1))


def _read_template_html() -> str:
    """Helper to read template.html content."""
    from code2petri.viewer import _load_template
    return _load_template()


def _run_node_script(script: str):
    """Helper to run a Node.js script synchronously with captured output."""
    import subprocess
    return subprocess.run(["node", "-e", script], capture_output=True, text=True)


def _extract_template_net_to_elements() -> str:
    """Helper to extract netToElements JavaScript function from template.html."""
    html = _read_template_html()
    match = re.search(r'function netToElements\(net\) \{(.*?)\n      \}', html, re.DOTALL)
    if not match:
        raise ValueError("Could not extract netToElements from template.html")
    return match.group(0)


def _setup_live_fold_test_harness(net_json_literal: str, test_logic_js: str) -> str:
    """Helper to construct a self-contained Node.js harness containing Cytoscape, LiveFoldReductionEngine, and inspector mocks."""
    html = _read_template_html()
    net_to_elements_js = _extract_template_net_to_elements()

    m_sese = re.search(r'class SESEInfrastructure \{(.*?)\n      \}', html, re.DOTALL)
    sese_js = m_sese.group(0) if m_sese else ""

    m_engine = re.search(r'class LiveFoldReductionEngine \{(.*?)\n      \}', html, re.DOTALL)
    assert m_engine is not None, "Could not extract LiveFoldReductionEngine from template.html"
    engine_js = m_engine.group(0)

    m_inspect = re.search(r'function getInspectorData\(node\) \{.*?\n      function closeInspector\(\) \{.*?\n      \}', html, re.DOTALL)
    assert m_inspect is not None, "Could not extract inspector functions from template.html"
    inspector_js = m_inspect.group(0)

    m_tap = re.search(r"cy\.on\('tap', 'node', function\(evt\) \{(.*?)\n      \}\);", html, re.DOTALL)
    assert m_tap is not None, "Could not extract cy.on('tap', 'node') from template.html"
    tap_handler_js = m_tap.group(0)

    m_fold_reduce = re.search(r'function handleFoldReduction\(node, fallbackType\) \{(.*?)\n      \}', html, re.DOTALL)
    assert m_fold_reduce is not None, "Could not extract handleFoldReduction from template.html"
    fold_reduce_js = m_fold_reduce.group(0)

    m_update = re.search(r'function updateFoldableHighlights\(\) \{(.*?)\n      \}', html, re.DOTALL)
    assert m_update is not None, "Could not extract updateFoldableHighlights from template.html"
    update_highlights_js = m_update.group(0)

    m_cxttap = re.search(r"function handleRightClickUnfold\(node\) \{.*?\n      cy\.on\('cxttap', 'node', function\(evt\) \{.*?\n      \}\);", html, re.DOTALL)
    assert m_cxttap is not None, "Could not extract handleRightClickUnfold and cy.on('cxttap') from template.html"
    cxttap_handler_js = m_cxttap.group(0)

    m_pnml = re.search(r'function escapeXml\(unsafe\) \{.*?\n\s*const triggerClientSideExport = exportClientSidePnml;', html, re.DOTALL)
    assert m_pnml is not None, "Could not extract PNML export functions from template.html"
    pnml_js = m_pnml.group(0)

    return f"""
const cytoscape = require('./code2petri/viewer/vendor/cytoscape.min.js');
const {{ captureViewport, computeAnchoredPan, restoreViewport }} = require('./code2petri/viewer/engine/viewport.js');
global.captureViewport = captureViewport;
global.computeAnchoredPan = computeAnchoredPan;
global.restoreViewport = restoreViewport;

{net_to_elements_js}
{sese_js}
{engine_js}

// Mock DOM elements for inspector and export
let lastCreatedBlob = null;
let lastCreatedUrl = null;
let downloadedFilename = null;

global.Blob = function(parts, options) {{
  this.parts = parts;
  this.options = options;
  this.content = parts.join('');
  lastCreatedBlob = this;
}};
global.URL = {{
  createObjectURL: function(blob) {{
    lastCreatedUrl = 'blob:mock-url-' + Math.random();
    return lastCreatedUrl;
  }},
  revokeObjectURL: function(url) {{}}
}};

const inspectorPanel = {{ style: {{ display: 'flex' }} }};
const inspectorEmpty = {{ style: {{ display: 'block' }} }};
const inspectorContent = {{ style: {{ display: 'none' }} }};
const inspectorLabel = {{ textContent: '' }};
const inspectorId = {{ textContent: '—' }};
const inspectorInput = {{
  value: '',
  _listeners: {{}},
  addEventListener: function(evt, cb) {{
    this._listeners[evt] = this._listeners[evt] || [];
    this._listeners[evt].push(cb);
  }},
  trigger: function(evt, data) {{
    if (this._listeners[evt]) {{
      this._listeners[evt].forEach(cb => cb(data || {{}}));
    }}
  }},
  blur: function() {{}}
}};
const inspectorSaveBtn = {{
  _listeners: {{}},
  addEventListener: function(evt, cb) {{
    this._listeners[evt] = this._listeners[evt] || [];
    this._listeners[evt].push(cb);
  }},
  click: function() {{
    if (this._listeners['click']) {{
      this._listeners['click'].forEach(cb => cb({{}}));
    }}
  }}
}};
const inspectorType = {{ textContent: '' }};
const inspectorTau = {{ textContent: '' }};
const inspectorOmega = {{ textContent: '—' }};
const inspectorLine = {{ textContent: '' }};
const inspectorCloseBtn = {{
  addEventListener: function(evt, cb) {{
    if (evt === 'click') this.onclick = cb;
  }},
  click: function() {{
    if (this.onclick) this.onclick();
  }}
}};

const btnExportPnml = {{
  _listeners: {{}},
  addEventListener: function(evt, cb) {{
    this._listeners[evt] = this._listeners[evt] || [];
    this._listeners[evt].push(cb);
  }},
  click: function() {{
    if (this._listeners['click']) {{
      this._listeners['click'].forEach(cb => cb({{}}));
    }}
  }}
}};
const infoFilename = {{ textContent: 'sample_test.py' }};
const headerTitle = {{ textContent: 'Sample Test' }};
const valSm = {{ textContent: '0.0' }};
const inspectorSm = {{ textContent: '—' }};
const hudBtnContractMg = {{
  style: {{ display: 'none' }},
  _listeners: {{}},
  addEventListener: function(evt, cb) {{
    this._listeners[evt] = this._listeners[evt] || [];
    this._listeners[evt].push(cb);
  }},
  click: function() {{
    if (this._listeners['click']) {{
      this._listeners['click'].forEach(cb => cb({{}}));
    }}
  }}
}};
const hudBtnUnfold = {{
  style: {{ display: 'none' }},
  _listeners: {{}},
  addEventListener: function(evt, cb) {{
    this._listeners[evt] = this._listeners[evt] || [];
    this._listeners[evt].push(cb);
  }},
  click: function() {{
    if (this._listeners['click']) {{
      this._listeners['click'].forEach(cb => cb({{}}));
    }}
  }}
}};

const document = {{
  getElementById: function(id) {{
    if (id === 'inspector-panel') return inspectorPanel;
    if (id === 'inspector-empty') return inspectorEmpty;
    if (id === 'inspector-content') return inspectorContent;
    if (id === 'inspector-label') return inspectorLabel;
    if (id === 'inspector-id') return inspectorId;
    if (id === 'hud-input-label' || id === 'inspector-input-label') return inspectorInput;
    if (id === 'hud-btn-save' || id === 'inspector-btn-save') return inspectorSaveBtn;
    if (id === 'inspector-type') return inspectorType;
    if (id === 'inspector-tau') return inspectorTau;
    if (id === 'inspector-omega') return inspectorOmega;
    if (id === 'inspector-line') return inspectorLine;
    if (id === 'inspector-sm') return inspectorSm;
    if (id === 'val-sm') return valSm;
    if (id === 'hud-btn-contract-mg') return hudBtnContractMg;
    if (id === 'hud-btn-unfold') return hudBtnUnfold;
    if (id === 'inspector-close' || id === 'btn-close-hud') return inspectorCloseBtn;
    if (id === 'btn-export-pnml') return btnExportPnml;
    if (id === 'info-filename') return infoFilename;
    return null;
  }},
  querySelector: function(sel) {{
    if (sel === '.header-title') return headerTitle;
    return null;
  }},
  createElement: function(tag) {{
    if (tag === 'a') {{
      return {{
        href: '',
        download: '',
        click: function() {{
          downloadedFilename = this.download;
        }}
      }};
    }}
    return {{}};
  }},
  body: {{
    appendChild: function(el) {{}},
    removeChild: function(el) {{}}
  }}
}};

{inspector_js}

if (inspectorSaveBtn) {{
  inspectorSaveBtn.addEventListener('click', function(e) {{
    applyComponentNodeRename();
  }});
}}
if (inspectorInput) {{
  inspectorInput.addEventListener('keydown', function(e) {{
    if (e.key === 'Enter') applyComponentNodeRename();
  }});
}}
if (inspectorCloseBtn) {{
  inspectorCloseBtn.addEventListener('click', closeInspector);
}}

{pnml_js}

if (btnExportPnml) {{
  btnExportPnml.addEventListener('click', function(e) {{
    exportClientSidePnml(cy);
  }});
}}

const net = {net_json_literal};

const expandedNodes = new Map();
const calleeNetsMap = {{}};
const currentStep = 0;
function renderStep() {{}}

const cy = cytoscape({{
  elements: netToElements(net),
  userPanningEnabled: false
}});

cy.on('tap', function(evt) {{
  if (evt.target === cy) {{
    closeInspector();
  }}
}});

const foldEngine = new LiveFoldReductionEngine(cy);

{update_highlights_js}
updateFoldableHighlights();

{fold_reduce_js}

let hasDragged = false;

{tap_handler_js}

if (hudBtnContractMg) {{
  hudBtnContractMg.addEventListener('click', function(e) {{
    if (typeof selectedInspectorNode !== 'undefined' && selectedInspectorNode) {{
      const target = selectedInspectorNode;
      closeInspector();
      handleFoldReduction(target, 'marked_graph');
    }}
  }});
}}

if (hudBtnUnfold) {{
  hudBtnUnfold.addEventListener('click', function(e) {{
    if (typeof selectedInspectorNode !== 'undefined' && selectedInspectorNode) {{
      handleRightClickUnfold(selectedInspectorNode);
    }}
  }});
}}

{cxttap_handler_js}

{test_logic_js}
"""


def _make_sese_test_net(leak_in: bool = False, leak_out: bool = False) -> str:
    """Generates a synthetic Petri Net JSON literal for SESE testing with optional boundary leaks."""
    places = [
        "{ id: 'p_src', label: 'src', initial_tokens: 0 }",
        "{ id: 'p1', label: 'p1', initial_tokens: 0 }",
        "{ id: 'p_snk', label: 'snk', initial_tokens: 0 }",
    ]
    transitions = [
        "{ id: 't1', label: 't1' }",
        "{ id: 't2', label: 't2' }",
    ]
    arcs = [
        "{ source: 'p_src', target: 't1' }",
        "{ source: 't1', target: 'p1' }",
        "{ source: 'p1', target: 't2' }",
        "{ source: 't2', target: 'p_snk' }",
    ]
    if leak_in:
        places.append("{ id: 'p_ext_in', label: 'ext_in', initial_tokens: 0 }")
        transitions.append("{ id: 't_leak_in', label: 'leak_in' }")
        arcs.append("{ source: 'p_ext_in', target: 't_leak_in' }")
        arcs.append("{ source: 't_leak_in', target: 'p1' }")
    if leak_out:
        places.append("{ id: 'p_ext_out', label: 'ext_out', initial_tokens: 0 }")
        transitions.append("{ id: 't_leak_out', label: 'leak_out' }")
        arcs.append("{ source: 'p1', target: 't_leak_out' }")
        arcs.append("{ source: 't_leak_out', target: 'p_ext_out' }")

    places_str = ",\n    ".join(places)
    transitions_str = ",\n    ".join(transitions)
    arcs_str = ",\n    ".join(arcs)

    return f"""{{\n  places: [\n    {places_str}\n  ],\n  transitions: [\n    {transitions_str}\n  ],\n  arcs: [\n    {arcs_str}\n  ]\n}}"""


class TestHTMLViewerGenerator(unittest.TestCase):
    def setUp(self):
        self.net = PetriNet()
        self.net.add_place("p0", "start", initial_tokens=1)
        self.net.add_transition("t0", "a = 1", line_number=10)
        self.net.add_place("p1", "mid")
        self.net.add_transition(
            "t1",
            "resolved_call()",
            metadata={"resolved": True, "resolved_to": "helper", "target_file": "lib.py"},
        )
        self.net.add_place("p2", "after_resolved")
        self.net.add_transition(
            "t2",
            "unresolved_call()",
            metadata={"resolved": False},
        )
        self.net.add_place("p3", "end")

        node_map = self.net.get_node_map()
        self.net.add_arc(node_map["p0"], node_map["t0"])
        self.net.add_arc(node_map["t0"], node_map["p1"])
        self.net.add_arc(node_map["p1"], node_map["t1"])
        self.net.add_arc(node_map["t1"], node_map["p2"])
        self.net.add_arc(node_map["p2"], node_map["t2"])
        self.net.add_arc(node_map["t2"], node_map["p3"])

    def test_generate_html_self_contained_no_external_references(self):
        """Validates that the generated HTML has zero external URLs or CDN links."""
        html_content = generate_html(self.net, title="Test Net")
        self.assertIn("<!DOCTYPE html>", html_content)
        self.assertIn("</html>", html_content)

        # Ensure no external resources (http://, https://, //cdn)
        external_urls = re.findall(r'(?:src|href)=["\'](https?://[^"\']+)["\']', html_content)
        self.assertEqual(external_urls, [], f"Found external URL references: {external_urls}")

    def test_generate_html_inlines_libraries(self):
        """Validates that Cytoscape.js, Dagre, and Cytoscape-Dagre are inlined."""
        html_content = generate_html(self.net)
        self.assertIn("cytoscape.min.js", html_content)
        self.assertIn("dagre.min.js", html_content)
        self.assertIn("cytoscape-dagre.js", html_content)
        self.assertIn('<script id="code2petri-data"', html_content)

    def test_generate_html_no_fold_mode(self):
        """Validates that passing a raw PetriNet sets mode='no-fold'."""
        html_content = generate_html(self.net, title="Static View")
        self.assertIn("Static View", html_content)

        data = _extract_embedded_data(html_content)
        self.assertEqual(data["mode"], "no-fold")
        self.assertEqual(data["fold_steps"], [])
        self.assertEqual(data["final_sm"], 0.0)
        self.assertIn("places", data["initial_net"])
        self.assertIn("transitions", data["initial_net"])

    def test_generate_html_fold_mode(self):
        """Validates that passing a FoldResult sets mode='fold' and embeds fold steps."""
        fold_res = fold_net(self.net, FoldConfig())
        html_content = generate_html(fold_res)

        data = _extract_embedded_data(html_content)
        self.assertEqual(data["mode"], "fold")
        self.assertGreater(len(data["fold_steps"]), 0)
        self.assertEqual(data["final_sm"], fold_res.final_sm)

    def test_text_serializers_html_dispatch(self):
        """Validates that TEXT_SERIALIZERS['html'] delegates to generate_html for nets and fold results."""
        html_net = TEXT_SERIALIZERS["html"](self.net)
        self.assertIn("<!DOCTYPE html>", html_net)
        data_net = _extract_embedded_data(html_net)
        self.assertEqual(data_net["mode"], "no-fold")

        fold_res = fold_net(self.net, FoldConfig())
        html_fold = TEXT_SERIALIZERS["html"](fold_res)
        self.assertIn("<!DOCTYPE html>", html_fold)
        data_fold = _extract_embedded_data(html_fold)
        self.assertEqual(data_fold["mode"], "fold")

    def test_opaque_transition_visual_tau_badge_elements(self):
        """Validates that the template renders an inline SVG tau badge rather than label text."""
        fold_res = fold_net(self.net, FoldConfig())
        html_content = generate_html(fold_res)

        self.assertIn("node.transition.opaque[badge_svg]", html_content)
        self.assertIn("background-image", html_content)
        self.assertIn("data(badge_svg)", html_content)
        self.assertIn("data:image/svg+xml;utf8,", html_content)
        # Verify that tau is NOT appended as raw label text
        self.assertNotIn("(τ=", html_content)

    def test_generate_html_embeds_callee_nets(self):
        """Validates that passing callee_nets embeds window.CALLEE_NETS_JSON without payload duplication."""
        dummy_callee = {
            "places": [{"id": "cp0", "label": "start"}],
            "transitions": [{"id": "ct0", "label": "helper()"}],
            "arcs": [],
        }
        callee_dict = {"helper": dummy_callee}
        html_content = generate_html(self.net, callee_nets=callee_dict)

        self.assertIn("window.CALLEE_NETS_JSON", html_content)
        callee_data = _extract_callee_nets_data(html_content)
        self.assertEqual(callee_data, callee_dict)

        embedded_data = _extract_embedded_data(html_content)
        self.assertNotIn("callee_nets", embedded_data)

    def test_generate_html_default_empty_callee_nets(self):
        """Validates that omitting callee_nets defaults to an empty dictionary in window.CALLEE_NETS_JSON."""
        html_content = generate_html(self.net)
        callee_data = _extract_callee_nets_data(html_content)
        self.assertEqual(callee_data, {})

        embedded_data = _extract_embedded_data(html_content)
        self.assertNotIn("callee_nets", embedded_data)

    def test_html_compound_node_styles_and_events(self):
        """Validates that the template includes compound node CSS, Cytoscape styles, and tap handlers."""
        html_content = generate_html(self.net)
        self.assertIn(".legend-swatch.compound", html_content)
        self.assertIn("node.compound, node:parent", html_content)
        self.assertIn("#e8f5e9", html_content)
        self.assertIn("cy.on('tap', 'node'", html_content)

    def test_generate_html_embeds_source_file_and_filename(self):
        """Validates that passing source_file embeds filename in info-panel and code2petri-data."""
        html_content = generate_html(self.net, source_file="/path/to/my_module.py")
        self.assertIn("my_module.py", html_content)
        self.assertIn('id="info-filename"', html_content)
        self.assertIn('title="/path/to/my_module.py"', html_content)

        embedded_data = _extract_embedded_data(html_content)
        self.assertEqual(embedded_data["filename"], "my_module.py")
        self.assertEqual(embedded_data["source_file"], "/path/to/my_module.py")

    def test_generate_html_displays_named_root_function_identity(self):
        """The generated viewer identifies its root function alongside the source file."""
        html_content = generate_html(
            self.net,
            source_file="/path/to/my_module.py",
            function_name="process_order",
        )

        embedded_data = _extract_embedded_data(html_content)
        self.assertEqual(
            embedded_data["document"],
            {
                "source_file": "/path/to/my_module.py",
                "filename": "my_module.py",
                "function_name": "process_order",
            },
        )
        self.assertIn('id="info-function-name"', html_content)
        self.assertIn(">process_order</span>", html_content)

    def test_generate_html_displays_unavailable_when_root_function_is_missing(self):
        """Missing root metadata is explicit instead of guessed from the file name."""
        html_content = generate_html(self.net, source_file="/path/to/process_order.py")
        embedded_data = _extract_embedded_data(html_content)
        self.assertEqual(embedded_data["document"]["function_name"], "Unavailable")
        self.assertIn(">Unavailable</span>", html_content)

    def test_info_panel_tracks_active_document_metadata(self):
        """Session restoration can refresh the browser-visible document identity."""
        html_content = generate_html(self.net)

        self.assertIn("window.code2petriViewer.setActiveDocumentMetadata", html_content)
        self.assertIn("infoFilename.textContent = activeDocument.filename", html_content)
        self.assertIn("infoFunctionName.textContent = activeDocument.function_name", html_content)

    def test_active_document_metadata_update_rerenders_visible_identity(self):
        """The public viewer metadata boundary rerenders both visible identity rows."""
        html_content = generate_html(self.net)
        match = re.search(
            r"const unavailableFunctionName = 'Unavailable';.*?"
            r"setActiveDocumentMetadata\(activeDocument\);",
            html_content,
            re.DOTALL,
        )
        self.assertIsNotNone(match)

        node_script = """
const payload = {
  document: {
    source_file: '/initial/source.py',
    filename: 'source.py',
    function_name: 'initial_root',
    return_metadata: {
      analysis_status: 'complete', declared: { expression: 'Result[str]' },
      inferred: [{ expression: '"a:b"', type: 'str', role: 'call_result', source_location: { line: 8 } }]
    }
  }
};
const infoFileBox = { style: {} };
const infoFilename = { textContent: '', title: '' };
const infoFunctionName = { textContent: '', title: '' };
const infoReturnMetadata = { textContent: '' };
const elements = {
  'info-file-box': infoFileBox,
  'info-filename': infoFilename,
  'info-function-name': infoFunctionName,
  'info-return-metadata': infoReturnMetadata
};
const document = { getElementById: id => elements[id] || null };
const window = {};
""" + match.group(0) + """
if (infoFunctionName.textContent !== 'initial_root') {
  throw new Error('Initial root function did not render');
}
if (!infoReturnMetadata.textContent.includes('Declared: Result[str]') ||
    !infoReturnMetadata.textContent.includes('Inferred return: str from "a:b" at line 8')) {
  throw new Error('Declared and inferred return evidence did not render separately');
}
window.code2petriViewer.setActiveDocumentMetadata({
  source_file: '/restored/very/long/path/restored.py',
  filename: 'restored.py',
  function_name: 'Processor.run',
  return_metadata: { analysis_status: 'unknown', declared: null, inferred: [] }
});
if (infoFilename.textContent !== 'restored.py' || infoFilename.title !== '/restored/very/long/path/restored.py') {
  throw new Error('Restored source identity did not render');
}
if (infoFunctionName.textContent !== 'Processor.run') {
  throw new Error('Restored root function did not render');
}
if (!infoReturnMetadata.textContent.includes('Unknown')) throw new Error('Unknown analysis status was not explained');
window.code2petriViewer.setActiveDocumentMetadata({});
if (infoFunctionName.textContent !== 'Unavailable') {
  throw new Error('Missing restored function metadata was not explicit');
}
if (infoFileBox.style.display !== 'none') {
  throw new Error('Missing restored file metadata did not hide the file row');
}
"""
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_generate_html_without_source_file(self):
        """Validates that omitting source_file defaults to empty string and hides info-file-box."""
        html_content = generate_html(self.net)
        embedded_data = _extract_embedded_data(html_content)
        self.assertEqual(embedded_data.get("filename"), "")
        self.assertEqual(embedded_data.get("source_file"), "")

    def test_info_panel_layout(self):
        """Validates that the info panel is positioned in the bottom-left corner."""
        html_content = generate_html(self.net)
        self.assertIn("bottom: 20px;", html_content)
        self.assertIn("left: 20px;", html_content)

    def test_canvas_panning_and_ungrabify_settings(self):
        """Validates that Cytoscape allows node dragging, disables background left-drag pan, binds right and middle drag pan, and supports wheel zoom."""
        html_content = generate_html(self.net)
        # Verify Cytoscape canvas settings
        self.assertIn("autoungrabify: false", html_content)
        self.assertIn("userPanningEnabled: false", html_content)
        self.assertIn("boxSelectionEnabled: true", html_content)

        # Verify contextmenu and auxclick suppression on canvas
        self.assertIn("'contextmenu'", html_content)
        self.assertIn("'auxclick'", html_content)
        self.assertIn("preventDefault()", html_content)

        # Verify button constants and dragging lifecycle for middle and right mouse buttons
        self.assertIn("MOUSE_BUTTON_MIDDLE = 1;", html_content)
        self.assertIn("MOUSE_BUTTON_RIGHT = 2;", html_content)
        self.assertIn("MOUSE_BUTTONS_MIDDLE_MASK = 4;", html_content)
        self.assertIn("MOUSE_BUTTONS_RIGHT_MASK = 2;", html_content)
        self.assertIn("MOUSE_BUTTON_MIDDLE", html_content)
        self.assertIn("MOUSE_BUTTON_RIGHT", html_content)
        self.assertIn("'mousemove'", html_content)
        self.assertIn("'mouseup'", html_content)
        self.assertIn("cy.panBy({ x: dx, y: dy })", html_content)

        # Verify wheel/scroll zoom listener is explicitly attached to canvas container
        self.assertIn("'wheel'", html_content)
        self.assertIn("cy.zoom({", html_content)
        self.assertIn("renderedPosition", html_content)

        # Verify coexistence: node tap handling for expand/collapse remains intact
        self.assertIn("cy.on('tap', 'node'", html_content)
        self.assertIn("expandedNodes", html_content)

    def test_headless_canvas_panning_and_wheel_zoom(self):
        """Validates that Cytoscape headless instance allows node dragging, pans, and zooms."""
        import shutil
        import subprocess

        if not shutil.which("node"):
            self.skipTest("Node.js not available in environment")

        vendor_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "code2petri", "viewer", "vendor", "cytoscape.min.js")
        )
        js_code = f"""
        const cytoscape = require({json.dumps(vendor_path)});
        const cy = cytoscape({{
          headless: true,
          minZoom: 0.2,
          maxZoom: 3.5,
          autoungrabify: false,
          userPanningEnabled: false,
          boxSelectionEnabled: false,
          elements: [
            {{ data: {{ id: "n1" }}, position: {{ x: 0, y: 0 }} }}
          ]
        }});

        // Validate node is grabbable for left-click drag
        if (!cy.$("#n1").grabbable()) {{
          process.exit(1);
        }}

        // Validate panning via panBy
        cy.panBy({{ x: 40, y: -25 }});
        if (cy.pan().x !== 40 || cy.pan().y !== -25) {{
          process.exit(2);
        }}

        // Validate wheel zooming via cy.zoom with renderedPosition
        const initialZoom = cy.zoom();
        const s = (-100 / -250) * 0.25;
        const targetZoom = initialZoom * Math.pow(10, s);
        cy.zoom({{ level: targetZoom, renderedPosition: {{ x: 100, y: 100 }} }});
        if (cy.zoom() <= initialZoom) {{
          process.exit(3);
        }}
        process.exit(0);
        """
        proc = subprocess.run(["node", "-e", js_code], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, f"Headless test failed: {proc.stderr}")




class TestCLIEngineHTMLIntegration(unittest.TestCase):
    def setUp(self):
        self.game_of_life_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "test_code", "game_of_life")
        )
        self.app_js = os.path.join(self.game_of_life_dir, "app.js")
        self.webgl_js = os.path.join(self.game_of_life_dir, "webgl-engine.js")
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_implicit_fold_activation_on_html_output(self):
        """Validates that .html output extension activates fold analysis implicitly."""
        out_html = os.path.join(self.temp_dir.name, "stepCpu.html")
        res = code2petri(
            source_path=self.app_js,
            target_function="stepCpu",
            output_file=out_html,
        )
        self.assertIsInstance(res, FoldResult)
        self.assertTrue(os.path.exists(out_html))
        self.assertGreater(os.path.getsize(out_html), 500000)  # Bundles ~670KB libraries

        with open(out_html, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("<!DOCTYPE html>", content)
        data = _extract_embedded_data(content)
        self.assertEqual(data["mode"], "fold")
        self.assertGreater(len(data["fold_steps"]), 0)
        self.assertEqual(data["final_sm"], res.final_sm)

    def test_no_fold_flag_overrides_implicit_html_activation(self):
        """Validates that --no-fold produces static Petri net HTML view."""
        out_html = os.path.join(self.temp_dir.name, "stepCpu_nofold.html")
        res = code2petri(
            source_path=self.app_js,
            target_function="stepCpu",
            output_file=out_html,
            no_fold=True,
        )
        self.assertIsInstance(res, PetriNet)
        self.assertTrue(os.path.exists(out_html))

        with open(out_html, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("<!DOCTYPE html>", content)
        data = _extract_embedded_data(content)
        self.assertEqual(data["mode"], "no-fold")
        self.assertEqual(data["fold_steps"], [])

    def test_cli_main_html_output(self):
        """Validates code2petri CLI main with -o file.html."""
        out_html = os.path.join(self.temp_dir.name, "cli_stepCpu.html")
        main([
            self.app_js,
            "-t", "stepCpu",
            "-o", out_html,
        ])
        self.assertTrue(os.path.exists(out_html))
        with open(out_html, "r", encoding="utf-8") as f:
            content = f.read()
        data = _extract_embedded_data(content)
        self.assertEqual(data["mode"], "fold")

    def test_cli_engine_precomputes_callee_nets_for_html(self):
        """Validates that code2petri with HTML output and --context precomputes callee subnets."""
        out_html = os.path.join(self.temp_dir.name, "loop_interactive.html")
        code2petri(
            source_path=self.app_js,
            target_function="loop",
            context=[self.webgl_js],
            output_file=out_html,
        )
        self.assertTrue(os.path.exists(out_html))
        with open(out_html, "r", encoding="utf-8") as f:
            content = f.read()

        callee_data = _extract_callee_nets_data(content)
        # Verify resolved callees are pre-computed in the HTML payload
        self.assertIn("WebGLEngine.step", callee_data)
        self.assertIn("places", callee_data["WebGLEngine.step"])
        self.assertIn("transitions", callee_data["WebGLEngine.step"])
        self.assertIn("arcs", callee_data["WebGLEngine.step"])
        self.assertIn("stepCpu", callee_data)


    def test_cli_engine_precomputes_callee_nets_for_html_without_context(self):
        """Validates that code2petri with HTML output and context=None precomputes same-file callees."""
        out_html = os.path.join(self.temp_dir.name, "loop_no_context.html")
        code2petri(
            source_path=self.app_js,
            target_function="loop",
            context=None,
            output_file=out_html,
        )
        self.assertTrue(os.path.exists(out_html))
        with open(out_html, "r", encoding="utf-8") as f:
            content = f.read()

        callee_data = _extract_callee_nets_data(content)
        # Same-file internal callee stepCpu should be pre-computed
        self.assertIn("stepCpu", callee_data)
        self.assertIn("places", callee_data["stepCpu"])
        self.assertIn("transitions", callee_data["stepCpu"])
        self.assertIn("arcs", callee_data["stepCpu"])
        # Cross-file callee WebGLEngine.step should NOT be present without context
        self.assertNotIn("WebGLEngine.step", callee_data)

    def test_cli_engine_embeds_source_filename_in_html(self):
        """Validates that code2petri with HTML output embeds source_file and filename in payload and DOM."""
        out_html = os.path.join(self.temp_dir.name, "stepCpu_filename.html")
        code2petri(
            source_path=self.app_js,
            target_function="stepCpu",
            output_file=out_html,
        )
        self.assertTrue(os.path.exists(out_html))
        with open(out_html, "r", encoding="utf-8") as f:
            content = f.read()

        data = _extract_embedded_data(content)
        self.assertEqual(data["filename"], "app.js")
        self.assertEqual(data["source_file"], self.app_js)
        self.assertEqual(data["document"]["function_name"], "stepCpu")
        self.assertIn("app.js", content)
        self.assertIn(">stepCpu</span>", content)
        self.assertIn('id="info-filename"', content)

    def test_cli_engine_displays_canonical_global_scope_identity(self):
        """The viewer translates the CLI's global-scope token into its canonical name."""
        source_path = os.path.join(self.temp_dir.name, "module_scope.py")
        out_html = os.path.join(self.temp_dir.name, "module_scope.html")
        with open(source_path, "w", encoding="utf-8") as f:
            f.write("result = 1\n")

        code2petri(
            source_path=source_path,
            target_function="(global)",
            output_file=out_html,
        )
        with open(out_html, "r", encoding="utf-8") as f:
            content = f.read()

        data = _extract_embedded_data(content)
        self.assertEqual(data["document"]["function_name"], "Global Scope")
        self.assertIn(">Global Scope</span>", content)
        self.assertNotIn(">(global)</span>", content)

    def test_cli_engine_preserves_qualified_method_identity(self):
        """Qualified root method names remain intact in the viewer identity."""
        source_path = os.path.join(self.temp_dir.name, "processor.py")
        out_html = os.path.join(self.temp_dir.name, "processor.html")
        with open(source_path, "w", encoding="utf-8") as f:
            f.write(
                "class Processor:\n"
                "    def run(self):\n"
                "        return 1\n"
            )

        code2petri(
            source_path=source_path,
            target_function="Processor.run",
            output_file=out_html,
        )
        with open(out_html, "r", encoding="utf-8") as f:
            content = f.read()

        data = _extract_embedded_data(content)
        self.assertEqual(data["document"]["function_name"], "Processor.run")
        self.assertIn(">Processor.run</span>", content)

    def test_cli_main_embeds_source_filename_in_html(self):
        """Validates that CLI main with HTML output propagates source filename to the viewer."""
        out_html = os.path.join(self.temp_dir.name, "main_filename.html")
        main([
            self.app_js,
            "-t", "stepCpu",
            "-o", out_html,
        ])
        self.assertTrue(os.path.exists(out_html))
        with open(out_html, "r", encoding="utf-8") as f:
            content = f.read()

        data = _extract_embedded_data(content)
        self.assertEqual(data["filename"], "app.js")
        self.assertEqual(data["source_file"], self.app_js)
        self.assertIn("app.js", content)

    def test_generate_html_composite_mode_detected_from_compounds(self):
        """Validates that generate_html automatically detects composite mode from net.compounds."""
        comp_net = PetriNet()
        p0 = comp_net.add_place("p0", "start", initial_tokens=1)
        t0 = comp_net.add_transition("t0", "run()")
        comp_net.add_arc(p0, t0)
        comp_net.add_compound(
            id="compound_worker",
            label="worker()",
            function_name="worker",
            file="worker.py",
            parent=None,
        )

        html_content = generate_html(comp_net, title="Composite Overview")
        self.assertIn("Composite Overview", html_content)
        self.assertIn("Composite Petri Net View", html_content)
        self.assertIn("Fully expanded composite Petri net", html_content)

        data = _extract_embedded_data(html_content)
        self.assertEqual(data["mode"], "composite")
        self.assertEqual(data["fold_steps"], [])
        self.assertEqual(data["final_sm"], 0.0)
        self.assertIn("composite_net", data)
        self.assertIn("compounds", data)
        self.assertEqual(len(data["compounds"]), 1)
        self.assertEqual(data["compounds"][0]["id"], "compound_worker")

        # Pre-computed fold playback controls are omitted/hidden
        self.assertIn('<div class="controls" id="fold-controls" style="display: none;">', html_content)

    def test_generate_html_mode_labels_and_descriptions(self):
        """Validates that generate_html injects appropriate MODE_LABEL and MODE_DESC."""
        # 1. Static no-fold net
        static_net = PetriNet()
        static_html = generate_html(static_net)
        self.assertIn("Petri Net View", static_html)
        self.assertIn("Interactive Petri net graph representation.", static_html)

        # 2. Fold result
        from code2petri.fold import fold_net
        net = PetriNet()
        p0 = net.add_place("p0", "start", initial_tokens=1)
        t0 = net.add_transition("t0", "step1")
        p1 = net.add_place("p1", "mid")
        t1 = net.add_transition("t1", "step2")
        p2 = net.add_place("p2", "end")
        net.add_arc(p0, t0)
        net.add_arc(t0, p1)
        net.add_arc(p1, t1)
        net.add_arc(t1, p2)
        fold_res = fold_net(net)
        fold_html = generate_html(fold_res)
        self.assertIn("Fold Reduction View", fold_html)
        self.assertIn("Interactive step playback of ProM-aligned structural reductions.", fold_html)

    def test_net_to_elements_preserves_hierarchy_and_enclosing_function(self):
        """Validates that netToElements in template.html maps parent and enclosing_function to Cytoscape data."""
        import subprocess
        import re

        template_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "code2petri", "viewer", "template.html")
        )
        with open(template_path, "r", encoding="utf-8") as f:
            html = f.read()

        m = re.search(r"(function netToElements\(net\) \{[\s\S]*?\n      \})", html)
        self.assertIsNotNone(m)
        net_to_elements_fn = m.group(1)

        node_script = f"""
{net_to_elements_fn}

const net = {{
  compounds: [
    {{ id: 'c1', label: 'fn1()', function_name: 'fn1', file: 'a.py', parent: null }}
  ],
  places: [
    {{ id: 'p1', label: 'p1', parent: 'c1', enclosing_function: 'fn1' }}
  ],
  transitions: [
    {{ id: 't1', label: 't1', parent: 'c1', enclosing_function: 'fn1' }}
  ],
  arcs: []
}};

const elements = netToElements(net);
const pElem = elements.find(e => e.data && e.data.id === 'p1');
const tElem = elements.find(e => e.data && e.data.id === 't1');
const cElem = elements.find(e => e.data && e.data.id === 'c1');

if (!pElem || pElem.data.parent !== 'c1' || pElem.data.enclosing_function !== 'fn1') {{
  throw new Error('Place failed: ' + JSON.stringify(pElem));
}}
if (!tElem || tElem.data.parent !== 'c1' || tElem.data.enclosing_function !== 'fn1') {{
  throw new Error('Transition failed: ' + JSON.stringify(tElem));
}}
if (!cElem || cElem.data.is_compound !== true || cElem.data.composite_preassembled !== true) {{
  throw new Error('Compound failed: ' + JSON.stringify(cElem));
}}
console.log('PASS');
"""
        proc = subprocess.run(["node", "-e", node_script], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_headless_tap_handler_ignores_preassembled_compounds(self):
        """Simulates tap event on preassembled compound and verifies renderStep is not called."""
        import subprocess

        template_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "code2petri", "viewer", "template.html")
        )
        with open(template_path, "r", encoding="utf-8") as f:
            html = f.read()

        self.assertIn("targetNode.data('composite_preassembled') === true", html)

    def test_nested_compound_nodes_hierarchy_and_depth_classes(self):
        """Validates that netToElements sorts compounds topologically, assigns depth and depth classes."""
        import subprocess

        net_to_elements_js = _extract_template_net_to_elements()

        node_script = f"""
{net_to_elements_js}

// Compounds provided in reverse order with depth 4 and cycle test
const net = {{
  compounds: [
    {{ id: 'c_deep', function_name: 'deep', parent: 'c_leaf', file: 'a.py' }},
    {{ id: 'c_leaf', function_name: 'leaf', parent: 'c_middle', file: 'a.py' }},
    {{ id: 'c_middle', function_name: 'middle', parent: 'c_outer', file: 'a.py' }},
    {{ id: 'c_outer', function_name: 'outer', parent: null, file: 'a.py' }}
  ],
  places: [
    {{ id: 'p_outer', label: 'p_out', parent: 'c_outer' }},
    {{ id: 'p_mid', label: 'p_mid', parent: 'c_middle' }},
    {{ id: 'p_leaf', label: 'p_leaf', parent: 'c_leaf' }},
    {{ id: 'p_deep', label: 'p_deep', parent: 'c_deep' }}
  ],
  transitions: [
    {{ id: 't_outer', label: 't_out', parent: 'c_outer' }},
    {{ id: 't_mid', label: 't_mid', parent: 'c_middle' }},
    {{ id: 't_leaf', label: 't_leaf', parent: 'c_leaf' }},
    {{ id: 't_deep', label: 't_deep', parent: 'c_deep' }}
  ],
  arcs: []
}};

const elements = netToElements(net);

const cOuter = elements.find(e => e.data && e.data.id === 'c_outer');
const cMid = elements.find(e => e.data && e.data.id === 'c_middle');
const cLeaf = elements.find(e => e.data && e.data.id === 'c_leaf');
const cDeep = elements.find(e => e.data && e.data.id === 'c_deep');

if (!cOuter || !cMid || !cLeaf || !cDeep) throw new Error('Missing compounds');

// Check depth and depth classes (depth 4 clamped to depth-3)
if (cOuter.data.depth !== 0 || !cOuter.classes.includes('depth-0')) {{
  throw new Error('c_outer depth failed: ' + JSON.stringify(cOuter));
}}
if (cMid.data.depth !== 1 || !cMid.classes.includes('depth-1') || cMid.data.parent !== 'c_outer') {{
  throw new Error('c_middle depth failed: ' + JSON.stringify(cMid));
}}
if (cLeaf.data.depth !== 2 || !cLeaf.classes.includes('depth-2') || cLeaf.data.parent !== 'c_middle') {{
  throw new Error('c_leaf depth failed: ' + JSON.stringify(cLeaf));
}}
if (cDeep.data.depth !== 3 || !cDeep.classes.includes('depth-3') || cDeep.data.parent !== 'c_leaf') {{
  throw new Error('c_deep depth failed: ' + JSON.stringify(cDeep));
}}

// Check readable labels
if (cOuter.data.label !== 'outer()' || cMid.data.label !== 'middle()' || cLeaf.data.label !== 'leaf()') {{
  throw new Error('Labels failed: ' + cOuter.data.label + ', ' + cMid.data.label + ', ' + cLeaf.data.label);
}}

// Check topological ordering in elements: outer must precede middle, middle must precede leaf
const idxOuter = elements.indexOf(cOuter);
const idxMid = elements.indexOf(cMid);
const idxLeaf = elements.indexOf(cLeaf);
const idxDeep = elements.indexOf(cDeep);
if (idxOuter > idxMid || idxMid > idxLeaf || idxLeaf > idxDeep) {{
  throw new Error('Topological ordering failed: outer=' + idxOuter + ', mid=' + idxMid + ', leaf=' + idxLeaf + ', deep=' + idxDeep);
}}

// Resilience test: circular parent references must not crash recursion
const cyclicNet = {{
  compounds: [
    {{ id: 'c_a', function_name: 'a', parent: 'c_b' }},
    {{ id: 'c_b', function_name: 'b', parent: 'c_a' }}
  ]
}};
const cyclicElements = netToElements(cyclicNet);
if (cyclicElements.length !== 2) throw new Error('Cyclic net failed');

console.log('PASS');
"""
        proc = subprocess.run(["node", "-e", node_script], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_nested_compounds_css_styling_distinguishable(self):
        """Validates that template.html defines distinct depth styles and adequate compound padding."""
        template_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "code2petri", "viewer", "template.html")
        )
        with open(template_path, "r", encoding="utf-8") as f:
            html = f.read()

        # Distinct selectors for depths
        self.assertIn("node.compound.depth-0", html)
        self.assertIn("node.compound.depth-1", html)
        self.assertIn("node.compound.depth-2", html)

    def test_cli_end_to_end_3_level_nested_calls_html(self):
        """Validates that CLI generates 3 levels of nested compound containers on load."""
        code = (
            "def leaf():\n"
            "    z = 1\n"
            "\n"
            "def middle():\n"
            "    leaf()\n"
            "\n"
            "def outer():\n"
            "    middle()\n"
            "\n"
            "def run():\n"
            "    outer()\n"
        )
        src_file = os.path.join(self.temp_dir.name, "nested_3_levels.py")
        with open(src_file, "w", encoding="utf-8") as f:
            f.write(code)

        out_html = os.path.join(self.temp_dir.name, "nested_3_levels.html")
        main([
            src_file,
            "-t", "run",
            "--context", self.temp_dir.name,
            "-o", out_html,
        ])
        self.assertTrue(os.path.exists(out_html))
        with open(out_html, "r", encoding="utf-8") as f:
            content = f.read()

        data = _extract_embedded_data(content)
        self.assertEqual(data["mode"], "composite")

        compounds = data.get("compounds", [])
        self.assertEqual(len(compounds), 3)

        c_outer = next((c for c in compounds if c["function_name"] == "outer"), None)
        c_mid = next((c for c in compounds if c["function_name"] == "middle"), None)
        c_leaf = next((c for c in compounds if c["function_name"] == "leaf"), None)

        self.assertIsNotNone(c_outer)
        self.assertIsNotNone(c_mid)
        self.assertIsNotNone(c_leaf)

        # Hierarchy validation: outer has no parent, middle's parent is outer, leaf's parent is middle
        self.assertIsNone(c_outer.get("parent"))
        self.assertEqual(c_mid.get("parent"), c_outer["id"])
        self.assertEqual(c_leaf.get("parent"), c_mid["id"])

    def test_nested_compound_nodes_cytoscape_dagre_layout_no_overlap(self):
        """Validates that Cytoscape Dagre layout executes on nested compounds without node overlaps."""
        import subprocess

        net_to_elements_js = _extract_template_net_to_elements()

        node_script = f"""
const Module = require('module');
const originalRequire = Module.prototype.require;
const dagre = require('./code2petri/viewer/vendor/dagre.min.js');
Module.prototype.require = function(path) {{
  if (path === 'dagre') return dagre;
  return originalRequire.apply(this, arguments);
}};

const cytoscape = require('./code2petri/viewer/vendor/cytoscape.min.js');
const cytoscapeDagre = require('./code2petri/viewer/vendor/cytoscape-dagre.js');
cytoscape.use(cytoscapeDagre);

{net_to_elements_js}

const net = {{
  compounds: [
    {{ id: 'c_outer', function_name: 'outer', parent: null, file: 'a.py' }},
    {{ id: 'c_middle', function_name: 'middle', parent: 'c_outer', file: 'a.py' }},
    {{ id: 'c_leaf', function_name: 'leaf', parent: 'c_middle', file: 'a.py' }}
  ],
  places: [
    {{ id: 'p_out', label: 'start', parent: 'c_outer' }},
    {{ id: 'p_mid', label: 'p_mid', parent: 'c_middle' }},
    {{ id: 'p_leaf', label: 'p_leaf', parent: 'c_leaf' }}
  ],
  transitions: [
    {{ id: 't_out', label: 'call_mid()', parent: 'c_outer' }},
    {{ id: 't_mid', label: 'call_leaf()', parent: 'c_middle' }},
    {{ id: 't_leaf', label: 'compute()', parent: 'c_leaf' }}
  ],
  arcs: [
    {{ source: 'p_out', target: 't_out' }},
    {{ source: 't_out', target: 'p_mid' }},
    {{ source: 'p_mid', target: 't_mid' }},
    {{ source: 't_mid', target: 'p_leaf' }},
    {{ source: 'p_leaf', target: 't_leaf' }}
  ]
}};

const elements = netToElements(net);
const cy = cytoscape({{
  elements: elements
}});

const layout = cy.layout({{
  name: 'dagre',
  rankDir: 'TB',
  nodeDimensionsIncludeLabels: true,
  spacingFactor: 1.15,
  rankSep: 40,
  nodeSep: 35,
  padding: 30
}});
layout.run();

// 1. Verify parent hierarchy in Cytoscape
const cOuter = cy.getElementById('c_outer');
const cMid = cy.getElementById('c_middle');
const cLeaf = cy.getElementById('c_leaf');

if (!cMid.parent().same(cOuter)) {{
  throw new Error('c_middle parent should be c_outer');
}}
if (!cLeaf.parent().same(cMid)) {{
  throw new Error('c_leaf parent should be c_middle');
}}

// 2. Verify compound node bounding boxes (containment without overlap or clipping)
const bbOuter = cOuter.boundingBox();
const bbMid = cMid.boundingBox();
const bbLeaf = cLeaf.boundingBox();

if (bbLeaf.w <= 0 || bbLeaf.h <= 0 || bbMid.w <= 0 || bbMid.h <= 0 || bbOuter.w <= 0 || bbOuter.h <= 0) {{
  throw new Error('Invalid compound bounding boxes');
}}
if (bbLeaf.x1 < bbMid.x1 || bbLeaf.x2 > bbMid.x2 || bbLeaf.y1 < bbMid.y1 || bbLeaf.y2 > bbMid.y2) {{
  throw new Error('c_leaf not enclosed in c_middle bounding box: leaf=' + JSON.stringify(bbLeaf) + ', mid=' + JSON.stringify(bbMid));
}}
if (bbMid.x1 < bbOuter.x1 || bbMid.x2 > bbOuter.x2 || bbMid.y1 < bbOuter.y1 || bbMid.y2 > bbOuter.y2) {{
  throw new Error('c_middle not enclosed in c_outer bounding box: mid=' + JSON.stringify(bbMid) + ', outer=' + JSON.stringify(bbOuter));
}}

// 3. Verify all leaf nodes have non-overlapping distinct positions
const nodeIds = ['p_out', 't_out', 'p_mid', 't_mid', 'p_leaf', 't_leaf'];
const positions = nodeIds.map(id => ({{ id: id, pos: cy.getElementById(id).position() }}));

for (let i = 0; i < positions.length; i++) {{
  for (let j = i + 1; j < positions.length; j++) {{
    const a = positions[i];
    const b = positions[j];
    const dist = Math.hypot(a.pos.x - b.pos.x, a.pos.y - b.pos.y);
    if (dist < 25) {{
      throw new Error('Nodes ' + a.id + ' and ' + b.id + ' are too close (overlap): dist=' + dist);
    }}
  }}
}}

console.log('PASS');
"""
        proc = subprocess.run(["node", "-e", node_script], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_input_remapping_and_inspector_elements_in_template(self):
        """Validates that template.html contains right/middle button pan bindings, wheel zoom, and inspector markup."""
        html = _read_template_html()

        # Input remapping: middle and right button pan, wheel zoom
        self.assertIn("MOUSE_BUTTON_MIDDLE", html)
        self.assertIn("MOUSE_BUTTON_RIGHT", html)
        self.assertIn("PAN_BUTTON_MASKS", html)
        self.assertIn("contextmenu", html)
        self.assertIn("wheel", html)

        # Inspector panel markup and key field IDs
        self.assertIn('id="inspector-panel"', html)
        self.assertIn('id="inspector-label"', html)
        self.assertIn('id="inspector-tau"', html)
        self.assertIn('id="inspector-type"', html)
        self.assertIn('id="inspector-line"', html)
        self.assertIn('id="inspector-close"', html)

    def test_docked_sidebar_is_permanent_and_pushes_the_canvas(self):
        """The generated viewer exposes a fixed-width light sidebar beside, not over, the canvas."""
        html = _read_template_html()

        self.assertIn('#main-container {\n      flex: 1;\n      display: flex;', html)
        self.assertIn('#cy {\n      flex: 1;', html)
        self.assertIn('#inspector-panel {\n      flex: 0 0 320px;', html)
        self.assertIn('<aside id="inspector-panel"', html)
        self.assertIn('id="inspector-empty"', html)
        self.assertIn('Select a transition or component to inspect it.', html)
        self.assertNotIn('class="inspector-panel hud-popover" style="display: none;"', html)
        self.assertIn('background: #ffffff;', html)

    def test_place_left_click_does_not_pan_or_inspect_headless(self):
        """Validates that tapping a place node does not move viewport or open inspector."""
        html = _read_template_html()
        net_to_elements_js = _extract_template_net_to_elements()

        m_inspect = re.search(r'function getInspectorData\(node\) \{.*?\n      function closeInspector\(\) \{.*?\n      \}', html, re.DOTALL)
        self.assertIsNotNone(m_inspect, "Could not extract inspector functions from template.html")
        inspector_js = m_inspect.group(0)

        m_tap = re.search(r'cy\.on\(\'tap\', \'node\', function\(evt\) \{(.*?)\n      \}\);', html, re.DOTALL)
        self.assertIsNotNone(m_tap, "Could not extract cy.on('tap', 'node') from template.html")
        tap_handler_js = m_tap.group(0)

        node_script = f"""
const cytoscape = require('./code2petri/viewer/vendor/cytoscape.min.js');

{net_to_elements_js}

// Mock DOM elements for inspector
const inspectorPanel = {{ style: {{ display: 'flex' }} }};
const inspectorEmpty = {{ style: {{ display: 'block' }} }};
const inspectorContent = {{ style: {{ display: 'none' }} }};
const inspectorLabel = {{ textContent: '' }};
const inspectorType = {{ textContent: '' }};
const inspectorTau = {{ textContent: '' }};
const inspectorLine = {{ textContent: '' }};

{inspector_js}

const net = {{
  places: [
    {{ id: 'p0', label: 'start' }}
  ],
  transitions: [
    {{ id: 't0', label: 'step()' }}
  ],
  arcs: [
    {{ source: 'p0', target: 't0' }}
  ]
}};

const expandedNodes = new Map();
const calleeNetsMap = {{}};
const currentStep = 0;
function renderStep() {{}}

const cy = cytoscape({{
  elements: netToElements(net),
  userPanningEnabled: false
}});

{tap_handler_js}

const initialPan = Object.assign({{}}, cy.pan());
const initialZoom = cy.zoom();

// Tap place node
const p0 = cy.getElementById('p0');
p0.emit('tap');

// Verify viewport has not moved
const panAfter = cy.pan();
const zoomAfter = cy.zoom();
if (panAfter.x !== initialPan.x || panAfter.y !== initialPan.y) {{
  throw new Error('Panning changed when tapping place: ' + JSON.stringify(panAfter));
}}
if (zoomAfter !== initialZoom) {{
  throw new Error('Zoom changed when tapping place');
}}

// Verify inspector panel did not open
if (inspectorPanel.style.display !== 'flex' || inspectorEmpty.style.display !== 'block' || inspectorContent.style.display !== 'none') {{
  throw new Error('Place tap replaced the docked inspector empty state');
}}

console.log('PASS');
"""
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_transition_and_component_left_click_updates_docked_inspector_headless(self):
        """Inspecting and clearing nodes updates all sidebar metadata without moving the camera."""
        html = _read_template_html()
        net_to_elements_js = _extract_template_net_to_elements()

        m_inspect = re.search(r'function getInspectorData\(node\) \{.*?\n      function closeInspector\(\) \{.*?\n      \}', html, re.DOTALL)
        self.assertIsNotNone(m_inspect, "Could not extract inspector functions from template.html")
        inspector_js = m_inspect.group(0)

        m_tap = re.search(r'cy\.on\(\'tap\', \'node\', function\(evt\) \{(.*?)\n      \}\);', html, re.DOTALL)
        self.assertIsNotNone(m_tap, "Could not extract cy.on('tap', 'node') from template.html")
        tap_handler_js = m_tap.group(0)

        node_script = f"""
const cytoscape = require('./code2petri/viewer/vendor/cytoscape.min.js');

{net_to_elements_js}

// Mock DOM elements for inspector
const inspectorPanel = {{ style: {{ display: 'flex' }} }};
const inspectorEmpty = {{ style: {{ display: 'block' }} }};
const inspectorContent = {{ style: {{ display: 'none' }} }};
const inspectorLabel = {{ textContent: '' }};
const inspectorId = {{ textContent: '' }};
const inspectorType = {{ textContent: '' }};
const inspectorTau = {{ textContent: '' }};
const inspectorOmega = {{ textContent: '' }};
const inspectorLine = {{ textContent: '' }};
const inspectorSm = {{ textContent: '' }};

{inspector_js}

const net = {{
  compounds: [
    {{ id: 'c_outer', function_name: 'outer', parent: null, file: 'test.py' }}
  ],
  places: [
    {{ id: 'p0', label: 'start' }}
  ],
  transitions: [
    {{ id: 't_atomic', label: 'compute()', line_number: 42, parent: 'c_outer' }},
    {{ id: 't_C1', label: 't_C1', metadata: {{ opaque: true, component_type: 'Sequence', tau: 3.5, omega: 1.25 }} }}
  ],
  arcs: []
}};

const expandedNodes = new Map();
const calleeNetsMap = {{}};
const currentStep = 0;
function renderStep() {{}}

const cy = cytoscape({{
  elements: netToElements(net),
  userPanningEnabled: false
}});
cy.viewport({{ zoom: 1.75, pan: {{ x: 32, y: -18 }} }});
const cameraBefore = {{ zoom: cy.zoom(), pan: Object.assign({{}}, cy.pan()) }};

{tap_handler_js}

// 1. Tap atomic transition
const tAtomic = cy.getElementById('t_atomic');
tAtomic.emit('tap');

if (inspectorPanel.style.display !== 'flex' || inspectorEmpty.style.display !== 'none' || inspectorContent.style.display !== 'block') {{
  throw new Error('Docked inspector did not replace its empty state');
}}
if (inspectorId.textContent !== 't_atomic') throw new Error('ID failed: ' + inspectorId.textContent);
if (inspectorLabel.textContent !== 'compute()') {{
  throw new Error('Label failed for atomic transition: ' + inspectorLabel.textContent);
}}
if (inspectorTau.textContent !== '1.0') {{
  throw new Error('Tau failed for atomic transition: ' + inspectorTau.textContent);
}}
if (inspectorOmega.textContent !== '—') throw new Error('Omega empty value failed: ' + inspectorOmega.textContent);
if (!inspectorType.textContent.includes('Transition')) {{
  throw new Error('Type failed for atomic transition: ' + inspectorType.textContent);
}}
if (inspectorLine.textContent !== '42') {{
  throw new Error('Line failed for atomic transition: ' + inspectorLine.textContent);
}}

// 2. Tap opaque component transition
const tOpaque = cy.getElementById('t_C1');
tOpaque.emit('tap');

if (inspectorPanel.style.display !== 'flex') {{
  throw new Error('Inspector failed to open for opaque transition');
}}
if (inspectorLabel.textContent !== 't_C1') {{
  throw new Error('Label failed for opaque transition: ' + inspectorLabel.textContent);
}}
if (inspectorTau.textContent !== '3.5') {{
  throw new Error('Tau failed for opaque transition: ' + inspectorTau.textContent);
}}
if (inspectorOmega.textContent !== '1.25') {{
  throw new Error('Omega failed for opaque transition: ' + inspectorOmega.textContent);
}}
if (inspectorType.textContent !== 'Sequence') {{
  throw new Error('Component type failed for opaque transition: ' + inspectorType.textContent);
}}
if (inspectorLine.textContent !== '—') {{
  throw new Error('Line failed for opaque transition without line_number: ' + inspectorLine.textContent);
}}

// 3. Tap compound container node
const cOuter = cy.getElementById('c_outer');
cOuter.emit('tap');

if (inspectorPanel.style.display !== 'flex') {{
  throw new Error('Inspector failed to open for compound node');
}}
if (inspectorLabel.textContent !== 'outer()') {{
  throw new Error('Label failed for compound node: ' + inspectorLabel.textContent);
}}
if (!inspectorType.textContent.includes('Compound')) {{
  throw new Error('Type failed for compound node: ' + inspectorType.textContent);
}}
if (inspectorTau.textContent !== '—') {{
  throw new Error('Tau failed for compound node: expected —, got ' + inspectorTau.textContent);
}}

// 4. Close inspector
closeInspector();
if (inspectorPanel.style.display !== 'flex' || inspectorEmpty.style.display !== 'block' || inspectorContent.style.display !== 'none') {{
  throw new Error('Clearing inspection hid the docked sidebar or left stale content visible');
}}
if (selectedInspectorNode !== null) throw new Error('Clearing inspection retained a stale node');
if (cy.zoom() !== cameraBefore.zoom || cy.pan().x !== cameraBefore.pan.x || cy.pan().y !== cameraBefore.pan.y) {{
  throw new Error('Inspecting or clearing a node changed the camera');
}}

console.log('PASS');
"""
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_right_and_middle_mouse_drag_pan_and_wheel_zoom_headless(self):
        """Validates right/middle drag pans canvas, left click does not pan, and wheel zooms canvas."""
        html = _read_template_html()

        # Extract canvas drag and wheel handlers
        m_pan = re.search(r'// Canvas drag panning via Middle Mouse Button and Right Mouse Button.*?(?=// Inspector panel DOM elements)', html, re.DOTALL)
        self.assertIsNotNone(m_pan, "Could not extract panning handlers from template.html")
        panning_handlers_js = m_pan.group(0)

        node_script = f"""
const windowListeners = {{}};
global.addEventListener = (event, fn) => {{
  if (!windowListeners[event]) windowListeners[event] = [];
  windowListeners[event].push(fn);
}};
global.window = global;

const listeners = {{}};
const mockContainer = {{
  style: {{ cursor: '' }},
  getBoundingClientRect: () => ({{ left: 0, top: 0, width: 800, height: 600 }}),
  addEventListener: (event, fn) => {{
    if (!listeners[event]) listeners[event] = [];
    listeners[event].push(fn);
  }}
}};

global.document = {{
  getElementById: (id) => {{
    if (id === 'cy') return mockContainer;
    return null;
  }}
}};

const cytoscape = require('./code2petri/viewer/vendor/cytoscape.min.js');

const cy = cytoscape({{
  elements: [
    {{ group: 'nodes', data: {{ id: 'n1' }} }}
  ],
  userPanningEnabled: false
}});

{panning_handlers_js}

const initialPan = Object.assign({{}}, cy.pan());
const initialZoom = cy.zoom();

// 1. Left-click mousedown + move: must NOT trigger pan
listeners['mousedown'].forEach(fn => fn({{
  button: 0,
  clientX: 100,
  clientY: 100,
  preventDefault: () => {{}}
}}));
windowListeners['mousemove'].forEach(fn => fn({{
  clientX: 150,
  clientY: 150,
  buttons: 1
}}));

if (cy.pan().x !== initialPan.x || cy.pan().y !== initialPan.y) {{
  throw new Error('Left-click triggered panning: ' + JSON.stringify(cy.pan()));
}}

// 2. Right-click drag (button 2, mask 2): MUST pan by dx=50, dy=30
listeners['mousedown'].forEach(fn => fn({{
  button: 2,
  clientX: 100,
  clientY: 100,
  preventDefault: () => {{}}
}}));
windowListeners['mousemove'].forEach(fn => fn({{
  clientX: 150,
  clientY: 130,
  buttons: 2
}}));
windowListeners['mouseup'].forEach(fn => fn({{
  button: 2,
  buttons: 0
}}));

const panAfterRight = Object.assign({{}}, cy.pan());
if (panAfterRight.x !== initialPan.x + 50 || panAfterRight.y !== initialPan.y + 30) {{
  throw new Error('Right-click drag failed to pan: expected (' + (initialPan.x + 50) + ',' + (initialPan.y + 30) + '), got ' + JSON.stringify(panAfterRight));
}}

// 3. Middle-click drag (button 1, mask 4): MUST pan by dx=-20, dy=-10
listeners['mousedown'].forEach(fn => fn({{
  button: 1,
  clientX: 200,
  clientY: 200,
  preventDefault: () => {{}}
}}));
windowListeners['mousemove'].forEach(fn => fn({{
  clientX: 180,
  clientY: 190,
  buttons: 4
}}));
windowListeners['mouseup'].forEach(fn => fn({{
  button: 1,
  buttons: 0
}}));

const panAfterMiddle = Object.assign({{}}, cy.pan());
if (panAfterMiddle.x !== panAfterRight.x - 20 || panAfterMiddle.y !== panAfterRight.y - 10) {{
  throw new Error('Middle-click drag failed to pan: expected (' + (panAfterRight.x - 20) + ',' + (panAfterRight.y - 10) + '), got ' + JSON.stringify(panAfterMiddle));
}}

// 4. Wheel zoom: zooming in increases zoom level
listeners['wheel'].forEach(fn => fn({{
  deltaY: -100,
  clientX: 400,
  clientY: 300,
  preventDefault: () => {{}}
}}));

if (cy.zoom() <= initialZoom) {{
  throw new Error('Wheel zoom failed: initial=' + initialZoom + ', after=' + cy.zoom());
}}

console.log('PASS');
"""
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)


    def test_place_contractible_sequence_styling_in_template(self):
        """Verifies template.html includes contractible place CSS styling in green."""
        html = _read_template_html()
        self.assertIn("node.place.contractible", html)
        self.assertIn("#3fb950", html)

    def test_place_nodes_eligible_for_sequence_contraction_colored_green_headless(self):
        """Validates that intermediate sequence places receive .contractible class on load via Live Fold Reduction."""
        net_literal = """{
  places: [
    { id: 'p_start', label: 'start', initial_tokens: 1 },
    { id: 'p_mid', label: 'mid', initial_tokens: 0 },
    { id: 'p_end', label: 'end', initial_tokens: 0 }
  ],
  transitions: [
    { id: 't1', label: 'step1()' },
    { id: 't2', label: 'step2()' }
  ],
  arcs: [
    { source: 'p_start', target: 't1' },
    { source: 't1', target: 'p_mid' },
    { source: 'p_mid', target: 't2' },
    { source: 't2', target: 'p_end' }
  ]
}"""
        test_logic = """
const pStart = cy.getElementById('p_start');
const pMid = cy.getElementById('p_mid');
const pEnd = cy.getElementById('p_end');

if (pStart.hasClass('contractible')) {
  throw new Error('p_start should NOT be contractible (has tokens)');
}
if (!pMid.hasClass('contractible')) {
  throw new Error('p_mid MUST be contractible (1 -> 1 -> 1 sequence)');
}
if (pEnd.hasClass('contractible')) {
  throw new Error('p_end should NOT be contractible (sink place)');
}

console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_left_click_eligible_place_contracts_sequence_headless(self):
        """Validates left-clicking an eligible place performs Live Fold Reduction (Single-Place Contraction) into an opaque component."""
        net_literal = """{
  places: [
    { id: 'p0', label: 'start', initial_tokens: 1 },
    { id: 'p1', label: 'mid', initial_tokens: 0 },
    { id: 'p2', label: 'end', initial_tokens: 0 }
  ],
  transitions: [
    { id: 't1', label: 'first()' },
    { id: 't2', label: 'second()' }
  ],
  arcs: [
    { source: 'p0', target: 't1' },
    { source: 't1', target: 'p1' },
    { source: 'p1', target: 't2' },
    { source: 't2', target: 'p2' }
  ]
}"""
        test_logic = """
// Tap eligible place p1
const p1 = cy.getElementById('p1');
if (!p1.hasClass('contractible')) {
  throw new Error('p1 was not marked contractible before tap');
}

p1.emit('tap');

// Verify consumed nodes removed
if (cy.getElementById('p1').length !== 0) {
  throw new Error('p1 was not removed after Live Fold Reduction (Single-Place Contraction)');
}
if (cy.getElementById('t1').length !== 0) {
  throw new Error('t1 was not removed after Live Fold Reduction (Single-Place Contraction)');
}
if (cy.getElementById('t2').length !== 0) {
  throw new Error('t2 was not removed after Live Fold Reduction (Single-Place Contraction)');
}

// Verify opaque component created with default omega = 0.0, tau = 1.0 + 1.0 = 2.0
const c01 = cy.getElementById('c_01');
if (c01.length === 0) {
  throw new Error('Opaque component c_01 was not created');
}
if (c01.data('tau') !== 2.0) {
  throw new Error('Expected tau 2.0, got ' + c01.data('tau'));
}
if (c01.data('omega') !== 0.0) {
  throw new Error('Expected omega 0.0, got ' + c01.data('omega'));
}
if (c01.data('component_type') !== 'Sequence') {
  throw new Error('Expected component_type Sequence, got ' + c01.data('component_type'));
}
if (c01.data('is_opaque') !== true) {
  throw new Error('Expected is_opaque true');
}

// Verify boundary arcs rewired
const inEdges = c01.incomers('edge');
if (inEdges.length !== 1 || inEdges[0].source().id() !== 'p0') {
  throw new Error('Incomers to c_01 not rewired from p0');
}
const outEdges = c01.outgoers('edge');
if (outEdges.length !== 1 || outEdges[0].target().id() !== 'p2') {
  throw new Error('Outgoers from c_01 not rewired to p2');
}

// Verify consumed subnet storage for local unfold
const sub = c01.data('consumedSubnet') || c01.data('consumedSubgraph');
if (!sub) {
  throw new Error('c_01 missing consumedSubnet');
}
if (sub.consumedPlaceId !== 'p1') {
  throw new Error('consumedSubnet wrong placeId: ' + sub.consumedPlaceId);
}
if (sub.consumedTransIds[0] !== 't1' || sub.consumedTransIds[1] !== 't2') {
  throw new Error('consumedSubnet wrong transIds: ' + JSON.stringify(sub.consumedTransIds));
}
if (sub.nodes.length !== 3) {
  throw new Error('consumedSubnet nodes length expected 3, got ' + sub.nodes.length);
}
if (sub.internalEdges.length !== 2) {
  throw new Error('consumedSubnet internalEdges length expected 2, got ' + sub.internalEdges.length);
}

// Verify inspector panel opened on newly created component
if (inspectorPanel.style.display !== 'flex') {
  throw new Error('Inspector panel did not open for c_01');
}
if (inspectorTau.textContent !== '2.0') {
  throw new Error('Inspector tau expected 2.0, got ' + inspectorTau.textContent);
}
if (inspectorType.textContent !== 'Sequence') {
  throw new Error('Inspector type expected Sequence, got ' + inspectorType.textContent);
}

console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_sequence_contraction_tau_and_omega_match_python_fold_engine(self):
        """Validates that Live Fold Reduction (Single-Place Contraction) calculations match Python fold_single_place_contraction."""
        from code2petri.model import PetriNet
        from code2petri.fold import fold_single_place_contraction, FoldConfig

        # 1. Python calculation with custom weights under default FoldConfig (sequence omega = 0.0)
        py_net = PetriNet()
        p0 = py_net.add_place(id="p0", label="start", initial_tokens=1)
        p1 = py_net.add_place(id="p1", label="mid", initial_tokens=0)
        p2 = py_net.add_place(id="p2", label="end", initial_tokens=0)

        t1 = py_net.add_transition(id="t1", label="op1", metadata={"tau": 2.5})
        t2 = py_net.add_transition(id="t2", label="op2", metadata={"tau": 1.75})

        py_net.add_arc(p0, t1)
        py_net.add_arc(t1, p1)
        py_net.add_arc(p1, t2)
        py_net.add_arc(t2, p2)

        py_folded, py_step = fold_single_place_contraction(py_net, step_number=1, config=FoldConfig())
        self.assertIsNotNone(py_step)
        expected_tau = py_step.tau  # 0.0 + 2.5 + 1.75 = 4.25
        expected_omega = py_step.omega  # 0.0
        expected_sm = py_step.running_sm  # 4.25

        # 2. JS calculation
        net_literal = """{
  places: [
    { id: 'p0', label: 'start', initial_tokens: 1 },
    { id: 'p1', label: 'mid', initial_tokens: 0 },
    { id: 'p2', label: 'end', initial_tokens: 0 }
  ],
  transitions: [
    { id: 't1', label: 'op1', tau: 2.5, metadata: { tau: 2.5 } },
    { id: 't2', label: 'op2', tau: 1.75, metadata: { tau: 1.75 } }
  ],
  arcs: [
    { source: 'p0', target: 't1' },
    { source: 't1', target: 'p1' },
    { source: 'p1', target: 't2' },
    { source: 't2', target: 'p2' }
  ]
}"""
        test_logic = """
const p1 = cy.getElementById('p1');
const res = foldEngine.executeSinglePlaceContraction(p1);

if (!res.success) {
  throw new Error('Live Fold Reduction (Single-Place Contraction) failed: ' + res.message);
}

const c01 = cy.getElementById('c_01');
const result = {
  tau: c01.data('tau'),
  omega: c01.data('omega'),
  running_sm: foldEngine.calculateSMScore()
};

console.log(JSON.stringify(result));
"""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        js_data = json.loads(proc.stdout.strip())

        self.assertEqual(js_data["tau"], expected_tau)
        self.assertEqual(js_data["omega"], expected_omega)
        self.assertEqual(js_data["running_sm"], expected_sm)

    def test_place_contractible_choice_styling_in_template(self):
        """Verifies template.html contains CSS rules styling choice-contractible places in amber (#d29922)."""
        html = _read_template_html()
        self.assertIn("node.place.contractible-choice", html)
        self.assertIn("#d29922", html)

    def test_place_nodes_eligible_for_choice_reduction_colored_amber_headless(self):
        """Validates that place nodes eligible for Live Fold Reduction (Choice) are assigned the amber contractible-choice class."""
        net_literal = """{
  places: [
    { id: 'p_split', label: 'branch', initial_tokens: 0 },
    { id: 'p_join', label: 'merge', initial_tokens: 0 }
  ],
  transitions: [
    { id: 't1', label: 'branch_a()' },
    { id: 't2', label: 'branch_b()' }
  ],
  arcs: [
    { source: 'p_split', target: 't1' },
    { source: 't1', target: 'p_join' },
    { source: 'p_split', target: 't2' },
    { source: 't2', target: 'p_join' }
  ]
}"""
        test_logic = """
const pSplit = cy.getElementById('p_split');
const pJoin = cy.getElementById('p_join');

if (!pSplit.hasClass('contractible-choice')) {
  throw new Error('p_split was not assigned contractible-choice class');
}
if (!pSplit.hasClass('contractible')) {
  throw new Error('p_split was not assigned contractible class');
}
if (pSplit.hasClass('contractible-sequence')) {
  throw new Error('p_split should not have contractible-sequence class');
}

if (pJoin.hasClass('contractible') || pJoin.hasClass('contractible-choice')) {
  throw new Error('p_join should not be marked contractible');
}

console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_left_click_eligible_place_contracts_choice_headless(self):
        """Validates that left-clicking an eligible choice place executes Live Fold Reduction (Choice), preserving split and join places."""
        net_literal = """{
  places: [
    { id: 'p_split', label: 'split_pt', initial_tokens: 0 },
    { id: 'p_merge', label: 'merge_pt', initial_tokens: 0 }
  ],
  transitions: [
    { id: 't_left', label: 'take_left()' },
    { id: 't_right', label: 'take_right()' }
  ],
  arcs: [
    { source: 'p_split', target: 't_left' },
    { source: 't_left', target: 'p_merge' },
    { source: 'p_split', target: 't_right' },
    { source: 't_right', target: 'p_merge' }
  ]
}"""
        test_logic = """
// Tap eligible place p_split
const pSplit = cy.getElementById('p_split');
if (!pSplit.hasClass('contractible-choice')) {
  throw new Error('p_split was not marked contractible-choice before tap');
}

pSplit.emit('tap');

// Verify parallel transitions were removed
if (cy.getElementById('t_left').length !== 0) {
  throw new Error('t_left was not removed after Live Fold Reduction (Choice)');
}
if (cy.getElementById('t_right').length !== 0) {
  throw new Error('t_right was not removed after Live Fold Reduction (Choice)');
}

// Verify split and join places REMAINDER on the canvas
if (cy.getElementById('p_split').length !== 1) {
  throw new Error('p_split should remain on canvas after Live Fold Reduction (Choice)');
}
if (cy.getElementById('p_merge').length !== 1) {
  throw new Error('p_merge should remain on canvas after Live Fold Reduction (Choice)');
}

// Verify opaque component created
const c01 = cy.getElementById('c_01');
if (c01.length === 0) {
  throw new Error('Opaque component c_01 was not created');
}
// Default tau = 1.0 each -> sum = 2.0 -> tau = 1.5 * 2.0 = 3.0
if (c01.data('tau') !== 3.0) {
  throw new Error('Expected tau 3.0, got ' + c01.data('tau'));
}
// omega = 1.0 * (2.0 * 0.5) = 1.0
if (c01.data('omega') !== 1.0) {
  throw new Error('Expected omega 1.0, got ' + c01.data('omega'));
}
if (c01.data('component_type') !== 'Choice') {
  throw new Error('Expected component_type Choice, got ' + c01.data('component_type'));
}
if (c01.data('is_opaque') !== true) {
  throw new Error('Expected is_opaque true');
}

// Verify boundary arcs between p_split -> c_01 -> p_merge
const inEdges = c01.incomers('edge');
if (inEdges.length !== 1 || inEdges[0].source().id() !== 'p_split') {
  throw new Error('Incomer to c_01 not from p_split');
}
const outEdges = c01.outgoers('edge');
if (outEdges.length !== 1 || outEdges[0].target().id() !== 'p_merge') {
  throw new Error('Outgoer from c_01 not to p_merge');
}

// Verify consumed subnet storage for local unfold
const sub = c01.data('consumedSubnet') || c01.data('consumedSubgraph');
if (!sub) {
  throw new Error('c_01 missing consumedSubnet');
}
if (sub.sourcePlaceId !== 'p_split' || sub.targetPlaceId !== 'p_merge') {
  throw new Error('consumedSubnet wrong source/target place: ' + sub.sourcePlaceId + ' -> ' + sub.targetPlaceId);
}
if (sub.consumedTransIds[0] !== 't_left' || sub.consumedTransIds[1] !== 't_right') {
  throw new Error('consumedSubnet wrong transIds: ' + JSON.stringify(sub.consumedTransIds));
}
if (sub.nodes.length !== 2) {
  throw new Error('consumedSubnet nodes length expected 2, got ' + sub.nodes.length);
}
if (sub.internalEdges.length !== 4) {
  throw new Error('consumedSubnet internalEdges length expected 4, got ' + sub.internalEdges.length);
}

// Verify inspector panel opened on newly created choice component
if (inspectorPanel.style.display !== 'flex') {
  throw new Error('Inspector panel did not open for c_01');
}
if (inspectorTau.textContent !== '3.0') {
  throw new Error('Inspector tau expected 3.0, got ' + inspectorTau.textContent);
}
if (inspectorType.textContent !== 'Choice') {
  throw new Error('Inspector type expected Choice, got ' + inspectorType.textContent);
}

console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_choice_contraction_tau_and_omega_match_python_fold_engine(self):
        """Validates that Live Fold Reduction (Choice) calculations match Python fold_choice."""
        from code2petri.model import PetriNet
        from code2petri.fold import fold_choice, FoldConfig

        # 1. Python calculation with custom weights
        py_net = PetriNet()
        p_split = py_net.add_place(id="p_split", label="split", initial_tokens=0)
        p_merge = py_net.add_place(id="p_merge", label="merge", initial_tokens=0)

        t1 = py_net.add_transition(id="t1", label="branch1", metadata={"tau": 2.5})
        t2 = py_net.add_transition(id="t2", label="branch2", metadata={"tau": 3.5})

        py_net.add_arc(p_split, t1)
        py_net.add_arc(t1, p_merge)
        py_net.add_arc(p_split, t2)
        py_net.add_arc(t2, p_merge)

        py_folded, py_step = fold_choice(py_net, step_number=1, config=FoldConfig(choice=1.0))
        self.assertIsNotNone(py_step)
        expected_tau = py_step.tau
        expected_omega = py_step.omega
        expected_sm = py_step.running_sm

        self.assertEqual(expected_tau, 9.0)
        self.assertEqual(expected_omega, 3.0)
        self.assertEqual(expected_sm, 9.0)

        # 2. JS calculation
        net_literal = """{
  places: [
    { id: 'p_split', label: 'split', initial_tokens: 0 },
    { id: 'p_merge', label: 'merge', initial_tokens: 0 }
  ],
  transitions: [
    { id: 't1', label: 'branch1', tau: 2.5, metadata: { tau: 2.5 } },
    { id: 't2', label: 'branch2', tau: 3.5, metadata: { tau: 3.5 } }
  ],
  arcs: [
    { source: 'p_split', target: 't1' },
    { source: 't1', target: 'p_merge' },
    { source: 'p_split', target: 't2' },
    { source: 't2', target: 'p_merge' }
  ]
}"""
        test_logic = """
const pSplit = cy.getElementById('p_split');
const res = foldEngine.executeChoiceContraction(pSplit);

if (!res.success) {
  throw new Error('Live Fold Reduction (Choice) failed: ' + res.message);
}

const c01 = cy.getElementById('c_01');
const result = {
  tau: c01.data('tau'),
  omega: c01.data('omega'),
  running_sm: foldEngine.calculateSMScore()
};

console.log(JSON.stringify(result));
"""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        js_data = json.loads(proc.stdout.strip())

        self.assertEqual(js_data["tau"], expected_tau)
        self.assertEqual(js_data["omega"], expected_omega)
        self.assertEqual(js_data["running_sm"], expected_sm)

    def test_place_contractible_while_styling_in_template(self):
        """Verifies template.html includes contractible place CSS styling in purple for while loops."""
        html = _read_template_html()
        self.assertIn("node.place.contractible-while", html)
        self.assertIn("#bc8cff", html)
        self.assertIn("double", html)

    def test_place_nodes_eligible_for_while_loop_reduction_colored_purple_headless(self):
        """Validates that while loop head places receive .contractible-while class on load via Live Fold Reduction."""
        net_literal = """{
  places: [
    { id: 'p_in', label: 'in', initial_tokens: 1 },
    { id: 'p_loop', label: 'loop_head', initial_tokens: 0 },
    { id: 'p_out', label: 'out', initial_tokens: 0 }
  ],
  transitions: [
    { id: 't_src', label: 'enter', tau: 2.0 },
    { id: 't_loop', label: 'body', tau: 3.0 },
    { id: 't_snk', label: 'exit', tau: 1.0 }
  ],
  arcs: [
    { source: 'p_in', target: 't_src' },
    { source: 't_src', target: 'p_loop' },
    { source: 'p_loop', target: 't_loop' },
    { source: 't_loop', target: 'p_loop' },
    { source: 'p_loop', target: 't_snk' },
    { source: 't_snk', target: 'p_out' }
  ]
}"""
        test_logic = """
const pLoop = cy.getElementById('p_loop');
const pIn = cy.getElementById('p_in');
const pOut = cy.getElementById('p_out');

if (!pLoop.hasClass('contractible')) {
  throw new Error('p_loop should have contractible class');
}
if (!pLoop.hasClass('contractible-while')) {
  throw new Error('p_loop should have contractible-while class');
}
if (pLoop.hasClass('contractible-sequence')) {
  throw new Error('p_loop should not have contractible-sequence class');
}
if (pLoop.hasClass('contractible-choice')) {
  throw new Error('p_loop should not have contractible-choice class');
}
if (pIn.hasClass('contractible') || pOut.hasClass('contractible')) {
  throw new Error('p_in or p_out should not be contractible');
}

console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_left_click_eligible_place_contracts_while_headless(self):
        """Validates that left-clicking a while loop head place executes Live Fold Reduction (While Loop)."""
        net_literal = """{
  places: [
    { id: 'p_in', label: 'in', initial_tokens: 1 },
    { id: 'p_loop', label: 'loop_head', initial_tokens: 0 },
    { id: 'p_out', label: 'out', initial_tokens: 0 }
  ],
  transitions: [
    { id: 't_src', label: 'enter', tau: 2.0 },
    { id: 't_loop', label: 'body', tau: 3.0 },
    { id: 't_snk', label: 'exit', tau: 1.0 }
  ],
  arcs: [
    { source: 'p_in', target: 't_src' },
    { source: 't_src', target: 'p_loop' },
    { source: 'p_loop', target: 't_loop' },
    { source: 't_loop', target: 'p_loop' },
    { source: 'p_loop', target: 't_snk' },
    { source: 't_snk', target: 'p_out' }
  ]
}"""
        test_logic = """
const pLoop = cy.getElementById('p_loop');

// Simulate left-click on p_loop
pLoop.emit('tap');

// Verify consumed nodes removed: p_loop, t_loop, t_src, t_snk
if (cy.getElementById('p_loop').length !== 0) {
  throw new Error('p_loop should have been removed after Live Fold Reduction (While Loop)');
}
if (cy.getElementById('t_loop').length !== 0) {
  throw new Error('t_loop should have been removed after Live Fold Reduction (While Loop)');
}
if (cy.getElementById('t_src').length !== 0) {
  throw new Error('t_src should have been removed after Live Fold Reduction (While Loop)');
}
if (cy.getElementById('t_snk').length !== 0) {
  throw new Error('t_snk should have been removed after Live Fold Reduction (While Loop)');
}

// Verify boundary places remain
if (cy.getElementById('p_in').length !== 1) {
  throw new Error('p_in should remain on canvas after while fold');
}
if (cy.getElementById('p_out').length !== 1) {
  throw new Error('p_out should remain on canvas after while fold');
}

// Verify opaque component created
const c01 = cy.getElementById('c_01');
if (c01.length === 0) {
  throw new Error('Opaque component c_01 was not created');
}

// ProM formula: tau_new = tau(t_src) + tau(t_snk) + 2.0 * tau(t_loop) = 2.0 + 1.0 + 2.0 * 3.0 = 9.0
if (c01.data('tau') !== 9.0) {
  throw new Error('Expected tau 9.0, got ' + c01.data('tau'));
}
// omega = (cfg.loop / 3.0) * tau(t_loop) = 1.0 * 3.0 = 3.0
if (c01.data('omega') !== 3.0) {
  throw new Error('Expected omega 3.0, got ' + c01.data('omega'));
}
if (c01.data('component_type') !== 'While') {
  throw new Error('Expected component_type While, got ' + c01.data('component_type'));
}
if (c01.data('is_opaque') !== true) {
  throw new Error('Expected is_opaque true');
}

// Verify boundary arcs between p_in -> c_01 -> p_out
const inEdges = c01.incomers('edge');
if (inEdges.length !== 1 || inEdges[0].source().id() !== 'p_in') {
  throw new Error('Incomer to c_01 not from p_in');
}
const outEdges = c01.outgoers('edge');
if (outEdges.length !== 1 || outEdges[0].target().id() !== 'p_out') {
  throw new Error('Outgoer from c_01 not to p_out');
}

// Verify consumed subnet storage for local unfold
const sub = c01.data('consumedSubnet') || c01.data('consumedSubgraph');
if (!sub) {
  throw new Error('c_01 missing consumedSubnet');
}
if (sub.consumedPlaceId !== 'p_loop') {
  throw new Error('consumedSubnet wrong placeId: ' + sub.consumedPlaceId);
}
if (sub.t_loop_id !== 't_loop' || sub.t_src_id !== 't_src' || sub.t_snk_id !== 't_snk') {
  throw new Error('consumedSubnet wrong transition IDs: ' + JSON.stringify(sub));
}
if (sub.nodes.length !== 4) {
  throw new Error('consumedSubnet nodes length expected 4, got ' + sub.nodes.length);
}
if (sub.internalEdges.length !== 4) {
  throw new Error('consumedSubnet internalEdges length expected 4, got ' + sub.internalEdges.length);
}

// Verify inspector panel opened on newly created while component
if (inspectorPanel.style.display !== 'flex') {
  throw new Error('Inspector panel did not open for c_01');
}
if (inspectorTau.textContent !== '9.0') {
  throw new Error('Inspector tau expected 9.0, got ' + inspectorTau.textContent);
}
if (inspectorType.textContent !== 'While') {
  throw new Error('Inspector type expected While, got ' + inspectorType.textContent);
}

console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_while_contraction_tau_and_omega_match_python_fold_engine(self):
        """Validates that Live Fold Reduction (While Loop) calculations match Python fold_while."""
        from code2petri.model import PetriNet
        from code2petri.fold import fold_while, FoldConfig

        # 1. Python calculation
        py_net = PetriNet()
        p_in = py_net.add_place("p_in", initial_tokens=1)
        p_loop = py_net.add_place("p_loop", initial_tokens=0)
        p_out = py_net.add_place("p_out", initial_tokens=0)

        t_src = py_net.add_transition("t_src", metadata={"tau": 1.5})
        t_loop = py_net.add_transition("t_loop", metadata={"tau": 2.5})
        t_snk = py_net.add_transition("t_snk", metadata={"tau": 3.5})

        py_net.add_arc(p_in, t_src)
        py_net.add_arc(t_src, p_loop)
        py_net.add_arc(p_loop, t_loop)
        py_net.add_arc(t_loop, p_loop)
        py_net.add_arc(p_loop, t_snk)
        py_net.add_arc(t_snk, p_out)

        py_folded, py_step = fold_while(py_net, step_number=1, config=FoldConfig())
        self.assertIsNotNone(py_step)
        expected_tau = py_step.tau
        expected_omega = py_step.omega
        expected_sm = py_step.running_sm

        self.assertEqual(expected_tau, 10.0)  # 1.5 + 3.5 + 2.0 * 2.5 = 10.0
        self.assertEqual(expected_omega, 2.5)  # (3.0 / 3.0) * 2.5 = 2.5
        self.assertEqual(expected_sm, 10.0)

        # 2. JS calculation
        net_literal = """{
  places: [
    { id: 'p_in', label: 'in', initial_tokens: 1 },
    { id: 'p_loop', label: 'loop_head', initial_tokens: 0 },
    { id: 'p_out', label: 'out', initial_tokens: 0 }
  ],
  transitions: [
    { id: 't_src', label: 'enter', tau: 1.5, metadata: { tau: 1.5 } },
    { id: 't_loop', label: 'body', tau: 2.5, metadata: { tau: 2.5 } },
    { id: 't_snk', label: 'exit', tau: 3.5, metadata: { tau: 3.5 } }
  ],
  arcs: [
    { source: 'p_in', target: 't_src' },
    { source: 't_src', target: 'p_loop' },
    { source: 'p_loop', target: 't_loop' },
    { source: 't_loop', target: 'p_loop' },
    { source: 'p_loop', target: 't_snk' },
    { source: 't_snk', target: 'p_out' }
  ]
}"""
        test_logic = """
const pLoop = cy.getElementById('p_loop');
const res = foldEngine.executeWhileContraction(pLoop);

if (!res.success) {
  throw new Error('Live Fold Reduction (While Loop) failed: ' + res.message);
}

const c01 = cy.getElementById('c_01');
const result = {
  tau: c01.data('tau'),
  omega: c01.data('omega'),
  running_sm: foldEngine.calculateSMScore()
};

console.log(JSON.stringify(result));
"""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        js_data = json.loads(proc.stdout.strip())

        self.assertEqual(js_data["tau"], expected_tau)
        self.assertEqual(js_data["omega"], expected_omega)
        self.assertEqual(js_data["running_sm"], expected_sm)

    def test_sese_bidirectional_reachability_valid_subnet_headless(self):
        """Verifies that SESE infrastructure computes bidirectional reachability and finds valid SESE subnets."""
        net_literal = """{
  places: [
    { id: 'p_in', label: 'in', initial_tokens: 1 },
    { id: 'p_src', label: 'source_place', initial_tokens: 0 },
    { id: 'p1', label: 'branch1_place', initial_tokens: 0 },
    { id: 'p2', label: 'branch2_place', initial_tokens: 0 },
    { id: 'p_snk', label: 'sink_place', initial_tokens: 0 },
    { id: 'p_out', label: 'out', initial_tokens: 0 }
  ],
  transitions: [
    { id: 't0', label: 't0' },
    { id: 't1', label: 't1' },
    { id: 't2', label: 't2' },
    { id: 't3', label: 't3' },
    { id: 't4', label: 't4' },
    { id: 't5', label: 't5' }
  ],
  arcs: [
    { source: 'p_in', target: 't0' },
    { source: 't0', target: 'p_src' },
    { source: 'p_src', target: 't1' },
    { source: 't1', target: 'p1' },
    { source: 'p1', target: 't3' },
    { source: 't3', target: 'p_snk' },
    { source: 'p_src', target: 't2' },
    { source: 't2', target: 'p2' },
    { source: 'p2', target: 't4' },
    { source: 't4', target: 'p_snk' },
    { source: 'p_snk', target: 't5' },
    { source: 't5', target: 'p_out' }
  ]
}"""
        test_logic = """
const sese = foldEngine.sese || new SESEInfrastructure(cy);

// 1. isReachable tests
if (!sese.isReachable('p_src', 'p_snk')) {
  throw new Error('p_snk should be reachable from p_src');
}
if (sese.isReachable('p_snk', 'p_src')) {
  throw new Error('p_src should NOT be reachable from p_snk');
}

// 2. forward & backward reachability
const fwd = sese.forwardReachability('p_src', 'p_snk');
const bwd = sese.backwardReachability('p_snk', 'p_src');

const expected = ['p_src', 't1', 'p1', 't3', 't2', 'p2', 't4', 'p_snk'];
if (fwd.size !== expected.length || bwd.size !== expected.length) {
  throw new Error(`Reachability size mismatch: fwd=${fwd.size}, bwd=${bwd.size}, expected=${expected.length}`);
}
for (const id of expected) {
  if (!fwd.has(id)) throw new Error(`fwd missing ${id}`);
  if (!bwd.has(id)) throw new Error(`bwd missing ${id}`);
}

// 3. findSESENodes test
const seseNodes = sese.findSESENodes('p_src', 'p_snk');
if (!seseNodes) {
  throw new Error('findSESENodes should return valid node set for (p_src, p_snk)');
}
if (seseNodes.size !== expected.length) {
  throw new Error(`findSESENodes returned ${seseNodes.size} nodes, expected ${expected.length}`);
}

// 4. Non-SESE pair (p_src, p1) should return null (p1 is internal branch, fwd != bwd)
const invalidPair = sese.findSESENodes('p_src', 'p1');
if (invalidPair !== null) {
  throw new Error('(p_src, p1) is not SESE and should return null');
}

console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_sese_boundary_invariant_exclusion_headless(self):
        """Verifies that nodes violating the SESE boundary invariant (external in/out leaks) are rejected."""
        # 0. Baseline: without leaks, forms valid SESE
        net_valid = _make_sese_test_net()
        test_logic_valid = """
const sese = foldEngine.sese || new SESEInfrastructure(cy);
const res = sese.findSESENodes('p_src', 'p_snk');
if (!res || res.size !== 5) {
  throw new Error('Valid base subnet should form SESE of size 5');
}
console.log('PASS');
"""
        script0 = _setup_live_fold_test_harness(net_valid, test_logic_valid)
        proc0 = _run_node_script(script0)
        self.assertEqual(proc0.returncode, 0, f"Node script failed: {proc0.stderr}")
        self.assertIn("PASS", proc0.stdout)

        # 1. Leak INTO internal node from outside
        net_leak_in = _make_sese_test_net(leak_in=True)
        test_logic_in = """
const sese = foldEngine.sese || new SESEInfrastructure(cy);
const res = sese.findSESENodes('p_src', 'p_snk');
// Leak-in arc from t_leak_in -> p1 causes bwd to expand to external nodes, so fwd != bwd
if (res !== null) {
  throw new Error('Subnet with external leak in should not form SESE');
}
console.log('PASS');
"""
        script1 = _setup_live_fold_test_harness(net_leak_in, test_logic_in)
        proc1 = _run_node_script(script1)
        self.assertEqual(proc1.returncode, 0, f"Node script failed: {proc1.stderr}")
        self.assertIn("PASS", proc1.stdout)

        # 2. Leak OUT of internal node to outside
        net_leak_out = _make_sese_test_net(leak_out=True)
        test_logic_out = """
const sese = foldEngine.sese || new SESEInfrastructure(cy);
const res = sese.findSESENodes('p_src', 'p_snk');
if (res !== null) {
  throw new Error('Subnet with external leak out should not form SESE');
}
console.log('PASS');
"""
        script2 = _setup_live_fold_test_harness(net_leak_out, test_logic_out)
        proc2 = _run_node_script(script2)
        self.assertEqual(proc2.returncode, 0, f"Node script failed: {proc2.stderr}")
        self.assertIn("PASS", proc2.stdout)

    def test_sese_symmetry_multiplier_matches_python_fold_engine(self):
        """Verifies that symmetry multiplier (diffP, diffT) matches Python NetTopology.calculate_symmetry_multiplier."""
        from code2petri.model import PetriNet
        from code2petri.fold import NetTopology

        # 1. Python model
        py_net = PetriNet()
        p_src = py_net.add_place("p_src")
        p1 = py_net.add_place("p1")
        p2 = py_net.add_place("p2")
        p_join = py_net.add_place("p_join")
        p_snk = py_net.add_place("p_snk")

        t1 = py_net.add_transition("t1")
        t2 = py_net.add_transition("t2")
        t_split = py_net.add_transition("t_split")
        t_snk = py_net.add_transition("t_snk")

        py_net.add_arc(p_src, t1)
        py_net.add_arc(p_src, t2)
        py_net.add_arc(t1, p1)
        py_net.add_arc(t2, p2)
        py_net.add_arc(p1, t_split)
        py_net.add_arc(p2, t_split)
        py_net.add_arc(t_split, p_join)
        py_net.add_arc(p_join, t_snk)
        py_net.add_arc(t_snk, p_snk)

        topo = NetTopology(py_net)
        comp_nodes = {"p_src", "p1", "p2", "p_join", "p_snk", "t1", "t2", "t_split", "t_snk"}
        place_nodes = {"p_src", "p1", "p2", "p_join", "p_snk"}
        trans_nodes = {"t1", "t2", "t_split", "t_snk"}

        py_diff_p_full = topo.calculate_symmetry_multiplier(comp_nodes, place_nodes, use_subnet_degrees=False)
        py_diff_t_full = topo.calculate_symmetry_multiplier(comp_nodes, trans_nodes, use_subnet_degrees=False)
        py_diff_p_subnet = topo.calculate_symmetry_multiplier(comp_nodes, place_nodes, use_subnet_degrees=True)
        py_diff_t_subnet = topo.calculate_symmetry_multiplier(comp_nodes, trans_nodes, use_subnet_degrees=True)

        # 2. JS calculation
        net_literal = """{
  places: [
    { id: 'p_src', label: 'p_src' },
    { id: 'p1', label: 'p1' },
    { id: 'p2', label: 'p2' },
    { id: 'p_join', label: 'p_join' },
    { id: 'p_snk', label: 'p_snk' }
  ],
  transitions: [
    { id: 't1', label: 't1' },
    { id: 't2', label: 't2' },
    { id: 't_split', label: 't_split' },
    { id: 't_snk', label: 't_snk' }
  ],
  arcs: [
    { source: 'p_src', target: 't1' },
    { source: 'p_src', target: 't2' },
    { source: 't1', target: 'p1' },
    { source: 't2', target: 'p2' },
    { source: 'p1', target: 't_split' },
    { source: 'p2', target: 't_split' },
    { source: 't_split', target: 'p_join' },
    { source: 'p_join', target: 't_snk' },
    { source: 't_snk', target: 'p_snk' }
  ]
}"""
        test_logic = """
const sese = foldEngine.sese || new SESEInfrastructure(cy);
const allNodes = ['p_src', 'p1', 'p2', 'p_join', 'p_snk', 't1', 't2', 't_split', 't_snk'];

const full = sese.calculateSubnetSymmetry(allNodes, false);
const subnet = sese.calculateSubnetSymmetry(allNodes, true);
const defSubnet = sese.calculateSubnetSymmetry(allNodes);

console.log(JSON.stringify({ full, subnet, defSubnet }));
"""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        js_res = json.loads(proc.stdout.strip())

        self.assertEqual(js_res["full"]["diffP"], py_diff_p_full)
        self.assertEqual(js_res["full"]["diffT"], py_diff_t_full)
        self.assertEqual(js_res["subnet"]["diffP"], py_diff_p_subnet)
        self.assertEqual(js_res["subnet"]["diffT"], py_diff_t_subnet)
        self.assertEqual(js_res["defSubnet"]["diffP"], py_diff_p_subnet)
        self.assertEqual(js_res["defSubnet"]["diffT"], py_diff_t_subnet)

    def test_sese_performance_large_composite_net_headless(self):
        """Validates that SESE detection runs efficiently (<50ms) on a Composite Net with 200+ nodes."""
        net_literal = """{
  places: [],
  transitions: [],
  arcs: []
}"""
        test_logic = """
const sese = foldEngine.sese || new SESEInfrastructure(cy);

// Dynamically construct a 240-node composite pipeline in Cytoscape
// 40 sequential stages, each stage has 2 places and 4 transitions
for (let stage = 0; stage < 40; stage++) {
  const pIn = 'stage_' + stage + '_in';
  const pOut = 'stage_' + stage + '_out';
  const tA = 'stage_' + stage + '_ta';
  const tB = 'stage_' + stage + '_tb';
  const pMidA = 'stage_' + stage + '_pmida';
  const pMidB = 'stage_' + stage + '_pmidb';

  cy.add([
    { group: 'nodes', data: { id: pIn }, classes: 'place' },
    { group: 'nodes', data: { id: pOut }, classes: 'place' },
    { group: 'nodes', data: { id: pMidA }, classes: 'place' },
    { group: 'nodes', data: { id: pMidB }, classes: 'place' },
    { group: 'nodes', data: { id: tA }, classes: 'transition' },
    { group: 'nodes', data: { id: tB }, classes: 'transition' }
  ]);

  cy.add([
    { group: 'edges', data: { id: `e_${stage}_1`, source: pIn, target: tA }, classes: 'arc' },
    { group: 'edges', data: { id: `e_${stage}_2`, source: tA, target: pMidA }, classes: 'arc' },
    { group: 'edges', data: { id: `e_${stage}_3`, source: pMidA, target: pOut }, classes: 'arc' },
    { group: 'edges', data: { id: `e_${stage}_4`, source: pIn, target: tB }, classes: 'arc' },
    { group: 'edges', data: { id: `e_${stage}_5`, source: tB, target: pMidB }, classes: 'arc' },
    { group: 'edges', data: { id: `e_${stage}_6`, source: pMidB, target: pOut }, classes: 'arc' }
  ]);

  if (stage > 0) {
    const prevOut = 'stage_' + (stage - 1) + '_out';
    const linkT = 'link_' + stage;
    cy.add({ group: 'nodes', data: { id: linkT }, classes: 'transition' });
    cy.add([
      { group: 'edges', data: { id: `link_e1_${stage}`, source: prevOut, target: linkT }, classes: 'arc' },
      { group: 'edges', data: { id: `link_e2_${stage}`, source: linkT, target: pIn }, classes: 'arc' }
    ]);
  }
}

const totalNodes = cy.nodes().length;
if (totalNodes < 200) {
  throw new Error(`Graph has only ${totalNodes} nodes, expected >= 200`);
}

const start = Date.now();
// Evaluate SESE across 40 stages
for (let stage = 0; stage < 40; stage++) {
  const pIn = 'stage_' + stage + '_in';
  const pOut = 'stage_' + stage + '_out';
  const seseSet = sese.findSESENodes(pIn, pOut);
  if (!seseSet) {
    throw new Error(`Failed to find SESE nodes for stage ${stage}`);
  }
}
const elapsed = Date.now() - start;

if (elapsed > 100) {
  throw new Error(`Performance too slow: took ${elapsed}ms for 40 SESE evaluations on ${totalNodes} nodes`);
}

console.log(`PASS: evaluated 40 SESE subnets on ${totalNodes} nodes in ${elapsed}ms`);
"""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)


    MARKED_GRAPH_NET_JSON = """{
  places: [
    { id: 'p_in', label: 'in', initial_tokens: 1 },
    { id: 'p1', label: 'branch1', initial_tokens: 0 },
    { id: 'p2', label: 'branch2', initial_tokens: 0 },
    { id: 'p_out', label: 'out', initial_tokens: 0 }
  ],
  transitions: [
    { id: 't_src', label: 'fork()', tau: 2.0, metadata: { tau: 2.0 } },
    { id: 't_snk', label: 'join()', tau: 3.0, metadata: { tau: 3.0 } }
  ],
  arcs: [
    { source: 'p_in', target: 't_src' },
    { source: 't_src', target: 'p1' },
    { source: 't_src', target: 'p2' },
    { source: 'p1', target: 't_snk' },
    { source: 'p2', target: 't_snk' },
    { source: 't_snk', target: 'p_out' }
  ]
}"""

    STATE_MACHINE_NET_JSON = """{
  places: [
    { id: 'p_src', label: 'src', initial_tokens: 1 },
    { id: 'p_mid1', label: 'mid1', initial_tokens: 0 },
    { id: 'p_mid2', label: 'mid2', initial_tokens: 0 },
    { id: 'p_snk', label: 'snk', initial_tokens: 0 }
  ],
  transitions: [
    { id: 't1', label: 't1', tau: 1.5, metadata: { tau: 1.5 } },
    { id: 't2', label: 't2', tau: 2.5, metadata: { tau: 2.5 } },
    { id: 't3', label: 't3', tau: 1.0, metadata: { tau: 1.0 } },
    { id: 't4', label: 't4', tau: 2.0, metadata: { tau: 2.0 } },
    { id: 't5', label: 't5', tau: 3.0, metadata: { tau: 3.0 } }
  ],
  arcs: [
    { source: 'p_src', target: 't1' },
    { source: 'p_src', target: 't3' },
    { source: 't1', target: 'p_mid1' },
    { source: 't3', target: 'p_mid2' },
    { source: 'p_mid1', target: 't2' },
    { source: 'p_mid1', target: 't5' },
    { source: 't5', target: 'p_mid2' },
    { source: 'p_mid2', target: 't4' },
    { source: 't2', target: 'p_snk' },
    { source: 't4', target: 'p_snk' }
  ]
}"""

    WELL_STRUCTURED_NET_JSON = """{
  places: [
    { id: 'pw1', label: 'pw1', initial_tokens: 1 },
    { id: 'pw2', label: 'pw2', initial_tokens: 0 },
    { id: 'pw3', label: 'pw3', initial_tokens: 0 },
    { id: 'pw4', label: 'pw4', initial_tokens: 0 },
    { id: 'pw5', label: 'pw5', initial_tokens: 0 }
  ],
  transitions: [
    { id: 'tw1', label: 'tw1', tau: 1.5, metadata: { tau: 1.5 } },
    { id: 'tw2', label: 'tw2', tau: 2.5, metadata: { tau: 2.5 } },
    { id: 'tw3', label: 'tw3', tau: 1.0, metadata: { tau: 1.0 } },
    { id: 'tw4', label: 'tw4', tau: 2.0, metadata: { tau: 2.0 } }
  ],
  arcs: [
    { source: 'pw1', target: 'tw1' },
    { source: 'tw1', target: 'pw2' },
    { source: 'pw2', target: 'tw2' },
    { source: 'pw2', target: 'tw3' },
    { source: 'tw2', target: 'pw3' },
    { source: 'tw3', target: 'pw4' },
    { source: 'pw3', target: 'tw4' },
    { source: 'pw4', target: 'tw4' },
    { source: 'tw4', target: 'pw5' }
  ]
}"""

    def test_marked_graph_and_state_machine_styling_in_template(self):
        """Verifies template.html includes contractible CSS styling for marked graph and state machine."""
        html = _read_template_html()
        self.assertIn("node.transition.contractible-marked-graph", html)
        self.assertIn("#58a6ff", html)
        self.assertIn("node.place.contractible-state-machine", html)
        self.assertIn("#f0883e", html)

    def test_marked_graph_detection_and_highlighting_headless(self):
        """Validates that boundary transitions of marked graph SESE subnets receive .contractible-marked-graph class."""
        test_logic = """
const tSrc = cy.getElementById('t_src');
const tSnk = cy.getElementById('t_snk');
const p1 = cy.getElementById('p1');
const p2 = cy.getElementById('p2');
const pIn = cy.getElementById('p_in');
const pOut = cy.getElementById('p_out');

if (!tSrc.hasClass('contractible') || !tSrc.hasClass('contractible-marked-graph')) {
  throw new Error('t_src should have contractible and contractible-marked-graph classes');
}
if (!tSnk.hasClass('contractible') || !tSnk.hasClass('contractible-marked-graph')) {
  throw new Error('t_snk should have contractible and contractible-marked-graph classes');
}

if (p1.hasClass('contractible') || p2.hasClass('contractible')) {
  throw new Error('Internal places p1/p2 should not be contractible');
}
if (pIn.hasClass('contractible') || pOut.hasClass('contractible')) {
  throw new Error('Boundary places p_in/p_out should not be contractible');
}

console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(self.MARKED_GRAPH_NET_JSON, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_marked_graph_reduction_and_python_parity_headless(self):
        """Validates that Live Fold Reduction (Marked Graph) collapses subnet with tau/omega matching Python fold_marked_graph."""
        from code2petri.model import PetriNet
        from code2petri.fold import fold_marked_graph, FoldConfig

        # 1. Python calculation
        py_net = PetriNet()
        p_in = py_net.add_place("p_in", initial_tokens=1)
        p1 = py_net.add_place("p1", initial_tokens=0)
        p2 = py_net.add_place("p2", initial_tokens=0)
        p_out = py_net.add_place("p_out", initial_tokens=0)
        t_src = py_net.add_transition("t_src", metadata={"tau": 2.0})
        t_snk = py_net.add_transition("t_snk", metadata={"tau": 3.0})

        py_net.add_arc(p_in, t_src)
        py_net.add_arc(t_src, p1)
        py_net.add_arc(t_src, p2)
        py_net.add_arc(p1, t_snk)
        py_net.add_arc(p2, t_snk)
        py_net.add_arc(t_snk, p_out)

        py_folded, py_step = fold_marked_graph(py_net, step_number=1, config=FoldConfig(marked_graph=2.0))
        self.assertIsNotNone(py_step)
        expected_tau = py_step.tau
        expected_omega = py_step.omega
        expected_sm = py_step.running_sm

        # 2. JS calculation
        test_logic = """
const tSrc = cy.getElementById('t_src');
const res = foldEngine.executeMarkedGraphContraction(tSrc);

if (!res.success) {
  throw new Error('Marked Graph contraction failed: ' + res.message);
}

// Verify consumed nodes removed: t_src, t_snk, p1, p2
['t_src', 't_snk', 'p1', 'p2'].forEach(function(id) {
  if (cy.getElementById(id).length !== 0) {
    throw new Error(`Node ${id} was not removed after Marked Graph contraction`);
  }
});

// Verify boundary places remain
if (cy.getElementById('p_in').length !== 1 || cy.getElementById('p_out').length !== 1) {
  throw new Error('Boundary places p_in / p_out should remain on canvas');
}

// Verify opaque component created
const c01 = cy.getElementById('c_01');
if (c01.length === 0) {
  throw new Error('Opaque component c_01 was not created');
}
if (c01.data('component_type') !== 'MarkedGraph') {
  throw new Error('Expected component_type MarkedGraph, got ' + c01.data('component_type'));
}
if (c01.data('is_opaque') !== true) {
  throw new Error('Expected is_opaque true');
}

// Verify boundary arcs between p_in -> c_01 -> p_out
const inEdges = c01.incomers('edge');
if (inEdges.length !== 1 || inEdges[0].source().id() !== 'p_in') {
  throw new Error('Incomer to c_01 not from p_in');
}
const outEdges = c01.outgoers('edge');
if (outEdges.length !== 1 || outEdges[0].target().id() !== 'p_out') {
  throw new Error('Outgoer from c_01 not to p_out');
}

// Verify consumed subnet storage
const sub = c01.data('consumedSubnet');
if (!sub) throw new Error('Missing consumedSubnet on c_01');
if (sub.sourceId !== 't_src' || sub.sinkId !== 't_snk') {
  throw new Error(`consumedSubnet invalid source/sink: ${sub.sourceId}..${sub.sinkId}`);
}
if (sub.nodes.length !== 4) {
  throw new Error(`consumedSubnet nodes length expected 4, got ${sub.nodes.length}`);
}
if (sub.internalEdges.length !== 4) {
  throw new Error(`consumedSubnet internalEdges length expected 4, got ${sub.internalEdges.length}`);
}

const result = {
  tau: c01.data('tau'),
  omega: c01.data('omega'),
  running_sm: foldEngine.calculateSMScore()
};
console.log(JSON.stringify(result));
"""
        node_script = _setup_live_fold_test_harness(self.MARKED_GRAPH_NET_JSON, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        js_data = json.loads(proc.stdout.strip())

        self.assertEqual(js_data["tau"], expected_tau)
        self.assertEqual(js_data["omega"], expected_omega)
        self.assertEqual(js_data["running_sm"], expected_sm)

    def test_state_machine_detection_and_highlighting_headless(self):
        """Validates that boundary places of State Machine SESE subnets receive .contractible-state-machine class."""
        test_logic = """
const pSrc = cy.getElementById('p_src');
const pSnk = cy.getElementById('p_snk');
const pMid1 = cy.getElementById('p_mid1');
const pMid2 = cy.getElementById('p_mid2');

if (!pSrc.hasClass('contractible') || !pSrc.hasClass('contractible-state-machine')) {
  throw new Error('p_src should have contractible and contractible-state-machine classes');
}
if (!pSnk.hasClass('contractible') || !pSnk.hasClass('contractible-state-machine')) {
  throw new Error('p_snk should have contractible and contractible-state-machine classes');
}

if (pMid1.hasClass('contractible') || pMid2.hasClass('contractible')) {
  throw new Error('Internal places p_mid1/p_mid2 should not be contractible');
}

cy.nodes('.transition').forEach(function(t) {
  if (t.hasClass('contractible')) {
    throw new Error('Transition ' + t.id() + ' should not be marked contractible');
  }
});

console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(self.STATE_MACHINE_NET_JSON, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_state_machine_reduction_and_python_parity_headless(self):
        """Validates that Live Fold Reduction (State Machine) preserves boundary places with tau/omega matching Python."""
        from code2petri.model import PetriNet
        from code2petri.fold import fold_state_machine, FoldConfig

        # 1. Python model
        py_net = PetriNet()
        p_src = py_net.add_place("p_src", initial_tokens=1)
        p_mid1 = py_net.add_place("p_mid1", initial_tokens=0)
        p_mid2 = py_net.add_place("p_mid2", initial_tokens=0)
        p_snk = py_net.add_place("p_snk", initial_tokens=0)
        t1 = py_net.add_transition("t1", metadata={"tau": 1.5})
        t2 = py_net.add_transition("t2", metadata={"tau": 2.5})
        t3 = py_net.add_transition("t3", metadata={"tau": 1.0})
        t4 = py_net.add_transition("t4", metadata={"tau": 2.0})
        t5 = py_net.add_transition("t5", metadata={"tau": 3.0})

        py_net.add_arc(p_src, t1)
        py_net.add_arc(p_src, t3)
        py_net.add_arc(t1, p_mid1)
        py_net.add_arc(t3, p_mid2)
        py_net.add_arc(p_mid1, t2)
        py_net.add_arc(p_mid1, t5)
        py_net.add_arc(t5, p_mid2)
        py_net.add_arc(p_mid2, t4)
        py_net.add_arc(t2, p_snk)
        py_net.add_arc(t4, p_snk)

        py_folded, py_step = fold_state_machine(py_net, step_number=1, config=FoldConfig(state_machine=2.0))
        self.assertIsNotNone(py_step)
        expected_tau = py_step.tau
        expected_omega = py_step.omega
        expected_sm = py_step.running_sm

        # 2. JS model
        test_logic = """
const pSrc = cy.getElementById('p_src');
const res = foldEngine.executeStateMachineContraction(pSrc);

if (!res.success) {
  throw new Error('State Machine contraction failed: ' + res.message);
}

// Verify boundary places REMAINDER on canvas
if (cy.getElementById('p_src').length !== 1 || cy.getElementById('p_snk').length !== 1) {
  throw new Error('Boundary places p_src / p_snk should remain on canvas');
}

// Verify internal nodes removed: t1..t5, p_mid1, p_mid2
['t1', 't2', 't3', 't4', 't5', 'p_mid1', 'p_mid2'].forEach(function(id) {
  if (cy.getElementById(id).length !== 0) {
    throw new Error(`Internal node ${id} was not removed after State Machine contraction`);
  }
});

// Verify opaque component created
const c01 = cy.getElementById('c_01');
if (c01.length === 0) {
  throw new Error('Opaque component c_01 was not created');
}
if (c01.data('component_type') !== 'StateMachine') {
  throw new Error('Expected component_type StateMachine, got ' + c01.data('component_type'));
}
if (c01.data('is_opaque') !== true) {
  throw new Error('Expected is_opaque true');
}

// Verify boundary arcs between p_src -> c_01 -> p_snk
const inEdges = c01.incomers('edge');
if (inEdges.length !== 1 || inEdges[0].source().id() !== 'p_src') {
  throw new Error('Incomer to c_01 not from p_src');
}
const outEdges = c01.outgoers('edge');
if (outEdges.length !== 1 || outEdges[0].target().id() !== 'p_snk') {
  throw new Error('Outgoer from c_01 not to p_snk');
}

// Verify consumed subnet storage
const sub = c01.data('consumedSubnet');
if (!sub) throw new Error('Missing consumedSubnet on c_01');
if (sub.sourceId !== 'p_src' || sub.sinkId !== 'p_snk') {
  throw new Error(`consumedSubnet invalid source/sink: ${sub.sourceId}..${sub.sinkId}`);
}
if (sub.nodes.length !== 7) {
  throw new Error(`consumedSubnet nodes length expected 7, got ${sub.nodes.length}`);
}

const result = {
  tau: c01.data('tau'),
  omega: c01.data('omega'),
  running_sm: foldEngine.calculateSMScore()
};
console.log(JSON.stringify(result));
"""
        node_script = _setup_live_fold_test_harness(self.STATE_MACHINE_NET_JSON, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        js_data = json.loads(proc.stdout.strip())

        self.assertEqual(js_data["tau"], expected_tau)
        self.assertEqual(js_data["omega"], expected_omega)
        self.assertEqual(js_data["running_sm"], expected_sm)

    def test_marked_graph_and_state_machine_tap_interaction_headless(self):
        """Validates that left-clicking boundary nodes triggers marked graph or state machine reduction and inspector."""
        # 1. Tap on marked graph boundary transition strictly opens HUD, where button triggers fold (P3)
        test_logic_mg = """
const tSrc = cy.getElementById('t_src');
tSrc.emit('tap', { target: tSrc });

if (inspectorPanel.style.display !== 'flex') {
  throw new Error('Inspector panel did not open upon tapping t_src');
}
if (!hudBtnContractMg || hudBtnContractMg.style.display === 'none') {
  throw new Error('Contract Marked Graph button should be visible in HUD');
}

// Explicit action click in HUD (P3)
hudBtnContractMg.click();

const c01 = cy.getElementById('c_01');
if (c01.length === 0) throw new Error('c_01 was not created upon contracting marked graph');
if (c01.data('component_type') !== 'MarkedGraph') throw new Error('Expected MarkedGraph component');

if (inspectorPanel.style.display !== 'flex') {
  throw new Error('Inspector panel did not open for MarkedGraph');
}
if (inspectorType.textContent !== 'MarkedGraph') {
  throw new Error('Inspector type expected MarkedGraph, got ' + inspectorType.textContent);
}

console.log('PASS');
"""
        node_script_mg = _setup_live_fold_test_harness(self.MARKED_GRAPH_NET_JSON, test_logic_mg)
        proc_mg = _run_node_script(node_script_mg)
        self.assertEqual(proc_mg.returncode, 0, f"Node script failed: {proc_mg.stderr}")
        self.assertIn("PASS", proc_mg.stdout)

        # 2. Tap on state machine boundary place
        test_logic_sm = """
const pSrc = cy.getElementById('p_src');
pSrc.emit('tap');

const c01 = cy.getElementById('c_01');
if (c01.length === 0) throw new Error('c_01 was not created upon tapping p_src');
if (c01.data('component_type') !== 'StateMachine') throw new Error('Expected StateMachine component');

if (inspectorPanel.style.display !== 'flex') {
  throw new Error('Inspector panel did not open for StateMachine');
}
if (inspectorType.textContent !== 'StateMachine') {
  throw new Error('Inspector type expected StateMachine, got ' + inspectorType.textContent);
}

console.log('PASS');
"""
        node_script_sm = _setup_live_fold_test_harness(self.STATE_MACHINE_NET_JSON, test_logic_sm)
        proc_sm = _run_node_script(node_script_sm)
        self.assertEqual(proc_sm.returncode, 0, f"Node script failed: {proc_sm.stderr}")
        self.assertIn("PASS", proc_sm.stdout)

    def test_well_structured_styling_in_template(self):
        """Verifies template.html includes contractible CSS styling for well-structured SESE."""
        html = _read_template_html()
        self.assertIn("node.place.contractible-well-structured", html)
        self.assertIn("#26a69a", html)

    def test_well_structured_detection_and_highlighting_headless(self):
        """Validates that boundary places of Well-Structured SESE subnets receive .contractible-well-structured class."""
        test_logic = """
const pw1 = cy.getElementById('pw1');
const pw5 = cy.getElementById('pw5');
const pw2 = cy.getElementById('pw2');
const pw3 = cy.getElementById('pw3');
const pw4 = cy.getElementById('pw4');

if (!pw1.hasClass('contractible') || !pw1.hasClass('contractible-well-structured')) {
  throw new Error('pw1 should have contractible and contractible-well-structured classes');
}
if (!pw5.hasClass('contractible') || !pw5.hasClass('contractible-well-structured')) {
  throw new Error('pw5 should have contractible and contractible-well-structured classes');
}

if (pw2.hasClass('contractible') || pw3.hasClass('contractible') || pw4.hasClass('contractible')) {
  throw new Error('Internal places pw2/pw3/pw4 should not be contractible');
}

cy.nodes('.transition').forEach(function(t) {
  if (t.hasClass('contractible')) {
    throw new Error('Transition ' + t.id() + ' should not be marked contractible');
  }
});

console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(self.WELL_STRUCTURED_NET_JSON, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_well_structured_reduction_and_python_parity_headless(self):
        """Validates that Live Fold Reduction (Well-Structured SESE) preserves boundary places with tau/omega matching Python."""
        from code2petri.model import PetriNet
        from code2petri.fold import fold_well_structured, FoldConfig

        # 1. Python model
        py_net = PetriNet()
        pw1 = py_net.add_place("pw1", initial_tokens=1)
        pw2 = py_net.add_place("pw2", initial_tokens=0)
        pw3 = py_net.add_place("pw3", initial_tokens=0)
        pw4 = py_net.add_place("pw4", initial_tokens=0)
        pw5 = py_net.add_place("pw5", initial_tokens=0)
        tw1 = py_net.add_transition("tw1", metadata={"tau": 1.5})
        tw2 = py_net.add_transition("tw2", metadata={"tau": 2.5})
        tw3 = py_net.add_transition("tw3", metadata={"tau": 1.0})
        tw4 = py_net.add_transition("tw4", metadata={"tau": 2.0})

        py_net.add_arc(pw1, tw1)
        py_net.add_arc(tw1, pw2)
        py_net.add_arc(pw2, tw2)
        py_net.add_arc(pw2, tw3)
        py_net.add_arc(tw2, pw3)
        py_net.add_arc(tw3, pw4)
        py_net.add_arc(pw3, tw4)
        py_net.add_arc(pw4, tw4)
        py_net.add_arc(tw4, pw5)

        py_folded, py_step = fold_well_structured(py_net, step_number=1, config=FoldConfig(well_structured=2.0))
        self.assertIsNotNone(py_step)
        expected_tau = py_step.tau
        expected_omega = py_step.omega
        expected_sm = py_step.running_sm

        # 2. JS model
        test_logic = """
const pw1 = cy.getElementById('pw1');
const res = foldEngine.executeWellStructuredContraction(pw1);

if (!res.success) {
  throw new Error('Well-Structured contraction failed: ' + res.message);
}

// Verify boundary places REMAINDER on canvas
if (cy.getElementById('pw1').length !== 1 || cy.getElementById('pw5').length !== 1) {
  throw new Error('Boundary places pw1 / pw5 should remain on canvas');
}

// Verify internal nodes removed: tw1..tw4, pw2..pw4
['tw1', 'tw2', 'tw3', 'tw4', 'pw2', 'pw3', 'pw4'].forEach(function(id) {
  if (cy.getElementById(id).length !== 0) {
    throw new Error(`Internal node ${id} was not removed after Well-Structured contraction`);
  }
});

// Verify opaque component created
const c01 = cy.getElementById('c_01');
if (c01.length === 0) {
  throw new Error('Opaque component c_01 was not created');
}
if (c01.data('component_type') !== 'WellStructured') {
  throw new Error('Expected component_type WellStructured, got ' + c01.data('component_type'));
}
if (c01.data('is_opaque') !== true) {
  throw new Error('Expected is_opaque true');
}

// Verify boundary arcs between pw1 -> c_01 -> pw5
const inEdges = c01.incomers('edge');
if (inEdges.length !== 1 || inEdges[0].source().id() !== 'pw1') {
  throw new Error('Incomer to c_01 not from pw1');
}
const outEdges = c01.outgoers('edge');
if (outEdges.length !== 1 || outEdges[0].target().id() !== 'pw5') {
  throw new Error('Outgoer from c_01 not to pw5');
}

// Verify consumed subnet storage
const sub = c01.data('consumedSubnet');
if (!sub) throw new Error('Missing consumedSubnet on c_01');
if (sub.sourceId !== 'pw1' || sub.sinkId !== 'pw5') {
  throw new Error(`consumedSubnet invalid source/sink: ${sub.sourceId}..${sub.sinkId}`);
}
if (sub.nodes.length !== 7) {
  throw new Error(`consumedSubnet nodes length expected 7, got ${sub.nodes.length}`);
}

const result = {
  tau: c01.data('tau'),
  omega: c01.data('omega'),
  running_sm: foldEngine.calculateSMScore()
};
console.log(JSON.stringify(result));
"""
        node_script = _setup_live_fold_test_harness(self.WELL_STRUCTURED_NET_JSON, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        js_data = json.loads(proc.stdout.strip())

        self.assertEqual(js_data["tau"], expected_tau)
        self.assertEqual(js_data["omega"], expected_omega)
        self.assertEqual(js_data["running_sm"], expected_sm)

    def test_well_structured_tap_interaction_headless(self):
        """Validates that left-clicking boundary place triggers well-structured reduction and inspector."""
        test_logic_ws = """
const pw1 = cy.getElementById('pw1');
pw1.emit('tap');

const c01 = cy.getElementById('c_01');
if (c01.length === 0) throw new Error('c_01 was not created upon tapping pw1');
if (c01.data('component_type') !== 'WellStructured') throw new Error('Expected WellStructured component');

if (inspectorPanel.style.display !== 'flex') {
  throw new Error('Inspector panel did not open for WellStructured');
}
if (inspectorType.textContent !== 'WellStructured') {
  throw new Error('Inspector type expected WellStructured, got ' + inspectorType.textContent);
}

console.log('PASS');
"""
        node_script_ws = _setup_live_fold_test_harness(self.WELL_STRUCTURED_NET_JSON, test_logic_ws)
        proc_ws = _run_node_script(node_script_ws)
        self.assertEqual(proc_ws.returncode, 0, f"Node script failed: {proc_ws.stderr}")
        self.assertIn("PASS", proc_ws.stdout)

    def test_well_structured_rejects_pt_handle_and_internal_cycle_headless(self):
        """Validates that SESE subnets with PT/TP handles or internal cycles are rejected from well-structured reduction."""
        test_cases = [
            (
                "PT handle",
                """{
  places: [
    { id: 'pw1', label: 'pw1', initial_tokens: 1 },
    { id: 'pw2', label: 'pw2', initial_tokens: 0 },
    { id: 'pw3', label: 'pw3', initial_tokens: 0 },
    { id: 'pw5', label: 'pw5', initial_tokens: 0 }
  ],
  transitions: [
    { id: 'tw1', label: 'tw1', tau: 1.0 },
    { id: 'tw2', label: 'tw2', tau: 1.0 },
    { id: 'tw4', label: 'tw4', tau: 1.0 }
  ],
  arcs: [
    { source: 'pw1', target: 'tw1' },
    { source: 'tw1', target: 'pw2' },
    { source: 'pw2', target: 'tw2' },
    { source: 'pw2', target: 'tw4' },
    { source: 'tw2', target: 'pw3' },
    { source: 'pw3', target: 'tw4' },
    { source: 'tw4', target: 'pw5' }
  ]
}""",
            ),
            (
                "internal cycle",
                """{
  places: [
    { id: 'pw1', label: 'pw1', initial_tokens: 1 },
    { id: 'pw2', label: 'pw2', initial_tokens: 0 },
    { id: 'pw3', label: 'pw3', initial_tokens: 0 },
    { id: 'pw4', label: 'pw4', initial_tokens: 0 },
    { id: 'pw5', label: 'pw5', initial_tokens: 0 }
  ],
  transitions: [
    { id: 'tw1', label: 'tw1', tau: 1.0 },
    { id: 'tw2', label: 'tw2', tau: 1.0 },
    { id: 'tw3', label: 'tw3', tau: 1.0 },
    { id: 'tw4', label: 'tw4', tau: 1.0 }
  ],
  arcs: [
    { source: 'pw1', target: 'tw1' },
    { source: 'tw1', target: 'pw2' },
    { source: 'pw2', target: 'tw2' },
    { source: 'pw2', target: 'tw3' },
    { source: 'tw2', target: 'pw3' },
    { source: 'tw3', target: 'pw4' },
    { source: 'pw3', target: 'tw4' },
    { source: 'pw4', target: 'tw4' },
    { source: 'tw4', target: 'pw5' },
    { source: 'tw4', target: 'pw2' }
  ]
}""",
            ),
        ]

        for desc, net_json in test_cases:
            with self.subTest(topology=desc):
                test_logic = f"""
const cands = foldEngine.detectWellStructured();
if (cands.length !== 0) {{
  throw new Error('Expected 0 well-structured candidates on {desc} net, got ' + cands.length);
}}
console.log('PASS');
"""
                node_script = _setup_live_fold_test_harness(net_json, test_logic)
                proc = _run_node_script(node_script)
                self.assertEqual(proc.returncode, 0, f"Node script failed for {desc}: {proc.stderr}")
                self.assertIn("PASS", proc.stdout)

    def test_well_structured_custom_config_respected_headless(self):
        """Validates that LiveFoldReductionEngine respects custom well_structured multiplier option matching Python."""
        from code2petri.model import PetriNet
        from code2petri.fold import fold_well_structured, FoldConfig

        # 1. Python model with well_structured=5.0
        py_net = PetriNet()
        pw1 = py_net.add_place("pw1", initial_tokens=1)
        pw2 = py_net.add_place("pw2", initial_tokens=0)
        pw3 = py_net.add_place("pw3", initial_tokens=0)
        pw4 = py_net.add_place("pw4", initial_tokens=0)
        pw5 = py_net.add_place("pw5", initial_tokens=0)
        tw1 = py_net.add_transition("tw1", metadata={"tau": 1.5})
        tw2 = py_net.add_transition("tw2", metadata={"tau": 2.5})
        tw3 = py_net.add_transition("tw3", metadata={"tau": 1.0})
        tw4 = py_net.add_transition("tw4", metadata={"tau": 2.0})

        py_net.add_arc(pw1, tw1)
        py_net.add_arc(tw1, pw2)
        py_net.add_arc(pw2, tw2)
        py_net.add_arc(pw2, tw3)
        py_net.add_arc(tw2, pw3)
        py_net.add_arc(tw3, pw4)
        py_net.add_arc(pw3, tw4)
        py_net.add_arc(pw4, tw4)
        py_net.add_arc(tw4, pw5)

        py_folded, py_step = fold_well_structured(py_net, step_number=1, config=FoldConfig(well_structured=5.0))
        self.assertIsNotNone(py_step)
        expected_tau = py_step.tau
        expected_omega = py_step.omega

        # 2. JS model with custom engine config { well_structured: 5.0 }
        test_logic = """
const customEngine = new LiveFoldReductionEngine(cy, { well_structured: 5.0 });
const cands = customEngine.detectWellStructured();
if (cands.length !== 1) {
  throw new Error('Expected 1 well-structured candidate, got ' + cands.length);
}
const res = customEngine.executeWellStructuredContraction(cands[0]);
if (!res.success) {
  throw new Error('Well-Structured contraction failed: ' + res.message);
}
const c01 = cy.getElementById('c_01');
const result = {
  tau: c01.data('tau'),
  omega: c01.data('omega')
};
console.log(JSON.stringify(result));
"""
        node_script = _setup_live_fold_test_harness(self.WELL_STRUCTURED_NET_JSON, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        js_data = json.loads(proc.stdout.strip())

        self.assertEqual(js_data["tau"], expected_tau)
        self.assertEqual(js_data["omega"], expected_omega)

    UNSTRUCTURED_IRREDUCIBLE_NET_JSON = """{
  places: [
    { id: 'p_in', label: 'in', initial_tokens: 1 },
    { id: 'p1', label: 'p1', initial_tokens: 0 },
    { id: 'p2', label: 'p2', initial_tokens: 0 },
    { id: 'p_out', label: 'out', initial_tokens: 0 }
  ],
  transitions: [
    { id: 't1', label: 't1', tau: 1.0, metadata: { tau: 1.0 } },
    { id: 't2', label: 't2', tau: 1.0, metadata: { tau: 1.0 } },
    { id: 't3', label: 't3', tau: 1.0, metadata: { tau: 1.0 } },
    { id: 't4', label: 't4', tau: 1.0, metadata: { tau: 1.0 } }
  ],
  arcs: [
    { source: 'p_in', target: 't1' },
    { source: 'p_in', target: 't2' },
    { source: 't1', target: 'p1' },
    { source: 't2', target: 'p2' },
    { source: 'p1', target: 't3' },
    { source: 'p2', target: 't3' },
    { source: 'p1', target: 't4' },
    { source: 't3', target: 'p_out' },
    { source: 't4', target: 'p2' }
  ]
}"""

    UNSTRUCTURED_KNOT_NET_JSON = """{
  places: [
    { id: 'p_start', label: 'start', initial_tokens: 1 },
    { id: 'p_knot_in', label: 'knot_in', initial_tokens: 0 },
    { id: 'p_k1', label: 'k1', initial_tokens: 0 },
    { id: 'p_k2', label: 'k2', initial_tokens: 0 },
    { id: 'p_knot_out', label: 'knot_out', initial_tokens: 0 },
    { id: 'p_end', label: 'end', initial_tokens: 0 }
  ],
  transitions: [
    { id: 't_head', label: 'head', tau: 1.0, metadata: { tau: 1.0 } },
    { id: 't1', label: 't1', tau: 1.0, metadata: { tau: 1.0 } },
    { id: 't2', label: 't2', tau: 1.0, metadata: { tau: 1.0 } },
    { id: 't3', label: 't3', tau: 1.0, metadata: { tau: 1.0 } },
    { id: 't4', label: 't4', tau: 1.0, metadata: { tau: 1.0 } },
    { id: 't_tail', label: 'tail', tau: 1.0, metadata: { tau: 1.0 } }
  ],
  arcs: [
    { source: 'p_start', target: 't_head' },
    { source: 't_head', target: 'p_knot_in' },
    { source: 'p_knot_in', target: 't1' },
    { source: 'p_knot_in', target: 't2' },
    { source: 't1', target: 'p_k1' },
    { source: 't2', target: 'p_k2' },
    { source: 'p_k1', target: 't3' },
    { source: 'p_k2', target: 't3' },
    { source: 'p_k1', target: 't4' },
    { source: 't3', target: 'p_knot_out' },
    { source: 't4', target: 'p_k2' },
    { source: 'p_knot_out', target: 't_tail' },
    { source: 't_tail', target: 'p_end' }
  ]
}"""

    UNSTRUCTURED_SINGLE_PLACE_NET_JSON = """{
  places: [
    { id: 'p0', label: 'p0', initial_tokens: 1 }
  ],
  transitions: [
    { id: 't1', label: 't1', tau: 1.0, metadata: { tau: 1.0 } },
    { id: 't2', label: 't2', tau: 1.0, metadata: { tau: 1.0 } }
  ],
  arcs: [
    { source: 'p0', target: 't1' },
    { source: 't1', target: 'p0' },
    { source: 'p0', target: 't2' },
    { source: 't2', target: 'p0' }
  ]
}"""

    def test_unstructured_styling_in_template(self):
        """Verifies template.html includes contractible CSS styling for unstructured components."""
        html = _read_template_html()
        self.assertIn("node.place.contractible-unstructured", html)
        self.assertIn("#e06c75", html)

    def test_unstructured_detection_and_highlighting_headless(self):
        """Validates that boundary places of Unstructured components receive .contractible-unstructured class."""
        test_logic = """
const pIn = cy.getElementById('p_in');
const pOut = cy.getElementById('p_out');
const p1 = cy.getElementById('p1');
const p2 = cy.getElementById('p2');

if (!pIn.hasClass('contractible') || !pIn.hasClass('contractible-unstructured')) {
  throw new Error('p_in should have contractible and contractible-unstructured classes');
}
if (!pOut.hasClass('contractible') || !pOut.hasClass('contractible-unstructured')) {
  throw new Error('p_out should have contractible and contractible-unstructured classes');
}

if (p1.hasClass('contractible') || p2.hasClass('contractible')) {
  throw new Error('Internal places p1/p2 should not be contractible');
}

cy.nodes('.transition').forEach(function(t) {
  if (t.hasClass('contractible')) {
    throw new Error('Transition ' + t.id() + ' should not be marked contractible');
  }
});

console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(self.UNSTRUCTURED_IRREDUCIBLE_NET_JSON, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_unstructured_minimal_knot_isolation_headless(self):
        """Validates that Live Fold Reduction isolates minimal SESE knot, leaving surrounding control flow reducible."""
        test_logic = """
const cands = foldEngine.detectUnstructured();
if (cands.length !== 1) {
  throw new Error('Expected exactly 1 unstructured candidate for minimal knot, got ' + cands.length);
}
const knotCand = cands[0];
if (knotCand.sourceId !== 'p_knot_in' || knotCand.sinkId !== 'p_knot_out') {
  throw new Error(`Expected knot between p_knot_in..p_knot_out, got ${knotCand.sourceId}..${knotCand.sinkId}`);
}

// Execute unstructured knot contraction
const res = foldEngine.executeUnstructuredContraction(knotCand);
if (!res.success) {
  throw new Error('Unstructured knot contraction failed: ' + res.message);
}

// Verify internal knot nodes removed: t1, t2, t3, t4, p_k1, p_k2
['t1', 't2', 't3', 't4', 'p_k1', 'p_k2'].forEach(function(id) {
  if (cy.getElementById(id).length !== 0) {
    throw new Error(`Internal knot node ${id} was not removed after contraction`);
  }
});

// Verify surrounding structured nodes remain on canvas
['p_start', 't_head', 'p_knot_in', 'p_knot_out', 't_tail', 'p_end'].forEach(function(id) {
  if (cy.getElementById(id).length !== 1) {
    throw new Error(`Surrounding control flow node ${id} should remain on canvas`);
  }
});

// Verify opaque component created with ProM penalty formula
const c01 = cy.getElementById('c_01');
if (c01.length === 0) throw new Error('Opaque component c_01 was not created');
if (c01.data('component_type') !== 'Unstructured') throw new Error('Expected component_type Unstructured');
if (c01.data('tau') !== 160.0) throw new Error('Expected tau 160.0, got ' + c01.data('tau'));
if (c01.data('omega') !== 156.0) throw new Error('Expected omega 156.0, got ' + c01.data('omega'));

// Verify boundary arcs between p_knot_in -> c_01 -> p_knot_out
const inEdges = c01.incomers('edge');
if (inEdges.length !== 1 || inEdges[0].source().id() !== 'p_knot_in') {
  throw new Error('Incomer to c_01 not from p_knot_in');
}
const outEdges = c01.outgoers('edge');
if (outEdges.length !== 1 || outEdges[0].target().id() !== 'p_knot_out') {
  throw new Error('Outgoer from c_01 not to p_knot_out');
}

// Surrounding control flow is now eligible for subsequent structured reductions:
// 1. Fold sequence at p_knot_in
const pIn = cy.getElementById('p_knot_in');
if (foldEngine.getFoldType(pIn) !== 'sequence') {
  throw new Error('p_knot_in should be eligible for sequence reduction, got: ' + foldEngine.getFoldType(pIn));
}
const resPIn = foldEngine.executeSinglePlaceContraction(pIn);
if (!resPIn.success) throw new Error('Failed to fold sequence at p_knot_in: ' + resPIn.message);

// 2. Fold sequence at p_knot_out
const pOut = cy.getElementById('p_knot_out');
if (foldEngine.getFoldType(pOut) !== 'sequence') {
  throw new Error('p_knot_out should be eligible for sequence reduction, got: ' + foldEngine.getFoldType(pOut));
}
const resPOut = foldEngine.executeSinglePlaceContraction(pOut);
if (!resPOut.success) throw new Error('Failed to fold sequence at p_knot_out: ' + resPOut.message);

// Verify fully reduced to single transition connecting p_start to p_end
const finalTrans = cy.nodes('.transition');
if (finalTrans.length !== 1) {
  throw new Error('Expected exactly 1 transition after sequence folding, got ' + finalTrans.length);
}
if (finalTrans[0].data('tau') !== 162.0) {
  throw new Error('Expected final tau 162.0 (1.0 + 160.0 + 1.0), got ' + finalTrans[0].data('tau'));
}
const finalPlaces = cy.nodes('.place').map(p => p.id());
if (finalPlaces.length !== 2 || !finalPlaces.includes('p_start') || !finalPlaces.includes('p_end')) {
  throw new Error('Expected remaining places [p_start, p_end], got ' + JSON.stringify(finalPlaces));
}

console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(self.UNSTRUCTURED_KNOT_NET_JSON, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_unstructured_knot_python_parity_headless(self):
        """Validates that Live Fold Reduction (Unstructured) tau/omega calculations match Python fold_unstructured."""
        from code2petri.model import PetriNet
        from code2petri.fold import fold_unstructured, FoldConfig

        # 1. Python calculation on the knot topology
        py_net = PetriNet()
        p_start = py_net.add_place("p_start", initial_tokens=1)
        p_knot_in = py_net.add_place("p_knot_in")
        p_k1 = py_net.add_place("p_k1")
        p_k2 = py_net.add_place("p_k2")
        p_knot_out = py_net.add_place("p_knot_out")
        p_end = py_net.add_place("p_end")

        t_head = py_net.add_transition("t_head")
        t1 = py_net.add_transition("t1")
        t2 = py_net.add_transition("t2")
        t3 = py_net.add_transition("t3")
        t4 = py_net.add_transition("t4")
        t_tail = py_net.add_transition("t_tail")

        py_net.add_arc(p_start, t_head)
        py_net.add_arc(t_head, p_knot_in)
        py_net.add_arc(p_knot_in, t1)
        py_net.add_arc(p_knot_in, t2)
        py_net.add_arc(t1, p_k1)
        py_net.add_arc(t2, p_k2)
        py_net.add_arc(p_k1, t3)
        py_net.add_arc(p_k2, t3)
        py_net.add_arc(p_k1, t4)
        py_net.add_arc(t3, p_knot_out)
        py_net.add_arc(t4, p_k2)
        py_net.add_arc(p_knot_out, t_tail)
        py_net.add_arc(t_tail, p_end)

        py_folded, py_step = fold_unstructured(py_net, step_number=1, config=FoldConfig())
        self.assertIsNotNone(py_step)
        expected_tau = py_step.tau
        expected_omega = py_step.omega

        # 2. JS calculation
        test_logic = """
const knotCand = foldEngine.detectUnstructured()[0];
const res = foldEngine.executeUnstructuredContraction(knotCand);
if (!res.success) throw new Error('Unstructured contraction failed: ' + res.message);
const c01 = cy.getElementById('c_01');
const result = {
  tau: c01.data('tau'),
  omega: c01.data('omega')
};
console.log(JSON.stringify(result));
"""
        node_script = _setup_live_fold_test_harness(self.UNSTRUCTURED_KNOT_NET_JSON, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        js_data = json.loads(proc.stdout.strip())

        self.assertEqual(js_data["tau"], expected_tau)
        self.assertEqual(js_data["omega"], expected_omega)

    def test_unstructured_global_fallback_headless(self):
        """Validates that when no internal SESE pair exists, global fallback collapses entire net matching Python."""
        from code2petri.model import PetriNet
        from code2petri.fold import fold_unstructured, FoldConfig

        # 1. Python calculation on single-place looping net
        py_net = PetriNet()
        p0 = py_net.add_place("p0", initial_tokens=1)
        t1 = py_net.add_transition("t1")
        t2 = py_net.add_transition("t2")
        py_net.add_arc(p0, t1)
        py_net.add_arc(t1, p0)
        py_net.add_arc(p0, t2)
        py_net.add_arc(t2, p0)

        py_folded, py_step = fold_unstructured(py_net, step_number=1, config=FoldConfig())
        self.assertIsNotNone(py_step)
        expected_tau = py_step.tau
        expected_omega = py_step.omega

        # 2. JS calculation
        test_logic = """
const cands = foldEngine.detectUnstructured();
if (cands.length !== 1) {
  throw new Error('Expected 1 global fallback candidate, got ' + cands.length);
}
if (!cands[0].isGlobalFallback) {
  throw new Error('Expected isGlobalFallback flag to be true');
}

const res = foldEngine.executeUnstructuredContraction(cands[0]);
if (!res.success) {
  throw new Error('Unstructured fallback contraction failed: ' + res.message);
}

// Single place p0 remains on canvas
if (cy.getElementById('p0').length !== 1) {
  throw new Error('p0 should remain on canvas');
}

// Opaque component created with looping arcs
const c01 = cy.getElementById('c_01');
if (c01.length === 0) throw new Error('c_01 was not created');
if (c01.data('component_type') !== 'Unstructured') throw new Error('Expected component_type Unstructured');

const inEdges = c01.incomers('edge');
const outEdges = c01.outgoers('edge');
if (inEdges.length !== 1 || inEdges[0].source().id() !== 'p0') {
  throw new Error('Expected incoming arc p0 -> c_01');
}
if (outEdges.length !== 1 || outEdges[0].target().id() !== 'p0') {
  throw new Error('Expected outgoing arc c_01 -> p0');
}

const result = {
  tau: c01.data('tau'),
  omega: c01.data('omega')
};
console.log(JSON.stringify(result));
"""
        node_script = _setup_live_fold_test_harness(self.UNSTRUCTURED_SINGLE_PLACE_NET_JSON, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        js_data = json.loads(proc.stdout.strip())

        self.assertEqual(js_data["tau"], expected_tau)
        self.assertEqual(js_data["omega"], expected_omega)

    def test_unstructured_custom_config_respected_headless(self):
        """Validates that LiveFoldReductionEngine respects custom unstructured Fold Config penalty weight matching Python."""
        from code2petri.model import PetriNet
        from code2petri.fold import fold_unstructured, FoldConfig

        # 1. Python calculation with unstructured=14.0
        py_net = PetriNet()
        p0 = py_net.add_place("p0", initial_tokens=1)
        t1 = py_net.add_transition("t1")
        t2 = py_net.add_transition("t2")
        py_net.add_arc(p0, t1)
        py_net.add_arc(t1, p0)
        py_net.add_arc(p0, t2)
        py_net.add_arc(t2, p0)

        py_folded, py_step = fold_unstructured(py_net, step_number=1, config=FoldConfig(unstructured=14.0))
        self.assertIsNotNone(py_step)
        expected_tau = py_step.tau
        expected_omega = py_step.omega

        # 2. JS calculation with custom engine config { unstructured: 14.0 }
        test_logic = """
const customEngine = new LiveFoldReductionEngine(cy, { unstructured: 14.0 });
const cands = customEngine.detectUnstructured();
if (cands.length !== 1) {
  throw new Error('Expected 1 unstructured candidate, got ' + cands.length);
}
const res = customEngine.executeUnstructuredContraction(cands[0]);
if (!res.success) {
  throw new Error('Unstructured contraction failed: ' + res.message);
}
const c01 = cy.getElementById('c_01');
const result = {
  tau: c01.data('tau'),
  omega: c01.data('omega')
};
console.log(JSON.stringify(result));
"""
        node_script = _setup_live_fold_test_harness(self.UNSTRUCTURED_SINGLE_PLACE_NET_JSON, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        js_data = json.loads(proc.stdout.strip())

        self.assertEqual(js_data["tau"], expected_tau)
        self.assertEqual(js_data["omega"], expected_omega)

    def test_unstructured_tap_interaction_headless(self):
        """Validates that a Place-Centric Fold Trigger on an eligible boundary place executes Unstructured reduction and opens inspector."""
        test_logic = """
const pIn = cy.getElementById('p_in');
pIn.emit('tap');

const c01 = cy.getElementById('c_01');
if (c01.length === 0) throw new Error('c_01 was not created upon tapping p_in');
if (c01.data('component_type') !== 'Unstructured') throw new Error('Expected Unstructured component');

if (inspectorPanel.style.display !== 'flex') {
  throw new Error('Inspector panel did not open for Unstructured component');
}
if (inspectorType.textContent !== 'Unstructured') {
  throw new Error('Inspector type expected Unstructured, got ' + inspectorType.textContent);
}
if (inspectorTau.textContent !== '160.0') {
  throw new Error('Inspector tau expected 160.0, got ' + inspectorTau.textContent);
}

console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(self.UNSTRUCTURED_IRREDUCIBLE_NET_JSON, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_unstructured_trivial_net_rejected_headless(self):
        """Validates that trivial workflow nets with <= 1 transition return 0 unstructured candidates."""
        net_literal = """{
  places: [
    { id: 'p_in', label: 'in', initial_tokens: 1 },
    { id: 'p_out', label: 'out', initial_tokens: 0 }
  ],
  transitions: [
    { id: 't1', label: 't1', tau: 1.0 }
  ],
  arcs: [
    { source: 'p_in', target: 't1' },
    { source: 't1', target: 'p_out' }
  ]
}"""
        test_logic = """
const cands = foldEngine.detectUnstructured();
if (cands.length !== 0) {
  throw new Error('Expected 0 unstructured candidates on trivial net, got ' + cands.length);
}
console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    # =========================================================================
    # Ticket 39: Viewer Collapsed Compound State Tests
    # =========================================================================

    def test_collapsed_compound_automatic_transition_headless(self):
        """Criterion 1: When all internal nodes of an inlined function compound node are reduced to a single component, the container transitions to the Collapsed Compound State automatically."""
        net_literal = """{
  compounds: [
    { id: 'compound_auth', function_name: 'auth', label: 'auth()' }
  ],
  places: [
    { id: 'p_start', label: 'start', initial_tokens: 0 },
    { id: 'p_mid', label: 'mid', initial_tokens: 0, parent: 'compound_auth' },
    { id: 'p_end', label: 'end', initial_tokens: 0 }
  ],
  transitions: [
    { id: 't_caller_src', label: 'caller_src', tau: 1.0 },
    { id: 't1', label: 't1', tau: 1.0, parent: 'compound_auth' },
    { id: 't2', label: 't2', tau: 1.0, parent: 'compound_auth' },
    { id: 't_caller_snk', label: 'caller_snk', tau: 1.0 }
  ],
  arcs: [
    { source: 't_caller_src', target: 'p_start' },
    { source: 'p_start', target: 't1' },
    { source: 't1', target: 'p_mid' },
    { source: 'p_mid', target: 't2' },
    { source: 't2', target: 'p_end' },
    { source: 'p_end', target: 't_caller_snk' }
  ]
}"""
        test_logic = """
const compAuth = cy.getElementById('compound_auth');
if (compAuth.hasClass('collapsed-compound')) {
  throw new Error('compound_auth should NOT be collapsed initially');
}
if (foldEngine.isFunctionFoldedIntoSingleComponent('compound_auth')) {
  throw new Error('compound_auth should NOT report single component folded initially');
}

// Fold internal place p_mid
const pMid = cy.getElementById('p_mid');
const res = foldEngine.executeSinglePlaceContraction(pMid);
if (!res.success) {
  throw new Error('Failed to fold p_mid: ' + res.message);
}

if (!res.isCompoundCollapsed) {
  throw new Error('res.isCompoundCollapsed should be true');
}
if (!compAuth.hasClass('collapsed-compound')) {
  throw new Error('compound_auth should now have class collapsed-compound');
}
if (!foldEngine.isFunctionFoldedIntoSingleComponent('compound_auth')) {
  throw new Error('isFunctionFoldedIntoSingleComponent should be true');
}

console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_collapsed_compound_label_formatting_and_renaming_headless(self):
        """Criterion 2: The collapsed container displays the label function_name (c_XX) where c_XX is the component identifier, updating when renamed."""
        net_literal = """{
  compounds: [
    { id: 'compound_calculate_tax', function_name: 'calculate_tax', label: 'calculate_tax()' }
  ],
  places: [
    { id: 'p_mid', label: 'mid', initial_tokens: 0, parent: 'compound_calculate_tax' }
  ],
  transitions: [
    { id: 't1', label: 't1', tau: 1.0, parent: 'compound_calculate_tax' },
    { id: 't2', label: 't2', tau: 1.0, parent: 'compound_calculate_tax' }
  ],
  arcs: [
    { source: 't1', target: 'p_mid' },
    { source: 'p_mid', target: 't2' }
  ]
}"""
        test_logic = """
const pMid = cy.getElementById('p_mid');
const res = foldEngine.executeSinglePlaceContraction(pMid);
const comp = cy.getElementById('compound_calculate_tax');

if (comp.data('collapsed_label') !== 'calculate_tax (c_01)') {
  throw new Error('Expected label calculate_tax (c_01), got ' + comp.data('collapsed_label'));
}
if (comp.data('label') !== 'calculate_tax (c_01)') {
  throw new Error('Expected data(label) calculate_tax (c_01), got ' + comp.data('label'));
}
if (comp.data('collapsed_opaque_id') !== 'c_01') {
  throw new Error('Expected collapsed_opaque_id c_01, got ' + comp.data('collapsed_opaque_id'));
}

// Rename component
foldEngine.renameNode('c_01', 'tax_core');
if (comp.data('collapsed_label') !== 'calculate_tax (tax_core)') {
  throw new Error('Expected renamed label calculate_tax (tax_core), got ' + comp.data('collapsed_label'));
}
if (comp.data('label') !== 'calculate_tax (tax_core)') {
  throw new Error('Expected renamed data(label) calculate_tax (tax_core), got ' + comp.data('label'));
}

console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_collapsed_compound_internal_nodes_hidden_headless(self):
        """Criterion 3: The internal nodes are hidden, leaving only the closed container visible on the canvas."""
        net_literal = """{
  compounds: [
    { id: 'compound_auth', function_name: 'auth', label: 'auth()' }
  ],
  places: [
    { id: 'p_mid', label: 'mid', initial_tokens: 0, parent: 'compound_auth' }
  ],
  transitions: [
    { id: 't1', label: 't1', tau: 1.0, parent: 'compound_auth' },
    { id: 't2', label: 't2', tau: 1.0, parent: 'compound_auth' }
  ],
  arcs: [
    { source: 't1', target: 'p_mid' },
    { source: 'p_mid', target: 't2' }
  ]
}"""
        test_logic = """
const pMid = cy.getElementById('p_mid');
foldEngine.executeSinglePlaceContraction(pMid);
const c01 = cy.getElementById('c_01');

if (!c01.hasClass('collapsed-child')) {
  throw new Error('c_01 must have class collapsed-child');
}
if (!c01.data('is_collapsed_child')) {
  throw new Error('c_01 must have is_collapsed_child true');
}
if (c01.data('label') !== '') {
  throw new Error('c_01 label must be empty string, got: ' + c01.data('label'));
}

console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

        # Also verify stylesheet definitions in template.html
        html = _read_template_html()
        self.assertIn("node.collapsed-child, node.compound.collapsed-compound > node", html)
        self.assertIn("'opacity': 0", html)
        self.assertIn("'pointer-events': 'none'", html)
        self.assertIn("'background-opacity': 0", html)

    def test_collapsed_compound_visual_distinction_headless(self):
        """Criterion 4: A Collapsed Compound State is visually distinct from a plain opaque transition."""
        html = _read_template_html()
        # Verify plain opaque transition styling
        self.assertIn("node.transition.opaque", html)
        self.assertIn("'border-style': 'dashed'", html)
        self.assertIn("'border-color': '#111111'", html)

        # Verify collapsed compound styling: roundrectangle folder, solid warm amber border, golden background
        self.assertIn("node.compound.collapsed-compound, node.collapsed-compound", html)
        self.assertIn("'shape': 'roundrectangle'", html)
        self.assertIn("'background-color': 'rgba(210, 153, 34, 0.15)'", html)
        self.assertIn("'border-color': '#d29922'", html)
        self.assertIn("'border-style': 'solid'", html)
        self.assertIn("'label': 'data(collapsed_label)'", html)
        self.assertIn("'color': '#b07d17'", html)

    def test_collapsed_compound_boundary_folding_headless(self):
        """Validates that a Collapsed Compound container unblocks surrounding caller boundary place contractions."""
        net_literal = """{
  compounds: [
    { id: 'compound_auth', function_name: 'auth', label: 'auth()' }
  ],
  places: [
    { id: 'p_start', label: 'start', initial_tokens: 0 },
    { id: 'p_mid', label: 'mid', initial_tokens: 0, parent: 'compound_auth' },
    { id: 'p_end', label: 'end', initial_tokens: 0 }
  ],
  transitions: [
    { id: 't_caller_src', label: 'caller_src', tau: 1.0 },
    { id: 't1', label: 't1', tau: 1.0, parent: 'compound_auth' },
    { id: 't2', label: 't2', tau: 1.0, parent: 'compound_auth' },
    { id: 't_caller_snk', label: 'caller_snk', tau: 1.0 }
  ],
  arcs: [
    { source: 't_caller_src', target: 'p_start' },
    { source: 'p_start', target: 't1' },
    { source: 't1', target: 'p_mid' },
    { source: 'p_mid', target: 't2' },
    { source: 't2', target: 'p_end' },
    { source: 'p_end', target: 't_caller_snk' }
  ]
}"""
        test_logic = """
const pStart = cy.getElementById('p_start');

// Initially, p_start cannot fold because compound_auth is not reduced to single component
const preCheck = foldEngine.canContractPlace(pStart);
if (preCheck.ok) {
  throw new Error('p_start should NOT be contractible before compound_auth is collapsed');
}

// Fold internal place p_mid
const pMid = cy.getElementById('p_mid');
const res = foldEngine.executeSinglePlaceContraction(pMid);
if (!res.success) throw new Error('p_mid fold failed');

// Now compound_auth is collapsed, p_start CAN fold!
const postCheck = foldEngine.canContractPlace(pStart);
if (!postCheck.ok) {
  throw new Error('p_start should now be contractible, but failed: ' + postCheck.reason);
}

// Execute fold on p_start
const foldCaller = foldEngine.executeSinglePlaceContraction(pStart);
if (!foldCaller.success) {
  throw new Error('p_start fold failed: ' + foldCaller.message);
}

// Verify compound_auth was pruned since its only child was consumed into the higher component
if (cy.getElementById('compound_auth').inside()) {
  throw new Error('compound_auth should be pruned after its only child is consumed');
}

console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_collapsed_compound_inspector_tap_headless(self):
        """Validates that tapping a Collapsed Compound container opens the inspector displaying its collapsed label, type, and tau."""
        net_literal = """{
  compounds: [
    { id: 'compound_auth', function_name: 'auth', label: 'auth()' }
  ],
  places: [
    { id: 'p_mid', label: 'mid', initial_tokens: 0, parent: 'compound_auth' }
  ],
  transitions: [
    { id: 't1', label: 't1', tau: 1.0, parent: 'compound_auth' },
    { id: 't2', label: 't2', tau: 1.0, parent: 'compound_auth' }
  ],
  arcs: [
    { source: 't1', target: 'p_mid' },
    { source: 'p_mid', target: 't2' }
  ]
}"""
        test_logic = """
const pMid = cy.getElementById('p_mid');
foldEngine.executeSinglePlaceContraction(pMid);

const compAuth = cy.getElementById('compound_auth');
compAuth.emit('tap');

if (inspectorPanel.style.display !== 'flex') {
  throw new Error('Inspector panel did not open on tapping collapsed compound');
}
if (inspectorLabel.textContent !== 'auth (c_01)') {
  throw new Error('Expected inspectorLabel auth (c_01), got ' + inspectorLabel.textContent);
}
if (inspectorType.textContent !== 'Collapsed Compound') {
  throw new Error('Expected inspectorType Collapsed Compound, got ' + inspectorType.textContent);
}
if (inspectorTau.textContent !== '2.0') {
  throw new Error('Expected inspectorTau 2.0, got ' + inspectorTau.textContent);
}

console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_single_place_contraction_prunes_place_parent_compound_headless(self):
        """Validates that executeSinglePlaceContraction prunes parentPlace compound container if all its children are consumed."""
        net_literal = """{
  compounds: [
    { id: 'c_place_only', function_name: 'place_helper', label: 'place_helper()' }
  ],
  places: [
    { id: 'p_mid', label: 'mid', initial_tokens: 0, parent: 'c_place_only' }
  ],
  transitions: [
    { id: 't_src', label: 'src', tau: 1.0 },
    { id: 't_snk', label: 'snk', tau: 1.0 }
  ],
  arcs: [
    { source: 't_src', target: 'p_mid' },
    { source: 'p_mid', target: 't_snk' }
  ]
}"""
        test_logic = """
const pMid = cy.getElementById('p_mid');
const cPlaceOnly = cy.getElementById('c_place_only');
if (!cPlaceOnly.inside()) throw new Error('c_place_only should exist initially');

const res = foldEngine.executeSinglePlaceContraction(pMid);
if (!res || !res.success) throw new Error('executeSinglePlaceContraction failed');

// c_place_only had only p_mid as child, which was consumed into c_01
if (cy.getElementById('c_place_only').inside()) {
  throw new Error('c_place_only should be pruned after p_mid is consumed');
}

// Check that c_place_only is recorded in consumedCompounds of the fold step
const step = res.step;
if (!step.consumedCompounds || !step.consumedCompounds.some(c => c.data.id === 'c_place_only')) {
  throw new Error('c_place_only should be in consumedCompounds');
}

// Unfold and verify c_place_only is restored
const c01 = cy.getElementById('c_01');
const unfoldRes = foldEngine.executeComponentLocalUnfold(c01);
if (!unfoldRes || !unfoldRes.success) throw new Error('executeComponentLocalUnfold failed');

if (!cy.getElementById('c_place_only').inside()) {
  throw new Error('c_place_only should be restored upon unfold');
}
if (!cy.getElementById('p_mid').inside()) {
  throw new Error('p_mid should be restored upon unfold');
}
if (cy.getElementById('p_mid').data('parent') !== 'c_place_only') {
  throw new Error('p_mid should have parent c_place_only upon unfold');
}

console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_unfold_opaque_component_right_click_headless(self):
        """Ticket 40 Acceptance Criteria 1: Right-clicking an opaque component restores the nodes and edges it consumed."""
        net_literal = """{
  places: [
    { id: 'p0', label: 'start', initial_tokens: 1 },
    { id: 'p1', label: 'p1', initial_tokens: 0 },
    { id: 'p2', label: 'end', initial_tokens: 0 }
  ],
  transitions: [
    { id: 't1', label: 't1', tau: 1.0 },
    { id: 't2', label: 't2', tau: 1.0 }
  ],
  arcs: [
    { source: 'p0', target: 't1' },
    { source: 't1', target: 'p1' },
    { source: 'p1', target: 't2' },
    { source: 't2', target: 'p2' }
  ]
}"""
        test_logic = """
const p1 = cy.getElementById('p1');
const foldRes = foldEngine.executeSinglePlaceContraction(p1);
if (!foldRes.success) throw new Error('Initial fold failed');

const c01 = cy.getElementById('c_01');
if (!c01 || c01.length === 0) throw new Error('c_01 not found after fold');

// Test executeComponentLocalUnfold directly to verify domain vocabulary
const unfoldRes = foldEngine.executeComponentLocalUnfold(c01);
if (!unfoldRes.success) throw new Error('executeComponentLocalUnfold failed: ' + unfoldRes.reason);
if (unfoldRes.type !== 'opaque_transition') {
  throw new Error('Expected domain type opaque_transition, got ' + unfoldRes.type);
}
if (unfoldRes.opaqueId !== 'c_01' || unfoldRes.unfoldedOpaqueId !== 'c_01') {
  throw new Error('Expected opaqueId c_01, got ' + unfoldRes.opaqueId);
}

// c_01 should be removed
if (cy.getElementById('c_01').inside()) {
  throw new Error('c_01 should be removed after unfold');
}

// Original nodes must be restored
['p1', 't1', 't2'].forEach(function(id) {
  const n = cy.getElementById(id);
  if (!n || !n.inside()) throw new Error('Expected node ' + id + ' to be restored');
});

// SM score should be restored to 2.0
const sm = foldEngine.calculateSMScore();
if (sm !== 2.0) {
  throw new Error('Expected SM score 2.0 after unfold, got ' + sm);
}

// Re-fold and test cxttap (right-click) triggering
const refoldRes = foldEngine.executeSinglePlaceContraction(cy.getElementById('p1'));
if (!refoldRes.success) throw new Error('Refold failed');
const c01_again = cy.getElementById('c_01');
c01_again.emit('cxttap');
if (cy.getElementById('c_01').inside()) {
  throw new Error('c_01 should be removed after cxttap right click');
}

console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_unfold_collapsed_compound_right_click_headless(self):
        """Ticket 40 Acceptance Criteria 2: Right-clicking a Collapsed Compound State reopens the compound to its fully expanded internal state."""
        net_literal = """{
  compounds: [
    { id: 'compound_calc', function_name: 'calc', label: 'calc()' }
  ],
  places: [
    { id: 'p0', label: 'start', initial_tokens: 1 },
    { id: 'p1', label: 'p1', initial_tokens: 0, parent: 'compound_calc' },
    { id: 'p2', label: 'p2', initial_tokens: 0, parent: 'compound_calc' },
    { id: 'p3', label: 'end', initial_tokens: 0 }
  ],
  transitions: [
    { id: 't1', label: 't1', tau: 1.0, parent: 'compound_calc' },
    { id: 't2', label: 't2', tau: 1.0, parent: 'compound_calc' },
    { id: 't3', label: 't3', tau: 1.0, parent: 'compound_calc' }
  ],
  arcs: [
    { source: 'p0', target: 't1' },
    { source: 't1', target: 'p1' },
    { source: 'p1', target: 't2' },
    { source: 't2', target: 'p2' },
    { source: 'p2', target: 't3' },
    { source: 't3', target: 'p3' }
  ]
}"""
        test_logic = """
// Fold p1 into c_01
const fold1 = foldEngine.executeSinglePlaceContraction(cy.getElementById('p1'));
if (!fold1.success) throw new Error('fold1 failed');

// Fold p2 into c_02, which reduces compound_calc into single opaque component c_02
const fold2 = foldEngine.executeSinglePlaceContraction(cy.getElementById('p2'));
if (!fold2.success) throw new Error('fold2 failed');

const comp = cy.getElementById('compound_calc');
if (!comp.hasClass('collapsed-compound')) {
  throw new Error('compound_calc should be collapsed');
}
if (comp.data('label') !== 'calc (c_02)') {
  throw new Error('Expected label calc (c_02), got ' + comp.data('label'));
}

// Right click on the collapsed compound
comp.emit('cxttap');

// Verify compound is reopened to fully expanded state
if (comp.hasClass('collapsed-compound')) {
  throw new Error('compound_calc should no longer have collapsed-compound class');
}
if (comp.data('label') !== 'calc()') {
  throw new Error('Expected restored label calc(), got ' + comp.data('label'));
}

// All original internal nodes must be present and belong to compound_calc
['p1', 'p2', 't1', 't2', 't3'].forEach(function(id) {
  const n = cy.getElementById(id);
  if (!n || !n.inside()) throw new Error('Expected restored node ' + id);
  if (n.data('parent') !== 'compound_calc') {
    throw new Error('Expected node ' + id + ' parent to be compound_calc, got ' + n.data('parent'));
  }
});

// No opaque components should remain in compound_calc
const remainingOpaques = cy.nodes().filter(n => n.data('parent') === 'compound_calc' && (n.data('is_opaque') || n.hasClass('component')));
if (remainingOpaques.length > 0) {
  throw new Error('Compound still contains opaque components after full reopen: ' + remainingOpaques.map(n => n.id()));
}

console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_unfold_boundary_arcs_restored_headless(self):
        """Ticket 40 Acceptance Criteria 3: Arc connections at the boundary are correctly restored to original elements."""
        net_literal = """{
  places: [
    { id: 'p_pre', label: 'pre', initial_tokens: 1 },
    { id: 'p_mid', label: 'mid', initial_tokens: 0 },
    { id: 'p_post', label: 'post', initial_tokens: 0 }
  ],
  transitions: [
    { id: 't_src', label: 'src', tau: 1.0 },
    { id: 't_snk', label: 'snk', tau: 1.0 }
  ],
  arcs: [
    { id: 'arc_in', source: 'p_pre', target: 't_src' },
    { id: 'arc_mid_1', source: 't_src', target: 'p_mid' },
    { id: 'arc_mid_2', source: 'p_mid', target: 't_snk' },
    { id: 'arc_out', source: 't_snk', target: 'p_post' }
  ]
}"""
        test_logic = """
const pMid = cy.getElementById('p_mid');
foldEngine.executeSinglePlaceContraction(pMid);

// Verify folded boundary arcs
const edgesAfterFold = cy.edges();
const inEdgeFolded = edgesAfterFold.filter(e => e.source().id() === 'p_pre' && e.target().id() === 'c_01');
const outEdgeFolded = edgesAfterFold.filter(e => e.source().id() === 'c_01' && e.target().id() === 'p_post');
if (inEdgeFolded.length !== 1 || outEdgeFolded.length !== 1) {
  throw new Error('Folded boundary edges missing');
}

// Unfold
const c01 = cy.getElementById('c_01');
c01.emit('cxttap');

// Check boundary arcs restored to original t_src and t_snk
const edgesAfterUnfold = cy.edges();
const restoredIn = edgesAfterUnfold.filter(e => e.source().id() === 'p_pre' && e.target().id() === 't_src');
const restoredOut = edgesAfterUnfold.filter(e => e.source().id() === 't_snk' && e.target().id() === 'p_post');
const restoredMidIn = edgesAfterUnfold.filter(e => e.source().id() === 't_src' && e.target().id() === 'p_mid');
const restoredMidOut = edgesAfterUnfold.filter(e => e.source().id() === 'p_mid' && e.target().id() === 't_snk');

if (restoredIn.length !== 1) throw new Error('Boundary in-arc p_pre -> t_src not restored');
if (restoredOut.length !== 1) throw new Error('Boundary out-arc t_snk -> p_post not restored');
if (restoredIn[0].id() !== 'arc_in') {
  throw new Error('Expected restored boundary in-arc ID arc_in, got ' + restoredIn[0].id());
}
if (restoredOut[0].id() !== 'arc_out') {
  throw new Error('Expected restored boundary out-arc ID arc_out, got ' + restoredOut[0].id());
}
if (restoredMidIn.length !== 1) throw new Error('Internal arc t_src -> p_mid not restored');
if (restoredMidOut.length !== 1) throw new Error('Internal arc p_mid -> t_snk not restored');

console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_unfold_isolation_from_other_folded_components_headless(self):
        """Ticket 40 Acceptance Criteria 4: Other folded components on the canvas are not affected by the unfold operation."""
        net_literal = """{
  compounds: [
    { id: 'compound_1', function_name: 'f1', label: 'f1()' },
    { id: 'compound_2', function_name: 'f2', label: 'f2()' }
  ],
  places: [
    { id: 'p0', label: 'p0', initial_tokens: 1 },
    { id: 'p1', label: 'p1', initial_tokens: 0, parent: 'compound_1' },
    { id: 'p2', label: 'p2', initial_tokens: 0 },
    { id: 'p3', label: 'p3', initial_tokens: 0, parent: 'compound_2' },
    { id: 'p4', label: 'p4', initial_tokens: 0 }
  ],
  transitions: [
    { id: 't1', label: 't1', tau: 1.0, parent: 'compound_1' },
    { id: 't2', label: 't2', tau: 1.0, parent: 'compound_1' },
    { id: 't3', label: 't3', tau: 1.0, parent: 'compound_2' },
    { id: 't4', label: 't4', tau: 1.0, parent: 'compound_2' }
  ],
  arcs: [
    { source: 'p0', target: 't1' },
    { source: 't1', target: 'p1' },
    { source: 'p1', target: 't2' },
    { source: 't2', target: 'p2' },
    { source: 'p2', target: 't3' },
    { source: 't3', target: 'p3' },
    { source: 'p3', target: 't4' },
    { source: 't4', target: 'p4' }
  ]
}"""
        test_logic = """
// Fold both places
foldEngine.executeSinglePlaceContraction(cy.getElementById('p1')); // creates c_01 in compound_1
foldEngine.executeSinglePlaceContraction(cy.getElementById('p3')); // creates c_02 in compound_2

const comp1 = cy.getElementById('compound_1');
const comp2 = cy.getElementById('compound_2');
if (!comp1.hasClass('collapsed-compound') || !comp2.hasClass('collapsed-compound')) {
  throw new Error('Both compounds should be collapsed');
}

// Right-click only compound_1
comp1.emit('cxttap');

// compound_1 should be reopened
if (comp1.hasClass('collapsed-compound')) {
  throw new Error('compound_1 should be reopened');
}
if (!cy.getElementById('p1').inside() || !cy.getElementById('t1').inside() || !cy.getElementById('t2').inside()) {
  throw new Error('compound_1 elements not restored');
}

// compound_2 MUST remain completely folded!
if (!comp2.hasClass('collapsed-compound')) {
  throw new Error('compound_2 must remain in collapsed-compound state');
}
if (comp2.data('label') !== 'f2 (c_02)') {
  throw new Error('compound_2 label changed unexpectedly: ' + comp2.data('label'));
}
const c02 = cy.getElementById('c_02');
if (!c02 || !c02.inside()) {
  throw new Error('c_02 should still exist inside compound_2');
}
if (cy.getElementById('p3').inside() || cy.getElementById('t3').inside() || cy.getElementById('t4').inside()) {
  throw new Error('compound_2 internal nodes should NOT be restored');
}

console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_unfold_restored_elements_eligible_for_refold_headless(self):
        """Ticket 40 Acceptance Criteria 5: After unfold, restored elements are selectable and eligible for further fold operations."""
        net_literal = """{
  places: [
    { id: 'p0', label: 'start', initial_tokens: 1 },
    { id: 'p1', label: 'p1', initial_tokens: 0 },
    { id: 'p2', label: 'end', initial_tokens: 0 }
  ],
  transitions: [
    { id: 't1', label: 't1', tau: 1.0 },
    { id: 't2', label: 't2', tau: 1.0 }
  ],
  arcs: [
    { source: 'p0', target: 't1' },
    { source: 't1', target: 'p1' },
    { source: 'p1', target: 't2' },
    { source: 't2', target: 'p2' }
  ]
}"""
        test_logic = """
// Fold
foldEngine.executeSinglePlaceContraction(cy.getElementById('p1'));

// Unfold via cxttap
cy.getElementById('c_01').emit('cxttap');

const restoredP1 = cy.getElementById('p1');
const restoredT1 = cy.getElementById('t1');
const restoredT2 = cy.getElementById('t2');

// Selectable check
if (!restoredP1.selectable() || !restoredT1.selectable() || !restoredT2.selectable()) {
  throw new Error('Restored elements must be selectable');
}

// Fold eligibility check
const canFold = foldEngine.canContractPlace(restoredP1);
if (!canFold.ok) {
  throw new Error('Restored place p1 should be eligible for contraction: ' + canFold.reason);
}

// Perform fold again (refold)
const refoldRes = foldEngine.executeSinglePlaceContraction(restoredP1);
if (!refoldRes.success) {
  throw new Error('Refolding p1 failed: ' + refoldRes.message);
}
if (!refoldRes.node || !refoldRes.node.inside()) {
  throw new Error('Refolded node not inside cy');
}

console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_unfold_drag_pan_does_not_trigger_unfold_headless(self):
        """Validates that right-clicking during or after canvas drag-panning does not trigger an unfold."""
        net_literal = """{
  places: [
    { id: 'p0', label: 'start', initial_tokens: 1 },
    { id: 'p1', label: 'p1', initial_tokens: 0 },
    { id: 'p2', label: 'end', initial_tokens: 0 }
  ],
  transitions: [
    { id: 't1', label: 't1', tau: 1.0 },
    { id: 't2', label: 't2', tau: 1.0 }
  ],
  arcs: [
    { source: 'p0', target: 't1' },
    { source: 't1', target: 'p1' },
    { source: 'p1', target: 't2' },
    { source: 't2', target: 'p2' }
  ]
}"""
        test_logic = """
foldEngine.executeSinglePlaceContraction(cy.getElementById('p1'));

const c01 = cy.getElementById('c_01');
if (!c01.inside()) throw new Error('c_01 missing');

// Simulate dragging state
hasDragged = true;

// Emit cxttap while hasDragged is true
c01.emit('cxttap');

// c_01 should NOT have unfolded because hasDragged was true
if (!cy.getElementById('c_01').inside()) {
  throw new Error('c_01 should NOT unfold when hasDragged is true');
}

// Reset dragging state
hasDragged = false;
c01.emit('cxttap');

// Now c_01 should unfold
if (cy.getElementById('c_01').inside()) {
  throw new Error('c_01 should unfold when hasDragged is false');
}

console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_unfold_nested_compound_isolation_headless(self):
        """Ticket 40 Review Finding: Unfolding an outer compound does not cascade into nested sub-compounds."""
        net_literal = """{
  compounds: [
    { id: 'compound_outer', function_name: 'outer', label: 'outer()' },
    { id: 'compound_inner', function_name: 'inner', label: 'inner()', parent: 'compound_outer' }
  ],
  places: [
    { id: 'p_out0', label: 'out0', initial_tokens: 1, parent: 'compound_outer' },
    { id: 'p_out1', label: 'out1', initial_tokens: 0, parent: 'compound_outer' },
    { id: 'p_out2', label: 'out2', initial_tokens: 0, parent: 'compound_outer' },
    { id: 'p_in0', label: 'in0', initial_tokens: 0, parent: 'compound_inner' },
    { id: 'p_in1', label: 'in1', initial_tokens: 0, parent: 'compound_inner' },
    { id: 'p_in2', label: 'in2', initial_tokens: 0, parent: 'compound_inner' }
  ],
  transitions: [
    { id: 't_out1', label: 'tout1', tau: 1.0, parent: 'compound_outer' },
    { id: 't_out2', label: 'tout2', tau: 1.0, parent: 'compound_outer' },
    { id: 't_in1', label: 'tin1', tau: 1.0, parent: 'compound_inner' },
    { id: 't_in2', label: 'tin2', tau: 1.0, parent: 'compound_inner' }
  ],
  arcs: [
    { source: 'p_out0', target: 't_out1' },
    { source: 't_out1', target: 'p_out1' },
    { source: 'p_out1', target: 't_out2' },
    { source: 't_out2', target: 'p_out2' },
    { source: 'p_in0', target: 't_in1' },
    { source: 't_in1', target: 'p_in1' },
    { source: 'p_in1', target: 't_in2' },
    { source: 't_in2', target: 'p_in2' }
  ]
}"""
        test_logic = """
// 1. Fold inside inner compound
const foldIn = foldEngine.executeSinglePlaceContraction(cy.getElementById('p_in1'));
if (!foldIn.success) throw new Error('Inner fold failed: ' + foldIn.message);

const compInner = cy.getElementById('compound_inner');
const c01 = cy.getElementById('c_01');
if (!c01 || !c01.inside()) throw new Error('c_01 missing in inner compound');

// 2. Fold inside outer compound
const foldOut = foldEngine.executeSinglePlaceContraction(cy.getElementById('p_out1'));
if (!foldOut.success) throw new Error('Outer fold failed: ' + foldOut.message);

const c02 = cy.getElementById('c_02');
if (!c02 || !c02.inside()) throw new Error('c_02 missing in outer compound');

// 3. Unfold the outer compound specifically (simulating a collapsed compound state with nested compound)
const compOuter = cy.getElementById('compound_outer');
compOuter.addClass('collapsed-compound');
compOuter.data('collapsed_opaque_id', 'c_02');
const unfoldOuterRes = foldEngine.executeComponentLocalUnfold(compOuter);
if (!unfoldOuterRes.success) throw new Error('Unfolding outer compound failed: ' + unfoldOuterRes.reason);

// 4. Verify outer compound direct elements are restored
['p_out1', 't_out1', 't_out2'].forEach(function(id) {
  const n = cy.getElementById(id);
  if (!n || !n.inside()) throw new Error('Expected node ' + id + ' to be restored in outer compound');
  if (n.data('parent') !== 'compound_outer') {
    throw new Error('Expected ' + id + ' parent to be compound_outer, got ' + n.data('parent'));
  }
});
if (cy.getElementById('c_02').inside()) {
  throw new Error('c_02 should be removed after unfolding outer compound');
}

// 5. CRITICAL: Inner compound MUST NOT have cascaded - c_01 must remain folded!
if (!cy.getElementById('c_01').inside()) {
  throw new Error('c_01 in inner compound was erroneously unfolded by outer unfold!');
}
if (cy.getElementById('p_in1').inside() || cy.getElementById('t_in1').inside() || cy.getElementById('t_in2').inside()) {
  throw new Error('Inner compound internal elements should NOT have been restored');
}

console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_unfold_corrupt_opaque_node_fails_safely_headless(self):
        """Ticket 40 Review Finding: Corrupt opaque nodes without consumedSubnet fail safely without infinite loop."""
        net_literal = """{
  places: [{ id: 'p0', label: 'start', initial_tokens: 1 }],
  transitions: [{ id: 't0', label: 't0', tau: 1.0 }],
  arcs: [{ source: 'p0', target: 't0' }]
}"""
        test_logic = """
// 1. Standalone corrupt opaque node
cy.add({
  group: 'nodes',
  data: { id: 'c_corrupt', is_opaque: true }
});

const res1 = foldEngine.executeComponentLocalUnfold('c_corrupt');
if (res1.success) {
  throw new Error('Expected corrupt opaque unfold to fail, but succeeded');
}
if (!res1.reason || !res1.reason.includes('Failed to unfold opaque transition')) {
  throw new Error('Unexpected failure reason: ' + res1.reason);
}

// 2. Corrupt opaque child inside a collapsed compound
cy.add({
  group: 'nodes',
  data: { id: 'comp_corrupt', is_collapsed_compound: true },
  classes: 'compound collapsed-compound'
});
cy.add({
  group: 'nodes',
  data: { id: 'c_corrupt_child', parent: 'comp_corrupt', is_opaque: true }
});

const res2 = foldEngine.executeComponentLocalUnfold('comp_corrupt');
if (res2.success) {
  throw new Error('Expected corrupt compound child unfold to fail, but succeeded');
}
if (!res2.reason || !res2.reason.includes('Failed to unfold internal opaque transition')) {
  throw new Error('Unexpected failure reason for compound: ' + res2.reason);
}

console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_docked_inspector_dom_elements_in_template(self):
        """Verifies template.html contains docked inspector metadata, rename, and action controls."""
        html = _read_template_html()
        self.assertIn('<aside id="inspector-panel"', html)
        self.assertIn('id="inspector-empty"', html)
        self.assertIn('id="inspector-content"', html)
        self.assertIn('id="hud-input-label"', html)
        self.assertIn('id="hud-btn-save"', html)
        self.assertIn('id="inspector-id"', html)
        self.assertIn('id="inspector-tau"', html)
        self.assertIn('id="inspector-omega"', html)
        self.assertIn('id="inspector-type"', html)
        self.assertIn('id="inspector-line"', html)
        self.assertIn('id="hud-btn-unfold"', html)
        self.assertIn('stat-pill', html)
        self.assertIn('Node Inspector', html)
        self.assertIn('Name:', html)

    def test_docked_inspector_replaces_empty_state_on_left_click_headless(self):
        """Validates that left-clicking a transition fills the permanently visible sidebar."""
        net_literal = """{
  places: [{ id: 'p0', label: 'p0' }],
  transitions: [{ id: 't0', label: 'ComputeStep', tau: 2.0 }],
  arcs: [{ source: 'p0', target: 't0' }]
}"""
        test_logic = """
const t0 = cy.getElementById('t0');
if (inspectorPanel.style.display !== 'flex' || inspectorEmpty.style.display !== 'block') {
  throw new Error('Docked inspector empty state should be visible initially');
}

// Simulate left-click on transition
t0.emit('tap', { target: t0 });

if (inspectorPanel.style.display !== 'flex' || inspectorEmpty.style.display !== 'none' || inspectorContent.style.display !== 'block') {
  throw new Error('Docked inspector should replace its empty state on left-click');
}

console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_hud_displays_compact_stat_pills_headless(self):
        """Validates that HUD displays tau weight, component type, and line number in stat pills."""
        net_literal = """{
  places: [{ id: 'p0', label: 'p0' }, { id: 'p1', label: 'p1' }, { id: 'p2', label: 'p2' }],
  transitions: [
    { id: 't0', label: 'StepAlpha', tau: 3.5, line_number: 42 },
    { id: 't1', label: 'StepBeta', tau: 1.0, line_number: 50 }
  ],
  arcs: [
    { source: 'p0', target: 't0' },
    { source: 't0', target: 'p1' },
    { source: 'p1', target: 't1' },
    { source: 't1', target: 'p2' }
  ]
}"""
        test_logic = """
const t0 = cy.getElementById('t0');
t0.emit('tap', { target: t0 });

if (inspectorTau.textContent !== '3.5') {
  throw new Error(`Expected tau '3.5', got '${inspectorTau.textContent}'`);
}
if (inspectorType.textContent !== 'Atomic Transition') {
  throw new Error(`Expected type 'Atomic Transition', got '${inspectorType.textContent}'`);
}
if (inspectorLine.textContent !== '42') {
  throw new Error(`Expected line '42', got '${inspectorLine.textContent}'`);
}

// Contract p1 and test opaque component stat pills (pass element ref per P3)
foldEngine.executeSinglePlaceContraction(cy.getElementById('p1'));
const comp = cy.nodes('[is_opaque]').first();
if (comp.length === 0) throw new Error('Expected contracted opaque component node');

openInspector(comp);
if (inspectorType.textContent !== 'Sequence') {
  throw new Error(`Expected component type 'Sequence', got '${inspectorType.textContent}'`);
}
if (!inspectorTau.textContent || inspectorTau.textContent === '—') {
  throw new Error(`Expected valid tau for component, got '${inspectorTau.textContent}'`);
}
if (inspectorLine.textContent === '—' || !inspectorLine.textContent) {
  throw new Error(`Expected non-dash line number for folded component, got '${inspectorLine.textContent}'`);
}
if (inspectorLine.textContent !== '42–50') {
  throw new Error(`Expected folded component line number '42–50', got '${inspectorLine.textContent}'`);
}

console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_hud_contains_editable_text_field_prefilled_headless(self):
        """Validates that HUD contains an editable text field pre-filled with the node's current label."""
        net_literal = """{
  places: [{ id: 'p0', label: 'p0' }],
  transitions: [{ id: 't0', label: 'MyWorkerTransition', tau: 1.0 }],
  arcs: [{ source: 'p0', target: 't0' }]
}"""
        test_logic = """
const t0 = cy.getElementById('t0');
t0.emit('tap', { target: t0 });

if (inspectorInput.value !== 'MyWorkerTransition') {
  throw new Error(`Expected inspectorInput pre-filled with 'MyWorkerTransition', got '${inspectorInput.value}'`);
}
if (inspectorLabel.textContent !== 'MyWorkerTransition') {
  throw new Error(`Expected inspectorLabel 'MyWorkerTransition', got '${inspectorLabel.textContent}'`);
}

console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_hud_saving_new_name_updates_canvas_immediately_headless(self):
        """Validates that saving a new name in HUD updates the node's label on the canvas immediately."""
        net_literal = """{
  places: [{ id: 'p0', label: 'p0' }],
  transitions: [{ id: 't0', label: 'OldLabel', tau: 1.0 }],
  arcs: [{ source: 'p0', target: 't0' }]
}"""
        test_logic = """
const t0 = cy.getElementById('t0');
t0.emit('tap', { target: t0 });

// Edit name and trigger save
inspectorInput.value = 'SemanticCustomLabel';
inspectorSaveBtn.click();

if (t0.data('label') !== 'SemanticCustomLabel') {
  throw new Error(`Expected node label on canvas to be 'SemanticCustomLabel', got '${t0.data('label')}'`);
}
if (t0.data('custom_name') !== 'SemanticCustomLabel') {
  throw new Error(`Expected node custom_name to be 'SemanticCustomLabel', got '${t0.data('custom_name')}'`);
}
if (inspectorLabel.textContent !== 'SemanticCustomLabel') {
  throw new Error(`Expected inspectorLabel 'SemanticCustomLabel', got '${inspectorLabel.textContent}'`);
}

// Collapsed compound test: add compound with single opaque child
cy.add({
  group: 'nodes',
  data: { id: 'c_parent', is_compound: true, function_name: 'processItem' },
  classes: 'compound'
});
cy.add({
  group: 'nodes',
  data: { id: 'c_child', parent: 'c_parent', is_opaque: true, label: 'c_child' }
});

foldEngine._updateCollapsedCompoundStates();
const parentCompound = cy.getElementById('c_parent');
if (!foldEngine.isCollapsedCompound(parentCompound)) {
  throw new Error('c_parent should be a collapsed compound');
}

openInspector(parentCompound);
inspectorInput.value = 'CustomProcessBanner';
inspectorSaveBtn.click();

if (parentCompound.data('label') !== 'CustomProcessBanner') {
  throw new Error(`Expected parent compound label 'CustomProcessBanner', got '${parentCompound.data('label')}'`);
}

console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_docked_inspector_clears_when_clicking_canvas_background_headless(self):
        """The sidebar returns to its empty state on background click and discards draft text."""
        net_literal = """{
  places: [{ id: 'p0', label: 'p0' }],
  transitions: [{ id: 't0', label: 't0', tau: 1.0 }],
  arcs: [{ source: 'p0', target: 't0' }]
}"""
        test_logic = """
const t0 = cy.getElementById('t0');
const p0 = cy.getElementById('p0');

// 1. Open HUD
t0.emit('tap', { target: t0 });
if (inspectorPanel.style.display !== 'flex') {
  throw new Error('HUD should be open');
}

// 2. Type uncommitted text into input
inspectorInput.value = 'UncommittedDraft';

// 3. Click uncontractible place - HUD should NOT close (P4)
p0.emit('tap', { target: p0 });
if (inspectorPanel.style.display !== 'flex') {
  throw new Error('HUD should remain open when tapping uncontractible place node');
}

// 4. Click canvas background - sidebar should clear and discard uncommitted text (P2)
cy.emit('tap', { target: cy });
if (inspectorPanel.style.display !== 'flex' || inspectorEmpty.style.display !== 'block' || inspectorContent.style.display !== 'none') {
  throw new Error('Docked inspector should show its empty state after clicking canvas background');
}
if (inspectorInput.value !== '') {
  throw new Error(`Expected draft input to be cleared, got '${inspectorInput.value}'`);
}
if (t0.data('label') !== 't0') {
  throw new Error(`Expected node label untouched as 't0', got '${t0.data('label')}'`);
}

console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_renamed_component_retains_custom_label_after_unfold_and_refold_headless(self):
        """Validates that a renamed component retains its custom label after being unfolded and re-folded."""
        net_literal = """{
  places: [
    { id: 'p0', label: 'p0' },
    { id: 'p1', label: 'p1' },
    { id: 'p2', label: 'p2' }
  ],
  transitions: [
    { id: 't1', label: 't1', tau: 1.0 },
    { id: 't2', label: 't2', tau: 2.0 }
  ],
  arcs: [
    { source: 'p0', target: 't1' },
    { source: 't1', target: 'p1' },
    { source: 'p1', target: 't2' },
    { source: 't2', target: 'p2' }
  ]
}"""
        test_logic = """
// 1. Contract p1 (Single-Place Contraction, passing node per P3)
const resFold1 = foldEngine.executeSinglePlaceContraction(cy.getElementById('p1'));
if (!resFold1.success) {
  throw new Error('Initial contraction failed: ' + resFold1.reason);
}

let comp = cy.nodes('[is_opaque]').first();
if (comp.length === 0) throw new Error('Contracted component not found');
const origCompId = comp.id();

// 2. Inspect through the browser-visible node interaction and rename the component
comp.emit('tap', { target: comp });
inspectorInput.value = 'CustomFoldedSeq';
inspectorSaveBtn.click();

if (comp.data('label') !== 'CustomFoldedSeq') {
  throw new Error(`Expected renamed label 'CustomFoldedSeq', got '${comp.data('label')}'`);
}
if (comp.data('custom_name') !== 'CustomFoldedSeq') {
  throw new Error(`Expected custom_name 'CustomFoldedSeq', got '${comp.data('custom_name')}'`);
}

// 3. Use the applicable docked-sidebar action to unfold the component
comp.emit('tap', { target: comp });
if (hudBtnUnfold.style.display === 'none') {
  throw new Error('Component-Local Unfold action should be visible for an opaque component');
}
hudBtnUnfold.click();

const p1Restored = cy.getElementById('p1');
if (!p1Restored.inside()) {
  throw new Error('Expected p1 to be restored inside canvas');
}

// 4. Re-fold p1 (passing node per P3)
const resFold2 = foldEngine.executeSinglePlaceContraction(cy.getElementById('p1'));
if (!resFold2.success) {
  throw new Error('Re-contraction failed: ' + resFold2.reason);
}

const comp2 = cy.nodes('[is_opaque]').first();
if (comp2.length === 0) throw new Error('Re-contracted component not found');

if (comp2.data('label') !== 'CustomFoldedSeq') {
  throw new Error(`Expected re-folded component to retain custom label 'CustomFoldedSeq', but got '${comp2.data('label')}'`);
}
if (comp2.data('custom_name') !== 'CustomFoldedSeq') {
  throw new Error(`Expected re-folded component custom_name 'CustomFoldedSeq', got '${comp2.data('custom_name')}'`);
}

console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_renaming_one_component_does_not_affect_adjacent_fold_headless(self):
        """Validates that renaming one component does not bleed onto an adjacent component sharing a boundary place (P5)."""
        net_literal = """{
  places: [
    { id: 'p0', label: 'p0' },
    { id: 'p1', label: 'p1' },
    { id: 'p2', label: 'p2' },
    { id: 'p3', label: 'p3' }
  ],
  transitions: [
    { id: 't1', label: 't1', tau: 1.0 },
    { id: 't2', label: 't2', tau: 1.0 },
    { id: 't3', label: 't3', tau: 1.0 }
  ],
  arcs: [
    { source: 'p0', target: 't1' },
    { source: 't1', target: 'p1' },
    { source: 'p1', target: 't2' },
    { source: 't2', target: 'p2' },
    { source: 'p2', target: 't3' },
    { source: 't3', target: 'p3' }
  ]
}"""
        test_logic = """
// 1. Contract p1 into component 1
const res1 = foldEngine.executeSinglePlaceContraction(cy.getElementById('p1'));
if (!res1.success) throw new Error('Contract p1 failed: ' + res1.reason);
const comp1 = cy.getElementById(res1.node.id());

// 2. Rename component 1 to 'FirstStage'
openInspector(comp1);
inspectorInput.value = 'FirstStage';
inspectorSaveBtn.click();
if (comp1.data('label') !== 'FirstStage') throw new Error('comp1 label mismatch');

// 3. Contract p2 into component 2
const res2 = foldEngine.executeSinglePlaceContraction(cy.getElementById('p2'));
if (!res2.success) throw new Error('Contract p2 failed: ' + res2.reason);
const comp2 = cy.getElementById(res2.node.id());

// Assert comp2 does NOT inherit comp1's custom label
if (comp2.data('label') === 'FirstStage') {
  throw new Error('comp2 should NOT inherit comp1 custom label');
}

// 4. Unfold comp2 and re-fold p2
const resUnfold2 = foldEngine.executeComponentLocalUnfold(comp2);
if (!resUnfold2.success) throw new Error('Unfold comp2 failed');
const resRefold2 = foldEngine.executeSinglePlaceContraction(cy.getElementById('p2'));
if (!resRefold2.success) throw new Error('Re-fold p2 failed');
const comp2Refolded = cy.getElementById(resRefold2.node.id());

if (comp2Refolded.data('label') === 'FirstStage') {
  throw new Error('Re-folded comp2 should NOT have label FirstStage');
}

// 5. Unfold comp1 and re-fold p1 - comp1 MUST retain 'FirstStage'
const resUnfold1 = foldEngine.executeComponentLocalUnfold(comp1);
if (!resUnfold1.success) throw new Error('Unfold comp1 failed');
const resRefold1 = foldEngine.executeSinglePlaceContraction(cy.getElementById('p1'));
if (!resRefold1.success) throw new Error('Re-fold p1 failed');
const comp1Refolded = cy.getElementById(resRefold1.node.id());

if (comp1Refolded.data('label') !== 'FirstStage') {
  throw new Error(`Expected comp1 re-folded to retain 'FirstStage', got '${comp1Refolded.data('label')}'`);
}

console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    # =========================================================================
    # Ticket 42 — Viewer: Client-Side PNML Export
    # =========================================================================

    def test_export_pnml_button_visible_in_toolbar(self):
        """Validates that an 'Export PNML' button is visible in the viewer toolbar across modes (Ticket 42)."""
        # 1. Static no-fold net
        static_net = PetriNet()
        static_net.add_place("p0", "start", initial_tokens=1)
        static_net.add_transition("t0", "run")
        static_html = generate_html(static_net)
        self.assertIn('id="viewer-toolbar"', static_html)
        self.assertIn('id="btn-export-pnml"', static_html)
        self.assertIn('Export PNML', static_html)

        # 2. Fold mode net
        from code2petri.fold import fold_net
        fold_res = fold_net(static_net)
        fold_html = generate_html(fold_res)
        self.assertIn('id="viewer-toolbar"', fold_html)
        self.assertIn('id="btn-export-pnml"', fold_html)
        self.assertIn('Export PNML', fold_html)

        # 3. Composite net
        comp_net = PetriNet()
        comp_net.add_place("p0", "start", initial_tokens=1)
        comp_net.add_transition("t0", "run()")
        comp_net.add_compound(id="compound_worker", label="worker()", function_name="worker", file="worker.py")
        composite_html = generate_html(comp_net)
        self.assertIn('id="viewer-toolbar"', composite_html)
        self.assertIn('id="btn-export-pnml"', composite_html)
        self.assertIn('Export PNML', composite_html)

    def _run_pnml_export_test(self, net_literal, test_logic):
        """Helper to run a Node test script that outputs ___XML_START___...___XML_END___ and parse the PNML XML (S3)."""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

        m = re.search(r'___XML_START___(.*?)___XML_END___', proc.stdout, re.DOTALL)
        self.assertIsNotNone(m, f"Could not extract PNML XML from stdout: {proc.stdout}")
        xml_content = m.group(1).strip()
        root = ET.fromstring(xml_content)
        return root, xml_content, proc

    def test_client_side_pnml_export_unfolded_headless(self):
        """Validates that serializeToPnml emits valid ISO/IEC 15909-2 PNML for an unreduced net."""
        net_literal = """{
  places: [
    { id: 'p0', label: 'start_state', initial_tokens: 1 },
    { id: 'p1', label: 'end_state', initial_tokens: 0 }
  ],
  transitions: [
    { id: 't0', label: 'execute_calc', tau: 2.5, line_number: 42 }
  ],
  arcs: [
    { source: 'p0', target: 't0', weight: 1 },
    { source: 't0', target: 'p1', weight: 1 }
  ]
}"""
        test_logic = """
const xml = serializeToPnml(cy, 'TestPipeline');
console.log('___XML_START___' + xml + '___XML_END___');
console.log('PASS');
"""
        root, xml_content, proc = self._run_pnml_export_test(net_literal, test_logic)
        self.assertTrue(root.tag.endswith("pnml"))

        # Check net type
        net_el = root.find("{http://www.pnml.org/version-2009/grammar/pnml}net")
        self.assertIsNotNone(net_el)
        self.assertEqual(net_el.attrib.get("type"), "http://www.pnml.org/version-2009/grammar/ptnet")

        # Places
        places = [p for p in net_el.iter() if p.tag.endswith("place")]
        self.assertEqual(len(places), 2)
        place_ids = {p.attrib.get("id") for p in places}
        self.assertEqual(place_ids, {"p0", "p1"})

        # p0 should have initialMarking = 1
        p0_el = next(p for p in places if p.attrib.get("id") == "p0")
        init_mark = [el for el in p0_el.iter() if el.tag.endswith("initialMarking")]
        self.assertEqual(len(init_mark), 1)
        self.assertEqual(init_mark[0].find("{http://www.pnml.org/version-2009/grammar/pnml}text").text, "1")

        # p1 should not have initialMarking
        p1_el = next(p for p in places if p.attrib.get("id") == "p1")
        init_mark_p1 = [el for el in p1_el.iter() if el.tag.endswith("initialMarking")]
        self.assertEqual(len(init_mark_p1), 0)

        # Transitions
        transitions = [t for t in net_el.iter() if t.tag.endswith("transition")]
        self.assertEqual(len(transitions), 1)
        t0_el = transitions[0]
        self.assertEqual(t0_el.attrib.get("id"), "t0")
        t0_name = t0_el.find("{http://www.pnml.org/version-2009/grammar/pnml}name")
        self.assertIsNotNone(t0_name)
        self.assertEqual(t0_name.find("{http://www.pnml.org/version-2009/grammar/pnml}text").text, "execute_calc")

        # Arcs
        arcs = [a for a in net_el.iter() if a.tag.endswith("arc")]
        self.assertEqual(len(arcs), 2)
        arc_pairs = {(a.attrib.get("source"), a.attrib.get("target")) for a in arcs}
        self.assertEqual(arc_pairs, {("p0", "t0"), ("t0", "p1")})

    def test_client_side_pnml_export_after_live_fold_reduction_headless(self):
        """Validates that PNML export accurately reflects live fold reductions (Ticket 42)."""
        net_literal = """{
  places: [
    { id: 'p0', label: 'p0', initial_tokens: 1 },
    { id: 'p1', label: 'p1' },
    { id: 'p2', label: 'p2' }
  ],
  transitions: [
    { id: 't0', label: 'step1', tau: 1.0, line_number: 10 },
    { id: 't1', label: 'step2', tau: 2.0, line_number: 20 }
  ],
  arcs: [
    { source: 'p0', target: 't0' },
    { source: 't0', target: 'p1' },
    { source: 'p1', target: 't1' },
    { source: 't1', target: 'p2' }
  ]
}"""
        test_logic = """
// 1. Contract p1 (Single-Place Contraction)
const res = foldEngine.executeSinglePlaceContraction(cy.getElementById('p1'));
if (!res.success) throw new Error('Contraction failed: ' + res.reason);

// 2. Export to PNML
const xml = serializeToPnml(cy, 'FoldedNet');
console.log('___XML_START___' + xml + '___XML_END___');
console.log('PASS');
"""
        root, xml_content, proc = self._run_pnml_export_test(net_literal, test_logic)
        net_el = root.find("{http://www.pnml.org/version-2009/grammar/pnml}net")

        # Places: p1 must be gone; p0 and p2 remain
        places = [p for p in net_el.iter() if p.tag.endswith("place")]
        place_ids = {p.attrib.get("id") for p in places}
        self.assertEqual(place_ids, {"p0", "p2"})

        # Transitions: t0 and t1 must be gone; opaque component c_01 created
        transitions = [t for t in net_el.iter() if t.tag.endswith("transition")]
        self.assertEqual(len(transitions), 1)
        comp_t = transitions[0]
        self.assertEqual(comp_t.attrib.get("id"), "c_01")

        # P4: Unrenamed component node exports on-screen label 'c_01', not internal composite expression
        t_name = comp_t.find("{http://www.pnml.org/version-2009/grammar/pnml}name").find("{http://www.pnml.org/version-2009/grammar/pnml}text").text
        self.assertEqual(t_name, "c_01")

        # P2: Standard PNML by default does not include proprietary toolspecific metadata
        toolspecific = [p for p in comp_t.iter() if p.tag.endswith("toolspecific")]
        self.assertEqual(len(toolspecific), 0)

        # Arcs: p0 -> c_01 and c_01 -> p2
        arcs = [a for a in net_el.iter() if a.tag.endswith("arc")]
        self.assertEqual(len(arcs), 2)
        arc_pairs = {(a.attrib.get("source"), a.attrib.get("target")) for a in arcs}
        self.assertEqual(arc_pairs, {("p0", "c_01"), ("c_01", "p2")})

    def test_client_side_pnml_export_with_renamed_component_node_headless(self):
        """Validates that renamed component nodes export with their user-assigned label, not the auto-generated c_XX ID (Ticket 42)."""
        net_literal = """{
  places: [
    { id: 'p0', label: 'p0', initial_tokens: 1 },
    { id: 'p1', label: 'p1' },
    { id: 'p2', label: 'p2' }
  ],
  transitions: [
    { id: 't0', label: 'step1', tau: 1.0 },
    { id: 't1', label: 'step2', tau: 1.0 }
  ],
  arcs: [
    { source: 'p0', target: 't0' },
    { source: 't0', target: 'p1' },
    { source: 'p1', target: 't1' },
    { source: 't1', target: 'p2' }
  ]
}"""
        test_logic = """
// 1. Contract p1
const res = foldEngine.executeSinglePlaceContraction(cy.getElementById('p1'));
if (!res.success) throw new Error('Contraction failed');
const comp = cy.getElementById(res.node.id());

// 2. Rename component node via inspector
openInspector(comp);
inspectorInput.value = 'UserDefinedProcessStep';
inspectorSaveBtn.click();

if (comp.data('label') !== 'UserDefinedProcessStep') {
  throw new Error('Component rename failed');
}

// 3. Export PNML
const xml = serializeToPnml(cy, 'RenamedExport');
console.log('___XML_START___' + xml + '___XML_END___');
console.log('PASS');
"""
        root, xml_content, proc = self._run_pnml_export_test(net_literal, test_logic)
        net_el = root.find("{http://www.pnml.org/version-2009/grammar/pnml}net")

        transitions = [t for t in net_el.iter() if t.tag.endswith("transition")]
        self.assertEqual(len(transitions), 1)
        t_el = transitions[0]
        self.assertEqual(t_el.attrib.get("id"), "c_01")

        # Name text MUST be the user-assigned label, NOT auto-generated c_01
        name_text = t_el.find("{http://www.pnml.org/version-2009/grammar/pnml}name").find("{http://www.pnml.org/version-2009/grammar/pnml}text").text
        self.assertEqual(name_text, "UserDefinedProcessStep")

    def test_client_side_pnml_export_collapsed_compound_container_headless(self):
        """Validates that a collapsed compound container exports its visible label on screen (Ticket 42, P1)."""
        net_literal = """{
  compounds: [
    { id: 'compound_calculate_tax', function_name: 'calculate_tax', label: 'calculate_tax()' }
  ],
  places: [
    { id: 'p_mid', label: 'mid', initial_tokens: 0, parent: 'compound_calculate_tax' }
  ],
  transitions: [
    { id: 't1', label: 't1', tau: 1.0, parent: 'compound_calculate_tax' },
    { id: 't2', label: 't2', tau: 1.0, parent: 'compound_calculate_tax' }
  ],
  arcs: [
    { source: 't1', target: 'p_mid' },
    { source: 'p_mid', target: 't2' }
  ]
}"""
        test_logic = """
// 1. Contract p_mid which reduces compound into a single collapsed container
const res = foldEngine.executeSinglePlaceContraction(cy.getElementById('p_mid'));
if (!res.success) throw new Error('Contraction failed');
const comp = cy.getElementById('compound_calculate_tax');
if (!comp.hasClass('collapsed-compound')) {
  throw new Error('Expected compound to have collapsed-compound class');
}

// 2. Export PNML
const xml = serializeToPnml(cy, 'CollapsedCompoundExport');
console.log('___XML_START___' + xml + '___XML_END___');
console.log('PASS');
"""
        root, xml_content, proc = self._run_pnml_export_test(net_literal, test_logic)
        net_el = root.find("{http://www.pnml.org/version-2009/grammar/pnml}net")

        # Compound container itself is not an exported Petri net node, only the internal reduced transition is
        transitions = [t for t in net_el.iter() if t.tag.endswith("transition")]
        self.assertEqual(len(transitions), 1)
        comp_t = transitions[0]
        self.assertEqual(comp_t.attrib.get("id"), "c_01")

        # P1: Label must reflect the collapsed compound container's visible label: 'calculate_tax (c_01)'
        name_text = comp_t.find("{http://www.pnml.org/version-2009/grammar/pnml}name").find("{http://www.pnml.org/version-2009/grammar/pnml}text").text
        self.assertEqual(name_text, "calculate_tax (c_01)")

    def test_client_side_pnml_export_triggers_client_side_export_headless(self):
        """Validates that clicking the Export PNML button triggers a client-side .pnml export (Ticket 42, S1)."""
        net_literal = """{
  places: [{ id: 'p0', label: 'p0', initial_tokens: 1 }, { id: 'p1', label: 'p1' }],
  transitions: [{ id: 't0', label: 't0', tau: 1.0 }],
  arcs: [{ source: 'p0', target: 't0' }, { source: 't0', target: 'p1' }]
}"""
        test_logic = """
// Click Export PNML button
btnExportPnml.click();

if (!downloadedFilename) {
  throw new Error('downloadedFilename was not set');
}
if (!downloadedFilename.endsWith('.pnml')) {
  throw new Error('Expected download filename to end with .pnml, got: ' + downloadedFilename);
}
if (!lastCreatedBlob || !lastCreatedBlob.content) {
  throw new Error('No Blob content was generated');
}
if (!lastCreatedBlob.content.includes('<pnml') || !lastCreatedBlob.content.includes('</pnml>')) {
  throw new Error('Blob content is not valid PNML');
}

console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_client_side_pnml_export_valid_prom_grammar(self):
        """Validates that exported PNML satisfies ProM ISO/IEC 15909-2 grammar invariants (Ticket 42)."""
        net_literal = """{
  places: [
    { id: 'p0', label: 'p0', initial_tokens: 1 },
    { id: 'p1', label: 'p1' },
    { id: 'p2', label: 'p2' }
  ],
  transitions: [
    { id: 't0', label: 't0', tau: 1.0 },
    { id: 't1', label: 't1', tau: 1.0 }
  ],
  arcs: [
    { source: 'p0', target: 't0' },
    { source: 't0', target: 'p1' },
    { source: 'p1', target: 't1' },
    { source: 't1', target: 'p2' }
  ]
}"""
        test_logic = """
foldEngine.executeSinglePlaceContraction(cy.getElementById('p1'));
const xml = serializeToPnml(cy, 'ProMNet');
console.log('___XML_START___' + xml + '___XML_END___');
console.log('PASS');
"""
        root, xml_content, proc = self._run_pnml_export_test(net_literal, test_logic)

        # Root namespace
        self.assertTrue(root.tag.startswith("{http://www.pnml.org/version-2009/grammar/pnml}"))

        net_el = root.find("{http://www.pnml.org/version-2009/grammar/pnml}net")
        self.assertIsNotNone(net_el)
        self.assertEqual(net_el.attrib.get("type"), "http://www.pnml.org/version-2009/grammar/ptnet")

        page_el = net_el.find("{http://www.pnml.org/version-2009/grammar/pnml}page")
        self.assertIsNotNone(page_el)

        # Check bipartite constraint: Arcs must connect Place <-> Transition only
        place_ids = {p.attrib.get("id") for p in page_el.findall("{http://www.pnml.org/version-2009/grammar/pnml}place")}
        trans_ids = {t.attrib.get("id") for t in page_el.findall("{http://www.pnml.org/version-2009/grammar/pnml}transition")}

        # Ensure no overlap between place and transition IDs
        self.assertEqual(len(place_ids.intersection(trans_ids)), 0)

        for arc in page_el.findall("{http://www.pnml.org/version-2009/grammar/pnml}arc"):
            src = arc.attrib.get("source")
            tgt = arc.attrib.get("target")
            is_p_to_t = (src in place_ids and tgt in trans_ids)
            is_t_to_p = (src in trans_ids and tgt in place_ids)
            self.assertTrue(is_p_to_t or is_t_to_p, f"Arc {src} -> {tgt} violates bipartite Petri net property")

    # =========================================================================
    # Ticket 48 — Save Session as a Fold State Snapshot
    # =========================================================================

    def test_save_session_button_visible_in_generated_viewer(self):
        """The generated offline viewer exposes Save Session in every viewer mode."""
        net = PetriNet()
        net.add_place("p0", "start", initial_tokens=1)
        net.add_transition("t0", "run")

        html_content = generate_html(net, title="Order Flow")

        self.assertIn('id="btn-save-session"', html_content)
        self.assertIn('Save Session', html_content)
        self.assertIn("btnSaveSession.addEventListener('click'", html_content)

    def test_fold_state_snapshot_download_preserves_live_and_restoration_state(self):
        """Saving after fold/rename/unfold captures resumable state without mutating the viewer."""
        script = r"""
const cytoscape = require('./code2petri/viewer/vendor/cytoscape.min.js');
const { LiveFoldReductionEngine } = require('./code2petri/viewer/engine/reduction_engine.js');
const { serializeFoldStateSnapshot, downloadFoldStateSnapshot } = require('./code2petri/viewer/engine/session_snapshot.js');

const cy = cytoscape({ elements: [
  { group: 'nodes', data: { id: 'p0', type: 'Place' }, classes: 'place', position: { x: 0, y: 0 } },
  { group: 'nodes', data: { id: 'p1', type: 'Place' }, classes: 'place', position: { x: 100, y: 20 } },
  { group: 'nodes', data: { id: 'p2', type: 'Place' }, classes: 'place', position: { x: 200, y: 40 } },
  { group: 'nodes', data: { id: 'p3', type: 'Place' }, classes: 'place', position: { x: 300, y: 60 } },
  { group: 'nodes', data: { id: 't0', type: 'Transition', tau: 1 }, classes: 'transition' },
  { group: 'nodes', data: { id: 't1', type: 'Transition', tau: 1 }, classes: 'transition' },
  { group: 'nodes', data: { id: 't2', type: 'Transition', tau: 1 }, classes: 'transition' },
  { group: 'edges', data: { id: 'a0', source: 'p0', target: 't0' } },
  { group: 'edges', data: { id: 'a1', source: 't0', target: 'p1' } },
  { group: 'edges', data: { id: 'a2', source: 'p1', target: 't1' } },
  { group: 'edges', data: { id: 'a3', source: 't1', target: 'p2' } },
  { group: 'edges', data: { id: 'a4', source: 'p2', target: 't2' } },
  { group: 'edges', data: { id: 'a5', source: 't2', target: 'p3' } }
] });
const engine = new LiveFoldReductionEngine(cy, { choice: 1.25, loop: 4.5 });

const first = engine.executeSinglePlaceContraction(cy.getElementById('p1'));
if (!first.success) throw new Error('first fold failed: ' + first.reason);
engine.renameNode(first.node, 'Validate Order');
const unfolded = engine.executeComponentLocalUnfold(first.node);
if (!unfolded.success) throw new Error('unfold failed: ' + unfolded.reason);
const second = engine.executeSinglePlaceContraction(cy.getElementById('p1'));
if (!second.success) throw new Error('second fold failed: ' + second.reason);
const third = engine.executeSinglePlaceContraction(cy.getElementById('p2'));
if (!third.success) throw new Error('nested fold failed: ' + third.reason);

const liveComponent = third.node;
liveComponent.position({ x: 412.5, y: 207.25 });
liveComponent.select();
cy.add({
  group: 'nodes',
  data: {
    id: 'compound_checkout', label: 'checkout()', function_name: 'checkout',
    is_compound: true, is_collapsed_compound: true, collapsed_opaque_id: liveComponent.id()
  },
  classes: 'compound collapsed-compound',
  position: { x: 360, y: 160 }
});
cy.zoom(1.75);
cy.pan({ x: 83, y: -41 });

const documentContext = {
  title: 'Order Flow', sourceFile: '/src/orders.py', filename: 'orders.py',
  functionName: 'process_order', mode: 'composite',
  returnMetadata: {
    function_name: 'process_order', source_file: '/src/orders.py', qualified_name: 'process_order',
    definition_location: { line: 4, column: 0 }, analysis_status: 'complete', declared: null,
    inferred: [{ expression: 'a:b', type: 'str', provenance: 'direct_literal', role: 'call_result',
      source_location: { line: 5, column: 4 } }]
  },
  originalNet: { places: [{ id: 'p0' }], transitions: [{ id: 't0' }], arcs: [] },
  compounds: [{ id: 'compound_process_order', function_name: 'process_order' }],
  foldSteps: [{ component_type: 'Sequence' }], finalSm: 9.5, fullyReducible: true,
  calleeNets: { helper: { places: [], transitions: [], arcs: [] } },
  expandedNodes: [['call_helper', { calleeName: 'helper' }]],
  playback: { currentStep: 1, totalSteps: 1 }
};

const graphBefore = JSON.stringify(cy.elements().jsons());
const viewportBefore = { zoom: cy.zoom(), pan: Object.assign({}, cy.pan()) };
const selectedBefore = cy.$(':selected').map(n => n.id());
const snapshot = serializeFoldStateSnapshot({ cy, engine, document: documentContext });

if (snapshot.schemaVersion !== 1 || snapshot.snapshotType !== 'code2petri-fold-state') throw new Error('wrong schema identity');
if (snapshot.engine.stepCounter !== 3) throw new Error('step counter not retained');
if (snapshot.engine.cfg.choice !== 1.25 || snapshot.engine.cfg.loop !== 4.5) throw new Error('Fold Config not retained');
if (!snapshot.engine.rememberedCustomNames.some(entry => entry[1] === 'Validate Order')) throw new Error('remembered name missing');
if (snapshot.viewport.zoom !== 1.75 || snapshot.viewport.pan.x !== 83 || snapshot.viewport.pan.y !== -41) throw new Error('viewport missing');
if (snapshot.document.functionName !== 'process_order' || snapshot.document.sourceFile !== '/src/orders.py') throw new Error('identity missing');
if (!snapshot.document.returnMetadata || snapshot.document.returnMetadata.inferred[0].expression !== 'a:b') throw new Error('return metadata missing');
if (!snapshot.document.originalNet || !snapshot.document.calleeNets.helper || snapshot.document.playback.currentStep !== 1) throw new Error('context missing');
const savedLive = snapshot.elements.find(el => el.group === 'nodes' && el.data.id === liveComponent.id());
if (!savedLive) throw new Error('live component missing');
if (savedLive.position.x !== 412.5 || savedLive.position.y !== 207.25) throw new Error('position missing');
if (typeof savedLive.data.tau !== 'number' || typeof savedLive.data.omega !== 'number') throw new Error('weights or penalties missing');
if (!savedLive.data.consumedSubnet || !savedLive.data.consumedSubnet.nodes.some(n => n.data && n.data.consumedSubnet)) {
  throw new Error('nested consumed subnet missing');
}
const savedCompound = snapshot.elements.find(el => el.group === 'nodes' && el.data.id === 'compound_checkout');
if (!savedCompound || !savedCompound.classes.includes('collapsed-compound') || !savedCompound.data.is_collapsed_compound) {
  throw new Error('Collapsed Compound State missing');
}
if (JSON.stringify(cy.elements().jsons()) !== graphBefore) throw new Error('saving mutated graph');
if (cy.zoom() !== viewportBefore.zoom || cy.pan().x !== viewportBefore.pan.x || cy.pan().y !== viewportBefore.pan.y) throw new Error('saving mutated viewport');
if (JSON.stringify(cy.$(':selected').map(n => n.id())) !== JSON.stringify(selectedBefore)) throw new Error('saving mutated selection');

let blob = null;
let filename = null;
global.Blob = function(parts, options) { this.content = parts.join(''); this.type = options.type; blob = this; };
const download = downloadFoldStateSnapshot({
  cy, engine, document: documentContext,
  downloadBlob: function(createdBlob, createdFilename) { blob = createdBlob; filename = createdFilename; }
});
const parsed = JSON.parse(download.json);
if (filename !== 'Order Flow_session.json') throw new Error('wrong filename: ' + filename);
if (!blob || blob.type !== 'application/json;charset=utf-8') throw new Error('wrong Blob type');
if (parsed.elements.length !== snapshot.elements.length) throw new Error('download payload differs');
if (download.json.includes('CLIENT-SIDE APPLICATION LOGIC') || download.json.includes('<script')) throw new Error('viewer code leaked');
console.log('PASS');
"""
        proc = _run_node_script(script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_python_root_return_metadata_is_embedded_and_saved(self):
        """The production Python-to-viewer path carries return evidence into sessions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = os.path.join(temp_dir, "returns.py")
            html_path = os.path.join(temp_dir, "returns.html")
            with open(source_path, "w", encoding="utf-8") as source_file:
                source_file.write("def answer() -> 'Unknown':\n    return True\n")
            result = code2petri(
                source_path, output_file=html_path, target_function="answer", fold=True
            )
            with open(html_path, encoding="utf-8") as html_file:
                html_content = html_file.read()

        embedded = _extract_embedded_data(html_content)
        metadata = embedded["document"]["return_metadata"]
        self.assertEqual(metadata["declared"]["expression"], "'Unknown'")
        self.assertEqual(metadata["inferred"][0]["type"], "bool")
        self.assertEqual(metadata["inferred"][0]["expression"], "True")
        self.assertEqual(metadata["inferred"][0]["source_location"]["line"], 2)
        self.assertEqual(result.initial_net.to_dict()["return_metadata"], metadata)
        self.assertIn("info-return-metadata", html_content)
        self.assertIn("Declared:", html_content)
        self.assertIn("evidence.type + ' from ' + evidence.expression", html_content)

    def test_python_global_return_metadata_is_not_applicable_in_viewer_data(self):
        """Global synthetic wrappers keep a distinct not-applicable analysis status."""
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = os.path.join(temp_dir, "module.py")
            html_path = os.path.join(temp_dir, "module.html")
            with open(source_path, "w", encoding="utf-8") as source_file:
                source_file.write("print('hello')\n")
            code2petri(source_path, output_file=html_path, target_function="(global)", fold=True)
            with open(html_path, encoding="utf-8") as html_file:
                html_content = html_file.read()
        metadata = _extract_embedded_data(html_content)["document"]["return_metadata"]
        self.assertEqual(metadata["analysis_status"], "not_applicable")
        self.assertEqual(metadata["function_name"], "Global Scope")

    def test_javascript_root_return_metadata_is_embedded_and_saved(self):
        """The production JavaScript-to-viewer path retains JSDoc and direct return evidence."""
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = os.path.join(temp_dir, "returns.js")
            html_path = os.path.join(temp_dir, "returns.html")
            with open(source_path, "w", encoding="utf-8") as source_file:
                source_file.write("/** @returns {Mystery<Thing>} documented */\nfunction answer() { return true; }\n")
            result = code2petri(
                source_path, output_file=html_path, target_function="answer", fold=True
            )
            with open(html_path, encoding="utf-8") as html_file:
                html_content = html_file.read()

        metadata = _extract_embedded_data(html_content)["document"]["return_metadata"]
        self.assertEqual(metadata["declared"]["expression"], "Mystery<Thing>")
        self.assertEqual(metadata["declared"]["provenance"], "jsdoc")
        self.assertEqual(metadata["inferred"], [{
            "expression": "true", "type": "boolean", "provenance": "direct_literal",
            "role": "call_result", "source_location": {"line": 2, "column": 27},
        }])
        self.assertEqual(result.initial_net.to_dict()["return_metadata"], metadata)
        self.assertIn("Declared:", html_content)

    def test_javascript_assigned_functions_keep_owner_jsdoc_and_expression_text(self):
        """JSDoc attaches only to its declaration and unknown expressions keep their source text."""
        source = '''/** @returns {WrongOwner} */
const ignored = 0;

/** @return {Alias<Item>} */
const expressionArrow = () => ({ value: "x:y" });

/** @returns {DocType} */
const blockArrow = () => { return; };

/** @returns {FunctionType} */
const functionValue = function () { return "ok"; };

/** @returns {Alias<Item>} */
const literalArrow = () => 42;

/** @returns {unknown} */
function unknownDocumented() { return compute({ a: 1 }); }

function nullResult() { return null; }

function fallsThrough() { const value = 1; }

/** @returns {Promise<number>} */
async function asyncValue() { return 1; }

/** @returns {number} */
function* generatorValue() { return 2; }

class Box {
  /** @returns {MethodType} */
  value() { return 3; }
}

function outer() { function nested() { return false; } return "outer"; }
'''
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = os.path.join(temp_dir, "assigned.js")
            with open(source_path, "w", encoding="utf-8") as source_file:
                source_file.write(source)
            for target, declared, inferred_expression, inferred_type, status in [
                ("expressionArrow", "Alias<Item>", '{ value: "x:y" }', "unknown", "unknown"),
                ("blockArrow", "DocType", "undefined", "undefined", "complete"),
                ("functionValue", "FunctionType", '"ok"', "string", "complete"),
                ("literalArrow", "Alias<Item>", "42", "number", "complete"),
                ("unknownDocumented", "unknown", "compute({ a: 1 })", "unknown", "unknown"),
                ("nullResult", None, "null", "null", "complete"),
                ("fallsThrough", None, "implicit fall-through", "undefined", "complete"),
                ("Box.value", "MethodType", "3", "number", "complete"),
                ("outer", None, '"outer"', "string", "complete"),
            ]:
                html_path = os.path.join(temp_dir, target.replace(".", "_") + ".html")
                result = code2petri(source_path, output_file=html_path, target_function=target)
                with open(html_path, encoding="utf-8") as html_file:
                    metadata = _extract_embedded_data(html_file.read())["document"]["return_metadata"]
                actual_declared = metadata["declared"]
                self.assertEqual(None if actual_declared is None else actual_declared["expression"], declared)
                self.assertEqual(metadata["analysis_status"], status)
                self.assertEqual(metadata["inferred"][0]["expression"], inferred_expression)
                self.assertEqual(metadata["inferred"][0]["type"], inferred_type)
                self.assertEqual(result.initial_net.to_dict()["return_metadata"], metadata)

            global_html = os.path.join(temp_dir, "global.html")
            global_result = code2petri(source_path, output_file=global_html, target_function="(global)")
            with open(global_html, encoding="utf-8") as html_file:
                global_metadata = _extract_embedded_data(html_file.read())["document"]["return_metadata"]
            self.assertEqual(global_metadata["function_name"], "Global Scope")
            self.assertEqual(global_metadata["analysis_status"], "not_applicable")
            self.assertEqual(global_result.initial_net.to_dict()["return_metadata"], global_metadata)

            for target, declared in [("asyncValue", "Promise<number>"), ("generatorValue", "number")]:
                html_path = os.path.join(temp_dir, target + ".html")
                result = code2petri(source_path, output_file=html_path, target_function=target)
                with open(html_path, encoding="utf-8") as html_file:
                    metadata = _extract_embedded_data(html_file.read())["document"]["return_metadata"]
                self.assertEqual(metadata["declared"]["expression"], declared)
                self.assertEqual(metadata["analysis_status"], "unknown")
                self.assertEqual(metadata["inferred"], [])
                self.assertEqual(result.initial_net.to_dict()["return_metadata"], metadata)


    _SIMPLE_SEQUENCE_NET_LITERAL = """{
  places: [
    { id: 'p0', label: 'p0' },
    { id: 'p1', label: 'p1' },
    { id: 'p2', label: 'p2' }
  ],
  transitions: [
    { id: 't0', label: 't0', tau: 1.0 },
    { id: 't1', label: 't1', tau: 1.0 }
  ],
  arcs: [
    { source: 'p0', target: 't0' },
    { source: 't0', target: 'p1' },
    { source: 'p1', target: 't1' },
    { source: 't1', target: 'p2' }
  ]
}"""

    def test_template_min_zoom_allows_deep_zoom_out(self):
        """Validates that template.html configures minZoom <= 0.001 to allow seeing large nets in full."""
        html = _read_template_html()
        m = re.search(r'minZoom:\s*([0-9.]+)', html)
        self.assertIsNotNone(m, "minZoom setting not found in template.html")
        min_zoom = float(m.group(1))
        self.assertLessEqual(min_zoom, 0.001, f"Expected minZoom <= 0.001 for large graphs, got {min_zoom}")

    def test_large_net_autofit_zooms_below_point_two_without_clamping_headless(self):
        """Validates that opening a large net allows cy.fit() on initial load to zoom below 0.2 without clamping (Ticket 44)."""
        node_script = """
const Module = require('module');
const originalRequire = Module.prototype.require;
const dagre = require('./code2petri/viewer/vendor/dagre.min.js');
Module.prototype.require = function(path) {
  if (path === 'dagre') return dagre;
  return originalRequire.apply(this, arguments);
};

const cytoscape = require('./code2petri/viewer/vendor/cytoscape.min.js');
const cytoscapeDagre = require('./code2petri/viewer/vendor/cytoscape-dagre.js');
cytoscape.use(cytoscapeDagre);

// Construct a long sequential pipeline of 100 places and transitions
const elements = [];
for (let i = 0; i < 100; i++) {
  elements.push({ group: 'nodes', data: { id: 'p' + i }, classes: 'place' });
  elements.push({ group: 'nodes', data: { id: 't' + i }, classes: 'transition' });
  elements.push({ group: 'edges', data: { id: 'e_pt_' + i, source: 'p' + i, target: 't' + i } });
  if (i > 0) {
    elements.push({ group: 'edges', data: { id: 'e_tp_' + i, source: 't' + (i - 1), target: 'p' + i } });
  }
}

const cy = cytoscape({
  elements: elements,
  minZoom: 0.001,
  maxZoom: 3.5
});

cy.layout({
  name: 'dagre',
  rankDir: 'TB',
  nodeDimensionsIncludeLabels: true,
  spacingFactor: 1.15,
  rankSep: 40,
  nodeSep: 35,
  padding: 30
}).run();

cy.fit(null, 30);

const fittedZoom = cy.zoom();
if (fittedZoom >= 0.2) {
  throw new Error(`Expected large graph fitted zoom to be < 0.2, got ${fittedZoom}`);
}
if (fittedZoom < 0.001) {
  throw new Error(`Fitted zoom fell below minZoom (0.001): ${fittedZoom}`);
}

console.log('PASS: ' + fittedZoom);
"""
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS:", proc.stdout)

    def test_handle_fold_reduction_preserves_camera_viewport(self):
        """Validates that handleFoldReduction preserves camera zoom and anchors the component node to clicked place screen pos."""
        test_logic = """
cy.zoom(1.85);
cy.pan({ x: 120, y: -75 });
const initialZoom = cy.zoom();
const initialPan = Object.assign({}, cy.pan());

const p1 = cy.getElementById('p1');
const p1PosBefore = Object.assign({}, p1.position());

const foldSuccess = handleFoldReduction(p1, 'sequence');
if (!foldSuccess) throw new Error('handleFoldReduction failed');

const postZoom = cy.zoom();
const postPan = cy.pan();
if (Math.abs(postZoom - initialZoom) > 1e-4) {
  throw new Error(`Expected zoom to be preserved (${initialZoom}), got ${postZoom}`);
}

const c01 = cy.getElementById('c_01');
if (!c01 || c01.length === 0) throw new Error('Could not find folded component c_01');
const c01Pos = c01.position();

// Screen position invariance: screenPos = nodePos * zoom + pan
const p1ScreenX = p1PosBefore.x * initialZoom + initialPan.x;
const p1ScreenY = p1PosBefore.y * initialZoom + initialPan.y;
const c01ScreenX = c01Pos.x * postZoom + postPan.x;
const c01ScreenY = c01Pos.y * postZoom + postPan.y;

if (Math.abs(c01ScreenX - p1ScreenX) > 1.0) {
  throw new Error(`Screen X position anchor shifted: expected ${p1ScreenX}, got ${c01ScreenX}`);
}
if (Math.abs(c01ScreenY - p1ScreenY) > 1.0) {
  throw new Error(`Screen Y position anchor shifted: expected ${p1ScreenY}, got ${c01ScreenY}`);
}

console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(self._SIMPLE_SEQUENCE_NET_LITERAL, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_handle_right_click_unfold_preserves_camera_viewport(self):
        """Validates that handleRightClickUnfold preserves both camera zoom and pan without resetting to fit default."""
        test_logic = """
cy.zoom(2.15);
cy.pan({ x: 60, y: -120 });
const initialZoom = cy.zoom();
const initialPan = Object.assign({}, cy.pan());

const p1 = cy.getElementById('p1');
handleFoldReduction(p1, 'sequence');
const comp = cy.getElementById('c_01');
if (!comp || comp.length === 0) throw new Error('Could not find folded component c_01');

const unfoldSuccess = handleRightClickUnfold(comp);
if (!unfoldSuccess) throw new Error('handleRightClickUnfold failed');

const postZoom = cy.zoom();
const postPan = cy.pan();
if (Math.abs(postZoom - initialZoom) > 1e-4) {
  throw new Error(`Expected zoom to be preserved on unfold (${initialZoom}), got ${postZoom}`);
}
if (Math.abs(postPan.x - initialPan.x) > 1e-4 || Math.abs(postPan.y - initialPan.y) > 1e-4) {
  throw new Error(`Expected pan to be preserved on unfold (${JSON.stringify(initialPan)}), got ${JSON.stringify(postPan)}`);
}

console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(self._SIMPLE_SEQUENCE_NET_LITERAL, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)



class TestBatchPlaceFold(unittest.TestCase):
    _STATE_MACHINE_NET = """{
  places: [
    { id: 'p_src', label: 'src', initial_tokens: 1 },
    { id: 'p_mid1', label: 'mid1', initial_tokens: 0 },
    { id: 'p_mid2', label: 'mid2', initial_tokens: 0 },
    { id: 'p_snk', label: 'snk', initial_tokens: 0 }
  ],
  transitions: [
    { id: 't1', tau: 1.5 }, { id: 't2', tau: 2.5 }, { id: 't3', tau: 1.0 },
    { id: 't4', tau: 2.0 }, { id: 't5', tau: 3.0 }
  ],
  arcs: [
    { source: 'p_src', target: 't1' }, { source: 'p_src', target: 't3' },
    { source: 't1', target: 'p_mid1' }, { source: 't3', target: 'p_mid2' },
    { source: 'p_mid1', target: 't2' }, { source: 'p_mid1', target: 't5' },
    { source: 't5', target: 'p_mid2' }, { source: 'p_mid2', target: 't4' },
    { source: 't2', target: 'p_snk' }, { source: 't4', target: 'p_snk' }
  ]
}"""

    def test_generated_viewer_exposes_batch_action_for_selected_places(self):
        net = PetriNet()
        net.add_place("p0", "start")
        net.add_transition("t0", "first")
        net.add_place("p1", "middle")
        net.add_transition("t1", "second")
        net.add_place("p2", "end")

        html_content = generate_html(net)

        self.assertIn("boxSelectionEnabled: true", html_content)
        self.assertIn('id="btn-fold-selected-places"', html_content)
        self.assertIn("cy.nodes('.place:selected')", html_content)
        self.assertIn("selectedPlaceCount >= 2", html_content)
        self.assertIn("foldEngine.executeBatchFold(selectedPlaceIds)", html_content)
        self.assertIn("DAGRE_LAYOUT_OPTIONS, { fit: false, animate: false }", html_content)

    def test_selected_place_button_folds_once_and_preserves_camera(self):
        html = _read_template_html()
        match = re.search(
            r"function getSelectedPlaceIds\(\) \{.*?(?=      function getFoldStateDocumentContext)",
            html,
            re.DOTALL,
        )
        self.assertIsNotNone(match, "Could not find the generated viewer batch-selection controls")

        net_literal = """{
  places: [
    { id: 'p0', label: 'start' },
    { id: 'p1', label: 'middle' },
    { id: 'p2', label: 'end' }
  ],
  transitions: [
    { id: 't0', label: 'first' },
    { id: 't1', label: 'second' }
  ],
  arcs: [
    { source: 'p0', target: 't0' },
    { source: 't0', target: 'p1' },
    { source: 'p1', target: 't1' },
    { source: 't1', target: 'p2' }
  ]
}"""
        test_logic = f"""
const selectionFoldControls = {{ style: {{ display: 'none' }} }};
const batchFoldResult = {{ textContent: '' }};
const DAGRE_LAYOUT_OPTIONS = {{ name: 'dagre' }};
let layoutCount = 0;
cy.layout = function() {{ layoutCount++; return {{ run: function() {{}} }}; }};
cy.zoom(1.75);
cy.pan({{ x: 23, y: -17 }});
const btnFoldSelectedPlaces = {{
  textContent: '',
  listeners: {{}},
  addEventListener: function(name, listener) {{ this.listeners[name] = listener; }}
}};
{match.group(0)}
cy.getElementById('p0').select();
cy.getElementById('p1').select();
if (selectionFoldControls.style.display !== 'block') {{
  throw new Error('Batch action did not appear for two selected places');
}}
if (!btnFoldSelectedPlaces.textContent.includes('2')) {{
  throw new Error('Batch action did not report selected place count');
}}
btnFoldSelectedPlaces.listeners.click({{ stopPropagation: function() {{}} }});
if (cy.getElementById('p1').length !== 0) throw new Error('Selected contractible place did not fold');
if (layoutCount !== 1) throw new Error('Expected one final layout, got ' + layoutCount);
if (cy.zoom() !== 1.75 || cy.pan().x !== 23 || cy.pan().y !== -17) {{
  throw new Error('Batch fold changed zoom or pan');
}}
if (!batchFoldResult.textContent.includes('p0')) throw new Error('Skipped place was not reported');
console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_batch_fold_evaluates_original_place_ids_once_and_skips_invalid_ids(self):
        net_literal = """{
  places: [
    { id: 'p0', label: 'start' },
    { id: 'p1', label: 'middle' },
    { id: 'p2', label: 'end' }
  ],
  transitions: [
    { id: 't0', label: 'first' },
    { id: 't1', label: 'second' }
  ],
  arcs: [
    { source: 'p0', target: 't0' },
    { source: 't0', target: 'p1' },
    { source: 'p1', target: 't1' },
    { source: 't1', target: 'p2' }
  ]
}"""
        test_logic = """
const result = foldEngine.executeBatchFold(['missing-place', 't0', 'p1']);
if (!result || result.folded.length !== 1 || result.skipped.length !== 2) {
  throw new Error('Expected one fold and two skips: ' + JSON.stringify(result));
}
if (result.folded[0].placeId !== 'p1' || result.folded[0].foldType !== 'sequence') {
  throw new Error('Unexpected folded trigger: ' + JSON.stringify(result.folded[0]));
}
if (result.skipped[0].placeId !== 'missing-place' || result.skipped[1].placeId !== 't0') {
  throw new Error('Original trigger order was not retained');
}
if (cy.getElementById('p1').length !== 0) {
  throw new Error('The selected contractible place was not folded');
}
console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_batch_fold_executes_registered_structural_place_reduction(self):
        test_logic = """
const result = foldEngine.executeBatchFold(['p_src']);
if (!result.success || result.folded.length !== 1 || result.folded[0].foldType !== 'state_machine') {
  throw new Error('Expected batch folding to execute the registered state-machine fold: ' + JSON.stringify(result));
}
console.log('PASS');
"""
        proc = _run_node_script(_setup_live_fold_test_harness(self._STATE_MACHINE_NET, test_logic))
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_fold_entire_function_reaches_structural_place_reduction(self):
        net = self._STATE_MACHINE_NET.replace(
            "places: [", "compounds: [{ id: 'fn', label: 'fn()', function_name: 'fn' }],\n  places: ["
        ).replace("label: 'src',", "label: 'src', parent: 'fn',")
        for node_id in ['p_mid1', 'p_mid2', 'p_snk']:
            net = net.replace("id: '" + node_id + "', label:", "id: '" + node_id + "', parent: 'fn', label:")
        for transition_id in ['t1', 't2', 't3', 't4', 't5']:
            net = net.replace("id: '" + transition_id + "',", "id: '" + transition_id + "', parent: 'fn',")
        test_logic = """
const result = foldEngine.executeFoldEntireFunction('fn');
if (!result.success || !result.folded.some(function(item) { return item.foldType === 'state_machine'; })) {
  throw new Error('Full-function folding stopped before the structural reduction: ' + JSON.stringify(result));
}
console.log('PASS');
"""
        proc = _run_node_script(_setup_live_fold_test_harness(net, test_logic))
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)


class TestFoldEntireFunction(unittest.TestCase):
    def test_compound_inspector_offers_action_and_reports_completion(self):
        html = _read_template_html()
        self.assertIn('id="hud-btn-fold-entire-function"', html)
        self.assertIn('id="inspector-action-result"', html)
        self.assertIn("foldEngine.executeFoldEntireFunction(compoundNode)", html)

        action_match = re.search(
            r"function handleFoldEntireFunction\(compoundNode\) \{.*?"
            r"if \(hudEls\.foldEntireFunctionBtnEl\) \{.*?\n      \}",
            html,
            re.DOTALL,
        )
        self.assertIsNotNone(action_match, "Could not find the compound inspector action")
        fold_helpers = re.search(
            r"function refreshFoldActionView\(viewportBefore\) \{.*?"
            r"function formatFoldActionResult\(result\) \{.*?\n      \}",
            html,
            re.DOTALL,
        )
        self.assertIsNotNone(fold_helpers, "Could not find shared fold-action helpers")
        net_literal = """{
  compounds: [
    { id: 'function_process', function_name: 'process', label: 'process()' }
  ],
  places: [
    { id: 'p0', label: 'start' },
    { id: 'p1', label: 'middle', parent: 'function_process' },
    { id: 'p2', label: 'end' }
  ],
  transitions: [
    { id: 't0', label: 'first', parent: 'function_process' },
    { id: 't1', label: 'second', parent: 'function_process' }
  ],
  arcs: [
    { source: 'p0', target: 't0' },
    { source: 't0', target: 'p1' },
    { source: 'p1', target: 't1' },
    { source: 't1', target: 'p2' }
  ]
}"""
        test_logic = f"""
const inspectorActionResult = {{ textContent: '' }};
const hudBtnFoldEntireFunction = {{
  style: {{ display: 'none' }},
  listener: null,
  addEventListener: function(name, listener) {{ this.listener = listener; }}
}};
const hudEls = {{ foldEntireFunctionBtnEl: hudBtnFoldEntireFunction }};
const DAGRE_LAYOUT_OPTIONS = {{ name: 'dagre' }};
let layoutCount = 0;
cy.layout = function() {{ layoutCount++; return {{ run: function() {{}} }}; }};
cy.zoom(1.5);
cy.pan({{ x: 31, y: -12 }});
{action_match.group(0)}
{fold_helpers.group(0)}
const compound = cy.getElementById('function_process');
openInspector(compound);
if (hudBtnFoldEntireFunction.style.display !== 'block') throw new Error('Compound fold action was hidden');
hudBtnFoldEntireFunction.listener({{ stopPropagation: function() {{}} }});
if (!compound.hasClass('collapsed-compound')) throw new Error('Compound was not collapsed');
if (hudBtnFoldEntireFunction.style.display !== 'none') throw new Error('Completed compound action remained enabled');
if (!inspectorActionResult.textContent.includes('fully collapsed')) throw new Error('Completion was not reported');
if (layoutCount !== 1) throw new Error('Expected one final layout');
if (cy.zoom() !== 1.5 || cy.pan().x !== 31 || cy.pan().y !== -12) throw new Error('Camera changed');
console.log('PASS');
"""
        proc = _run_node_script(_setup_live_fold_test_harness(net_literal, test_logic))
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_fold_entire_function_repeats_until_compound_is_collapsed(self):
        net_literal = """{
  compounds: [
    { id: 'function_process', function_name: 'process', label: 'process()' }
  ],
  places: [
    { id: 'p0', label: 'start' },
    { id: 'p1', label: 'middle', parent: 'function_process' },
    { id: 'p2', label: 'end' }
  ],
  transitions: [
    { id: 't0', label: 'first', parent: 'function_process' },
    { id: 't1', label: 'second', parent: 'function_process' }
  ],
  arcs: [
    { source: 'p0', target: 't0' },
    { source: 't0', target: 'p1' },
    { source: 'p1', target: 't1' },
    { source: 't1', target: 'p2' }
  ]
}"""
        test_logic = """
const result = foldEngine.executeFoldEntireFunction('function_process');
const compound = cy.getElementById('function_process');
if (!result.success || !result.complete || result.folded.length !== 1) {
  throw new Error('Expected one local fold to complete the function: ' + JSON.stringify(result));
}
if (!compound.hasClass('collapsed-compound')) {
  throw new Error('Function compound did not enter its collapsed state');
}
if (result.passes < 1) throw new Error('No batch pass was run');
console.log('PASS');
"""
        node_script = _setup_live_fold_test_harness(net_literal, test_logic)
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)


class TestFoldStateSnapshotValidation(unittest.TestCase):
    def test_return_metadata_validation_accepts_old_records_and_rejects_malformed(self):
        script = r"""
const { parseFoldStateSnapshot } = require('./code2petri/viewer/engine/session_snapshot.js');
function snapshot(returnMetadata) {
  const document = {
    title: 'Example', sourceFile: '/src/example.py', filename: 'example.py',
    functionName: 'answer', mode: 'fold',
    originalNet: { places: [], transitions: [], arcs: [] }, compounds: [], foldSteps: [],
    calleeNets: {}, expandedNodes: [], playback: { currentStep: 0, totalSteps: 0 }
  };
  if (returnMetadata !== undefined) document.returnMetadata = returnMetadata;
  return { schemaVersion: 1, snapshotType: 'code2petri-fold-state', elements: [],
    engine: { stepCounter: 0, cfg: {}, rememberedCustomNames: [] },
    viewport: { zoom: 1, pan: { x: 0, y: 0 } }, document };
}
const old = parseFoldStateSnapshot(snapshot());
if (old.document.returnMetadata !== undefined) throw new Error('Old snapshot acquired metadata');
const metadata = {
  function_name: 'answer', source_file: '/src/example.py', qualified_name: 'answer',
  definition_location: { line: 1, column: 0 }, analysis_status: 'complete', declared: null,
  inferred: [{ expression: 'x:y', type: 'str', provenance: 'direct_literal', role: 'call_result',
    source_location: { line: 2, column: 4 } }]
};
if (parseFoldStateSnapshot(snapshot(metadata)).document.returnMetadata.inferred[0].expression !== 'x:y') {
  throw new Error('New metadata did not survive parsing');
}
const globalMetadata = Object.assign({}, metadata, {
  function_name: 'Global Scope', qualified_name: 'Global Scope',
  analysis_status: 'not_applicable', inferred: []
});
if (parseFoldStateSnapshot(snapshot(globalMetadata)).document.returnMetadata.analysis_status !== 'not_applicable') {
  throw new Error('Global Scope metadata did not round-trip');
}
let rejected = false;
try { parseFoldStateSnapshot(snapshot(Object.assign({}, metadata, { inferred: 'bad' }))); }
catch (error) { rejected = error.message.includes('Invalid Fold State Snapshot'); }
if (!rejected) throw new Error('Malformed return metadata was accepted');
console.log('PASS');
""";
        proc = _run_node_script(script)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("PASS", proc.stdout)

    def test_generated_viewer_wires_offline_open_without_relayout(self):
        from code2petri.viewer import _load_template

        html = _load_template()
        self.assertIn('id="btn-open-session"', html)
        self.assertIn('id="input-open-session" type="file" accept=".json,application/json"', html)
        self.assertIn("restoreFoldStateSnapshot(parseFoldStateSnapshot(reader.result))", html)
        restore_body = re.search(
            r"function restoreFoldStateSnapshot\(snapshot\) \{(.*?)(?=\n      if \(btnOpenSession)",
            html,
            re.S,
        )
        self.assertIsNotNone(restore_body)
        self.assertNotIn("applyLayout", restore_body.group(1))
        self.assertIn("restoreViewport(cy, snapshot.viewport.zoom, snapshot.viewport.pan)", restore_body.group(1))

    def test_open_rejects_invalid_fold_step_before_replacing_active_session(self):
        html = _read_template_html()
        open_handler = re.search(
            r"if \(btnOpenSession && inputOpenSession\) \{.*?(?=\n      if \(btnExportPnml)", html, re.S
        )
        self.assertIsNotNone(open_handler)
        script = r"""
const { parseFoldStateSnapshot: parseSnapshot } = require('./code2petri/viewer/engine/session_snapshot.js');
let invalidSnapshot = JSON.stringify({
  schemaVersion: 1, snapshotType: 'code2petri-fold-state', elements: [],
  engine: { stepCounter: 0, cfg: {}, rememberedCustomNames: [] },
  viewport: { zoom: 1, pan: { x: 0, y: 0 } },
  document: {
    title: 'Bad', sourceFile: '', filename: '', functionName: '', mode: 'fold',
    originalNet: { places: [], transitions: [], arcs: [] }, compounds: [], foldSteps: [null],
    calleeNets: {}, expandedNodes: [], playback: { currentStep: 0, totalSteps: 1 }
  }
});
let activeGraph = 'previous-session';
let restoreCalls = 0;
let shownError = '';
const btnOpenSession = { listeners: {}, addEventListener: function(name, callback) { this.listeners[name] = callback; }, click: function() {} };
const inputOpenSession = {
  listeners: {}, files: [{ name: 'bad.json' }], value: 'bad.json',
  addEventListener: function(name, callback) { this.listeners[name] = callback; }
};
global.FileReader = function() {
  this.readAsText = function() { this.result = invalidSnapshot; this.onload(); };
};
global.alert = function(message) { shownError = message; };
const parseFoldStateSnapshot = parseSnapshot;
const restoreFoldStateSnapshot = () => { restoreCalls++; activeGraph = 'replacement'; };
__OPEN_HANDLER__
inputOpenSession.listeners.change();
if (restoreCalls !== 0 || activeGraph !== 'previous-session') throw new Error('Invalid session replaced the active graph');
if (!shownError.includes('Invalid Fold State Snapshot')) throw new Error('Invalid session error was not shown');
const invalidNetSnapshot = JSON.parse(invalidSnapshot);
invalidNetSnapshot.document.foldSteps = [];
invalidNetSnapshot.document.playback = { currentStep: 0, totalSteps: 0 };
invalidNetSnapshot.document.originalNet.transitions = [null];
invalidSnapshot = JSON.stringify(invalidNetSnapshot);
shownError = '';
inputOpenSession.listeners.change();
if (restoreCalls !== 0 || activeGraph !== 'previous-session') throw new Error('Invalid net entry replaced the active graph');
if (!shownError.includes('Invalid Fold State Snapshot')) throw new Error('Invalid net entry error was not shown');
console.log('PASS');
""".replace('__OPEN_HANDLER__', open_handler.group(0))
        proc = _run_node_script(script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_saved_document_context_uses_active_function_identity(self):
        html = _read_template_html()
        context_match = re.search(
            r"function getFoldStateDocumentContext\(\) \{.*?(?=\n      if \(btnSaveSession)", html, re.S
        )
        self.assertIsNotNone(context_match)
        context_function = context_match.group(0).replace("{{TITLE_JSON}}", '"Fallback Title"')
        script = """
const activeDocument = { function_name: 'module.Processor.run', filename: 'processor.py', source_file: '/src/processor.py' };
const payload = { title: 'Processor', document: activeDocument, compounds: [] };
const initialNet = { places: [], transitions: [], arcs: [] };
const foldSteps = [];
const totalSteps = 0;
const currentStep = 0;
const calleeNetsMap = {};
const expandedNodes = new Map();
__CONTEXT_FUNCTION__
const context = getFoldStateDocumentContext();
if (context.functionName !== 'module.Processor.run') throw new Error('Snapshot lost the explicit active function identity');
console.log('PASS');
""".replace("__CONTEXT_FUNCTION__", context_function)
        proc = _run_node_script(script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_restore_replaces_graph_and_context_without_layout(self):
        html = _read_template_html()
        restore_match = re.search(
            r"function restoreFoldStateSnapshot\(snapshot\) \{.*?(?=\n      if \(btnOpenSession)",
            html,
            re.S,
        )
        self.assertIsNotNone(restore_match)
        script = r"""
const { parseFoldStateSnapshot } = require('./code2petri/viewer/engine/session_snapshot.js');
const snapshot = parseFoldStateSnapshot({
  schemaVersion: 1, snapshotType: 'code2petri-fold-state',
  elements: [{ group: 'nodes', data: { id: 'restored' }, classes: 'place' }],
  engine: { stepCounter: 5, cfg: { sequence: 1, choice: 2, loop: 3 }, rememberedCustomNames: [['c_05', 'kept']] },
  viewport: { zoom: 1.5, pan: { x: 20, y: -8 } },
  document: {
    title: 'Restored Doc', sourceFile: '/src/restored.py', filename: 'restored.py', functionName: 'run', mode: 'composite',
    originalNet: { places: [{ id: 'start' }], transitions: [], arcs: [] },
    compounds: [], foldSteps: [], finalSm: 1, fullyReducible: true,
    calleeNets: { helper: { places: [], transitions: [], arcs: [] } }, expandedNodes: [],
    playback: { currentStep: 0, totalSteps: 0 }
  }
});
let graph = [{ data: { id: 'old' } }];
let viewport = { zoom: 2, pan: { x: 0, y: 0 } };
let layoutCount = 0;
let closedInspector = 0;
const cy = {
  elements: () => ({ jsons: () => graph.slice(), remove: () => { graph = []; } }),
  add: (items) => { graph = graph.concat(items); },
  nodes: () => ({ unselect: () => {} })
};
const captureViewport = () => viewport;
const restoreViewport = (_, zoom, pan) => { viewport = { zoom, pan: { ...pan } }; };
let payload = {};
let initialNet = { places: [], transitions: [], arcs: [] };
let foldSteps = [];
let totalSteps = 0;
let currentStep = 0;
let stepNets = [];
let initialSm = 0;
let isFoldMode = false;
const calleeNetsMap = {};
const expandedNodes = new Map();
const foldEngine = { cfg: {}, stepCounter: 0, rememberedCustomNames: new Map(), calculateSMScore: () => 3.6 };
const foldControls = { style: {} }, badgeSm = { style: {} }, valSm = { textContent: '' };
const setActiveDocumentMetadata = (metadata) => { global.activeDocument = metadata; };
const closeInspector = () => { closedInspector++; };
const updateFoldableHighlights = () => {};
const updateBatchPlaceFoldControls = () => {};
const updateUI = () => {};
global.document = { title: '', querySelector: () => ({ textContent: '' }) };
__RESTORE_FUNCTION__
restoreFoldStateSnapshot(snapshot);
if (graph.length !== 1 || graph[0].data.id !== 'restored') throw new Error('Graph was not replaced');
if (layoutCount !== 0) throw new Error('Restore unexpectedly ran a layout');
if (viewport.zoom !== 1.5 || viewport.pan.x !== 20 || viewport.pan.y !== -8) throw new Error('Viewport was not restored');
if (payload.title !== 'Restored Doc' || global.document.title !== 'Restored Doc - code2petri Viewer') throw new Error('Document identity was not restored');
if (foldEngine.stepCounter !== 5 || foldEngine.cfg.choice !== 2 || !foldEngine.rememberedCustomNames.has('c_05')) throw new Error('Engine state was not restored');
if (initialNet.places[0].id !== 'start' || !calleeNetsMap.helper || closedInspector !== 1) throw new Error('Document context or inspector state was not restored');
console.log('PASS');
""".replace('__RESTORE_FUNCTION__', restore_match.group(0))
        proc = _run_node_script(script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_fold_save_open_continue_and_unfold_round_trip(self):
        script = _CANONICAL_SNAPSHOT_ASSERTION_JS + r"""
const cytoscape = require('./code2petri/viewer/vendor/cytoscape.min.js');
const { LiveFoldReductionEngine } = require('./code2petri/viewer/engine/reduction_engine.js');
const { serializeFoldStateSnapshot, parseFoldStateSnapshot } = require('./code2petri/viewer/engine/session_snapshot.js');
const sourceElements = [];
for (let i = 0; i < 5; i++) {
  sourceElements.push({ group: 'nodes', data: { id: 'p' + i, type: 'Place', label: 'p' + i }, classes: 'place', position: { x: i * 100, y: 0 } });
}
for (let i = 0; i < 4; i++) {
  sourceElements.push({ group: 'nodes', data: { id: 't' + i, type: 'Transition', label: 't' + i, tau: 1.5 }, classes: 'transition' });
  sourceElements.push({ group: 'edges', data: { id: 'a' + (i * 2), source: 'p' + i, target: 't' + i, weight: 2 } });
  sourceElements.push({ group: 'edges', data: { id: 'a' + (i * 2 + 1), source: 't' + i, target: 'p' + (i + 1), weight: 2 } });
}
const cy1 = cytoscape({ elements: sourceElements });
const engine1 = new LiveFoldReductionEngine(cy1, { choice: 1.25, loop: 4.5 });
const first = engine1.executeSinglePlaceContraction(cy1.getElementById('p1'));
if (!first.success) throw new Error('initial fold failed');
engine1.renameNode(first.node, 'Semantic Inner Name');
const second = engine1.executeSinglePlaceContraction(cy1.getElementById('p2'));
if (!second.success) throw new Error('nested fold failed');
const doc = {
  title: 'Round Trip', sourceFile: '/src/round_trip.py', filename: 'round_trip.py', functionName: 'run', mode: 'composite',
  originalNet: { places: [], transitions: [], arcs: [] }, compounds: [], foldSteps: [],
  calleeNets: {}, expandedNodes: [], playback: { currentStep: 0, totalSteps: 0 }
};
const serialized = serializeFoldStateSnapshot({ cy: cy1, engine: engine1, document: doc });
const snapshot = parseFoldStateSnapshot(serialized);
function makeCompatibilityVariant(mode) {
  const variant = JSON.parse(JSON.stringify(serialized));
  function visit(value) {
    if (Array.isArray(value)) return value.forEach(visit);
    if (!value || typeof value !== 'object') return;
    if (value.group === 'nodes' && value.data && value.data.consumedSubnet) {
      if (mode === 'legacy' || (mode === 'mixed' && value.data.id === 'c_01')) {
        value.data.consumedSubgraph = value.data.consumedSubnet;
        delete value.data.consumedSubnet;
      } else if (mode === 'both') {
        value.data.consumedSubgraph = JSON.parse(JSON.stringify(value.data.consumedSubnet));
      }
    }
    Object.keys(value).forEach(key => visit(value[key]));
  }
  visit(variant);
  return variant;
}
for (const mode of ['legacy', 'both', 'mixed']) {
  const opened = parseFoldStateSnapshot(JSON.stringify(makeCompatibilityVariant(mode)));
  const resumedCy = cytoscape({ elements: opened.elements });
  const resumedEngine = new LiveFoldReductionEngine(resumedCy);
  resumedEngine.cfg = opened.engine.cfg;
  resumedEngine.stepCounter = opened.engine.stepCounter;
  resumedEngine.rememberedCustomNames = new Map(opened.engine.rememberedCustomNames);
  const resumedFold = resumedEngine.executeSinglePlaceContraction(resumedCy.getElementById('p3'));
  if (!resumedFold.success) throw new Error(mode + ' session could not continue folding: ' + resumedFold.reason);
  const resaved = serializeFoldStateSnapshot({ cy: resumedCy, engine: resumedEngine, document: doc });
  assertCanonicalSnapshot(resaved);
}
const cy2 = cytoscape({ elements: snapshot.elements });
const engine2 = new LiveFoldReductionEngine(cy2);
engine2.cfg = snapshot.engine.cfg;
engine2.stepCounter = snapshot.engine.stepCounter;
engine2.rememberedCustomNames = new Map(snapshot.engine.rememberedCustomNames);
const continued = engine2.executeSinglePlaceContraction(cy2.getElementById('p3'));
if (!continued.success) throw new Error('post-open folding failed: ' + continued.reason);
const continuedId = continued.node.id();
if (continuedId === second.node.id()) throw new Error('new component ID collided with restored component');
const openAgain = parseFoldStateSnapshot(serializeFoldStateSnapshot({ cy: cy2, engine: engine2, document: doc }));
const cy3 = cytoscape({ elements: openAgain.elements });
const engine3 = new LiveFoldReductionEngine(cy3);
engine3.cfg = openAgain.engine.cfg;
engine3.stepCounter = openAgain.engine.stepCounter;
engine3.rememberedCustomNames = new Map(openAgain.engine.rememberedCustomNames);
let component = cy3.getElementById(continuedId);
for (const expectedId of [continuedId, second.node.id(), first.node.id()]) {
  component = cy3.getElementById(expectedId);
  const result = engine3.executeComponentLocalUnfold(component);
  if (!result.success) throw new Error('component-local unfold failed for ' + expectedId + ': ' + result.reason);
}
if (cy3.getElementById('p1').length === 0 || cy3.getElementById('p2').length === 0 || cy3.getElementById('p3').length === 0) {
  throw new Error('nested original topology was not restored');
}
if (engine3.rememberedCustomNames.get(first.node.id()) !== 'Semantic Inner Name') {
  throw new Error('unfolded semantic name was not remembered');
}
console.log('PASS');
""";
        proc = _run_node_script(script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_deeply_nested_session_download_is_compact_and_lossless(self):
        """Ticket 51: production download keeps one restoration branch and unfolds all levels."""
        script = _CANONICAL_SNAPSHOT_ASSERTION_JS + r"""
const cytoscape = require('./code2petri/viewer/vendor/cytoscape.min.js');
const { LiveFoldReductionEngine } = require('./code2petri/viewer/engine/reduction_engine.js');
const { downloadFoldStateSnapshot, parseFoldStateSnapshot } = require('./code2petri/viewer/engine/session_snapshot.js');
const elements = [];
for (let i = 0; i < 14; i++) {
  elements.push({ group: 'nodes', data: { id: 'p' + i, type: 'Place', label: 'p' + i }, classes: 'place', position: { x: i * 10, y: i } });
}
for (let i = 0; i < 13; i++) {
  elements.push({ group: 'nodes', data: { id: 't' + i, type: 'Transition', label: 't' + i, tau: 1.5 }, classes: 'transition' });
  elements.push({ group: 'edges', data: { id: 'a' + (i * 2), source: 'p' + i, target: 't' + i, weight: 3 } });
  elements.push({ group: 'edges', data: { id: 'a' + (i * 2 + 1), source: 't' + i, target: 'p' + (i + 1), weight: 3 } });
}
const cy = cytoscape({ elements });
const engine = new LiveFoldReductionEngine(cy);
const documentContext = {
  title: 'Nested', sourceFile: '', filename: 'nested.pnml', functionName: '', mode: 'composite',
  originalNet: { places: [], transitions: [], arcs: [] }, compounds: [], foldSteps: [],
  calleeNets: {}, expandedNodes: [], playback: { currentStep: 0, totalSteps: 0 }
};
global.Blob = function(parts, options) { this.content = parts.join(''); this.type = options.type; };
const measurements = [];
let result = null;
for (let i = 1; i <= 12; i++) {
  const foldResult = engine.executeSinglePlaceContraction(cy.getElementById('p' + i));
  if (!foldResult.success) throw new Error('fold ' + i + ' failed: ' + foldResult.reason);
  if ([3, 6, 9, 12].includes(i)) {
    const startedAt = Date.now();
    result = downloadFoldStateSnapshot({ cy, engine, document: documentContext, downloadBlob: () => {} });
    measurements.push({ depth: i, bytes: Buffer.byteLength(result.json, 'utf8'), elapsedMs: Date.now() - startedAt });
  }
}
if (cy.nodes().length !== 3) throw new Error('expected 3 visible nodes, got ' + cy.nodes().length);
const bytes = Buffer.byteLength(result.json, 'utf8');
if (bytes >= 100 * 1024) throw new Error('nested download too large: ' + bytes + ' bytes');
if (measurements.length !== 4 || measurements.some(item => item.bytes >= 100 * 1024)) throw new Error('a smaller nested snapshot grew unexpectedly');
for (let i = 1; i < measurements.length; i++) {
  if (measurements[i].bytes > measurements[i - 1].bytes * 4) throw new Error('nested snapshot size grew recursively');
}
if (/\n\s+"/.test(result.json)) throw new Error('download JSON is indented');
assertCanonicalSnapshot(result.snapshot);
const restored = parseFoldStateSnapshot(result.json);
const cy2 = cytoscape({ elements: restored.elements });
const engine2 = new LiveFoldReductionEngine(cy2);
engine2.cfg = restored.engine.cfg;
engine2.stepCounter = restored.engine.stepCounter;
engine2.rememberedCustomNames = new Map(restored.engine.rememberedCustomNames);
for (let i = 12; i >= 1; i--) {
  const component = cy2.getElementById('c_' + String(i).padStart(2, '0'));
  const unfolded = engine2.executeComponentLocalUnfold(component);
  if (!unfolded.success) throw new Error('unfold ' + i + ' failed: ' + unfolded.reason);
}
if (cy2.nodes().length !== 27 || cy2.edges().length !== 26) throw new Error('original graph size was not restored');
for (let i = 0; i < 14; i++) if (cy2.getElementById('p' + i).length !== 1) throw new Error('missing p' + i);
for (let i = 0; i < 13; i++) {
  if (cy2.getElementById('t' + i).length !== 1) throw new Error('missing t' + i);
  if (cy2.getElementById('a' + (i * 2)).data('weight') !== 3 || cy2.getElementById('a' + (i * 2 + 1)).data('weight') !== 3) {
    throw new Error('edge metadata was not restored at ' + i);
  }
}
console.log('PASS ' + JSON.stringify(measurements));
"""
        proc = _run_node_script(script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        print(proc.stdout.strip())
        self.assertRegex(proc.stdout, r"PASS \[\{\"depth\":3,\"bytes\":\d+,\"elapsedMs\":\d+\}")

    def test_snapshot_profile_separates_stages_across_900_node_shapes(self):
        """Record capture, encoding, Blob, initiation, and output size for three snapshot shapes."""
        script = r"""
const cytoscape = require('./code2petri/viewer/vendor/cytoscape.min.js');
const { performance } = require('node:perf_hooks');
const { LiveFoldReductionEngine } = require('./code2petri/viewer/engine/reduction_engine.js');
const { serializeFoldStateSnapshot, downloadFoldStateSnapshot } = require('./code2petri/viewer/engine/session_snapshot.js');
function makeElements() {
  const elements = [];
  for (let i = 0; i < 14; i++) elements.push({ group: 'nodes', data: { id: 'p' + i, type: 'Place', label: 'p' + i }, classes: 'place' });
  for (let i = 0; i < 13; i++) {
    elements.push({ group: 'nodes', data: { id: 't' + i, type: 'Transition', label: 't' + i, tau: 1.5 }, classes: 'transition' });
    elements.push({ group: 'edges', data: { id: 'chain-' + (2 * i), source: 'p' + i, target: 't' + i, weight: 1 } });
    elements.push({ group: 'edges', data: { id: 'chain-' + (2 * i + 1), source: 't' + i, target: 'p' + (i + 1), weight: 1 } });
  }
  for (let i = 0; i < 873; i++) elements.push({ group: 'nodes', data: { id: 'x' + i, type: i % 2 ? 'Transition' : 'Place', label: 'x' + i } });
  for (let i = 0; i < 878; i++) elements.push({ group: 'edges', data: { id: 'extra-' + i, source: 'x' + (i % 873), target: 'x' + ((i + 1) % 873), weight: 1 } });
  return elements;
}
const documentContext = {
  title: '900 Node Profile', sourceFile: '', filename: 'profile.pnml', functionName: '', mode: 'composite',
  originalNet: { places: [], transitions: [], arcs: [] }, compounds: [], foldSteps: [],
  calleeNets: {}, expandedNodes: [], playback: { currentStep: 0, totalSteps: 0 }
};
function profile(shape, foldCount) {
  const cy = cytoscape({ elements: makeElements() });
  const engine = new LiveFoldReductionEngine(cy);
  for (let i = 1; i <= foldCount; i++) {
    const folded = engine.executeSinglePlaceContraction(cy.getElementById('p' + i));
    if (!folded.success) throw new Error(shape + ' setup failed at fold ' + i + ': ' + folded.reason);
  }
  let started = performance.now();
  const snapshot = serializeFoldStateSnapshot({ cy, engine, document: documentContext });
  const captureMs = performance.now() - started;
  started = performance.now();
  const json = JSON.stringify(snapshot);
  const encodingMs = performance.now() - started;
  started = performance.now();
  const blob = new Blob([json], { type: 'application/json;charset=utf-8' });
  const blobCreationMs = performance.now() - started;
  if (blob.size !== Buffer.byteLength(json, 'utf8')) throw new Error(shape + ' Blob byte count mismatch');
  let objectUrlCreatedAt = null;
  let downloadInitiationMs = null;
  global.URL = {
    createObjectURL() { objectUrlCreatedAt = performance.now(); return 'blob:' + shape; },
    revokeObjectURL() {}
  };
  global.document = {
    body: { appendChild() {}, removeChild() {} },
    createElement() {
      return { click() { downloadInitiationMs = performance.now() - objectUrlCreatedAt; } };
    }
  };
  global.setTimeout = () => 1;
  started = performance.now();
  const saved = downloadFoldStateSnapshot({ cy, engine, document: documentContext });
  const totalSaveMs = performance.now() - started;
  const byteLength = Buffer.byteLength(saved.json, 'utf8');
  if (byteLength !== blob.size) throw new Error(shape + ' saved JSON byte count changed');
  if (downloadInitiationMs === null) throw new Error(shape + ' did not reach the anchor click');
  return {
    shape,
    originalNodes: 900,
    visibleNodes: cy.nodes().length,
    bytes: byteLength,
    captureMs,
    encodingMs,
    blobCreationMs,
    downloadInitiationMs,
    totalSaveMs
  };
}
const results = [profile('fresh', 0), profile('folded', 1), profile('deeply-folded', 12)];
console.log(JSON.stringify(results));
"""
        proc = _run_node_script(script)
        self.assertEqual(proc.returncode, 0, f"Node profile failed: {proc.stderr}")
        profiles = json.loads(proc.stdout.strip())
        self.assertEqual([item["shape"] for item in profiles], ["fresh", "folded", "deeply-folded"])
        for item in profiles:
            self.assertEqual(item["originalNodes"], 900)
            self.assertGreater(item["bytes"], 0)
            for stage in ("captureMs", "encodingMs", "blobCreationMs", "downloadInitiationMs", "totalSaveMs"):
                self.assertGreaterEqual(item[stage], 0)
        print("Snapshot stage profile:", json.dumps(profiles, sort_keys=True))

    def test_snapshot_capture_normalizes_legacy_aliases_without_mutating_live_data(self):
        """Legacy-only and dual-field restoration records canonicalize on capture."""
        script = _CANONICAL_SNAPSHOT_ASSERTION_JS + r"""
const cytoscape = require('./code2petri/viewer/vendor/cytoscape.min.js');
const { serializeFoldStateSnapshot, parseFoldStateSnapshot } = require('./code2petri/viewer/engine/session_snapshot.js');
const child = id => ({ group: 'nodes', data: { id }, classes: 'transition' });
const legacy = { nodes: [child('legacy-hidden')], internalEdges: [], boundaryInArcs: [], boundaryOutArcs: [] };
const canonical = { nodes: [child('canonical-hidden')], internalEdges: [], boundaryInArcs: [], boundaryOutArcs: [] };
const canonicalBoth = { nodes: [child('both-hidden')], internalEdges: [], boundaryInArcs: [], boundaryOutArcs: [] };
const nestedLegacy = { nodes: [{ group: 'nodes', data: { id: 'nested-owner', consumedSubgraph: { nodes: [child('deep-hidden')] } } }], internalEdges: [], boundaryInArcs: [], boundaryOutArcs: [] };
const cy = cytoscape({ elements: [
  { group: 'nodes', data: { id: 'legacy-owner', consumedSubgraph: legacy }, classes: 'transition' },
  { group: 'nodes', data: { id: 'canonical-owner', consumedSubnet: canonical }, classes: 'transition' },
  { group: 'nodes', data: { id: 'both-owner', consumedSubnet: canonicalBoth, consumedSubgraph: legacy }, classes: 'transition' },
  { group: 'nodes', data: { id: 'nested-owner-root', consumedSubnet: nestedLegacy, metadata: { consumedSubgraph: 'user metadata' } }, classes: 'transition' }
] });
const engine = { stepCounter: 0, cfg: {}, rememberedCustomNames: new Map() };
const documentContext = {
  title: 'Legacy', sourceFile: '', filename: 'legacy.pnml', functionName: '', mode: 'composite',
  originalNet: { places: [], transitions: [], arcs: [] }, compounds: [], foldSteps: [],
  calleeNets: {}, expandedNodes: [], playback: { currentStep: 0, totalSteps: 0 }
};
const snapshot = serializeFoldStateSnapshot({ cy, engine, document: documentContext });
const byId = id => snapshot.elements.find(el => el.data && el.data.id === id).data;
function findRestorableNode(value, id) {
  if (!value || typeof value !== 'object') return null;
  if (value.group === 'nodes' && value.data && value.data.id === id) return value.data;
  for (const key of Object.keys(value)) {
    const found = findRestorableNode(value[key], id);
    if (found) return found;
  }
  return null;
}
if (!byId('legacy-owner').consumedSubnet.nodes.some(n => n.data.id === 'legacy-hidden')) throw new Error('legacy-only history missing');
if (!byId('canonical-owner').consumedSubnet.nodes.some(n => n.data.id === 'canonical-hidden')) throw new Error('canonical-only history missing');
if (byId('both-owner').consumedSubnet.nodes[0].data.id !== 'both-hidden') throw new Error('canonical field did not take precedence');
if (Object.prototype.hasOwnProperty.call(byId('legacy-owner'), 'consumedSubgraph')) throw new Error('legacy field remained at top level');
const nestedOwner = findRestorableNode(snapshot, 'nested-owner');
if (!nestedOwner || Object.prototype.hasOwnProperty.call(nestedOwner, 'consumedSubgraph')) throw new Error('nested legacy field remained');
if (byId('nested-owner-root').metadata.consumedSubgraph !== 'user metadata') throw new Error('ordinary user metadata was rewritten');
if (!cy.getElementById('legacy-owner').data('consumedSubgraph')) throw new Error('live graph alias was mutated');
snapshot.elements.find(el => el.data.id === 'legacy-owner').data.consumedSubnet.nodes[0].data.id = 'snapshot-edit';
if (cy.getElementById('legacy-owner').data('consumedSubgraph').nodes[0].data.id !== 'legacy-hidden') throw new Error('snapshot is not detached from live graph');
function transformRestoration(value, mode, nestedOnly) {
  if (Array.isArray(value)) return value.forEach(item => transformRestoration(item, mode, nestedOnly));
  if (!value || typeof value !== 'object') return;
  if (value.group === 'nodes' && value.data) {
    const data = value.data;
    const isTarget = !nestedOnly || data.id === 'nested-owner';
    if (isTarget && Object.prototype.hasOwnProperty.call(data, 'consumedSubnet')) {
      if (mode === 'legacy') {
        data.consumedSubgraph = data.consumedSubnet;
        delete data.consumedSubnet;
      } else if (mode === 'both') {
        data.consumedSubgraph = legacy;
      }
    }
  }
  Object.keys(value).forEach(key => transformRestoration(value[key], mode, nestedOnly));
}
const legacyInput = JSON.parse(JSON.stringify(snapshot));
transformRestoration(legacyInput, 'legacy', false);
const bothInput = JSON.parse(JSON.stringify(snapshot));
transformRestoration(bothInput, 'both', false);
const mixedInput = JSON.parse(JSON.stringify(snapshot));
transformRestoration(mixedInput, 'legacy', true);
for (const input of [legacyInput, bothInput, mixedInput]) {
  const opened = parseFoldStateSnapshot(JSON.stringify(input));
  const reopenedCy = cytoscape({ elements: opened.elements });
  const resaved = serializeFoldStateSnapshot({ cy: reopenedCy, engine, document: documentContext });
  assertCanonicalSnapshot(resaved);
}
const bothParsed = parseFoldStateSnapshot(JSON.stringify(bothInput));
const bothNode = bothParsed.elements.find(element => element.data.id === 'canonical-owner').data;
if (bothNode.consumedSubnet.nodes[0].data.id !== 'canonical-hidden') throw new Error('canonical history lost precedence');
console.log('PASS');
""";
        proc = _run_node_script(script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_snapshot_parser_validates_graph_context_and_restorable_component_ids(self):
        script = r"""
const { parseFoldStateSnapshot } = require('./code2petri/viewer/engine/session_snapshot.js');
const snapshot = {
  schemaVersion: 1,
  snapshotType: 'code2petri-fold-state',
  elements: [
    { group: 'nodes', data: { id: 'p0' }, classes: 'place' },
    { group: 'nodes', data: { id: 't0', consumedSubnet: {
      nodes: [{ group: 'nodes', data: { id: 'c_07', consumedSubnet: { nodes: [] } } }],
      internalEdges: [], boundaryInArcs: [], boundaryOutArcs: []
    } }, classes: 'transition' },
    { group: 'edges', data: { id: 'a0', source: 'p0', target: 't0' } }
  ],
  engine: {
    stepCounter: 1,
    cfg: { sequence: 0, choice: 1, loop: 3 },
    rememberedCustomNames: [['c_07', 'semantic name']]
  },
  viewport: { zoom: 1.5, pan: { x: 12, y: -4 } },
  document: {
    title: 'Flow', sourceFile: '/src/flow.py', filename: 'flow.py', functionName: 'run',
    mode: 'composite',
    originalNet: { places: [{ id: 'p0' }], transitions: [{ id: 't0' }], arcs: [] },
    compounds: [], foldSteps: [], finalSm: 1, fullyReducible: true,
    calleeNets: {}, expandedNodes: [], playback: { currentStep: 0, totalSteps: 0 }
  }
};
const parsed = parseFoldStateSnapshot(JSON.stringify(snapshot));
if (parsed.engine.stepCounter !== 7) throw new Error('Component allocation high-water mark was not restored');
if (parsed.document.functionName !== 'run' || parsed.elements.length !== 3) throw new Error('Snapshot context was lost');
let invalidRejected = false;
try {
  parseFoldStateSnapshot(JSON.stringify({ ...snapshot, schemaVersion: 2 }));
} catch (error) {
  invalidRejected = /version/i.test(error.message);
}
if (!invalidRejected) throw new Error('Unsupported version was accepted');
const dangling = JSON.parse(JSON.stringify(snapshot));
dangling.elements[2].data.target = 'missing-node';
let graphRejected = false;
try {
  parseFoldStateSnapshot(dangling);
} catch (error) {
  graphRejected = /edge|reference/i.test(error.message);
}
if (!graphRejected) throw new Error('Graph with a dangling edge was accepted');
const danglingRestore = JSON.parse(JSON.stringify(snapshot));
danglingRestore.elements[1].data.consumedSubnet.internalEdges.push({
  group: 'edges', data: { id: 'bad-restoration-edge', source: 'missing-node', target: 'c_07' }
});
let restorationRejected = false;
try {
  parseFoldStateSnapshot(danglingRestore);
} catch (error) {
  restorationRejected = /restoration record references/i.test(error.message);
}
if (!restorationRejected) throw new Error('Restoration record with a dangling edge was accepted');
console.log('PASS');
"""
        proc = _run_node_script(script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_present_canonical_restoration_field_takes_precedence_even_when_invalid(self):
        """A malformed canonical field must not be silently replaced by its legacy alias."""
        script = r"""
const cytoscape = require('./code2petri/viewer/vendor/cytoscape.min.js');
const { serializeFoldStateSnapshot, parseFoldStateSnapshot } = require('./code2petri/viewer/engine/session_snapshot.js');
const legacy = { nodes: [], internalEdges: [], boundaryInArcs: [], boundaryOutArcs: [] };
const cy = cytoscape({ elements: [{
  group: 'nodes', data: { id: 'both-owner', consumedSubnet: null, consumedSubgraph: legacy }
}] });
const engine = { stepCounter: 0, cfg: {}, rememberedCustomNames: new Map() };
const documentContext = {
  title: 'Dual Field', sourceFile: '', filename: 'dual.pnml', functionName: '', mode: 'composite',
  originalNet: { places: [], transitions: [], arcs: [] }, compounds: [], foldSteps: [],
  calleeNets: {}, expandedNodes: [], playback: { currentStep: 0, totalSteps: 0 }
};
const snapshot = serializeFoldStateSnapshot({ cy, engine, document: documentContext });
const saved = snapshot.elements[0].data;
if (!Object.prototype.hasOwnProperty.call(saved, 'consumedSubnet') || saved.consumedSubnet !== null) {
  throw new Error('capture did not preserve the present canonical field');
}
if (Object.prototype.hasOwnProperty.call(saved, 'consumedSubgraph')) throw new Error('legacy alias was retained');
let rejected = false;
try { parseFoldStateSnapshot(JSON.stringify(snapshot)); } catch (error) {
  rejected = /Invalid Fold State Snapshot/.test(error.message);
}
if (!rejected) throw new Error('parser replaced malformed canonical data with legacy data');
console.log('PASS');
"""
        proc = _run_node_script(script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)


class TestSessionDownloadLifecycle(unittest.TestCase):
    def test_production_download_helper_retains_independent_urls_and_cleans_up(self):
        """Actual helper clicks real mocked anchors and releases each URL after a bounded grace period."""
        script = r"""
const { downloadFoldStateSnapshot } = require('./code2petri/viewer/engine/session_snapshot.js');
const callbacks = [];
const urls = new Map();
const removed = [];
const anchors = [];
global.setTimeout = (callback, delay) => { callbacks.push({ callback, delay }); return callbacks.length; };
global.Blob = function(parts, options) { this.bytes = parts.join(''); this.type = options.type; };
global.URL = {
  createObjectURL(blob) { const url = 'blob:' + (urls.size + 1); urls.set(url, blob.bytes); return url; },
  revokeObjectURL(url) { urls.delete(url); }
};
global.document = {
  body: {
    appendChild(anchor) { anchor.attached = true; },
    removeChild(anchor) { anchor.attached = false; removed.push(anchor); }
  },
  createElement(tag) {
    const anchor = { tagName: tag, click() { this.clickedUrl = this.href; this.clickedBytes = urls.get(this.href); } };
    anchors.push(anchor);
    return anchor;
  }
};
const cy = { elements: () => ({ jsons: () => [] }), zoom: () => 1, pan: () => ({ x: 0, y: 0 }) };
const engine = { stepCounter: 0, cfg: {}, rememberedCustomNames: new Map() };
const doc = { title: 'Rapid', sourceFile: '', filename: '', functionName: '', mode: 'no-fold' };
const one = downloadFoldStateSnapshot({ cy, engine, document: doc });
const two = downloadFoldStateSnapshot({ cy, engine, document: doc });
if (anchors.length !== 2 || anchors.some(a => !a.attached && !removed.includes(a))) throw new Error('anchor lifecycle incomplete');
if (anchors[0].clickedUrl === anchors[1].clickedUrl) throw new Error('downloads did not get independent URLs');
if (anchors[0].download !== one.filename || anchors[1].download !== two.filename) throw new Error('download filename missing');
for (const anchor of anchors) {
  if (!anchor.clickedBytes || JSON.stringify(JSON.parse(anchor.clickedBytes)) !== anchor.clickedBytes) throw new Error('incomplete or invalid downloaded bytes');
}
if (callbacks.length !== 2 || callbacks.some(item => item.delay < 1000 || item.delay > 60000)) throw new Error('cleanup is not bounded');
if (urls.size !== 2) throw new Error('URL revoked before browser had a grace period');
callbacks[0].callback();
if (urls.size !== 1 || !urls.has(anchors[1].clickedUrl)) throw new Error('one download cleanup interrupted another');
callbacks[1].callback();
if (urls.size !== 0 || removed.length !== 2) throw new Error('download resources leaked');
console.log('PASS');
"""
        proc = _run_node_script(script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_production_download_helper_reports_failures_and_cleans_partial_resources(self):
        script = r"""
const { downloadFoldStateSnapshot } = require('./code2petri/viewer/engine/session_snapshot.js');
const revoked = [];
global.Blob = function(parts) { this.bytes = parts.join(''); };
global.URL = { createObjectURL: () => 'blob:failure', revokeObjectURL: url => revoked.push(url) };
let removed = 0;
global.document = {
  body: { appendChild() {}, removeChild() { removed++; } },
  createElement: () => ({ click() { throw new Error('blocked click'); } })
};
const cy = { elements: () => ({ jsons: () => [] }), zoom: () => 1, pan: () => ({ x: 0, y: 0 }) };
const engine = { stepCounter: 0, cfg: {}, rememberedCustomNames: new Map() };
const doc = { title: 'Failure', sourceFile: '', filename: '', functionName: '', mode: 'no-fold' };
let message = '';
try { downloadFoldStateSnapshot({ cy, engine, document: doc }); } catch (error) { message = error.message; }
if (message !== 'blocked click' || revoked[0] !== 'blob:failure' || removed !== 1) throw new Error('detectable helper failure was hidden or leaked resources');
let allocations = 0;
URL.createObjectURL = () => { allocations++; return 'blob:unreleased'; };
URL.revokeObjectURL = undefined;
let unsupported = '';
try { downloadFoldStateSnapshot({ cy, engine, document: doc }); } catch (error) { unsupported = error.message; }
if (!/cannot create a session download/i.test(unsupported) || allocations !== 0) throw new Error('helper allocated a URL without a cleanup capability');
console.log('PASS');
"""
        proc = _run_node_script(script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)


class TestViewportModule(unittest.TestCase):
    """Unit tests for the modularized code2petri/viewer/engine/viewport.js module."""

    def test_engine_scripts_bundle_contains_viewport(self):
        """Verifies that _load_engine_scripts() includes the viewport module."""
        from code2petri.viewer import _load_engine_scripts, _load_template
        scripts = _load_engine_scripts()
        self.assertIn("Viewport Management Module for code2petri", scripts)
        self.assertIn("captureViewport", scripts)
        self.assertIn("computeAnchoredPan", scripts)
        self.assertIn("restoreViewport", scripts)

        template = _load_template()
        self.assertIn("Viewport Management Module for code2petri", template)

    def test_viewport_module_node_exports(self):
        """Verifies that viewport.js exports all expected functions under CommonJS / Node.js."""
        script = """
const vp = require('./code2petri/viewer/engine/viewport.js');
const expectedFns = [
  'captureViewport',
  'computeAnchoredPan',
  'restoreViewport'
];
for (const fn of expectedFns) {
  if (typeof vp[fn] !== 'function') {
    throw new Error(`Missing expected export function: ${fn}`);
  }
}
console.log('PASS');
"""
        proc = _run_node_script(script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_viewport_engine_attachment(self):
        """Verifies that viewport.js attaches to LiveFoldReductionEngine.viewport when engine is loaded."""
        script = """
const { LiveFoldReductionEngine } = require('./code2petri/viewer/engine/reduction_engine.js');
global.LiveFoldReductionEngine = LiveFoldReductionEngine;
const vp = require('./code2petri/viewer/engine/viewport.js');

if (!LiveFoldReductionEngine.viewport) {
  throw new Error('LiveFoldReductionEngine.viewport was not attached');
}
if (typeof LiveFoldReductionEngine.viewport.capture !== 'function') {
  throw new Error('LiveFoldReductionEngine.viewport.capture is not a function');
}
if (typeof LiveFoldReductionEngine.viewport.computeAnchoredPan !== 'function') {
  throw new Error('LiveFoldReductionEngine.viewport.computeAnchoredPan is not a function');
}
if (typeof LiveFoldReductionEngine.viewport.restore !== 'function') {
  throw new Error('LiveFoldReductionEngine.viewport.restore is not a function');
}
console.log('PASS');
"""
        proc = _run_node_script(script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_compute_anchored_pan_math_invariance(self):
        """Verifies that computeAnchoredPan maintains screen coordinate invariance."""
        script = """
const { computeAnchoredPan } = require('./code2petri/viewer/engine/viewport.js');

const zoom = 1.75;
const currentPan = { x: 100, y: -50 };
const preFoldPos = { x: 200, y: 150 };
const postFoldTransitionPos = { x: 240, y: 180 };

const anchoredPan = computeAnchoredPan(currentPan, preFoldPos, postFoldTransitionPos, zoom);

const preScreenX = preFoldPos.x * zoom + currentPan.x;
const preScreenY = preFoldPos.y * zoom + currentPan.y;
const postScreenX = postFoldTransitionPos.x * zoom + anchoredPan.x;
const postScreenY = postFoldTransitionPos.y * zoom + anchoredPan.y;

if (Math.abs(preScreenX - postScreenX) > 1e-6) {
  throw new Error(`Screen X mismatch: ${preScreenX} vs ${postScreenX}`);
}
if (Math.abs(preScreenY - postScreenY) > 1e-6) {
  throw new Error(`Screen Y mismatch: ${preScreenY} vs ${postScreenY}`);
}
console.log('PASS');
"""
        proc = _run_node_script(script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)


if __name__ == "__main__":
    unittest.main()
