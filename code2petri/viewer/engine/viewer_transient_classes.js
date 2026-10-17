/**
 * Helpers for excluding temporary viewer-only classes from saved graph records.
 */
(function(root, factory) {
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = factory();
  } else if (root) {
    Object.assign(root, factory());
  }
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this), function() {
  const TRANSIENT_SEARCH_CLASSES = new Set(['search-match', 'search-active']);

  function stripTransientSearchClasses(classes) {
    if (typeof classes !== 'string') return classes;
    return classes.split(/\s+/).filter(function(name) {
      return name && !TRANSIENT_SEARCH_CLASSES.has(name);
    }).join(' ');
  }

  return { stripTransientSearchClasses: stripTransientSearchClasses };
});
