/**
 * Session-local chronological history for committed viewer gestures.
 * Graph entries contain only changed Cytoscape records and detached editing context.
 */
(function(root, factory) {
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = factory(require('./viewer_transient_classes.js'));
  } else if (root) {
    Object.assign(root, factory(root));
  }
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this), function(viewerClassUtils) {
  const DEFAULT_MAX_ACTIONS = 50;
  const DEFAULT_MAX_BYTES = 32 * 1024 * 1024;
  const stripTransientSearchClasses = viewerClassUtils.stripTransientSearchClasses;

  function cloneJson(value) {
    if (value === undefined) return undefined;
    return JSON.parse(JSON.stringify(value));
  }

  function normalizeRestorationAliases(value) {
    if (!value || typeof value !== 'object') return;
    if (Array.isArray(value)) {
      value.forEach(normalizeRestorationAliases);
      return;
    }
    if (value.data && typeof value.data === 'object' && !Array.isArray(value.data)) {
      if (value.data.consumedSubnet === undefined && value.data.consumedSubgraph !== undefined) {
        value.data.consumedSubnet = value.data.consumedSubgraph;
      }
      delete value.data.consumedSubgraph;
    }
    Object.keys(value).forEach(function(key) { normalizeRestorationAliases(value[key]); });
  }

  function canonicalElement(element) {
    const copy = cloneJson(element);
    normalizeRestorationAliases(copy);
    if (copy && Object.prototype.hasOwnProperty.call(copy, 'selected')) delete copy.selected;
    if (copy && copy.group === 'nodes' && typeof copy.classes === 'string') {
      copy.classes = stripTransientSearchClasses(copy.classes);
    }
    return copy;
  }

  function stableString(value) {
    return JSON.stringify(value);
  }

  function sortedElements(cy) {
    return cy.elements().jsons().map(canonicalElement).sort(function(a, b) {
      return String(a.data.id).localeCompare(String(b.data.id));
    });
  }

  function elementMap(elements) {
    const result = new Map();
    elements.forEach(function(element) { result.set(element.data.id, element); });
    return result;
  }

  function parentDepth(elementById, element, visiting) {
    const parentId = element.data && element.data.parent;
    if (!parentId || !elementById.has(parentId)) return 0;
    if (visiting.has(element.data.id)) throw new Error('Cannot restore a cyclic compound hierarchy');
    visiting.add(element.data.id);
    const depth = parentDepth(elementById, elementById.get(parentId), visiting) + 1;
    visiting.delete(element.data.id);
    return depth;
  }

  class ViewerActionHistory {
    constructor(options) {
      const opts = options || {};
      if (!opts.cy || typeof opts.cy.elements !== 'function') {
        throw new Error('Viewer Action History requires a Cytoscape instance');
      }
      this.cy = opts.cy;
      this.captureContext = typeof opts.captureContext === 'function' ? opts.captureContext : function() { return {}; };
      this.restoreContext = typeof opts.restoreContext === 'function' ? opts.restoreContext : function() {};
      this.captureUi = typeof opts.captureUi === 'function' ? opts.captureUi : function() { return null; };
      this.restoreUi = typeof opts.restoreUi === 'function' ? opts.restoreUi : function() {};
      this.afterRestore = typeof opts.afterRestore === 'function' ? opts.afterRestore : function() {};
      this.onChange = typeof opts.onChange === 'function' ? opts.onChange : function() {};
      this.maxActions = Number.isInteger(opts.maxActions) && opts.maxActions > 0 ? opts.maxActions : DEFAULT_MAX_ACTIONS;
      this.maxBytes = Number.isFinite(opts.maxBytes) && opts.maxBytes > 0 ? opts.maxBytes : DEFAULT_MAX_BYTES;
      this.undoStack = [];
      this.redoStack = [];
      this.nextSequence = 1;
      this.bytes = 0;
    }

    get canUndo() { return this.undoStack.length > 0; }
    get canRedo() { return this.redoStack.length > 0; }

    captureContextState() {
      return cloneJson(this.captureContext());
    }

    _capture() {
      return { elements: sortedElements(this.cy), context: this.captureContextState() };
    }

    _captureViewport() {
      return {
        zoom: typeof this.cy.zoom === 'function' ? this.cy.zoom() : null,
        pan: typeof this.cy.pan === 'function' ? cloneJson(this.cy.pan()) : null
      };
    }

    _restoreViewport(viewport) {
      if (!viewport || viewport.zoom === null || !viewport.pan ||
          typeof this.cy.viewport !== 'function') return;
      this.cy.viewport({ zoom: viewport.zoom, pan: viewport.pan });
    }

    _selectedIds() {
      if (typeof this.cy.nodes !== 'function') return [];
      return this.cy.nodes(':selected').map(function(node) { return node.id(); });
    }

    _rebuild(elements, selectedIds) {
      const elementById = elementMap(elements);
      const nodes = elements.filter(function(element) { return element.group === 'nodes'; });
      const edges = elements.filter(function(element) { return element.group === 'edges'; });
      nodes.sort(function(a, b) {
        return parentDepth(elementById, a, new Set()) - parentDepth(elementById, b, new Set()) ||
          String(a.data.id).localeCompare(String(b.data.id));
      });
      this.cy.startBatch();
      try {
        this.cy.elements().remove();
        // Cytoscape may retain nested references from element definitions. The
        // reducer mutates live compounds inside retained consumedSubnet data,
        // so rebuilds must never share objects with detached history entries.
        const addedNodes = this.cy.add(nodes.map(canonicalElement));
        if (addedNodes.length !== nodes.length) throw new Error('Cytoscape did not restore all graph nodes');
        const addedEdges = this.cy.add(edges.map(canonicalElement));
        if (addedEdges.length !== edges.length) throw new Error('Cytoscape did not restore all graph edges');
        const actual = this.cy.elements().jsons().map(canonicalElement);
        if (actual.length !== elements.length) throw new Error('Graph restoration produced a different element count');
        const actualById = elementMap(actual);
        elements.forEach(function(expected) {
          const found = actualById.get(expected.data.id);
          if (!found || stableString(found) !== stableString(expected)) {
            throw new Error('Graph restoration did not exactly restore element ' + expected.data.id);
          }
        });
        const nodesById = new Set(this.cy.nodes().map(function(node) { return node.id(); }));
        selectedIds.forEach((id) => {
          if (nodesById.has(id)) this.cy.getElementById(id).select();
        });
      } finally {
        this.cy.endBatch();
      }
    }

    _makeEntry(label, before, after) {
      const beforeById = elementMap(before.elements);
      const afterById = elementMap(after.elements);
      const ids = new Set([...beforeById.keys(), ...afterById.keys()]);
      const changes = [];
      ids.forEach(function(id) {
        const oldValue = beforeById.get(id);
        const newValue = afterById.get(id);
        if (stableString(oldValue) !== stableString(newValue)) {
          changes.push({ id: id, before: oldValue || null, after: newValue || null });
        }
      });
      changes.sort(function(a, b) { return String(a.id).localeCompare(String(b.id)); });
      const record = {
        label: String(label || 'Edit'),
        changes: changes,
        contextBefore: before.context,
        contextAfter: after.context
      };
      return this._entryWithBytes(this.nextSequence++, record);
    }

    _entryWithBytes(sequence, record) {
      const json = stableString(record);
      let bytes = json.length * 2;
      if (typeof TextEncoder === 'function') bytes = new TextEncoder().encode(json).length;
      else if (typeof Buffer !== 'undefined') bytes = Buffer.byteLength(json, 'utf8');
      return { sequence: sequence, record: record, bytes: bytes };
    }

    _mergeEntries(older, later) {
      if (stableString(older.record.contextAfter) !== stableString(later.record.contextBefore)) {
        throw new Error('Cannot compact non-contiguous viewer history entries');
      }
      const changesById = new Map();
      older.record.changes.forEach(function(change) {
        changesById.set(change.id, { id: change.id, before: change.before, after: change.after });
      });
      later.record.changes.forEach(function(change) {
        const combined = changesById.get(change.id);
        if (combined) {
          if (stableString(combined.after) !== stableString(change.before)) {
            throw new Error('Cannot compact viewer history with a mismatched graph path');
          }
          combined.after = change.after;
          if (stableString(combined.before) === stableString(combined.after)) changesById.delete(change.id);
        } else if (stableString(change.before) !== stableString(change.after)) {
          changesById.set(change.id, { id: change.id, before: change.before, after: change.after });
        }
      });
      const changes = Array.from(changesById.values()).sort(function(a, b) {
        return String(a.id).localeCompare(String(b.id));
      });
      return this._entryWithBytes(later.sequence, {
        label: later.record.label,
        changes: changes,
        contextBefore: older.record.contextBefore,
        contextAfter: later.record.contextAfter
      });
    }

    _applyEntry(entry, direction, ui, viewport) {
      const stateBefore = this._capture();
      const selectedBefore = this._selectedIds();
      const currentViewport = viewport || this._captureViewport();
      const targetContext = direction === 'undo' ? entry.record.contextBefore : entry.record.contextAfter;
      const targetElements = elementMap(stateBefore.elements);
      entry.record.changes.forEach(function(change) {
        targetElements.delete(change.id);
        const target = direction === 'undo' ? change.before : change.after;
        if (target) targetElements.set(change.id, target);
      });
      const targetState = {
        elements: Array.from(targetElements.values()).sort(function(a, b) {
          return String(a.data.id).localeCompare(String(b.data.id));
        }),
        context: targetContext
      };
      try {
        this._rebuild(targetState.elements, selectedBefore);
        this.restoreContext(cloneJson(targetContext));
        this.restoreUi(ui);
        this.afterRestore();
        this._restoreViewport(currentViewport);
      } catch (error) {
        try {
          this._rebuild(stateBefore.elements, selectedBefore);
          this.restoreContext(cloneJson(stateBefore.context));
          this.restoreUi(ui);
          this.afterRestore();
          this._restoreViewport(currentViewport);
        } catch (_) {
          // Preserve the original restoration failure; the best-effort rollback was attempted.
        }
        throw error;
      }
    }

    _changed(before, after) {
      return stableString(before.elements) !== stableString(after.elements) ||
        stableString(before.context) !== stableString(after.context);
    }

    _restoreFailedAction(before, ui, viewport) {
      this._rebuild(before.elements, ui && Array.isArray(ui.selectionIds) ? ui.selectionIds : []);
      this.restoreContext(cloneJson(before.context));
      this.restoreUi(ui);
      this.afterRestore();
      this._restoreViewport(viewport);
    }

    perform(label, operation, shouldCommit) {
      if (typeof operation !== 'function') throw new Error('Viewer history action must be a function');
      const gesture = this.beginGesture(label);
      let result;
      try {
        result = operation();
      } catch (error) {
        try { this.cancelGesture(gesture); } catch (_) { /* Keep action error. */ }
        throw error;
      }
      this.commitGesture(gesture, result, shouldCommit);
      return result;
    }

    beginGesture(label) {
      return {
        label: label,
        before: this._capture(),
        ui: this.captureUi(),
        viewport: this._captureViewport()
      };
    }

    commitGesture(gesture, result, shouldCommit) {
      if (!gesture || !gesture.before) throw new Error('Unknown viewer history gesture');
      let after;
      try {
        after = this._capture();
      } catch (error) {
        try { this._restoreFailedAction(gesture.before, gesture.ui, gesture.viewport); } catch (_) { /* Keep capture error. */ }
        throw error;
      }
      const changed = this._changed(gesture.before, after);
      let accepted = true;
      if (typeof shouldCommit === 'function') accepted = Boolean(shouldCommit(result));
      else if (result === false || (result && typeof result === 'object' && result.success === false)) accepted = false;
      if (!accepted) {
        if (changed) this._restoreFailedAction(gesture.before, gesture.ui, gesture.viewport);
        return false;
      }
      if (!changed) return false;

      const entry = this._makeEntry(gesture.label, gesture.before, after);
      this.redoStack.forEach((redoEntry) => { this.bytes -= redoEntry.bytes; });
      this.redoStack.length = 0;
      this.undoStack.push(entry);
      this.bytes += entry.bytes;
      this._evictOldest();
      this.onChange();
      return true;
    }

    cancelGesture(gesture) {
      if (!gesture || !gesture.before) return false;
      this._restoreFailedAction(gesture.before, gesture.ui, gesture.viewport);
      return true;
    }

    _evictOldest() {
      const count = () => this.undoStack.length + this.redoStack.length;
      while (count() > this.maxActions || (this.bytes > this.maxBytes && count() > 1)) {
        const oldestUndo = this.undoStack.length ? this.undoStack[0] : null;
        const oldestRedoIndex = this.redoStack.length - 1;
        const oldestRedo = oldestRedoIndex >= 0 ? this.redoStack[oldestRedoIndex] : null;
        if (oldestUndo && (!oldestRedo || oldestUndo.sequence < oldestRedo.sequence)) {
          this.undoStack.shift();
          this.bytes -= oldestUndo.bytes;
        } else if (oldestRedo && this.redoStack.length > 1) {
          // The current graph is before the earliest Redo. Fold that evicted
          // gesture into its successor so the remaining delta path still starts
          // at the current graph and can be replayed exactly.
          const laterIndex = this.redoStack.length - 2;
          const later = this.redoStack[laterIndex];
          const merged = this._mergeEntries(oldestRedo, later);
          this.redoStack.pop();
          this.redoStack[laterIndex] = merged;
          this.bytes += merged.bytes - oldestRedo.bytes - later.bytes;
        } else {
          break;
        }
      }
    }

    undo() {
      if (!this.canUndo) return false;
      const entry = this.undoStack[this.undoStack.length - 1];
      const ui = this.captureUi();
      const viewport = this._captureViewport();
      this._applyEntry(entry, 'undo', ui, viewport);
      this.undoStack.pop();
      this.redoStack.push(entry);
      this._evictOldest();
      this.onChange();
      return true;
    }

    redo() {
      if (!this.canRedo) return false;
      const entry = this.redoStack[this.redoStack.length - 1];
      const ui = this.captureUi();
      const viewport = this._captureViewport();
      this._applyEntry(entry, 'redo', ui, viewport);
      this.redoStack.pop();
      this.undoStack.push(entry);
      this._evictOldest();
      this.onChange();
      return true;
    }

    clear() {
      this.undoStack.length = 0;
      this.redoStack.length = 0;
      this.bytes = 0;
      this.onChange();
    }
  }

  return { ViewerActionHistory: ViewerActionHistory };
});
