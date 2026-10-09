/**
 * Fold State Snapshot serialization for the self-contained code2petri viewer.
 */

(function(root, factory) {
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = factory(require('./viewport.js'));
  } else {
    const exports = factory(root);
    if (typeof window !== 'undefined') {
      Object.assign(window, exports);
    } else if (typeof globalThis !== 'undefined') {
      Object.assign(globalThis, exports);
    }
  }
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this), function(viewportModule) {
  const SCHEMA_VERSION = 1;
  const SNAPSHOT_TYPE = 'code2petri-fold-state';

  function _cloneJson(value) {
    if (value === undefined) return null;
    return JSON.parse(JSON.stringify(value));
  }

  function _rememberedCustomNameEntries(engine) {
    if (!engine || !(engine.rememberedCustomNames instanceof Map)) return [];
    return Array.from(engine.rememberedCustomNames.entries()).map(function(entry) {
      return [String(entry[0]), entry[1]];
    });
  }

  /**
   * Captures a versioned Fold State Snapshot without changing graph or UI state.
   *
   * @param {{cy: Object, engine: Object, document: Object}} options
   * @returns {Object}
   */
  function serializeFoldStateSnapshot(options) {
    const opts = options || {};
    const cy = opts.cy;
    const engine = opts.engine;
    if (!cy || !cy.elements || !engine) {
      throw new Error('A Cytoscape graph and Live Fold Reduction engine are required');
    }

    const capture = viewportModule && viewportModule.captureViewport;
    const viewport = typeof capture === 'function'
      ? capture(cy)
      : {
          zoom: typeof cy.zoom === 'function' ? cy.zoom() : 1,
          pan: typeof cy.pan === 'function' ? Object.assign({}, cy.pan()) : { x: 0, y: 0 }
        };

    return {
      schemaVersion: SCHEMA_VERSION,
      snapshotType: SNAPSHOT_TYPE,
      elements: _cloneJson(cy.elements().jsons()),
      engine: {
        stepCounter: Number(engine.stepCounter) || 0,
        cfg: _cloneJson(engine.cfg || {}),
        rememberedCustomNames: _cloneJson(_rememberedCustomNameEntries(engine))
      },
      viewport: _cloneJson(viewport),
      document: _cloneJson(opts.document || {})
    };
  }

  function getFoldStateSnapshotFilename(netTitle) {
    const raw = String(netTitle || '').trim();
    const safeTitle = raw
      .replace(/[<>:"/\\|?*\u0000-\u001f]/g, '_')
      .replace(/[. ]+$/g, '');
    return (safeTitle || 'petri_net') + '_session.json';
  }

  function _downloadBlob(blob, filename) {
    if (typeof document === 'undefined' || typeof URL === 'undefined' || typeof URL.createObjectURL !== 'function') return;
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = filename;
    if (document.body && typeof document.body.appendChild === 'function') {
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
    } else if (typeof anchor.click === 'function') {
      anchor.click();
    }
    if (typeof URL.revokeObjectURL === 'function') {
      setTimeout(function() { URL.revokeObjectURL(url); }, 100);
    }
  }

  /**
   * Serializes and downloads the active viewer as JSON session data.
   * Returns the serialized result so generated-viewer tests can inspect it.
   */
  function downloadFoldStateSnapshot(options) {
    const opts = options || {};
    const snapshot = serializeFoldStateSnapshot(opts);
    const json = JSON.stringify(snapshot, null, 2);
    const title = opts.document && opts.document.title;
    const filename = opts.filename || getFoldStateSnapshotFilename(title);
    const blob = new Blob([json], { type: 'application/json;charset=utf-8' });
    const downloadBlob = opts.downloadBlob || _downloadBlob;
    downloadBlob(blob, filename);
    return { snapshot: snapshot, json: json, filename: filename };
  }

  return {
    FOLD_STATE_SNAPSHOT_SCHEMA_VERSION: SCHEMA_VERSION,
    FOLD_STATE_SNAPSHOT_TYPE: SNAPSHOT_TYPE,
    serializeFoldStateSnapshot,
    getFoldStateSnapshotFilename,
    downloadFoldStateSnapshot
  };
});
