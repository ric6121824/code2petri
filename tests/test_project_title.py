import importlib.util
import json
import os
import re
import tempfile
import unittest

from code2petri.engine import code2petri, main
from code2petri.model import PetriNet
from code2petri.viewer import generate_html
from tests.test_html_viewer import _extract_embedded_data, _run_node_script


class TestProjectTitleWorkflow(unittest.TestCase):
    def setUp(self):
        self.net = PetriNet()
        self.net.add_place("p0", "start", initial_tokens=1)
        self.net.add_transition("t0", "return 1")
        self.net.add_place("p1", "end")
        nodes = self.net.get_node_map()
        self.net.add_arc(nodes["p0"], nodes["t0"])
        self.net.add_arc(nodes["t0"], nodes["p1"])

    def test_generated_project_title_is_document_identity_separate_from_header(self):
        title = "Tic Tac Toe — <img src=x onerror=alert(1)>"
        html = generate_html(
            self.net,
            title="Analysis run 2026-10-13",
            project_title=title,
            source_file="/temporary/moved/main.py",
            function_name="(global)",
        )

        data = _extract_embedded_data(html)
        self.assertEqual(data["title"], "Analysis run 2026-10-13")
        self.assertEqual(data["document"]["project_title"], title)
        self.assertEqual(data["document"]["filename"], "main.py")
        self.assertEqual(data["document"]["function_name"], "Global Scope")
        self.assertLess(html.index('id="info-project-title"'), html.index('id="info-filename"'))
        self.assertLess(html.index('id="info-filename"'), html.index('id="info-function-name"'))
        self.assertIn("overflow-wrap: anywhere", html)
        self.assertNotIn("</script><img src=x onerror=alert(1)>", html)

    def test_cli_and_api_propagate_explicit_titles_for_global_and_function_views(self):
        with tempfile.TemporaryDirectory(prefix="dots-boxes-2026-fixed-") as output_dir:
            source_path = os.path.join(output_dir, "main.py")
            with open(source_path, "w", encoding="utf-8") as source_file:
                source_file.write("def play():\n    return 1\n\nready = True\n")

            cases = [
                ("Tic Tac Toe", "(global)", "dated-tic-tac-toe.html", False),
                ("Tic Tac Toe", "play", "fixed-tic-tac-toe.html", True),
                ("Dots & Boxes", "(global)", "dated-dots-and-boxes.html", True),
                ("Dots & Boxes", "play", "fixed-dots-and-boxes.html", False),
            ]
            for project_title, function_name, filename, via_cli in cases:
                with self.subTest(project_title=project_title, function_name=function_name):
                    output_path = os.path.join(output_dir, filename)
                    arguments = [
                        source_path, "--target-function", function_name,
                        "--project-title", project_title, "--output", output_path,
                    ]
                    if via_cli:
                        main(arguments)
                    else:
                        code2petri(
                            source_path,
                            output_file=output_path,
                            target_function=function_name,
                            project_title=project_title,
                        )
                    with open(output_path, encoding="utf-8") as html_file:
                        data = _extract_embedded_data(html_file.read())
                    self.assertEqual(data["document"]["project_title"], project_title)
                    self.assertEqual(
                        data["document"]["function_name"],
                        "Global Scope" if function_name == "(global)" else "play",
                    )

    def test_all_games_batch_uses_original_names_for_global_and_function_views(self):
        script_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            ".scratch", "code2petri", "batch_generate_all_games.py",
        )
        spec = importlib.util.spec_from_file_location("code2petri_batch_generate", script_path)
        batch_generator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(batch_generator)

        with tempfile.TemporaryDirectory(prefix="project-title-batch-") as temp_dir:
            games_dir = os.path.join(temp_dir, "games")
            graphs_dir = os.path.join(temp_dir, "graphs")
            os.makedirs(games_dir)
            batch_generator.GAMES_DIR = games_dir
            batch_generator.GRAPHS_BASE = graphs_dir

            for game_name in ("Tic Tac Toe", "Dots & Boxes"):
                with self.subTest(game_name=game_name):
                    source_dir = os.path.join(games_dir, game_name)
                    os.makedirs(source_dir)
                    with open(os.path.join(source_dir, "main.py"), "w", encoding="utf-8") as source_file:
                        source_file.write("def play():\n    return 1\n\nready = True\n")

                    for suffix in ("dated-run", "fixed-run"):
                        batch_generator.DATE_SUFFIX = suffix
                        result = batch_generator.process_game(game_name)
                        prefix = batch_generator.normalize_game_name(game_name).lower()
                        for html_name in (f"{prefix}_global_foldable.html", "play_foldable.html"):
                            output_path = os.path.join(result["out_dir"], html_name)
                            with open(output_path, encoding="utf-8") as html_file:
                                data = _extract_embedded_data(html_file.read())
                            self.assertEqual(data["document"]["project_title"], game_name)

    def test_missing_and_blank_titles_are_unavailable_without_path_guessing(self):
        for project_title in (None, "", " \t\n"):
            with self.subTest(project_title=project_title):
                kwargs = {} if project_title is None else {"project_title": project_title}
                html = generate_html(
                    self.net,
                    source_file="/Tic Tac Toe/dated-run/main.py",
                    **kwargs,
                )
                data = _extract_embedded_data(html)
                self.assertNotIn("project_title", data["document"])
                self.assertIn(
                    '<span id="info-project-title" class="info-identity-value">Unavailable</span>',
                    html,
                )

    def test_active_project_identity_and_snapshot_round_trip(self):
        title = "Dots & Boxes <script>alert('x')</script> — 特別"
        html = generate_html(
            self.net, project_title=title, source_file="/source/main.py", function_name="(global)"
        )
        match = re.search(
            r"const unavailableFunctionName = 'Unavailable';.*?setActiveDocumentMetadata\(activeDocument\);",
            html,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        node_script = """
const fs = require('fs');
const { serializeFoldStateSnapshot, parseFoldStateSnapshot } = require('./code2petri/viewer/engine/session_snapshot.js');
const payload = __PAYLOAD__;
const html = fs.readFileSync('code2petri/viewer/template.html', 'utf8');
const project = { textContent: '', title: '' };
const fileBox = { style: {} };
const filename = { textContent: '', title: '' };
const functionName = { textContent: '', title: '' };
const returnMetadata = { textContent: '' };
const elements = {
  'info-project-title': project,
  'info-file-box': fileBox,
  'info-filename': filename,
  'info-function-name': functionName,
  'info-return-metadata': returnMetadata
};
const document = { getElementById: id => elements[id] || null };
global.window = {};
__SETTER__
if (project.textContent !== payload.document.project_title || project.title !== payload.document.project_title) throw new Error('Project title was not rendered as text');
if (fileBox.style.display !== 'flex' || filename.textContent !== 'main.py' || functionName.textContent !== 'Global Scope') throw new Error('Project, file, function identity did not initialize');
const originalNet = { places: [], transitions: [], arcs: [] };
const sessionDocument = {
  title: 'different analysis header', sourceFile: payload.document.source_file,
  filename: payload.document.filename, functionName: 'Global Scope', mode: 'fold',
  projectTitle: project.textContent, originalNet, compounds: [], foldSteps: [],
  calleeNets: {}, expandedNodes: [], playback: { currentStep: 0, totalSteps: 0 }
};
const cy = { elements: () => ({ jsons: () => [] }), zoom: () => 1, pan: () => ({ x: 0, y: 0 }) };
const engine = { stepCounter: 0, cfg: {}, rememberedCustomNames: new Map() };
const opened = parseFoldStateSnapshot(serializeFoldStateSnapshot({ cy, engine, document: sessionDocument }));
if (opened.document.projectTitle !== payload.document.project_title) throw new Error('Project title did not survive snapshot round-trip');
setActiveDocumentMetadata({
  source_file: opened.document.sourceFile, filename: opened.document.filename,
  function_name: opened.document.functionName, project_title: opened.document.projectTitle
});
if (project.textContent !== payload.document.project_title) throw new Error('Incoming session identity was not applied');
setActiveDocumentMetadata({ source_file: '', filename: '', function_name: 'Unavailable', project_title: '' });
if (project.textContent !== 'Unavailable') throw new Error('Missing incoming project title did not clear host identity');
const legacyDocument = { ...sessionDocument };
delete legacyDocument.projectTitle;
const legacy = parseFoldStateSnapshot(serializeFoldStateSnapshot({ cy, engine, document: legacyDocument }));
if (Object.hasOwn(legacy.document, 'projectTitle')) throw new Error('Legacy snapshot acquired a guessed project title');
setActiveDocumentMetadata({
  source_file: legacy.document.sourceFile, filename: legacy.document.filename,
  function_name: legacy.document.functionName, project_title: legacy.document.projectTitle || ''
});
if (project.textContent !== 'Unavailable') throw new Error('Legacy snapshot did not clear the host project title');
setActiveDocumentMetadata({
  source_file: sessionDocument.sourceFile, filename: sessionDocument.filename,
  function_name: sessionDocument.functionName, project_title: sessionDocument.projectTitle
});
const priorActiveProject = project.textContent;
const malformed = serializeFoldStateSnapshot({ cy, engine, document: sessionDocument });
malformed.document.projectTitle = 42;
let malformedRejected = false;
try {
  // The open flow parses and validates before calling restoreFoldStateSnapshot.
  parseFoldStateSnapshot(malformed);
} catch (_) { malformedRejected = true; }
if (!malformedRejected) throw new Error('Non-string project metadata was accepted');
if (project.textContent !== priorActiveProject) throw new Error('Rejected snapshot changed active document identity');
console.log('PASS');
""".replace("__PAYLOAD__", json.dumps(_extract_embedded_data(html))).replace(
            "__SETTER__", match.group(0)
        )
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Project title session workflow failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)


if __name__ == "__main__":
    unittest.main()
