import json
import os
import tempfile
import unittest

from code2petri.engine import code2petri
from tests.test_html_viewer import (
    _extract_embedded_data,
    _run_node_script,
    _setup_live_fold_test_harness,
)


class TestPythonListReturnInferenceWorkflow(unittest.TestCase):
    def _metadata_for(self, source, function_name):
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = os.path.join(temp_dir, "cases.py")
            html_path = os.path.join(temp_dir, function_name + ".html")
            with open(source_path, "w", encoding="utf-8") as source_file:
                source_file.write(source)
            result = code2petri(
                source_path, output_file=html_path, target_function=function_name, fold=True
            )
            with open(html_path, encoding="utf-8") as html_file:
                metadata = _extract_embedded_data(html_file.read())["document"]["return_metadata"]
        self.assertEqual(result.initial_net.to_dict()["return_metadata"], metadata)
        return metadata

    def test_create_board_concatenation_is_inferred_and_survives_offline_open(self):
        source = (
            "def create_board():\n"
            "    return ['|'] + [' ' for _ in range(9)]\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = os.path.join(temp_dir, "board.py")
            html_path = os.path.join(temp_dir, "board.html")
            with open(source_path, "w", encoding="utf-8") as source_file:
                source_file.write(source)

            result = code2petri(
                source_path, output_file=html_path, target_function="create_board", fold=True
            )
            with open(html_path, encoding="utf-8") as html_file:
                html_content = html_file.read()

        metadata = _extract_embedded_data(html_content)["document"]["return_metadata"]
        public_net = result.initial_net.to_dict()
        self.assertEqual(metadata["analysis_status"], "complete")
        self.assertEqual(metadata["inferred_types"], ["list"])
        self.assertEqual(metadata["inferred"][0]["expression"], "['|'] + [' ' for _ in range(9)]")
        self.assertEqual(metadata["inferred"][0]["type"], "list")
        self.assertEqual(metadata["inferred"][0]["role"], "call_result")
        self.assertEqual(metadata["inferred"][0]["provenance"], "expression_inference")
        self.assertEqual(metadata["inferred"][0]["source_location"], {"line": 2, "column": 4})
        self.assertEqual(metadata["inferred"][0]["expression_location"], {"line": 2, "column": 11})
        self.assertEqual(metadata["inferred"][0]["evidence"], [])
        self.assertEqual(result.initial_net.to_dict()["return_metadata"], metadata)
        self.assertIn('id="info-return-metadata"', html_content)

        node_script = f"""
const cytoscape = require('./code2petri/viewer/vendor/cytoscape.min.js');
const fs = require('fs');
const {{ LiveFoldReductionEngine }} = require('./code2petri/viewer/engine/reduction_engine.js');
const {{ serializeFoldStateSnapshot, parseFoldStateSnapshot }} = require('./code2petri/viewer/engine/session_snapshot.js');
const cy = cytoscape({{ elements: [] }});
const engine = new LiveFoldReductionEngine(cy);
const metadata = {json.dumps(metadata)};
const template = fs.readFileSync('code2petri/viewer/template.html', 'utf8');
const rootStart = template.indexOf('function formatReturnMetadata(metadata)');
const rolesStart = template.indexOf('function formatFunctionRoles(metadata)', rootStart);
const callStart = template.indexOf('function formatFunctionReturnInspection(metadata)');
const inspectorEnd = template.indexOf('function getInspectorData(node)', callStart);
const display = new Function('metadata', template.slice(rootStart, rolesStart) +
  template.slice(callStart, inspectorEnd) +
  'return {{ root: formatReturnMetadata(metadata), call: formatFunctionReturnInspection(metadata) }};');
const visible = display(metadata);
for (const text of [visible.root, visible.call]) {{
  if (!text.includes('Inferred result: list') ||
      !text.includes("Returned expression: ['|'] + [' ' for _ in range(9)]") ||
      !text.includes('Inferred type at this return: list')) {{
    throw new Error('list result or source expression missing from viewer text: ' + text);
  }}
}}
const document = {{
  title: 'Board', sourceFile: '/offline/board.py', filename: 'board.html',
  functionName: 'create_board', mode: 'fold', returnMetadata: metadata,
  originalNet: {json.dumps(public_net)}, compounds: [], foldSteps: [],
  calleeNets: {{}}, expandedNodes: [], playback: {{ currentStep: 0, totalSteps: 0 }}
}};
const snapshot = serializeFoldStateSnapshot({{ cy, engine, document }});
const reopened = parseFoldStateSnapshot(snapshot);
if (JSON.stringify(reopened.document.returnMetadata) !== JSON.stringify(metadata)) {{
  throw new Error('list return metadata changed during offline save/open');
}}
if (JSON.stringify(reopened.document.originalNet.return_metadata) !== JSON.stringify(metadata)) {{
  throw new Error('public net metadata changed during offline save/open');
}}
const reopenedVisible = display(reopened.document.returnMetadata);
if (!reopenedVisible.root.includes('Inferred result: list') ||
    !reopenedVisible.call.includes('Inferred type at this return: list')) {{
  throw new Error('reopened offline viewer no longer displays list metadata');
}}
const olderUnknown = JSON.parse(JSON.stringify(metadata));
olderUnknown.analysis_status = 'unknown';
olderUnknown.inferred_types = [];
olderUnknown.inferred[0].type = 'unknown';
document.returnMetadata = olderUnknown;
document.originalNet.return_metadata = olderUnknown;
const oldSnapshot = serializeFoldStateSnapshot({{ cy, engine, document }});
const oldReopened = parseFoldStateSnapshot(oldSnapshot);
if (JSON.stringify(oldReopened.document.returnMetadata) !== JSON.stringify(olderUnknown)) {{
  throw new Error('previously saved unknown result was reanalyzed or changed on open');
}}
console.log('PASS');
"""
        proc = _run_node_script(node_script)
        self.assertEqual(proc.returncode, 0, f"Node script failed: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)

    def test_supported_lists_and_concatenation_stay_bounded_and_scoped(self):
        source = '''
def filtered_nested(rows):
    return [item for row in rows for item in row if item]

def empty_list_addition():
    return [] + []

async def asynchronous_comprehension(items):
    return [item async for item in items]

def chained_copy(rows):
    prefix = ['|']
    spaces = [' ' for _ in range(9)]
    partial = prefix + spaces
    board = partial + []
    copy = board
    return copy

def unknown_right():
    return [] + make_items()

def unknown_left():
    return make_items() + []

def annotated_only(values: list) -> list:
    return values + []

def incompatible():
    return [] + ()

def unsupported_repetition():
    return [] * 9

def unsupported_reassignment():
    board = []
    board = make_items()
    return board

def comprehension_scope(items):
    item = 1
    ignored = [item for item in items]
    return item

def comprehension_walrus_effect(items):
    item = 1
    ignored = [(item := 'changed') for _ in items]
    return item

def partial_list_observation(rows):
    if flag:
        return [] + [item for item in rows]
    return make_items()
'''
        expected_types = {
            "filtered_nested": "list",
            "empty_list_addition": "list",
            "asynchronous_comprehension": "unknown",
            "chained_copy": "list",
            "unknown_right": "unknown",
            "unknown_left": "unknown",
            "annotated_only": "unknown",
            "incompatible": "unknown",
            "unsupported_repetition": "unknown",
            "unsupported_reassignment": "unknown",
            "comprehension_scope": "int",
            "comprehension_walrus_effect": "unknown",
        }
        for function_name, expected_type in expected_types.items():
            with self.subTest(function_name=function_name):
                metadata = self._metadata_for(source, function_name)
                role = metadata.get("roles", {}).get("awaited", metadata)
                self.assertEqual(role["inferred"][0]["type"], expected_type)
                if expected_type == "list":
                    self.assertEqual(role["analysis_status"], "complete")
        annotated = self._metadata_for(source, "annotated_only")
        self.assertEqual(annotated["declared"]["expression"], "list")
        self.assertEqual(annotated["analysis_status"], "unknown")
        partial = self._metadata_for(source, "partial_list_observation")
        self.assertEqual(partial["analysis_status"], "unknown")
        self.assertEqual(partial["observed_types"], ["list"])
        copied = self._metadata_for(source, "chained_copy")["inferred"][0]
        self.assertEqual(copied["expression"], "copy")
        self.assertEqual(
            [item["expression"] for item in copied["evidence"]],
            ["prefix = ['|']", "spaces = [' ' for _ in range(9)]", "partial = prefix + spaces",
             "board = partial + []", "copy = board"],
        )

    def test_called_list_metadata_is_shared_across_repeated_call_references(self):
        source = (
            "def create_board():\n"
            "    return ['|'] + [' ' for _ in range(9)]\n"
            "\n"
            "def caller():\n"
            "    create_board()\n"
            "    create_board()\n"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            source_path = os.path.join(temp_dir, "called_board.py")
            html_path = os.path.join(temp_dir, "caller.html")
            composite_path = os.path.join(temp_dir, "caller-composite.html")
            with open(source_path, "w", encoding="utf-8") as source_file:
                source_file.write(source)
            result = code2petri(
                source_path, output_file=html_path, target_function="caller",
                context=[source_path], fold=True,
            )
            composite_result = code2petri(
                source_path, output_file=composite_path, target_function="caller",
                context=[source_path], fold=False,
            )
            with open(html_path, encoding="utf-8") as html_file:
                html_content = html_file.read()
            with open(composite_path, encoding="utf-8") as html_file:
                composite_html_content = html_file.read()

        viewer_net = _extract_embedded_data(html_content)["initial_net"]
        calls = [
            transition for transition in viewer_net["transitions"]
            if transition.get("metadata", {}).get("resolved_to") == "create_board"
        ]
        self.assertEqual(len(calls), 2)
        references = [transition["metadata"]["function_ref"] for transition in calls]
        self.assertEqual(references[0], references[1])
        record = viewer_net["function_metadata_registry"][references[0]]
        self.assertEqual(record["qualified_name"], "create_board")
        self.assertEqual(record["inferred_types"], ["list"])
        self.assertEqual(record["inferred"][0]["expression"], "['|'] + [' ' for _ in range(9)]")
        self.assertEqual(
            result.initial_net.clone().to_dict()["function_metadata_registry"],
            viewer_net["function_metadata_registry"],
        )
        self.assertIn('id="inspector-function-return-content"', html_content)
        self.assertIn("functionRef = node.data('function_ref')", html_content)

        composite_net = _extract_embedded_data(composite_html_content)["composite_net"]
        board_compound = next(
            item for item in composite_net["compounds"]
            if item["function_name"] == "create_board"
        )
        self.assertEqual(board_compound["function_ref"], references[0])
        self.assertEqual(
            composite_net["function_metadata_registry"][references[0]]["inferred_types"],
            ["list"],
        )
        self.assertEqual(
            composite_result.to_dict()["function_metadata_registry"][references[0]]["inferred_types"],
            ["list"],
        )

        source_transition = next(
            item for item in composite_net["transitions"]
            if item.get("parent") == board_compound["id"]
        )
        fold_logic = f"""
const fn = cy.getElementById({json.dumps(board_compound['id'])});
const functionRef = {json.dumps(references[0])};
const functionId = {json.dumps(board_compound['id'])};
const transitionId = {json.dumps(source_transition['id'])};
const metadataBefore = JSON.stringify(net.function_metadata_registry[functionRef]);
const folded = foldEngine.executeFoldEntireFunction(fn);
if (!folded.success || !folded.complete || !fn.hasClass('collapsed-compound')) throw new Error('Function did not collapse: ' + JSON.stringify(folded));
if (fn.data('function_ref') !== functionRef || JSON.stringify(net.function_metadata_registry[functionRef]) !== metadataBefore) throw new Error('Collapse changed function metadata association');
const component = cy.nodes().filter(function(node) {{ return node.data('parent') === functionId && node.data('opaque'); }}).first();
if (!component.length) throw new Error('Folded function component missing');
foldEngine.renameNode(component, 'Board internals');
const unfolded = foldEngine.executeComponentLocalUnfold(component);
if (!unfolded.success || fn.hasClass('collapsed-compound')) throw new Error('Renamed component could not unfold');
if (fn.data('function_ref') !== functionRef || JSON.stringify(net.function_metadata_registry[functionRef]) !== metadataBefore) throw new Error('Rename/unfold changed function metadata association');
if (!cy.getElementById(transitionId).length) throw new Error('Source-generated function transition was not restored');
console.log('PASS');
"""
        proc = _run_node_script(
            _setup_live_fold_test_harness(json.dumps(composite_net), fold_logic)
        )
        self.assertEqual(proc.returncode, 0, f"Fold/rename/unfold changed metadata: {proc.stderr}")
        self.assertIn("PASS", proc.stdout)


if __name__ == "__main__":
    unittest.main()
