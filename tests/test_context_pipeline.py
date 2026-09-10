import json
import os
import tempfile
import unittest
import xml.etree.ElementTree as ET

from code2petri.engine import code2petri, discover_context_files, main
from code2petri.model import PetriNet


class TestContextDiscovery(unittest.TestCase):
    def setUp(self):
        self.game_of_life_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "test_code", "game_of_life")
        )
        self.app_js = os.path.join(self.game_of_life_dir, "app.js")
        self.webgl_js = os.path.join(self.game_of_life_dir, "webgl-engine.js")

    def test_discover_explicit_files(self):
        files = discover_context_files([self.app_js, self.webgl_js])
        self.assertEqual(len(files), 2)
        self.assertIn(self.app_js, files)
        self.assertIn(self.webgl_js, files)

    def test_discover_directory_recursive(self):
        files = discover_context_files([self.game_of_life_dir])
        self.assertGreaterEqual(len(files), 2)
        self.assertIn(self.app_js, files)
        self.assertIn(self.webgl_js, files)
        # Ensure no AppleDouble or hidden files were included
        for f in files:
            self.assertFalse(os.path.basename(f).startswith("._"))
            self.assertFalse(os.path.basename(f).startswith(".") and not os.path.basename(f).startswith(".js"))

    def test_non_existent_path_raises(self):
        with self.assertRaises(AssertionError) as ctx:
            discover_context_files(["/non/existent/path/never_exists.js"])
        self.assertIn("does not exist", str(ctx.exception))

    def test_unsupported_file_extension_raises(self):
        with tempfile.NamedTemporaryFile(suffix=".txt") as tmp:
            with self.assertRaises(AssertionError) as ctx:
                discover_context_files([tmp.name])
            self.assertIn("Unsupported context file extension", str(ctx.exception))


