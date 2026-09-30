/**
 * Client-Side PNML Exporter (Prototype Facade)
 * Re-exports the canonical implementation from code2petri/viewer/engine/pnml_exporter.js
 */

const exporter = typeof require !== 'undefined'
  ? require('../engine/pnml_exporter.js')
  : (typeof window !== 'undefined' ? window : {});

if (typeof module !== 'undefined' && module.exports) {
  module.exports = exporter;
} else if (typeof window !== 'undefined') {
  Object.assign(window, exporter);
}
