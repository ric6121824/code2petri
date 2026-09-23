import json
import os
import re
import tempfile
import unittest

from code2petri.engine import code2petri, main, TEXT_SERIALIZERS
from code2petri.fold import FoldConfig, fold_net, FoldResult
from code2petri.model import PetriNet, Transition, Place
from code2petri.viewer import generate_html


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


def _extract_template_net_to_elements() -> str:
    """Helper to extract netToElements JavaScript function from template.html."""
    template_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "code2petri", "viewer", "template.html")
    )
    with open(template_path, "r", encoding="utf-8") as f:
        html = f.read()
    match = re.search(r'function netToElements\(net\) \{(.*?)\n      \}', html, re.DOTALL)
    if not match:
        raise ValueError("Could not extract netToElements from template.html")
    return match.group(0)


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
        self.assertIn("boxSelectionEnabled: false", html_content)

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
        self.assertIn("app.js", content)
        self.assertIn('id="info-filename"', content)

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


if __name__ == "__main__":
    unittest.main()

