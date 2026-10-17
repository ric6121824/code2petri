import re
import subprocess
import unittest

from code2petri.model import PetriNet
from code2petri.viewer import generate_html
from tests.test_html_viewer import _make_sese_test_net, _setup_live_fold_test_harness


class ViewerActionHistoryTests(unittest.TestCase):
    def run_node(self, script):
        return subprocess.run(["node", "-e", script], capture_output=True, text=True)

    def test_history_restores_exact_graph_state_and_keeps_current_camera(self):
        script = r"""
const cytoscape = require('./code2petri/viewer/vendor/cytoscape.min.js');
const { ViewerActionHistory } = require('./code2petri/viewer/engine/action_history.js');
const cy = cytoscape({
  headless: true,
  elements: [
    { group: 'nodes', data: { id: 'root', label: 'Root' }, position: { x: 10, y: 20 } },
    { group: 'nodes', data: { id: 'p', parent: 'root', label: 'Place', initial_tokens: 1 }, position: { x: 30, y: 40 } },
    { group: 'nodes', data: { id: 't', parent: 'root', label: 'Call', function_ref: 'fn-1' }, position: { x: 50, y: 60 } },
    { group: 'edges', data: { id: 'e', source: 'p', target: 't', weight: 3 } }
  ]
});
const engine = { stepCounter: 4, cfg: { choice: 1 }, rememberedCustomNames: new Map([['key', 'Known']]) };
let currentStep = 2;
const history = new ViewerActionHistory({
  cy,
  captureContext: () => ({
    stepCounter: engine.stepCounter,
    cfg: engine.cfg,
    rememberedCustomNames: Array.from(engine.rememberedCustomNames),
    currentStep
  }),
  restoreContext: state => {
    engine.stepCounter = state.stepCounter;
    engine.cfg = state.cfg;
    engine.rememberedCustomNames = new Map(state.rememberedCustomNames);
    currentStep = state.currentStep;
  }
});
function graphState() {
  return cy.elements().jsons().map(element => ({
    group: element.group, data: element.data, classes: element.classes, position: element.position
  })).sort((a, b) => a.data.id.localeCompare(b.data.id));
}
const before = JSON.stringify({ graph: graphState(), context: history.captureContext() });
const didEdit = history.perform('fold', () => {
  cy.getElementById('t').remove();
  cy.getElementById('e').remove();
  cy.add({ group: 'nodes', data: { id: 'c_5', type: 'Opaque Transition', custom_name: 'Nested' }, position: { x: 70, y: 80 } });
  engine.stepCounter = 5;
  engine.rememberedCustomNames.set('place::p', 'Remembered');
  currentStep = 3;
  return true;
});
if (!didEdit || !history.canUndo || history.canRedo) throw new Error('successful edit was not recorded');
cy.viewport({ zoom: 1.7, pan: { x: 91, y: -33 } });
cy.getElementById('p').select();
if (!history.undo()) throw new Error('undo failed');
const undone = JSON.stringify({ graph: graphState(), context: history.captureContext() });
if (undone !== before) throw new Error('undo did not restore exact graph and editing state');
if (cy.zoom() !== 1.7 || cy.pan().x !== 91 || cy.pan().y !== -33) throw new Error('undo rewound the camera');
if (!history.canRedo || history.canUndo) throw new Error('undo did not move the history cursor');
if (!history.redo()) throw new Error('redo failed');
if (!cy.getElementById('c_5').length || engine.stepCounter !== 5 || currentStep !== 3) throw new Error('redo did not restore its recorded result');
"""
        result = self.run_node(script)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_production_fold_handler_records_one_exact_undoable_action(self):
        logic = r"""
function normalizedGraph() {
  return cy.elements().jsons().map(element => {
    const copy = JSON.parse(JSON.stringify(element));
    delete copy.selected;
    if (copy.data.consumedSubgraph !== undefined) delete copy.data.consumedSubgraph;
    return copy;
  }).sort((a, b) => a.data.id.localeCompare(b.data.id));
}
const before = JSON.stringify(normalizedGraph());
if (!handleFoldReduction(cy.getElementById('p1'), null)) throw new Error('production fold handler did not fold');
const folded = JSON.stringify(normalizedGraph());
if (!viewerActionHistory.canUndo || viewerActionHistory.canRedo) throw new Error('production fold was not added to history');
if (!viewerActionHistory.undo()) throw new Error('production fold Undo failed');
if (JSON.stringify(normalizedGraph()) !== before) throw new Error('Undo did not restore the production fold input');
if (!viewerActionHistory.redo()) throw new Error('production fold Redo failed');
if (JSON.stringify(normalizedGraph()) !== folded) throw new Error('Redo did not restore the exact production fold output');
"""
        script = _setup_live_fold_test_harness(_make_sese_test_net(), logic)
        result = self.run_node(script)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_production_rename_and_local_unfold_are_separate_gestures_with_draft_continuity(self):
        logic = r"""
if (!handleFoldReduction(cy.getElementById('p1'), null)) throw new Error('fold setup failed');
const componentId = selectedInspectorNode.id();
const originalGeneratedName = selectedInspectorNode.data('label');
if (viewerActionHistory.undoStack.length !== 1) throw new Error('fold was split into multiple gestures');
inspectorInput.value = 'Semantic name';
if (!applyComponentNodeRename()) throw new Error('production rename did not commit');
if (viewerActionHistory.undoStack.length !== 2 || cy.getElementById(componentId).data('custom_name') !== 'Semantic name') {
  throw new Error('rename was not recorded as one gesture');
}
inspectorInput.value = 'unfinished draft';
if (!viewerActionHistory.undo()) throw new Error('rename undo failed');
if (cy.getElementById(componentId).data('label') !== originalGeneratedName || inspectorInput.value !== 'unfinished draft') {
  throw new Error('Undo did not restore the committed name while retaining an unfinished draft');
}
if (!viewerActionHistory.redo()) throw new Error('rename redo failed');
if (cy.getElementById(componentId).data('label') !== 'Semantic name' || inspectorInput.value !== 'unfinished draft') {
  throw new Error('Redo did not restore the name while retaining the current draft');
}
function currentGraph() {
  return JSON.stringify(cy.elements().jsons().map(element => {
    const copy = JSON.parse(JSON.stringify(element));
    delete copy.selected;
    if (copy.data.consumedSubgraph !== undefined) delete copy.data.consumedSubgraph;
    return copy;
  }).sort((a, b) => a.data.id.localeCompare(b.data.id)));
}
const foldedGraph = currentGraph();
if (!handleRightClickUnfold(cy.getElementById(componentId))) throw new Error('production Component-Local Unfold failed');
if (viewerActionHistory.undoStack.length !== 3 || cy.getElementById('p1').length === 0) {
  throw new Error('Component-Local Unfold did not produce one history entry');
}
if (!viewerActionHistory.undo() || currentGraph() !== foldedGraph) {
  throw new Error('Undo did not restore the exact named folded component');
}
if (!viewerActionHistory.redo() || cy.getElementById(componentId).length !== 0) {
  throw new Error('Redo did not restore the exact unfolded result');
}
if (!handleFoldReduction(cy.getElementById('p1'), null)) throw new Error('refold after local unfold failed');
const refolded = cy.nodes('.opaque').filter(node => node.data('custom_name') === 'Semantic name');
if (refolded.length !== 1 || refolded.id() === componentId) {
  throw new Error('Refold did not reuse the remembered name with a collision-free component ID');
}
const refoldedGraph = currentGraph();
if (!viewerActionHistory.undo() || cy.getElementById('p1').length === 0 || currentGraph() === refoldedGraph) {
  throw new Error('Undo did not restore the graph before the remembered-name refold');
}
if (!viewerActionHistory.redo() || currentGraph() !== refoldedGraph ||
    cy.nodes('.opaque').filter(node => node.data('custom_name') === 'Semantic name').length !== 1) {
  throw new Error('Redo did not restore the remembered-name refold exactly');
}
"""
        script = _setup_live_fold_test_harness(_make_sese_test_net(), logic)
        result = self.run_node(script)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_production_batch_and_function_folds_each_form_one_gesture(self):
        net_literal = """{
  compounds: [{ id: 'fn', label: 'called()', function_name: 'called' }],
  places: [
    { id: 'p_entry', label: 'entry' }, { id: 'p_trigger', parent: 'fn', label: 'split' },
    { id: 'p1', parent: 'fn', label: 'left middle' }, { id: 'p2', parent: 'fn', label: 'right middle' },
    { id: 'p_unused', parent: 'fn', label: 'unconnected' },
    { id: 'p_exit', label: 'exit' }
  ],
  transitions: [
    { id: 't_before', parent: 'fn', label: 'before()' }, { id: 't1', parent: 'fn', label: 'left first()' },
    { id: 't1b', parent: 'fn', label: 'left second()' }, { id: 't2', parent: 'fn', label: 'right first()' },
    { id: 't2b', parent: 'fn', label: 'right second()' }
  ],
  arcs: [
    { source: 'p_entry', target: 't_before' }, { source: 't_before', target: 'p_trigger' },
    { source: 'p_trigger', target: 't1' }, { source: 't1', target: 'p1' },
    { source: 'p1', target: 't1b' }, { source: 't1b', target: 'p_exit' },
    { source: 'p_trigger', target: 't2' }, { source: 't2', target: 'p2' },
    { source: 'p2', target: 't2b' }, { source: 't2b', target: 'p_exit' }
  ]
}"""
        batch_logic = r"""
const selectionFoldControls = { style: { display: 'none' } };
const batchFoldResult = { textContent: '' };
const btnFoldSelectedPlaces = { textContent: '' };
const DAGRE_LAYOUT_OPTIONS = { name: 'dagre' };
cy.layout = function() { return { run: function() {} }; };
function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (!value || typeof value !== 'object') return value;
  const copy = {};
  Object.keys(value).forEach(key => {
    if (key === 'consumedSubgraph' && value.consumedSubnet !== undefined) return;
    if (key === 'consumedSubgraph' && value.data && value.data.consumedSubnet !== undefined) return;
    copy[key] = canonical(value[key]);
  });
  if (copy.data && copy.data.consumedSubnet === undefined && copy.data.consumedSubgraph !== undefined) {
    copy.data.consumedSubnet = canonical(copy.data.consumedSubgraph);
    delete copy.data.consumedSubgraph;
  }
  return copy;
}
function graph() {
  return JSON.stringify(cy.elements().jsons().map(element => {
    const copy = canonical(element);
    delete copy.selected;
    return copy;
  }).sort((a, b) => a.data.id.localeCompare(b.data.id)));
}
const before = graph();
cy.getElementById('p1').select();
cy.getElementById('p2').select();
const batch = handleBatchPlaceFold();
if (!batch || batch.folded.length !== 2 || viewerActionHistory.undoStack.length !== 1) {
  throw new Error('Batch fold was not recorded as one gesture');
}
const folded = graph();
if (!viewerActionHistory.undo() || graph() !== before) {
  throw new Error('Batch Undo did not restore both original branches');
}
if (!viewerActionHistory.redo() || graph() !== folded) {
  throw new Error('Batch Redo did not restore both recorded folds');
}
"""
        batch_script = _setup_live_fold_test_harness(net_literal, batch_logic)
        batch_result = self.run_node(batch_script)
        self.assertEqual(batch_result.returncode, 0, batch_result.stderr)

        function_logic = r"""
const DAGRE_LAYOUT_OPTIONS = { name: 'dagre' };
cy.layout = function() { return { run: function() {} }; };
function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (!value || typeof value !== 'object') return value;
  const copy = {};
  Object.keys(value).forEach(key => {
    if (key === 'consumedSubgraph' && value.consumedSubnet !== undefined) return;
    if (key === 'consumedSubgraph' && value.data && value.data.consumedSubnet !== undefined) return;
    copy[key] = canonical(value[key]);
  });
  if (copy.data && copy.data.consumedSubnet === undefined && copy.data.consumedSubgraph !== undefined) {
    copy.data.consumedSubnet = canonical(copy.data.consumedSubgraph);
    delete copy.data.consumedSubgraph;
  }
  return copy;
}
function graph() {
  return JSON.stringify(cy.elements().jsons().map(element => {
    const copy = canonical(element);
    delete copy.selected;
    if (copy.data.consumedSubgraph !== undefined) delete copy.data.consumedSubgraph;
    return copy;
  }).sort((a, b) => a.data.id.localeCompare(b.data.id)));
}
const before = graph();
const result = handleFoldEntireFunction(cy.getElementById('fn'));
if (!result || !result.success || result.complete || result.folded.length < 2 || viewerActionHistory.undoStack.length !== 1) {
  throw new Error('Partial Fold Entire Function progress was not grouped as one gesture');
}
const folded = graph();
if (!viewerActionHistory.undo() || graph() !== before) {
  throw new Error('Function-fold Undo did not restore its original subnet');
}
if (!viewerActionHistory.redo() || graph() !== folded) {
  throw new Error('Function-fold Redo did not restore the recorded subnet');
}
"""
        function_script = _setup_live_fold_test_harness(net_literal, function_logic)
        function_result = self.run_node(function_script)
        self.assertEqual(function_result.returncode, 0, function_result.stderr)

    def test_production_batch_records_valid_partial_progress_as_one_action(self):
        net_literal = """{
  places: [{ id: 'p0', label: 'start' }, { id: 'p1', label: 'middle' }, { id: 'p2', label: 'end' }],
  transitions: [{ id: 't0', label: 'first' }, { id: 't1', label: 'second' }],
  arcs: [{ source: 'p0', target: 't0' }, { source: 't0', target: 'p1' },
    { source: 'p1', target: 't1' }, { source: 't1', target: 'p2' }]
}"""
        logic = r"""
const selectionFoldControls = { style: {} };
const batchFoldResult = { textContent: '' };
const btnFoldSelectedPlaces = { textContent: '' };
const DAGRE_LAYOUT_OPTIONS = { name: 'dagre' };
cy.layout = function() { return { run: function() {} }; };
function graph() {
  return JSON.stringify(cy.elements().jsons().map(element => {
    const copy = JSON.parse(JSON.stringify(element));
    delete copy.selected;
    if (copy.data.consumedSubgraph !== undefined) delete copy.data.consumedSubgraph;
    return copy;
  }).sort((a, b) => a.data.id.localeCompare(b.data.id)));
}
const before = graph();
cy.getElementById('p0').select();
cy.getElementById('p1').select();
const result = handleBatchPlaceFold();
if (!result || result.folded.length !== 1 || result.skipped.length !== 1 || viewerActionHistory.undoStack.length !== 1) {
  throw new Error('Valid partial Batch Place Fold was not recorded as one action');
}
const folded = graph();
if (!viewerActionHistory.undo() || graph() !== before) throw new Error('Undo did not roll back the whole partial batch');
if (!viewerActionHistory.redo() || graph() !== folded) throw new Error('Redo did not restore the partial batch result');
"""
        result = self.run_node(_setup_live_fold_test_harness(net_literal, logic))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_production_failed_batch_rolls_back_and_preserves_redo(self):
        net_literal = _make_sese_test_net()
        logic = r"""
const selectionFoldControls = { style: {} };
const batchFoldResult = { textContent: '' };
const btnFoldSelectedPlaces = { textContent: '' };
const DAGRE_LAYOUT_OPTIONS = { name: 'dagre' };
cy.layout = function() { return { run: function() {} }; };
function graph() {
  return JSON.stringify(cy.elements().jsons().map(element => {
    const copy = JSON.parse(JSON.stringify(element));
    delete copy.selected;
    return copy;
  }).sort((a, b) => a.data.id.localeCompare(b.data.id)));
}
if (!handleFoldReduction(cy.getElementById('p1'), null) || !viewerActionHistory.undo()) {
  throw new Error('Redo setup action failed');
}
const before = graph();
cy.getElementById('p1').select();
cy.getElementById('p_src').select();
foldEngine.executeBatchFold = function() {
  cy.getElementById('p1').data('label', 'partial mutation before failure');
  foldEngine.stepCounter += 1;
  return { success: false, folded: [], skipped: [{ placeId: 'p1', reason: 'injected failure' }], message: 'No progress.' };
};
const result = handleBatchPlaceFold();
if (!result || result.success || graph() !== before || foldEngine.stepCounter !== 0) {
  throw new Error('Production batch failure did not restore graph and editing context');
}
if (!viewerActionHistory.canRedo || viewerActionHistory.canUndo) {
  throw new Error('Failed production batch cleared or advanced Redo');
}
"""
        result = self.run_node(_setup_live_fold_test_harness(net_literal, logic))
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_production_function_call_expansion_and_collapse_are_undoable(self):
        net_literal = """{
  places: [{ id: 'p_in', label: 'in' }, { id: 'p_out', label: 'out' }],
  transitions: [{ id: 't_call', label: 'helper()' }],
  arcs: [{ source: 'p_in', target: 't_call' }, { source: 't_call', target: 'p_out' }]
}"""
        logic = r"""
const call = cy.getElementById('t_call');
call.data('resolved', true);
call.data('resolved_to', 'helper');
call.data('raw_label', 'helper()');
calleeNetsMap.helper = {
  places: [{ id: 'helper_start', label: 'start' }, { id: 'helper_end', label: 'end' }],
  transitions: [{ id: 'helper_inner', label: 'work()' }],
  arcs: [{ source: 'helper_start', target: 'helper_inner' }, { source: 'helper_inner', target: 'helper_end' }]
};
call.emit('tap');
if (!expandedNodes.has('t_call') || viewerActionHistory.undoStack.length !== 1) {
  throw new Error('Production resolved-call tap did not record expansion');
}
call.emit('tap');
if (expandedNodes.has('t_call') || viewerActionHistory.undoStack.length !== 2) {
  throw new Error('Production expanded-call tap did not record collapse');
}
if (!viewerActionHistory.undo() || !expandedNodes.has('t_call')) {
  throw new Error('Undo did not restore the expanded function-call state');
}
if (!viewerActionHistory.redo() || expandedNodes.has('t_call')) {
  throw new Error('Redo did not restore the collapsed function-call state');
}
if (!viewerActionHistory.undo() || !viewerActionHistory.undo() || expandedNodes.has('t_call')) {
  throw new Error('Undo did not restore the original unexpanded call');
}
"""
        script = _setup_live_fold_test_harness(net_literal, logic)
        result = self.run_node(script)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_production_playback_fold_unfold_and_reset_are_undoable(self):
        from tests.test_html_viewer import _read_template_html

        html = _read_template_html()

        def extract(pattern):
            match = re.search(pattern, html, re.DOTALL)
            if not match:
                raise AssertionError("Could not extract production playback control")
            return match.group(0)

        update_ui = extract(r"function updateUI\(\) \{.*?\n      \}")
        render_step = extract(r"function renderStep\(stepIndex, animate\) \{.*?\n      \}")
        controls = extract(r"if \(btnFold\) \{.*?(?=\n\n      function getSelectedPlaceIds\()")
        net_literal = """{
  places: [{ id: 'p0', label: 'start' }, { id: 'p1', label: 'end' }],
  transitions: [{ id: 't0', label: 'first()' }],
  arcs: [{ source: 'p0', target: 't0' }, { source: 't0', target: 'p1' }]
}"""
        logic = f"""
const isFoldMode = true;
const totalSteps = 2;
const foldSteps = [
  {{ component_type: 'Sequence', opaque_transition: 'c_01', sm_score: 1.0, omega: 0, tau: 2 }},
  {{ component_type: 'Choice', opaque_transition: 'c_02', sm_score: 0.5, omega: 1, tau: 3 }}
];
const stepNets = [net,
  {{ places: [{{ id: 'p0', label: 'start' }}, {{ id: 'p1', label: 'end' }}], transitions: [{{ id: 'c_01', label: 'first()' }}], arcs: [{{ source: 'p0', target: 'c_01' }}, {{ source: 'c_01', target: 'p1' }}] }},
  {{ places: [{{ id: 'p0', label: 'start' }}, {{ id: 'p1', label: 'end' }}], transitions: [{{ id: 'c_02', label: 'first()' }}], arcs: [{{ source: 'p0', target: 'c_02' }}, {{ source: 'c_02', target: 'p1' }}] }}
];
const valStep = {{ textContent: '' }};
const btnFold = {{ listener: null, disabled: false, addEventListener: function(name, listener) {{ this.listener = listener; }} }};
const btnUnfold = {{ listener: null, disabled: false, addEventListener: function(name, listener) {{ this.listener = listener; }} }};
const btnReset = {{ listener: null, disabled: false, addEventListener: function(name, listener) {{ this.listener = listener; }} }};
const initialSm = 2.0;
const infoTitle = {{ textContent: '' }}, infoDesc = {{ textContent: '' }};
function applyLayout() {{}}
{update_ui}
{render_step}
{controls}
function graph() {{
  return JSON.stringify(cy.elements().jsons().map(element => {{
    const copy = JSON.parse(JSON.stringify(element));
    delete copy.selected;
    return copy;
  }}).sort((a, b) => a.data.id.localeCompare(b.data.id)));
}}
cy.zoom(1.6);
cy.pan({{ x: 41, y: -12 }});
const initial = graph();
btnFold.listener();
if (currentStep !== 1 || !viewerActionHistory.canUndo || btnUnfold.disabled || btnReset.disabled) throw new Error('Fold playback control did not advance one step');
const stepOne = graph();
if (stepOne === initial) throw new Error('Fold playback did not change the graph');
if (!viewerActionHistory.undo() || currentStep !== 0 || graph() !== initial || btnUnfold.disabled !== true) throw new Error('Undo did not restore the initial playback step');
if (cy.zoom() !== 1.6 || cy.pan().x !== 41 || cy.pan().y !== -12) throw new Error('Playback Undo changed the camera');
if (!viewerActionHistory.redo() || currentStep !== 1 || graph() !== stepOne) throw new Error('Redo did not restore the exact playback fold');
btnFold.listener();
const stepTwo = graph();
btnReset.listener();
if (currentStep !== 0 || graph() !== initial) throw new Error('Reset did not restore the initial graph');
if (!viewerActionHistory.undo() || currentStep !== 2 || graph() !== stepTwo) throw new Error('Undo did not restore the pre-reset playback state');
btnUnfold.listener();
if (currentStep !== 1 || graph() !== stepOne) throw new Error('Unfold playback control did not move back one step');
if (!viewerActionHistory.undo() || currentStep !== 2 || graph() !== stepTwo) throw new Error('Undo did not restore the unfolded playback step');
"""
        script = _setup_live_fold_test_harness(net_literal, logic)
        script = script.replace(
            "afterRestore: () => updateFoldableHighlights()",
            "afterRestore: () => { updateFoldableHighlights(); updateUI(); }"
        )
        result = self.run_node(script)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_production_compound_drag_groups_all_moved_descendants(self):
        from tests.test_html_viewer import _read_template_html

        html = _read_template_html()
        match = re.search(r"let moveGesture = null;.*?(?=\n\n      function handleBatchPlaceFold\()", html, re.DOTALL)
        self.assertIsNotNone(match)
        net_literal = """{
  compounds: [{ id: 'fn', label: 'function()' }],
  places: [{ id: 'p1', parent: 'fn' }, { id: 'p2', parent: 'fn' }],
  transitions: [], arcs: []
}"""
        logic = f"""
let isPanningDrag = false;
{match.group(0)}
function graph() {{
  return JSON.stringify(cy.elements().jsons().map(element => {{
    const copy = JSON.parse(JSON.stringify(element));
    delete copy.selected;
    return copy;
  }}).sort((a, b) => a.data.id.localeCompare(b.data.id)));
}}
const parent = cy.getElementById('fn');
const left = cy.getElementById('p1');
const right = cy.getElementById('p2');
const original = graph();
parent.emit('grab');
parent.emit('free');
Promise.resolve().then(() => new Promise(resolve => setTimeout(resolve, 5))).then(() => {{
  if (viewerActionHistory.undoStack.length !== 0) throw new Error('Unchanged drag created a history entry');
  parent.emit('grab');
  left.position({{ x: 32, y: 18 }});
  right.position({{ x: 72, y: 18 }});
  parent.emit('free');
  return new Promise(resolve => setTimeout(resolve, 5));
}}).then(() => {{
  const moved = graph();
  if (moved === original || viewerActionHistory.undoStack.length !== 1) throw new Error('Compound drag was split or not recorded');
  if (!viewerActionHistory.undo() || graph() !== original) throw new Error('Undo did not restore all moved descendants');
  if (!viewerActionHistory.redo() || graph() !== moved) throw new Error('Redo did not restore the complete compound move');
}}).catch(error => {{
  console.error(error && error.stack ? error.stack : error);
  process.exitCode = 1;
}});
"""
        script = _setup_live_fold_test_harness(net_literal, logic)
        result = self.run_node(script)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_noops_failures_and_branching_preserve_history_semantics(self):
        script = r"""
const cytoscape = require('./code2petri/viewer/vendor/cytoscape.min.js');
const { ViewerActionHistory } = require('./code2petri/viewer/engine/action_history.js');
const cy = cytoscape({ headless: true, elements: [{ data: { id: 'n', label: 'start' } }] });
let context = { count: 0 };
let failRestore = false;
const history = new ViewerActionHistory({
  cy,
  captureContext: () => context,
  restoreContext: next => {
    if (failRestore && next.count === 0) { failRestore = false; throw new Error('injected restore error'); }
    context = next;
  }
});
history.perform('first', () => { context.count = 1; cy.getElementById('n').data('label', 'one'); return true; });
if (!history.undo() || !history.canRedo) throw new Error('setup undo failed');
history.perform('unchanged', () => false);
if (!history.canRedo) throw new Error('unchanged action cleared Redo');
const oldGraph = JSON.stringify(cy.elements().jsons());
const rejected = history.perform('rejected mutation', () => {
  context.count = 9;
  cy.getElementById('n').data('label', 'bad');
  return false;
});
if (rejected !== false) throw new Error('rejected action result was not preserved');
if (context.count !== 0 || JSON.stringify(cy.elements().jsons()) !== oldGraph || !history.canRedo) {
  throw new Error('failed action did not roll back while preserving Redo');
}
history.perform('second branch', () => { context.count = 2; cy.getElementById('n').data('label', 'two'); return true; });
if (history.canRedo) throw new Error('successful new edit did not clear Redo');
const afterBranch = JSON.stringify(cy.elements().jsons());
failRestore = true;
let sawError = false;
try { history.undo(); } catch (error) { sawError = /injected restore error/.test(error.message); }
if (!sawError || !history.canUndo || history.canRedo || context.count !== 2 || JSON.stringify(cy.elements().jsons()) !== afterBranch) {
  throw new Error('failed Undo did not restore graph and keep the history cursor unchanged');
}
"""
        result = self.run_node(script)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_history_retention_evicts_oldest_and_keeps_an_oversized_newest_action(self):
        script = r"""
const cytoscape = require('./code2petri/viewer/vendor/cytoscape.min.js');
const { ViewerActionHistory } = require('./code2petri/viewer/engine/action_history.js');
const cy = cytoscape({ headless: true, elements: [{ data: { id: 'n', value: 0 } }] });
const history = new ViewerActionHistory({ cy, maxActions: 2, maxBytes: 1 });
for (let value = 1; value <= 3; value++) {
  history.perform('set value', () => { cy.getElementById('n').data('value', value); return true; });
}
if (history.undoStack.length + history.redoStack.length !== 1 || history.bytes <= 1) {
  throw new Error('byte eviction did not retain exactly the oversized newest gesture');
}
if (!history.undo() || cy.getElementById('n').data('value') !== 2 || history.canUndo) {
  throw new Error('oldest retained history path was not evicted');
}
"""
        result = self.run_node(script)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_retention_compacts_earliest_redo_without_breaking_the_remaining_path(self):
        script = r"""
const cytoscape = require('./code2petri/viewer/vendor/cytoscape.min.js');
const { ViewerActionHistory } = require('./code2petri/viewer/engine/action_history.js');
const cy = cytoscape({ headless: true, elements: [{ data: { id: 'n', value: 0 } }] });
let context = { value: 0 };
const history = new ViewerActionHistory({
  cy,
  maxActions: 4,
  captureContext: () => context,
  restoreContext: next => { context = next; }
});
for (let value = 1; value <= 4; value++) {
  history.perform('set value ' + value, () => {
    cy.getElementById('n').data('value', value);
    context = { value };
    return true;
  });
}
if (!history.undo() || !history.undo() || !history.undo()) throw new Error('undo mix setup failed');
if (cy.getElementById('n').data('value') !== 1 || history.redoStack.length !== 3) {
  throw new Error('mixed history was not positioned after the first gesture');
}
history.maxActions = 2;
if (!history.undo()) throw new Error('oldest gesture undo failed');
if (cy.getElementById('n').data('value') !== 0 || history.undoStack.length !== 0 ||
    history.undoStack.length + history.redoStack.length !== 2) {
  throw new Error('retention did not trim the over-limit mixed history');
}
if (!history.redo() || cy.getElementById('n').data('value') !== 3 || context.value !== 3) {
  throw new Error('earliest retained Redo did not replay its compacted contiguous path');
}
if (!history.undo() || cy.getElementById('n').data('value') !== 0 || context.value !== 0) {
  throw new Error('Undo of the compacted Redo path did not return to its reachable base');
}
if (!history.redo() || !history.redo() || cy.getElementById('n').data('value') !== 4 || context.value !== 4) {
  throw new Error('remaining Redo entries were not replayable after compaction');
}
"""
        result = self.run_node(script)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_generated_viewer_has_toolbar_and_native_editing_shortcut_guards(self):
        net = PetriNet()
        net.add_place('p0', 'start', initial_tokens=1)
        net.add_transition('t0', 'work()')
        net.add_place('p1', 'end')
        nodes = net.get_node_map()
        net.add_arc(nodes['p0'], nodes['t0'])
        net.add_arc(nodes['t0'], nodes['p1'])
        html = generate_html(net, title='History Controls')
        self.assertIn('id="btn-undo"', html)
        self.assertIn('id="btn-redo"', html)
        self.assertIn('event.isComposing || event.keyCode === 229', html)
        self.assertIn('target.isContentEditable === true', html)
        self.assertIn("if (viewerActionHistory) viewerActionHistory.clear();", html)
        self.assertIn('class ViewerActionHistory', html)

    def test_session_serialization_excludes_action_history_stacks(self):
        script = r"""
const cytoscape = require('./code2petri/viewer/vendor/cytoscape.min.js');
const { serializeFoldStateSnapshot } = require('./code2petri/viewer/engine/session_snapshot.js');
const { ViewerActionHistory } = require('./code2petri/viewer/engine/action_history.js');
const cy = cytoscape({ headless: true, elements: [{ data: { id: 'n', label: 'start' } }] });
const engine = { stepCounter: 0, cfg: {}, rememberedCustomNames: new Map() };
const history = new ViewerActionHistory({ cy });
history.perform('rename', () => { cy.getElementById('n').data('label', 'edited'); return true; });
const snapshot = serializeFoldStateSnapshot({
  cy, engine,
  document: { title: 'Session', originalNet: { places: [], transitions: [], arcs: [] }, foldSteps: [], calleeNets: {}, expandedNodes: [], playback: { currentStep: 0, totalSteps: 0 } }
});
if (history.canUndo !== true) throw new Error('history setup failed');
if (Object.prototype.hasOwnProperty.call(snapshot, 'history') || Object.prototype.hasOwnProperty.call(snapshot.engine, 'history') ||
    Object.prototype.hasOwnProperty.call(snapshot.document, 'history')) {
  throw new Error('session serialization retained viewer action history');
}
"""
        result = self.run_node(script)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