class TestCrossFileResolutionEndToEnd(unittest.TestCase):
    def setUp(self):
        self.game_of_life_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "test_code", "game_of_life")
        )
        self.app_js = os.path.join(self.game_of_life_dir, "app.js")
        self.webgl_js = os.path.join(self.game_of_life_dir, "webgl-engine.js")
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_game_of_life_loop_resolution_explicit_context(self):
        out_pnml = os.path.join(self.temp_dir.name, "loop.pnml")
        net = code2petri(
            source_path=self.app_js,
            target_function="loop",
            context=[self.webgl_js],
            output_file=out_pnml,
        )
        self.assertIsInstance(net, PetriNet)
        self.assertTrue(os.path.exists(out_pnml))

        # Check resolved transitions in memory
        resolved_transitions = [t for t in net.transitions if t.resolution and t.resolution.resolved]
        unresolved_transitions = [t for t in net.transitions if t.resolution and not t.resolution.resolved]

        self.assertGreaterEqual(len(resolved_transitions), 2)
        self.assertGreaterEqual(len(unresolved_transitions), 1)

        # 1. gpuEngine.step() -> WebGLEngine.step in webgl-engine.js
        step_trans = next(
            (t for t in resolved_transitions if t.resolution.resolved_to == "WebGLEngine.step"),
            None,
        )
        self.assertIsNotNone(step_trans)
        self.assertEqual(step_trans.resolution.target_file, self.webgl_js)
        self.assertEqual(step_trans.metadata.get("resolved_to"), "WebGLEngine.step")

        # 2. stepCpu() -> stepCpu in app.js
        step_cpu_trans = next(
            (t for t in resolved_transitions if t.resolution.resolved_to == "stepCpu"),
            None,
        )
        self.assertIsNotNone(step_cpu_trans)
        self.assertEqual(step_cpu_trans.resolution.target_file, self.app_js)

        # 3. requestAnimationFrame(loop) -> unresolved
        raf_trans = next(
            (t for t in unresolved_transitions if "requestAnimationFrame" in t.label),
            None,
        )
        self.assertIsNotNone(raf_trans)
        self.assertFalse(raf_trans.resolution.resolved)

    def test_game_of_life_loop_resolution_directory_context(self):
        out_json = os.path.join(self.temp_dir.name, "loop.json")
        net = code2petri(
            source_path=self.app_js,
            target_function="loop",
            context=[self.game_of_life_dir],
            output_file=out_json,
        )
        self.assertIsInstance(net, PetriNet)
        self.assertTrue(os.path.exists(out_json))

        with open(out_json, "r", encoding="utf-8") as f:
            data = json.load(f)

        trans_list = data.get("transitions", [])
        resolved_entries = [t for t in trans_list if t.get("resolved") is True]
        unresolved_entries = [t for t in trans_list if t.get("resolved") is False]

        self.assertGreaterEqual(len(resolved_entries), 2)
        self.assertGreaterEqual(len(unresolved_entries), 1)

        step_entry = next((t for t in resolved_entries if t.get("resolved_to") == "WebGLEngine.step"), None)
        self.assertIsNotNone(step_entry)
        self.assertEqual(step_entry.get("target_file"), self.webgl_js)

    def test_pnml_format_serialization(self):
        out_pnml = os.path.join(self.temp_dir.name, "out.pnml")
        code2petri(
            source_path=self.app_js,
            target_function="loop",
            context=[self.webgl_js],
            output_file=out_pnml,
        )

        tree = ET.parse(out_pnml)
        root = tree.getroot()

        toolspecifics = [el for el in root.iter() if el.tag.endswith("toolspecific")]
        self.assertGreater(len(toolspecifics), 0)

        resolved_elems = [el for el in root.iter() if el.tag.endswith("resolved")]
        self.assertGreaterEqual(len(resolved_elems), 2)
        self.assertTrue(any(el.attrib.get("target") == "WebGLEngine.step" for el in resolved_elems))

        unresolved_elems = [el for el in root.iter() if el.tag.endswith("unresolved")]
        self.assertGreaterEqual(len(unresolved_elems), 1)

    def test_dot_format_serialization(self):
        out_dot = os.path.join(self.temp_dir.name, "out.dot")
        code2petri(
            source_path=self.app_js,
            target_function="loop",
            context=[self.webgl_js],
            output_file=out_dot,
        )

        with open(out_dot, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn('color="#2e7d32"', content)
        self.assertIn('color="#e65100"', content)
        self.assertIn("Resolved to WebGLEngine.step in", content)
        self.assertIn('tooltip="Unresolved call"', content)


class TestSingleFileBackwardCompatibility(unittest.TestCase):
    def setUp(self):
        self.game_of_life_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "test_code", "game_of_life")
        )
        self.app_js = os.path.join(self.game_of_life_dir, "app.js")
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_single_file_without_context_preserves_unannotated_transitions(self):
        out_pnml = os.path.join(self.temp_dir.name, "single.pnml")
        net = code2petri(
            source_path=self.app_js,
            target_function="loop",
            context=None,
            output_file=out_pnml,
        )
        self.assertIsInstance(net, PetriNet)

        # None of the transitions should have call resolution attached
        for t in net.transitions:
            self.assertIsNone(t.resolution)

        # PNML output should not have toolspecific call resolution elements
        tree = ET.parse(out_pnml)
        root = tree.getroot()
        resolved_elems = [el for el in root.iter() if el.tag.endswith("resolved")]
        unresolved_elems = [el for el in root.iter() if el.tag.endswith("unresolved")]
        self.assertEqual(len(resolved_elems), 0)
        self.assertEqual(len(unresolved_elems), 0)


class TestCLIContextInvocation(unittest.TestCase):
    def setUp(self):
        self.game_of_life_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "test_code", "game_of_life")
        )
        self.app_js = os.path.join(self.game_of_life_dir, "app.js")
        self.webgl_js = os.path.join(self.game_of_life_dir, "webgl-engine.js")
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_cli_long_flag_context(self):
        out_json = os.path.join(self.temp_dir.name, "cli_out.json")
        main([
            self.app_js,
            "--target-function", "loop",
            "--context", self.webgl_js,
            "--output", out_json,
        ])
        self.assertTrue(os.path.exists(out_json))
        with open(out_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        resolved = [t for t in data["transitions"] if t.get("resolved") is True]
        self.assertGreaterEqual(len(resolved), 1)

    def test_cli_short_flag_context(self):
        out_json = os.path.join(self.temp_dir.name, "cli_short.json")
        main([
            self.app_js,
            "-t", "loop",
            "-c", self.game_of_life_dir,
            "-o", out_json,
        ])
        self.assertTrue(os.path.exists(out_json))
        with open(out_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        resolved = [t for t in data["transitions"] if t.get("resolved") is True]
        self.assertGreaterEqual(len(resolved), 1)


if __name__ == "__main__":
    unittest.main()
