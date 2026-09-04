import io
import json
import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from code2petri import code2petri  # noqa: E402
from code2petri.engine import main  # noqa: E402
from code2petri.model import PetriNet  # noqa: E402


class TestPetriPipeline(unittest.TestCase):
    def setUp(self):
        self.fixture_path = os.path.join(
            os.path.dirname(__file__),
            "test_code",
            "petri_py",
            "mixed_pipeline.py",
        )
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_e2e_mixed_pipeline_pnml(self):
        out_pnml = os.path.join(self.temp_dir.name, "out.pnml")
        net = code2petri(
            source_path=self.fixture_path,
            target_function="mixed_pipeline_func",
            output_file=out_pnml,
        )
        self.assertIsInstance(net, PetriNet)
        self.assertTrue(os.path.exists(out_pnml))

        # Assert valid XML and PNML structure
        tree = ET.parse(out_pnml)
        root = tree.getroot()
        self.assertTrue(root.tag.endswith("pnml"))
        net_elem = root.find("{http://www.pnml.org/version-2009/grammar/pnml}net")
        self.assertIsNotNone(net_elem)

        # Assert places, transitions, arcs present
        places = [el for el in root.iter() if el.tag.endswith("place")]
        transitions = [el for el in root.iter() if el.tag.endswith("transition")]
        arcs = [el for el in root.iter() if el.tag.endswith("arc")]
        self.assertGreater(len(places), 5)
        self.assertGreater(len(transitions), 5)
        self.assertGreater(len(arcs), 10)

    def test_e2e_mixed_pipeline_dot(self):
        out_gv = os.path.join(self.temp_dir.name, "out.gv")
        net = code2petri(
            source_path=self.fixture_path,
            target_function="mixed_pipeline_func",
            output_file=out_gv,
        )
        self.assertIsInstance(net, PetriNet)
        self.assertTrue(os.path.exists(out_gv))

        with open(out_gv, "r", encoding="utf-8") as f:
            content = f.read().strip()
        self.assertTrue(content.startswith("digraph"))
        self.assertTrue(content.endswith("}"))
        self.assertIn("shape=circle", content)
        self.assertIn("shape=rect", content)
        self.assertIn("total = 0", content)
        self.assertIn("total += helper_calc(item)", content)

    def test_e2e_mixed_pipeline_json(self):
        out_json = os.path.join(self.temp_dir.name, "out.json")
        net = code2petri(
            source_path=self.fixture_path,
            target_function="mixed_pipeline_func",
            output_file=out_json,
        )
        self.assertIsInstance(net, PetriNet)
        self.assertTrue(os.path.exists(out_json))

        with open(out_json, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("places", data)
        self.assertIn("transitions", data)
        self.assertIn("arcs", data)
        self.assertEqual(len(data["places"]), len(net.places))
        self.assertEqual(len(data["transitions"]), len(net.transitions))
        self.assertEqual(len(data["arcs"]), len(net.arcs))

    def test_list_functions(self):
        stdout_capture = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = stdout_capture
            code2petri(
                source_path=self.fixture_path,
                list_functions=True,
            )
        finally:
            sys.stdout = old_stdout

        output = stdout_capture.getvalue()
        lines = [line.strip() for line in output.strip().splitlines() if line.strip()]
        self.assertEqual(lines, ["helper_calc", "mixed_pipeline_func", "secondary_func"])

    def test_target_function_not_found(self):
        with self.assertRaises(AssertionError) as ctx:
            code2petri(
                source_path=self.fixture_path,
                target_function="nonexistent_function",
            )
        self.assertIn("nonexistent_function", str(ctx.exception))

    def test_missing_target_function_without_list_functions(self):
        with self.assertRaises(AssertionError) as ctx:
            code2petri(
                source_path=self.fixture_path,
                target_function=None,
            )
        self.assertIn("target function", str(ctx.exception).lower())

    def test_unparseable_file(self):
        bad_file = os.path.join(self.temp_dir.name, "bad.py")
        with open(bad_file, "w") as f:
            f.write("def invalid_syntax(:")
        with self.assertRaises(AssertionError) as ctx:
            code2petri(
                source_path=bad_file,
                target_function="foo",
            )
        self.assertIn("parse", str(ctx.exception).lower())

    def test_cli_main_e2e(self):
        out_pnml = os.path.join(self.temp_dir.name, "cli_out.pnml")
        main([
            self.fixture_path,
            "--target-function", "mixed_pipeline_func",
            "--output", out_pnml,
        ])
        self.assertTrue(os.path.exists(out_pnml))

    def test_cli_main_list_functions(self):
        stdout_capture = io.StringIO()
        old_stdout = sys.stdout
        try:
            sys.stdout = stdout_capture
            main([self.fixture_path, "--list-functions"])
        finally:
            sys.stdout = old_stdout

        output = stdout_capture.getvalue()
        self.assertIn("helper_calc", output)
        self.assertIn("mixed_pipeline_func", output)
        self.assertIn("secondary_func", output)

    def test_cli_logging_flags_conflict(self):
        with self.assertRaises(AssertionError) as ctx:
            main([
                self.fixture_path,
                "--target-function", "mixed_pipeline_func",
                "--quiet",
                "--verbose",
            ])
        self.assertIn("both", str(ctx.exception).lower())

    def test_unsupported_output_extension(self):
        out_bad = os.path.join(self.temp_dir.name, "out.xyz")
        with self.assertRaises(AssertionError) as ctx:
            code2petri(
                source_path=self.fixture_path,
                target_function="mixed_pipeline_func",
                output_file=out_bad,
            )
        self.assertIn("unsupported", str(ctx.exception).lower())

    def test_nonexistent_source_file(self):
        with self.assertRaises(AssertionError) as ctx:
            code2petri(
                source_path="nonexistent_file_xyz.py",
                target_function="foo",
            )
        self.assertIn("does not exist", str(ctx.exception))

    def test_image_output_without_dot(self):
        from unittest.mock import patch
        with patch("code2petri.engine.is_installed", return_value=False):
            with self.assertRaises(AssertionError) as ctx:
                code2petri(
                    source_path=self.fixture_path,
                    target_function="mixed_pipeline_func",
                    output_file=os.path.join(self.temp_dir.name, "out.png"),
                )
            self.assertIn("Graphviz", str(ctx.exception))

    def test_image_output_with_mocked_dot(self):
        from unittest.mock import patch, MagicMock
        with patch("code2petri.engine.is_installed", return_value=True):
            mock_proc = MagicMock(returncode=0)
            with patch("subprocess.run", return_value=mock_proc) as mock_run:
                out_png = os.path.join(self.temp_dir.name, "out.png")
                code2petri(
                    source_path=self.fixture_path,
                    target_function="mixed_pipeline_func",
                    output_file=out_png,
                )
                self.assertTrue(mock_run.called)
                args, kwargs = mock_run.call_args
                self.assertEqual(args[0], ["dot", "-Tpng", "-o", out_png])
                self.assertIn(b"digraph", kwargs["input"])

    def test_cli_quiet_flag(self):
        out_pnml = os.path.join(self.temp_dir.name, "quiet_out.pnml")
        main([
            self.fixture_path,
            "--target-function", "mixed_pipeline_func",
            "--output", out_pnml,
            "--quiet",
        ])
        self.assertTrue(os.path.exists(out_pnml))

    def test_cli_verbose_flag(self):
        out_pnml = os.path.join(self.temp_dir.name, "verbose_out.pnml")
        main([
            self.fixture_path,
            "--target-function", "mixed_pipeline_func",
            "--output", out_pnml,
            "--verbose",
        ])
        self.assertTrue(os.path.exists(out_pnml))


if __name__ == '__main__':
    unittest.main()
