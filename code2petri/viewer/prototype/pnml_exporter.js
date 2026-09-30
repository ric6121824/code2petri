/**
 * Phase 2.7 Client-Side PNML Exporter
 * Serializes the current Cytoscape interactive graph state directly into
 * ISO/IEC 15909-2 compliant PNML XML and triggers a browser file download.
 */

function escapeXml(unsafe) {
  if (unsafe === undefined || unsafe === null) return '';
  return String(unsafe).replace(/[<>&'"]/g, function (c) {
    switch (c) {
      case '<': return '&lt;';
      case '>': return '&gt;';
      case '&': return '&amp;';
      case '\'': return '&apos;';
      case '"': return '&quot;';
    }
  });
}

/**
 * Converts the active Cytoscape net to ISO/IEC 15909-2 PNML XML string.
 * @param {cytoscape.Core} cy
 * @param {string} [netName='PetriNet']
 * @returns {string}
 */
function serializeToPnml(cy, netName = 'LiveFoldPetriNet') {
  let xml = '<?xml version="1.0" encoding="utf-8"?>\n';
  xml += '<pnml xmlns="http://www.pnml.org/version-2009/grammar/pnml">\n';
  xml += '  <net id="net0" type="http://www.pnml.org/version-2009/grammar/ptnet">\n';
  xml += '    <name>\n';
  xml += `      <text>${escapeXml(netName || 'LiveFoldPetriNet')}</text>\n`;
  xml += '    </name>\n';
  xml += '    <page id="page0">\n';

  // 1. Places (excluding compound container parent nodes)
  const places = cy.nodes('.place').filter(function(p) {
    return p.inside() && !p.hasClass('compound');
  });
  places.forEach(p => {
    const pId = p.id();
    const label = p.data('raw_label') || p.data('label') || pId;
    const tokens = parseInt(p.data('initial_tokens') || p.data('tokens') || 0, 10);

    xml += `      <place id="${escapeXml(pId)}">\n`;
    xml += '        <name>\n';
    xml += `          <text>${escapeXml(label)}</text>\n`;
    xml += '        </name>\n';
    if (tokens > 0) {
      xml += '        <initialMarking>\n';
      xml += `          <text>${tokens}</text>\n`;
      xml += '        </initialMarking>\n';
    }
    xml += '      </place>\n';
  });

  // 2. Transitions
  const transitions = cy.nodes('.transition').filter(function(t) {
    return t.inside() && !t.hasClass('compound');
  });
  transitions.forEach(t => {
    const tId = t.id();
    let label = t.data('custom_name') || t.data('raw_label');
    if (!label) {
      const rawDataLabel = t.data('label');
      if (rawDataLabel) {
        label = rawDataLabel;
      } else {
        label = t.data('original_label') || tId;
      }
    }

    const rawTau = t.data('tau');
    const tauVal = (rawTau !== undefined && rawTau !== null) ? Number(rawTau) : 1.0;
    const tauStr = Number.isInteger(tauVal) ? tauVal.toFixed(1) : String(tauVal);

    const rawOmega = t.data('omega');
    const omegaVal = (rawOmega !== undefined && rawOmega !== null) ? Number(rawOmega) : 0.0;
    const omegaStr = Number.isInteger(omegaVal) ? omegaVal.toFixed(1) : String(omegaVal);

    const isOpaque = t.data('is_opaque') === true || t.hasClass('opaque') || Boolean(t.data('opaque'));
    const lineNo = t.data('source_line') || t.data('line_number');
    const compType = t.data('component_type');
    const parent = t.data('parent') || t.data('enclosing_function');
    const resolved = t.data('resolved');
    const resolvedTo = t.data('resolved_to');
    const targetFile = t.data('target_file');

    xml += `      <transition id="${escapeXml(tId)}">\n`;
    xml += '        <name>\n';
    xml += `          <text>${escapeXml(label)}</text>\n`;
    xml += '        </name>\n';
    xml += '        <toolspecific tool="code2petri" version="1.0">\n';
    xml += `          <property name="tau" value="${escapeXml(tauStr)}"/>\n`;
    if (isOpaque) {
      xml += '          <property name="opaque" value="true"/>\n';
      xml += `          <property name="omega" value="${escapeXml(omegaStr)}"/>\n`;
      if (compType) {
        xml += `          <property name="component_type" value="${escapeXml(compType)}"/>\n`;
      }
    }
    if (lineNo !== undefined && lineNo !== null && lineNo !== '') {
      xml += `          <property name="line_number" value="${escapeXml(lineNo)}"/>\n`;
    }
    if (parent) {
      xml += `          <property name="enclosing_function" value="${escapeXml(parent)}"/>\n`;
    }
    if (resolved === true) {
      xml += `          <resolved target="${escapeXml(resolvedTo || '')}" file="${escapeXml(targetFile || '')}"/>\n`;
    } else if (resolved === false) {
      xml += '          <unresolved/>\n';
    }
    xml += '        </toolspecific>\n';
    xml += '      </transition>\n';
  });

  // 3. Arcs
  const edges = cy.edges().filter(function(e) {
    if (!e.inside()) return false;
    const src = cy.getElementById(e.data('source'));
    const tgt = cy.getElementById(e.data('target'));
    return src && src.inside() && !src.hasClass('compound') &&
           tgt && tgt.inside() && !tgt.hasClass('compound');
  });
  edges.forEach((edge, index) => {
    const arcId = edge.id() || `a${index + 1}`;
    const sourceId = edge.data('source');
    const targetId = edge.data('target');
    const weight = parseInt(edge.data('weight') || 1, 10);

    xml += `      <arc id="${escapeXml(arcId)}" source="${escapeXml(sourceId)}" target="${escapeXml(targetId)}">\n`;
    if (weight !== 1) {
      xml += '        <inscription>\n';
      xml += `          <text>${weight}</text>\n`;
      xml += '        </inscription>\n';
    }
    xml += '      </arc>\n';
  });

  xml += '    </page>\n';
  xml += '  </net>\n';
  xml += '</pnml>\n';

  return xml;
}

/**
 * Triggers a browser file download of the current graph as a PNML file.
 * @param {cytoscape.Core} cy
 * @param {string} [filename='petri_net_export.pnml']
 */
function downloadPnmlFile(cy, filename = 'petri_net_export.pnml') {
  const netName = filename.replace(/\.pnml$/i, '');
  const xmlContent = serializeToPnml(cy, netName);
  if (typeof document !== 'undefined' && typeof Blob !== 'undefined' && typeof URL !== 'undefined' && typeof URL.createObjectURL === 'function') {
    const blob = new Blob([xmlContent], { type: 'application/xml;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    if (document.body && typeof document.body.appendChild === 'function') {
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } else if (typeof a.click === 'function') {
      a.click();
    }
    if (typeof URL.revokeObjectURL === 'function') {
      setTimeout(() => URL.revokeObjectURL(url), 100);
    }
  }
  return xmlContent;
}
const exportPnml = downloadPnmlFile;

// Export for browser or node
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { serializeToPnml, downloadPnmlFile, exportPnml };
} else {
  window.serializeToPnml = serializeToPnml;
  window.downloadPnmlFile = downloadPnmlFile;
  window.exportPnml = exportPnml;
}
