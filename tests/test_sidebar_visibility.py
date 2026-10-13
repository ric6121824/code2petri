import re
import subprocess
import unittest
from pathlib import Path


class TestDockedSidebarSessionVisibility(unittest.TestCase):
    def test_save_session_context_captures_the_current_visibility(self):
        template_path = Path(__file__).resolve().parents[1] / "code2petri" / "viewer" / "template.html"
        template = template_path.read_text(encoding="utf-8")
        match = re.search(
            r"function getFoldStateDocumentContext\(\) \{.*?\n      \}",
            template,
            re.DOTALL,
        )
        self.assertIsNotNone(match, "Could not locate the Save Session document context")
        script = r"""
const { serializeFoldStateSnapshot, parseFoldStateSnapshot } = require('./code2petri/viewer/engine/session_snapshot.js');
const payload = {
  title: 'Example', source_file: '/src/example.py', filename: 'example.py',
  mode: 'fold', initial_net: { places: [], transitions: [], arcs: [], compounds: [] },
  compounds: [], fold_steps: [], final_sm: 0, fully_reducible: false
};
const initialNet = payload.initial_net;
const activeDocument = { function_name: 'answer', project_title: 'Example Project', return_metadata: null };
const foldSteps = [];
const currentStep = 0;
const totalSteps = 0;
const calleeNetsMap = {};
const expandedNodes = new Map();
const compounds = [];
let dockedSidebarVisible = false;
__FUNCTION__
const cy = { elements: () => ({ jsons: () => [] }), zoom: () => 1.25, pan: () => ({ x: 7, y: -3 }) };
const engine = { stepCounter: 0, cfg: {}, rememberedCustomNames: new Map() };
const captured = parseFoldStateSnapshot(serializeFoldStateSnapshot({ cy, engine, document: getFoldStateDocumentContext() }));
if (captured.document.sidebarVisible !== false) throw new Error('Save Session omitted hidden visibility');
dockedSidebarVisible = true;
if (getFoldStateDocumentContext().sidebarVisible !== true) throw new Error('Save Session did not capture shown visibility');
console.log('PASS');
""".replace("__FUNCTION__", match.group(0).replace("{{TITLE_JSON}}", '"Example"'))
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASS", result.stdout)

    def test_snapshot_round_trip_accepts_boolean_and_rejects_invalid_visibility(self):
        script = r"""
const { serializeFoldStateSnapshot, parseFoldStateSnapshot } = require('./code2petri/viewer/engine/session_snapshot.js');
function documentContext() {
  return {
    title: 'Example', sourceFile: '/src/example.py', filename: 'example.py',
    functionName: 'answer', mode: 'fold',
    originalNet: { places: [], transitions: [], arcs: [] }, compounds: [], foldSteps: [],
    finalSm: 0, fullyReducible: false, calleeNets: {}, expandedNodes: [],
    playback: { currentStep: 0, totalSteps: 0 }
  };
}
const cy = {
  elements: () => ({ jsons: () => [] }),
  zoom: () => 1.5,
  pan: () => ({ x: 12, y: -4 })
};
const engine = { stepCounter: 0, cfg: {}, rememberedCustomNames: new Map() };
for (const visible of [true, false]) {
  const document = Object.assign(documentContext(), { sidebarVisible: visible });
  const captured = serializeFoldStateSnapshot({ cy, engine, document });
  document.sidebarVisible = !visible;
  const opened = parseFoldStateSnapshot(captured);
  if (opened.document.sidebarVisible !== visible) throw new Error('Sidebar visibility did not round-trip detached from its source');
}
const legacy = parseFoldStateSnapshot({
  schemaVersion: 1, snapshotType: 'code2petri-fold-state', elements: [],
  engine: { stepCounter: 0, cfg: {}, rememberedCustomNames: [] },
  viewport: { zoom: 1, pan: { x: 0, y: 0 } }, document: documentContext()
});
if (Object.hasOwn(legacy.document, 'sidebarVisible')) throw new Error('Legacy snapshot acquired visibility metadata');
for (const sidebarVisible of [null, 'false', 0, 1, {}]) {
  const snapshot = {
    schemaVersion: 1, snapshotType: 'code2petri-fold-state', elements: [],
    engine: { stepCounter: 0, cfg: {}, rememberedCustomNames: [] },
    viewport: { zoom: 1, pan: { x: 0, y: 0 } },
    document: Object.assign(documentContext(), { sidebarVisible })
  };
  let rejected = false;
  try { parseFoldStateSnapshot(snapshot); } catch (_) { rejected = true; }
  if (!rejected) throw new Error('Invalid sidebar visibility metadata was accepted: ' + JSON.stringify(sidebarVisible));
}
console.log('PASS');
"""
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASS", result.stdout)

    def test_toggle_keeps_inspection_draft_and_camera_while_changing_panel_state(self):
        template_path = Path(__file__).resolve().parents[1] / "code2petri" / "viewer" / "template.html"
        template = template_path.read_text(encoding="utf-8")
        match = re.search(
            r"function updateDockedSidebarToggle\(\) \{.*?\n      \}\n\n"
            r"      function setDockedSidebarVisible\(visible, options\) \{.*?\n      \}",
            template,
            re.DOTALL,
        )
        self.assertIsNotNone(match, "Could not locate docked sidebar visibility behavior")
        script = r"""
const panel = {
  style: { display: 'flex' }, attributes: {}, inert: false,
  contains: element => element === input,
  setAttribute(name, value) { this.attributes[name] = value; }
};
const input = { value: 'Unfinished component name' };
const toggle = {
  textContent: '', title: '', attributes: {}, focused: false,
  setAttribute(name, value) { this.attributes[name] = value; },
  focus() { this.focused = true; document.activeElement = this; }
};
const mainContainer = { classes: new Set(), classList: {
  toggle(name, force) { if (force) mainContainer.classes.add(name); else mainContainer.classes.delete(name); }
}};
const document = { activeElement: input };
let resizeCount = 0;
let viewport = { zoom: 1.75, pan: { x: 83, y: -41 } };
const cy = { resize() { resizeCount += 1; } };
const captureViewport = () => ({ zoom: viewport.zoom, pan: { ...viewport.pan } });
const restoreViewport = (_, zoom, pan) => { viewport = { zoom, pan: { ...pan } }; };
let dockedSidebarVisible = true;
let selectedInspectorNode = { inside: () => true };
let closeInspectorCount = 0;
const closeInspector = () => { closeInspectorCount += 1; selectedInspectorNode = null; };
const inspectorPanel = panel;
const sidebarVisibilityToggle = toggle;
__FUNCTIONS__
setDockedSidebarVisible(false);
if (panel.style.display !== 'none' || panel.attributes['aria-hidden'] !== 'true' || !panel.inert) throw new Error('Sidebar did not hide accessibly');
if (!mainContainer.classes.has('sidebar-hidden') || toggle.title !== 'Show Sidebar' || toggle.attributes['aria-expanded'] !== 'false') throw new Error('Hidden toggle state is wrong');
if (!toggle.focused || input.value !== 'Unfinished component name') throw new Error('Hide did not preserve focus/draft safely');
if (viewport.zoom !== 1.75 || viewport.pan.x !== 83 || viewport.pan.y !== -41 || resizeCount !== 1) throw new Error('Hide changed camera or skipped canvas resize');
document.activeElement = toggle;
setDockedSidebarVisible(true);
if (panel.style.display !== 'flex' || panel.attributes['aria-hidden'] !== 'false' || panel.inert) throw new Error('Sidebar did not recall accessibly');
if (mainContainer.classes.has('sidebar-hidden') || toggle.title !== 'Hide Sidebar' || toggle.attributes['aria-expanded'] !== 'true') throw new Error('Shown toggle state is wrong');
if (input.value !== 'Unfinished component name' || selectedInspectorNode === null || closeInspectorCount !== 0) throw new Error('Recall changed the current inspection or draft');
if (viewport.zoom !== 1.75 || viewport.pan.x !== 83 || viewport.pan.y !== -41 || resizeCount !== 2) throw new Error('Recall changed camera or skipped canvas resize');
selectedInspectorNode = { inside: () => false };
setDockedSidebarVisible(true);
if (closeInspectorCount !== 1) throw new Error('Recall kept details for a removed node');
console.log('PASS');
""".replace("__FUNCTIONS__", match.group(0))
        result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
