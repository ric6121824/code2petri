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

    def test_generate_html_composite_mode_explicit(self):
        """Validates that generate_html with mode='composite' or composite_net embeds composite payload."""
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

        html_content = generate_html(comp_net, title="Composite Overview", mode="composite")
        self.assertIn("Composite Overview", html_content)

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

    def test_generate_html_composite_mode_via_composite_net_arg(self):
        """Validates passing composite_net parameter directly into generate_html."""
        comp_net = PetriNet()
        comp_net.add_place("p_start", "start", initial_tokens=1)
        comp_net.add_compound(
            id="compound_calc",
            label="calc()",
            function_name="calc",
            file="math.py",
            parent=None,
        )

        dummy_net = PetriNet()
        html_content = generate_html(dummy_net, composite_net=comp_net)
        data = _extract_embedded_data(html_content)
        self.assertEqual(data["mode"], "composite")
        self.assertIn("composite_net", data)
        self.assertEqual(len(data["compounds"]), 1)
        self.assertEqual(data["compounds"][0]["id"], "compound_calc")

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
if (!cElem || cElem.data.is_compound !== true) {{
  throw new Error('Compound failed: ' + JSON.stringify(cElem));
}}
console.log('PASS');
"""
        proc = subprocess.run(["node", "-e", node_script], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)


if __name__ == "__main__":
    unittest.main()

