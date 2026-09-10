import json
import os
import tempfile
import unittest
import xml.etree.ElementTree as ET

from code2petri.engine import code2petri, main
from code2petri.model import PetriNet


class TestGameOfLifeCrossFileValidation(unittest.TestCase):
    def setUp(self):
        self.game_of_life_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "test_code", "game_of_life")
        )
        self.app_js = os.path.join(self.game_of_life_dir, "app.js")
        self.webgl_js = os.path.join(self.game_of_life_dir, "webgl-engine.js")
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_loop_cross_file_resolution(self):
        """Validates loop in app.js with webgl-engine.js as context."""
        out_pnml = os.path.join(self.temp_dir.name, "loop.pnml")
        net = code2petri(
            source_path=self.app_js,
            target_function="loop",
            context=[self.webgl_js],
            output_file=out_pnml,
        )
        self.assertIsInstance(net, PetriNet)

        # gpuEngine.step() must resolve to WebGLEngine.step in webgl-engine.js
        step_trans = next(
            (t for t in net.transitions if t.resolution and t.resolution.resolved_to == "WebGLEngine.step"),
            None,
        )
        self.assertIsNotNone(step_trans)
        self.assertTrue(step_trans.resolution.resolved)
        self.assertEqual(step_trans.resolution.target_file, self.webgl_js)

        # stepCpu() must resolve to stepCpu in app.js
        step_cpu_trans = next(
            (t for t in net.transitions if t.resolution and t.resolution.resolved_to == "stepCpu"),
            None,
        )
        self.assertIsNotNone(step_cpu_trans)
        self.assertTrue(step_cpu_trans.resolution.resolved)
        self.assertEqual(step_cpu_trans.resolution.target_file, self.app_js)

        # requestAnimationFrame(loop) must remain unresolved
        raf_trans = next(
            (t for t in net.transitions if t.resolution and not t.resolution.resolved and "requestAnimationFrame" in t.label),
            None,
        )
        self.assertIsNotNone(raf_trans)
        self.assertFalse(raf_trans.resolution.resolved)

    def test_init_and_randomize_with_directory_context(self):
        """Validates init, randomizeBoth, and WebGLEngine.randomize with directory context."""
        # 1. Analyze randomizeBoth in app.js
        out_randomize = os.path.join(self.temp_dir.name, "randomize.json")
        net_randomize = code2petri(
            source_path=self.app_js,
            target_function="randomizeBoth",
            context=[self.game_of_life_dir],
            output_file=out_randomize,
        )
        self.assertIsInstance(net_randomize, PetriNet)

        # gpuEngine.randomize() must resolve to WebGLEngine.randomize in webgl-engine.js
        gpu_rand = next(
            (t for t in net_randomize.transitions if t.resolution and t.resolution.resolved_to == "WebGLEngine.randomize"),
            None,
        )
        self.assertIsNotNone(gpu_rand)
        self.assertEqual(gpu_rand.resolution.target_file, self.webgl_js)

        # Local functions in randomizeBoth
        grid_rand = next(
            (t for t in net_randomize.transitions if t.resolution and t.resolution.resolved_to == "createGrid"),
            None,
        )
        self.assertIsNotNone(grid_rand)
        self.assertEqual(grid_rand.resolution.target_file, self.app_js)

        draw_rand = next(
            (t for t in net_randomize.transitions if t.resolution and t.resolution.resolved_to == "drawCpuGrid"),
            None,
        )
        self.assertIsNotNone(draw_rand)
        self.assertEqual(draw_rand.resolution.target_file, self.app_js)

        # 2. Analyze init in app.js
        net_init = code2petri(
            source_path=self.app_js,
            target_function="init",
            context=[self.game_of_life_dir],
            output_file=None,
        )
        self.assertIsInstance(net_init, PetriNet)
        rand_call = next(
            (t for t in net_init.transitions if t.resolution and t.resolution.resolved_to == "randomizeBoth"),
            None,
        )
        self.assertIsNotNone(rand_call)
        self.assertEqual(rand_call.resolution.target_file, self.app_js)

        setup_call = next(
            (t for t in net_init.transitions if t.resolution and t.resolution.resolved_to == "setupEventListeners"),
            None,
        )
        self.assertIsNotNone(setup_call)
        self.assertEqual(setup_call.resolution.target_file, self.app_js)

        # 3. Analyze WebGLEngine.randomize in webgl-engine.js
        net_webgl_rand = code2petri(
            source_path=self.webgl_js,
            target_function="WebGLEngine.randomize",
            context=[self.game_of_life_dir],
            output_file=None,
        )
        self.assertIsInstance(net_webgl_rand, PetriNet)
        draw_screen_call = next(
            (t for t in net_webgl_rand.transitions if t.resolution and t.resolution.resolved_to == "WebGLEngine.drawToScreen"),
            None,
        )
        self.assertIsNotNone(draw_screen_call)
        self.assertEqual(draw_screen_call.resolution.target_file, self.webgl_js)

    def test_browser_and_webgl_apis_remain_unresolved(self):
        """Verifies DOM and WebGL APIs are cleanly marked with resolved: False."""
        # 1. (global) in app.js contains document.getElementById calls
        net_global = code2petri(
            source_path=self.app_js,
            target_function="(global)",
            context=[self.webgl_js],
            output_file=None,
        )
        self.assertIsInstance(net_global, PetriNet)
        doc_calls = [
            t for t in net_global.transitions
            if t.resolution and not t.resolution.resolved and "getElementById" in t.label
        ]
        self.assertGreaterEqual(len(doc_calls), 1)
        for dc in doc_calls:
            self.assertFalse(dc.resolution.resolved)

        # 2. WebGLEngine.step in webgl-engine.js contains gl.* calls
        net_step = code2petri(
            source_path=self.webgl_js,
            target_function="WebGLEngine.step",
            context=[self.app_js],
            output_file=None,
        )
        self.assertIsInstance(net_step, PetriNet)

        # this.drawToScreen() is resolved
        draw_screen = next(
            (t for t in net_step.transitions if t.resolution and t.resolution.resolved_to == "WebGLEngine.drawToScreen"),
            None,
        )
        self.assertIsNotNone(draw_screen)
        self.assertTrue(draw_screen.resolution.resolved)

        # gl calls are unresolved
        unresolved_gl = [
            t for t in net_step.transitions
            if t.resolution and not t.resolution.resolved
        ]
        self.assertGreaterEqual(len(unresolved_gl), 3)

    def test_format_serialization_annotations(self):
        """Verifies PNML, DOT, and JSON output formatting for GameOfLife simulator."""
        out_pnml = os.path.join(self.temp_dir.name, "gol_loop.pnml")
        out_dot = os.path.join(self.temp_dir.name, "gol_loop.dot")
        out_json = os.path.join(self.temp_dir.name, "gol_loop.json")

        code2petri(
            source_path=self.app_js,
            target_function="loop",
            context=[self.webgl_js],
            output_file=out_pnml,
        )
        code2petri(
            source_path=self.app_js,
            target_function="loop",
            context=[self.webgl_js],
            output_file=out_dot,
        )
        code2petri(
            source_path=self.app_js,
            target_function="loop",
            context=[self.webgl_js],
            output_file=out_json,
        )

        # 1. Check PNML
        tree = ET.parse(out_pnml)
        root = tree.getroot()
        resolved_nodes = [el for el in root.iter() if el.tag.endswith("resolved")]
        self.assertGreaterEqual(len(resolved_nodes), 2)
        step_node = next(el for el in resolved_nodes if el.attrib.get("target") == "WebGLEngine.step")
        self.assertEqual(step_node.attrib.get("file"), self.webgl_js)

        unresolved_nodes = [el for el in root.iter() if el.tag.endswith("unresolved")]
        self.assertGreaterEqual(len(unresolved_nodes), 1)

        # 2. Check DOT
        with open(out_dot, "r", encoding="utf-8") as f:
            dot_text = f.read()
        self.assertIn('color="#2e7d32"', dot_text)
        self.assertIn('color="#e65100"', dot_text)
        self.assertIn("Resolved to WebGLEngine.step in", dot_text)
        self.assertIn('tooltip="Unresolved call"', dot_text)

        # 3. Check JSON
        with open(out_json, "r", encoding="utf-8") as f:
            json_data = json.load(f)
        transitions = json_data.get("transitions", [])
        resolved_json = [t for t in transitions if t.get("resolved") is True]
        unresolved_json = [t for t in transitions if t.get("resolved") is False]
        self.assertGreaterEqual(len(resolved_json), 2)
        self.assertGreaterEqual(len(unresolved_json), 1)
        step_json = next(t for t in resolved_json if t.get("resolved_to") == "WebGLEngine.step")
        self.assertEqual(step_json.get("target_file"), self.webgl_js)


if __name__ == "__main__":
    unittest.main()
