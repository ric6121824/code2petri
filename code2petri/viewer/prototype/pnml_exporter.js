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
  xml += `      <text>${escapeXml(netName)}</text>\n`;
  xml += '    </name>\n';
  xml += '    <page id="page0">\n';

  // 1. Places (excluding compound container parent nodes)
  cy.nodes('.place').forEach(p => {
    const pId = p.id();
    const label = p.data('label') || pId;
    const tokens = parseInt(p.data('initial_tokens') || 0, 10);

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
  cy.nodes('.transition').forEach(t => {
    const tId = t.id();
    const label = t.data('label') || tId;
    const tau = t.data('tau') !== undefined ? t.data('tau') : 1.0;
    const omega = t.data('omega') !== undefined ? t.data('omega') : 0.0;
    const isOpaque = Boolean(t.data('opaque'));
    const lineNo = t.data('line_number');

    xml += `      <transition id="${escapeXml(tId)}">\n`;
    xml += '        <name>\n';
    xml += `          <text>${escapeXml(label)}</text>\n`;
    xml += '        </name>\n';
    xml += '        <toolspecific tool="code2petri" version="1.0">\n';
    xml += `          <property name="tau" value="${escapeXml(tau)}"/>\n`;
    if (isOpaque) {
      xml += '          <property name="opaque" value="true"/>\n';
      xml += `          <property name="omega" value="${escapeXml(omega)}"/>\n`;
      if (t.data('component_type')) {
        xml += `          <property name="component_type" value="${escapeXml(t.data('component_type'))}"/>\n`;
      }
    }
    if (lineNo !== undefined && lineNo !== null) {
      xml += `          <property name="line_number" value="${escapeXml(lineNo)}"/>\n`;
    }
    if (t.data('parent')) {
      xml += `          <property name="enclosing_function" value="${escapeXml(t.data('parent'))}"/>\n`;
    }
    xml += '        </toolspecific>\n';
    xml += '      </transition>\n';
  });

  // 3. Arcs
  cy.edges('.arc').forEach((edge, index) => {
    const arcId = edge.id() || `a${index + 1}`;
    const sourceId = edge.data('source');
    const targetId = edge.data('target');
    const weight = edge.data('weight') || 1;

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
  const xmlContent = serializeToPnml(cy, filename.replace('.pnml', ''));
  const blob = new Blob([xmlContent], { type: 'application/xml;charset=utf-8' });
  const url = URL.createObjectURL(blob);

  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// Export for browser or node
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { serializeToPnml, downloadPnmlFile };
} else {
  window.serializeToPnml = serializeToPnml;
  window.downloadPnmlFile = downloadPnmlFile;
}
