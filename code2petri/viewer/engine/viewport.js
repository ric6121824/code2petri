/**
 * Viewport Management Module for code2petri Cytoscape Viewer.
 * Preserves camera zoom, pan, and screen-anchor positions during fold and unfold operations.
 */

(function(root, factory) {
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = factory();
  } else {
    const exports = factory();
    if (typeof window !== 'undefined') {
      Object.assign(window, exports);
    } else if (typeof globalThis !== 'undefined') {
      Object.assign(globalThis, exports);
    }
  }
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this), function() {
  /**
   * Captures the current camera zoom level and pan coordinates from a Cytoscape instance.
   * @param {cytoscape.Core} cy
   * @returns {{ zoom: number, pan: { x: number, y: number } }}
   */
  function _captureViewport(cy) {
    if (!cy) return { zoom: 1, pan: { x: 0, y: 0 } };
    const zoom = typeof cy.zoom === 'function' ? cy.zoom() : 1;
    const pan = (typeof cy.pan === 'function' && cy.pan()) ? Object.assign({}, cy.pan()) : { x: 0, y: 0 };
    return { zoom: zoom, pan: pan };
  }

  /**
   * Computes the new pan coordinates required to anchor the replacement component node
   * at the exact same screen position as the pre-fold place node.
   *
   * In Cytoscape, screen position is: screen = model * zoom + pan.
   * Preserving screen position means:
   * preFoldPos * zoom + currentPan = postFoldPos * zoom + targetPan
   * => targetPan = currentPan + (preFoldPos - postFoldPos) * zoom
   *
   * @param {{ x: number, y: number }} currentPan
   * @param {{ x: number, y: number }} preFoldPlacePos
   * @param {{ x: number, y: number }} postFoldCompPos
   * @param {number} zoom
   * @returns {{ x: number, y: number }}
   */
  function _computeAnchoredPan(currentPan, preFoldPlacePos, postFoldCompPos, zoom) {
    if (!currentPan) return { x: 0, y: 0 };
    if (!preFoldPlacePos || !postFoldCompPos) return Object.assign({}, currentPan);
    return {
      x: currentPan.x + (preFoldPlacePos.x - postFoldCompPos.x) * zoom,
      y: currentPan.y + (preFoldPlacePos.y - postFoldCompPos.y) * zoom
    };
  }

  /**
   * Restores viewport zoom and pan onto a Cytoscape instance without resetting the camera fit.
   * @param {cytoscape.Core} cy
   * @param {number} zoom
   * @param {{ x: number, y: number }} pan
   */
  function _restoreViewport(cy, zoom, pan) {
    if (!cy) return;
    if (typeof cy.viewport === 'function') {
      cy.viewport({ zoom: zoom, pan: pan });
    } else {
      if (typeof cy.zoom === 'function') cy.zoom(zoom);
      if (typeof cy.pan === 'function') cy.pan(pan);
    }
  }

  const viewportExports = {
    _captureViewport,
    _computeAnchoredPan,
    _restoreViewport,
    captureViewport: _captureViewport,
    computeAnchoredPan: _computeAnchoredPan,
    restoreViewport: _restoreViewport
  };

  const globalScope = typeof globalThis !== 'undefined' ? globalThis : (typeof window !== 'undefined' ? window : (typeof global !== 'undefined' ? global : null));
  if (globalScope && globalScope.LiveFoldReductionEngine) {
    globalScope.LiveFoldReductionEngine.viewport = {
      capture: _captureViewport,
      computeAnchoredPan: _computeAnchoredPan,
      restore: _restoreViewport
    };
  }

  return viewportExports;
});
