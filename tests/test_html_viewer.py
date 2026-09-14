import json
import os
import re
import tempfile
import unittest

from code2petri.engine import code2petri, main
from code2petri.fold import FoldConfig, fold_net, FoldResult
from code2petri.model import PetriNet, Transition, Place
from code2petri.viewer import generate_html


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

        match = re.search(r'<script id="code2petri-data" type="application/json">\s*(\{.*?\})\s*</script>', html_content, re.DOTALL)
        self.assertIsNotNone(match)
        data = json.loads(match.group(1))
        self.assertEqual(data["mode"], "no-fold")
        self.assertEqual(data["fold_steps"], [])
        self.assertEqual(data["final_sm"], 0.0)
        self.assertIn("places", data["initial_net"])
        self.assertIn("transitions", data["initial_net"])

    def test_generate_html_fold_mode(self):
        """Validates that passing a FoldResult sets mode='fold' and embeds fold steps."""
        fold_res = fold_net(self.net, FoldConfig())
        html_content = generate_html(fold_res)

        match = re.search(r'<script id="code2petri-data" type="application/json">\s*(\{.*?\})\s*</script>', html_content, re.DOTALL)
        self.assertIsNotNone(match)
        data = json.loads(match.group(1))
        self.assertEqual(data["mode"], "fold")
        self.assertGreater(len(data["fold_steps"]), 0)
        self.assertEqual(data["final_sm"], fold_res.final_sm)

    def test_petrinet_to_html_method(self):
        """Validates that PetriNet.to_html() produces valid HTML."""
        html_content = self.net.to_html(title="Model to_html")
        self.assertIn("Model to_html", html_content)
        self.assertIn("cytoscape", html_content)

    def test_foldresult_to_html_method(self):
        """Validates that FoldResult.to_html() produces valid HTML."""
        fold_res = fold_net(self.net, FoldConfig())
        html_content = fold_res.to_html(title="FoldResult to_html")
        self.assertIn("FoldResult to_html", html_content)
        self.assertIn('"mode": "fold"', html_content)


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
        self.assertIn('"mode": "fold"', content)
        self.assertIn('"fold_steps"', content)
        self.assertIn(f'"final_sm": {res.final_sm}', content)

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
        self.assertIn('"mode": "no-fold"', content)
        self.assertNotIn('"component_type"', content)

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
        self.assertIn('"mode": "fold"', content)


if __name__ == "__main__":
    unittest.main()
