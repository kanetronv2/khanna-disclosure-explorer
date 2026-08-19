const YEARS = new Set(Array.from({length: 11}, (_, i) => String(2016 + i)));
const KINDS = new Set(['assets', 'transactions']);
const {enrichWithIssuer} = require('../../lib/issuer.js');
const {evidenceUrl} = require('../../lib/evidence.js');

function origin(req) {
  const host = req.headers['x-forwarded-host'] || req.headers.host;
  if (!host && process.env.VERCEL_URL) return `https://${process.env.VERCEL_URL}`;
  const protocol = String(host || '').startsWith('localhost:') ? 'http' : 'https';
  return `${protocol}://${host}`;
}

function text(value) {
  return String(value == null ? '' : value).trim().toLowerCase();
}

function one(value) {
  return Array.isArray(value) ? value[0] : value;
}

function withEvidence(row, base) {
  const doc = row.doc || '';
  const documentPath = doc === '2024-1' ? 'disclosures.pdf' : `docs/src/${doc}.pdf`;
  return {
    ...enrichWithIssuer(row, base),
    url: `${base}/api/v1/evidence?id=${encodeURIComponent(row.id)}`,
    source_document_url: evidenceUrl(documentPath, base),
    source_page_url: `${base}/${String(row.id || '').split(':')[1]}/#p${row.page}`,
  };
}

module.exports = async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Accept, Content-Type');
  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method !== 'GET') return res.status(405).json({error: 'GET only'});

  const year = String(one(req.query.year) || '');
  const kind = String(one(req.query.kind) || '');
  if (!YEARS.has(year)) return res.status(400).json({error: 'year must be between 2016 and 2026'});
  if (!KINDS.has(kind)) return res.status(400).json({error: 'kind must be assets or transactions'});

  const query = text(one(req.query.q));
  const owner = text(one(req.query.owner));
  const assetClass = text(one(req.query.class));
  const transactionType = text(one(req.query.type));
  const offset = Math.max(0, Number.parseInt(one(req.query.offset) || '0', 10) || 0);
  const limit = Math.min(100, Math.max(1, Number.parseInt(one(req.query.limit) || '25', 10) || 25));
  const endpoint = `${origin(req)}/api/v1/years/${year}/${kind}.json`;

  try {
    const response = await fetch(endpoint, {headers: {accept: 'application/json'}});
    if (!response.ok) throw new Error(`data endpoint returned ${response.status}`);
    const rows = await response.json();
    const filtered = rows.filter(row => {
      const haystack = [row.name, row.desc, row.group, row.cls, row.tx_type, row.date]
        .map(text).join(' ');
      if (query && !haystack.includes(query)) return false;
      if (owner && text(row.owner) !== owner) return false;
      if (assetClass && text(row.cls) !== assetClass) return false;
      if (transactionType && text(row.tx_type) !== transactionType) return false;
      return true;
    });
    const results = filtered.slice(offset, offset + limit).map(row => withEvidence(row, origin(req)));
    const nextOffset = offset + results.length < filtered.length ? offset + results.length : null;
    res.setHeader('Cache-Control', 'public, s-maxage=300, stale-while-revalidate=86400');
    return res.status(200).json({
      dataset: 'Khanna Disclosure Explorer',
      year: Number(year),
      kind,
      query: {q: query || null, owner: owner || null, class: assetClass || null, type: transactionType || null},
      total: filtered.length,
      offset,
      limit,
      returned: results.length,
      next_offset: nextOffset,
      source_endpoint: endpoint,
      results,
    });
  } catch (error) {
    return res.status(502).json({error: 'Could not load the source dataset', detail: error.message});
  }
};
