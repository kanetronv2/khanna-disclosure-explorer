const YEARS = new Set(Array.from({length: 11}, (_, i) => String(2016 + i)));
const {enrichWithIssuer} = require('../../lib/issuer.js');
const {evidenceUrl, officialSource} = require('../../lib/evidence.js');

function origin(req) {
  const host = req.headers['x-forwarded-host'] || req.headers.host;
  if (!host && process.env.VERCEL_URL) return `https://${process.env.VERCEL_URL}`;
  const protocol = String(host || '').startsWith('localhost:') ? 'http' : 'https';
  return `${protocol}://${host}`;
}

function one(value) {
  return Array.isArray(value) ? value[0] : value;
}

module.exports = async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Accept, Content-Type');
  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method !== 'GET') return res.status(405).json({error: 'GET only'});

  const id = String(one(req.query.id) || '');
  const match = /^(asset|transaction):(20\d{2}):(\d{6})$/.exec(id);
  if (!match || !YEARS.has(match[2])) {
    return res.status(400).json({error: 'id must look like asset:2025:000001 or transaction:2025:000001'});
  }
  const [, singular, year, ordinal] = match;
  const kind = singular === 'asset' ? 'assets' : 'transactions';
  const endpoint = `${origin(req)}/api/v1/years/${year}/${kind}.json`;

  try {
    const response = await fetch(endpoint, {headers: {accept: 'application/json'}});
    if (!response.ok) throw new Error(`data endpoint returned ${response.status}`);
    const rows = await response.json();
    const row = rows[Number.parseInt(ordinal, 10) - 1];
    if (!row || row.id !== id) return res.status(404).json({error: `No evidence record ${id}`});
    res.setHeader('Cache-Control', 'public, s-maxage=300, stale-while-revalidate=86400');
    const base = origin(req);
    const doc = row.doc || '';
    const documentPath = doc === '2024-1' ? 'disclosures.pdf' : `docs/src/${doc}.pdf`;
    const mirrorUrl = evidenceUrl(documentPath, base);
    const official = officialSource(doc);
    return res.status(200).json({
      ...enrichWithIssuer(row, base),
      url: `${base}/api/v1/evidence?id=${encodeURIComponent(row.id)}`,
      source_document_url: official?.official_url || mirrorUrl,
      source_document_mirror_url: mirrorUrl,
      official_source_url: official?.official_url || null,
      house_filing_id: official?.filing_id || null,
      source_page_url: `${base}/${year}/#p${row.page}`,
      citation_note: 'Cite this evidence record and the official filing when available; verify consequential claims against the scanned page. Reported amounts are statutory ranges, not exact values.',
    });
  } catch (error) {
    return res.status(502).json({error: 'Could not load the source dataset', detail: error.message});
  }
};
