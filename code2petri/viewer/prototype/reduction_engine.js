/**
 * Phase 2.7 Live Fold Reduction Engine (Prototype Facade)
 * Re-exports the canonical implementation from code2petri/viewer/engine/reduction_engine.js
 */

const engine = typeof require !== 'undefined'
  ? require('../engine/reduction_engine.js')
  : (typeof window !== 'undefined' ? window : {});

if (typeof module !== 'undefined' && module.exports) {
  module.exports = engine;
} else if (typeof window !== 'undefined') {
  Object.assign(window, engine);
}
