from contextlib import redirect_stderr
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

from code2petri.engine import code2petri, main, is_installed
from code2petri.fold import FoldResult, FoldConfig
from code2petri.model import PetriNet, RenderingConfig


class TestCLIFoldAndInlineIntegration(unittest.TestCase):
    def setUp(self):
        self.game_of_life_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "test_code", "game_of_life")
        )
        self.app_js = os.path.join(self.game_of_life_dir, "app.js")
        self.webgl_js = os.path.join(self.game_of_life_dir, "webgl-engine.js")
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_fold_json_schema(self):
        """Validates that --fold with .json output serializes the full FoldResult schema."""
        out_json = os.path.join(self.temp_dir.name, "fold_result.json")
        res = code2petri(
            source_path=self.app_js,
            target_function="stepCpu",
            output_file=out_json,
            fold=True,
        )
        self.assertIsInstance(res, FoldResult)
        self.assertTrue(os.path.exists(out_json))

        with open(out_json, "r", encoding="utf-8") as f:
            data = json.load(f)

        # FoldResult schema checks
        self.assertIn("initial_net", data)
        self.assertIn("fold_steps", data)
        self.assertIn("final_sm", data)
        self.assertIn("fully_reducible", data)

        self.assertIsInstance(data["initial_net"], dict)
        self.assertIn("places", data["initial_net"])
        self.assertIn("transitions", data["initial_net"])
        self.assertIn("arcs", data["initial_net"])

        self.assertIsInstance(data["fold_steps"], list)
        self.assertGreater(len(data["fold_steps"]), 0)
        first_step = data["fold_steps"][0]
        for key in ("step", "component_type", "folded_nodes", "opaque_transition", "omega", "tau", "sm_score", "net"):
            self.assertIn(key, first_step)

        self.assertIsInstance(data["final_sm"], (int, float))
        self.assertGreater(data["final_sm"], 0.0)

    def test_fold_dot_penultimate_state(self):
        """Validates that --fold with .dot output renders the penultimate state with title and tau labels."""
        out_dot = os.path.join(self.temp_dir.name, "fold_penultimate.dot")
        code2petri(
            source_path=self.app_js,
            target_function="stepCpu",
            output_file=out_dot,
            fold=True,
        )
        self.assertTrue(os.path.exists(out_dot))

        with open(out_dot, "r", encoding="utf-8") as f:
            content = f.read()

        # Embedded SM score in graph title
        self.assertIn('labelloc="t";', content)
        self.assertIn('label="SM score = ', content)

        # Penultimate state has opaque transitions styled with bold border and tau labels
        self.assertIn('style="filled,bold"', content)
        self.assertNotIn('penwidth="2"', content)
        self.assertIn("(tau=", content)

    def test_fold_pnml_penultimate_state(self):
        """Validates that --fold with .pnml output carries toolspecific metadata for component type and tau."""
        out_pnml = os.path.join(self.temp_dir.name, "fold_penultimate.pnml")
        code2petri(
            source_path=self.app_js,
            target_function="stepCpu",
            output_file=out_pnml,
            fold=True,
        )
        self.assertTrue(os.path.exists(out_pnml))

        tree = ET.parse(out_pnml)
        root = tree.getroot()

        toolspecifics = [el for el in root.iter() if el.tag.endswith("toolspecific")]
        self.assertGreater(len(toolspecifics), 0)

        props = [el for el in root.iter() if el.tag.endswith("property")]
        comp_props = [p for p in props if p.attrib.get("name") == "component_type"]
        tau_props = [p for p in props if p.attrib.get("name") == "tau"]
        self.assertGreater(len(comp_props), 0)
        self.assertGreater(len(tau_props), 0)

    def test_fold_image_generation(self):
        """Validates that --fold generates PNG and SVG images when dot is available."""
        if not is_installed("dot") and not is_installed("dot.exe"):
            self.skipTest("Graphviz dot not installed on PATH")

        out_png = os.path.join(self.temp_dir.name, "fold.png")
        code2petri(
            source_path=self.app_js,
            target_function="stepCpu",
            output_file=out_png,
            fold=True,
        )
        self.assertTrue(os.path.exists(out_png))
        self.assertGreater(os.path.getsize(out_png), 0)

        out_svg = os.path.join(self.temp_dir.name, "fold.svg")
        code2petri(
            source_path=self.app_js,
            target_function="stepCpu",
            output_file=out_svg,
            fold=True,
        )
        self.assertTrue(os.path.exists(out_svg))
        self.assertGreater(os.path.getsize(out_svg), 0)

    def test_no_fold_passthrough(self):
        """Validates that --no-fold overrides fold analysis and outputs standard PetriNet."""
        out_json = os.path.join(self.temp_dir.name, "no_fold.json")
        res = code2petri(
            source_path=self.app_js,
            target_function="stepCpu",
            output_file=out_json,
            fold=True,
            no_fold=True,
        )
        self.assertIsInstance(res, PetriNet)

        with open(out_json, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Standard PetriNet dictionary (no fold_steps or final_sm)
        self.assertIn("places", data)
        self.assertIn("transitions", data)
        self.assertIn("arcs", data)
        self.assertNotIn("fold_steps", data)
        self.assertNotIn("final_sm", data)

    def test_weights_override_changes_sm_score(self):
        """Validates that overriding weights via JSON string alters the computed SM score."""
        res_default = code2petri(
            source_path=self.app_js,
            target_function="stepCpu",
            output_file=None,
            fold=True,
        )
        res_weighted = code2petri(
            source_path=self.app_js,
            target_function="stepCpu",
            output_file=None,
            fold=True,
            weights='{"sequence": 15.0, "choice": 25.0}',
        )
        self.assertIsInstance(res_default, FoldResult)
        self.assertIsInstance(res_weighted, FoldResult)
        self.assertNotEqual(res_default.final_sm, res_weighted.final_sm)
        self.assertGreater(res_weighted.final_sm, res_default.final_sm)

    def test_weights_file_override(self):
        """Validates that overriding weights via a JSON file alters the computed SM score."""
        weights_file = os.path.join(self.temp_dir.name, "custom_weights.json")
        with open(weights_file, "w", encoding="utf-8") as f:
            json.dump({"sequence": 20.0, "choice": 30.0}, f)

        res = code2petri(
            source_path=self.app_js,
            target_function="stepCpu",
            output_file=None,
            fold=True,
            weights=weights_file,
        )
        self.assertIsInstance(res, FoldResult)
        self.assertGreater(res.final_sm, 30.0)

    def test_inline_without_context_raises_error(self):
        """Validates that activating --inline without --context raises an AssertionError."""
        with self.assertRaises(AssertionError) as ctx:
            code2petri(
                source_path=self.app_js,
                target_function="loop",
                inline=True,
                context=None,
                output_file=None,
            )
        self.assertIn("requires --context", str(ctx.exception))

    def test_inline_with_context(self):
        """Validates that --inline splices callee nets into a Composite Net."""
        out_json = os.path.join(self.temp_dir.name, "composite.json")
        res = code2petri(
            source_path=self.app_js,
            target_function="loop",
            output_file=out_json,
            context=[self.webgl_js],
            inline=True,
            inline_depth=1,
        )
        self.assertIsInstance(res, PetriNet)
        inlined_trans = [t for t in res.transitions if t.is_inlined]
        self.assertGreater(len(inlined_trans), 0)

        with open(out_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        inlined_dict_trans = [
            t for t in data["transitions"]
            if t.get("metadata", {}).get("inline_expansion")
        ]
        self.assertGreater(len(inlined_dict_trans), 0)

    def test_inline_combined_with_fold(self):
        """Validates that inline expansion runs first, followed by fold analysis on composite net."""
        out_json = os.path.join(self.temp_dir.name, "composite_folded.json")
        res = code2petri(
            source_path=self.app_js,
            target_function="loop",
            output_file=out_json,
            context=[self.webgl_js],
            inline=True,
            inline_depth=1,
            fold=True,
        )
        self.assertIsInstance(res, FoldResult)
        # Composite net before folding had inlined nodes
        inlined_initial = [t for t in res.initial_net.transitions if t.is_inlined]
        self.assertGreater(len(inlined_initial), 0)
        self.assertGreater(res.final_sm, 0.0)

    def test_stderr_sm_score_output(self):
        """Validates that the final SM score is printed to stderr when --fold is active."""
        captured = io.StringIO()
        with redirect_stderr(captured):
            code2petri(
                source_path=self.app_js,
                target_function="stepCpu",
                output_file=None,
                fold=True,
            )
        output = captured.getvalue()
        self.assertIn("Code2Petri: SM score = ", output)

    def test_stderr_no_sm_score_when_fold_inactive(self):
        """Validates that SM score is NOT printed to stderr when fold is inactive."""
        captured = io.StringIO()
        with redirect_stderr(captured):
            code2petri(
                source_path=self.app_js,
                target_function="stepCpu",
                output_file=None,
                fold=False,
            )
        output = captured.getvalue()
        self.assertNotIn("SM score =", output)

    def test_invalid_output_extension_fails_early(self):
        """Validates that an unsupported output extension raises AssertionError."""
        with self.assertRaises(AssertionError) as ctx:
            code2petri(
                source_path=self.app_js,
                target_function="stepCpu",
                output_file="out.xyz",
                fold=True,
            )
        self.assertIn("Unsupported output extension '.xyz'", str(ctx.exception))

    def test_cli_main_fold_and_weights_flags(self):
        """Validates CLI invocation with --fold and --weights."""
        out_json = os.path.join(self.temp_dir.name, "cli_fold.json")
        main([
            self.app_js,
            "-t", "stepCpu",
            "--fold",
            "--weights", '{"sequence": 5.0}',
            "-o", out_json,
        ])
        self.assertTrue(os.path.exists(out_json))
        with open(out_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("final_sm", data)
        self.assertIn("fold_steps", data)

    def test_cli_main_inline_without_context_exits(self):
        """Validates that CLI main with --inline without -c raises AssertionError."""
        with self.assertRaises(AssertionError):
            main([
                self.app_js,
                "-t", "loop",
                "--inline",
            ])

    def test_backward_compatible_output_unchanged(self):
        """Validates that running without new flags produces identical output to Phase 2."""
        out_json = os.path.join(self.temp_dir.name, "p2_out.json")
        net = code2petri(
            source_path=self.app_js,
            target_function="stepCpu",
            output_file=out_json,
        )
        self.assertIsInstance(net, PetriNet)
        with open(out_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("places", data)
        self.assertIn("transitions", data)
        self.assertIn("arcs", data)
        self.assertNotIn("fold_steps", data)
        self.assertNotIn("final_sm", data)

    def test_html_output_with_context_implicitly_activates_composite_mode(self):
        """Validates that generating HTML with --context implicitly produces composite net without --inline."""
        out_html = os.path.join(self.temp_dir.name, "implicit_comp.html")
        main([
            self.app_js,
            "-t", "loop",
            "--context", self.game_of_life_dir,
            "-o", out_html,
        ])
        self.assertTrue(os.path.exists(out_html))
        with open(out_html, "r", encoding="utf-8") as f:
            content = f.read()

        import re
        m = re.search(r'<script id="code2petri-data" type="application/json">\s*(\{.*?\})\s*</script>', content, re.DOTALL)
        self.assertIsNotNone(m)
        data = json.loads(m.group(1))
        self.assertEqual(data["mode"], "composite")
        self.assertIn("compounds", data)
        self.assertGreater(len(data["compounds"]), 0)
        t_ids = [t["id"] for t in data["initial_net"]["transitions"]]
        self.assertTrue(any("WebGLEngine.step" in tid for tid in t_ids))

    def test_html_output_with_context_expands_to_maximum_depth_by_default(self):
        """Validates that composite HTML expands to maximum depth by default without --inline-depth."""
        code = (
            "def leaf():\n"
            "    z = 1\n"
            "\n"
            "def branch():\n"
            "    leaf()\n"
            "\n"
            "def root():\n"
            "    branch()\n"
        )
        src_file = os.path.join(self.temp_dir.name, "depth_test.py")
        with open(src_file, "w", encoding="utf-8") as f:
            f.write(code)

        out_html = os.path.join(self.temp_dir.name, "max_depth.html")
        main([
            src_file,
            "-t", "root",
            "--context", self.temp_dir.name,
            "-o", out_html,
        ])
        self.assertTrue(os.path.exists(out_html))
        with open(out_html, "r", encoding="utf-8") as f:
            content = f.read()

        import re
        m = re.search(r'<script id="code2petri-data" type="application/json">\s*(\{.*?\})\s*</script>', content, re.DOTALL)
        self.assertIsNotNone(m)
        data = json.loads(m.group(1))
        self.assertEqual(data["mode"], "composite")
        # Both branch and leaf must be in compounds
        fn_names = [c["function_name"] for c in data["compounds"]]
        self.assertIn("branch", fn_names)
        self.assertIn("leaf", fn_names)

    def test_fold_flag_with_composite_html_logs_warning(self):
        """Validates that --fold alongside --inline with composite HTML logs a warning about incompatibility."""
        out_html = os.path.join(self.temp_dir.name, "warning.html")
        with self.assertLogs("code2petri", level="WARNING") as cm:
            main([
                self.app_js,
                "-t", "loop",
                "--context", self.game_of_life_dir,
                "--inline",
                "--fold",
                "-o", out_html,
            ])
        self.assertTrue(any("--fold is not compatible with composite HTML output and will be ignored." in msg for msg in cm.output))


if __name__ == "__main__":
    unittest.main()

