// Diagnostic replay derived from the reported Aeroblasters post-fold remainders.
// No source, generated viewer, or user session is modified.
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const repo = path.resolve(__dirname, '../../../..');
const cytoscape = require(path.join(repo, 'code2petri/viewer/vendor/cytoscape.min.js'));
const { LiveFoldReductionEngine } = require(path.join(repo, 'code2petri/viewer/engine/reduction_engine.js'));
const template = fs.readFileSync(path.join(repo, 'code2petri/viewer/template.html'), 'utf8');
const start = template.indexOf('function updateFoldableHighlights()');
const suffix = template.slice(start);
const end = /\n      \}/.exec(suffix);
if (start < 0 || !end) throw new Error('Cannot locate the actual highlight function');
const highlightCode = suffix.slice(0, end.index + end[0].length);

function elements(branchSide) {
  const node = (id, classes, parent, opaque) => ({
    group: 'nodes', classes,
    data: { id, ...(parent ? { parent } : {}), ...(opaque ? { is_opaque: true } : {}) }
  });
  const arcs = branchSide === 'exit'
    ? [['entry', 'linear'], ['linear', 'middle'], ['middle', 'branch_a'],
       ['middle', 'branch_b'], ['branch_a', 'exit'], ['branch_b', 'exit']]
    : [['entry', 'branch_a'], ['entry', 'branch_b'], ['branch_a', 'middle'],
       ['branch_b', 'middle'], ['middle', 'linear'], ['linear', 'exit']];
  const compound = node('function', 'compound');
  compound.data.is_compound = true;
  compound.data.function_name = branchSide === 'exit' ? 'BlinkingText.update' : 'Message.update';
  return [compound, node('entry', 'place'), node('exit', 'place'),
    node('middle', 'place', 'function'), node('linear', 'transition', 'function', true),
    node('branch_a', 'transition', 'function', true), node('branch_b', 'transition', 'function'),
    ...arcs.map(([source, target], i) => ({
      group: 'edges', classes: 'arc', data: { id: 'arc_' + i, source, target }
    }))];
}

let failures = 0;
for (const branchSide of ['exit', 'entrance']) {
  const cy = cytoscape({ elements: elements(branchSide), headless: true });
  const foldEngine = new LiveFoldReductionEngine(cy);
  const context = { cy, foldEngine, LiveFoldReductionEngine };
  vm.createContext(context);
  vm.runInContext(highlightCode + '\nupdateFoldableHighlights();', context);
  const middle = cy.getElementById('middle');
  const before = {
    internalFoldType: foldEngine.getFoldType(middle),
    internalGreen: middle.hasClass('contractible')
  };
  const result = foldEngine.executeFoldEntireFunction('function');
  const collapsed = cy.getElementById('function').hasClass('collapsed-compound');
  const callerBoundariesSurvive = ['entry', 'exit'].every(id => cy.getElementById(id).length === 1);
  const pass = before.internalGreen && result.complete && collapsed && callerBoundariesSurvive;
  console.log(JSON.stringify({ branchSide, before, complete: result.complete, collapsed, callerBoundariesSurvive, pass }));
  if (!pass) failures++;
  cy.destroy();
}
console.log(JSON.stringify({ failures, cases: 2 }));
process.exitCode = failures ? 1 : 0;
