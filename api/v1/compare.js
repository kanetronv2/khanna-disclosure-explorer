'use strict';

const {normalized, resolveIssuer, rowMatchesIssuer, absoluteIssuer, enrichWithIssuer} = require('../../lib/issuer.js');

const YEARS = new Set(Array.from({length: 11}, (_, i) => String(2016 + i)));

function origin(req) {
  const host = req.headers['x-forwarded-host'] || req.headers.host;
  if (!host && process.env.VERCEL_URL) return `https://${process.env.VERCEL_URL}`;
  const protocol = String(host || '').startsWith('localhost:') ? 'http' : 'https';
  return `${protocol}://${host}`;
}

function one(value) {
  return Array.isArray(value) ? value[0] : value;
}

function money(value) {
  return value == null ? null : `$${Number(value).toLocaleString('en-US')}`;
}

function displayRange(value) {
  if (!value || value.minimum_usd == null) return 'None';
  if (value.open_ended) {
    return value.calculated_upper_floor_usd === value.minimum_usd ? `${money(value.minimum_usd)}+` :
      `${money(value.minimum_usd)}–${money(value.calculated_upper_floor_usd)}+`;
  }
  if (value.minimum_usd === value.maximum_usd) return money(value.minimum_usd);
  return `${money(value.minimum_usd)}–${money(value.maximum_usd)}${value.open_ended ? '+' : ''}`;
}

function aggregate(year, rows, base) {
  let minimum = 0;
  let maximum = 0;
  let openEnded = false;
  let hasValue = false;
  const bands = [];
  for (const row of rows) {
    if (row.vlo != null) {
      hasValue = true;
      minimum += row.vlo;
      if (row.vhi == null) {
        openEnded = true;
        maximum += row.vlo;
      } else {
        maximum += row.vhi;
      }
    }
    if (row.value && !bands.includes(row.value)) bands.push(row.value);
  }
  const value = {
    minimum_usd: hasValue ? minimum : null,
    calculated_upper_floor_usd: hasValue ? maximum : null,
    maximum_usd: hasValue && !openEnded ? maximum : null,
    open_ended: openEnded,
    reported_bands: bands,
  };
  value.display = displayRange(value);
  return {
    year: Number(year),
    holding_count: rows.length,
    reported_value: value,
    source_endpoint: `${base}/api/v1/years/${year}/assets.json`,
    records: rows.map(row => ({
      ...enrichWithIssuer(row, base),
      url: `${base}/api/v1/evidence?id=${encodeURIComponent(row.id)}`,
      source_page_url: `${base}/${year}/#p${row.page}`,
    })),
  };
}

function boundDirection(oldValue, newValue, key) {
  const oldBound = oldValue[key];
  const newBound = newValue[key];
  if (oldBound == null || newBound == null) return 'not_comparable';
  if (newBound > oldBound) return 'increased';
  if (newBound < oldBound) return 'decreased';
  return 'unchanged';
}

function comparison(from, to, facts) {
  const oldValue = from.reported_value;
  const newValue = to.reported_value;
  const lower = boundDirection(oldValue, newValue, 'minimum_usd');
  const upper = boundDirection(oldValue, newValue, 'calculated_upper_floor_usd');
  const bothFinite = oldValue.maximum_usd != null && newValue.maximum_usd != null;
  let relation = 'not_comparable';
  if (bothFinite) {
    if (newValue.minimum_usd > oldValue.maximum_usd) relation = 'higher_non_overlapping_range';
    else if (newValue.maximum_usd < oldValue.minimum_usd) relation = 'lower_non_overlapping_range';
    else if (newValue.minimum_usd === oldValue.minimum_usd && newValue.maximum_usd === oldValue.maximum_usd) relation = 'same_reported_range';
    else relation = 'overlapping_reported_ranges';
  }
  const warnings = facts.flatMap(item => {
    const crossYear = item.comparability && item.comparability.cross_year_holdings;
    return crossYear && crossYear.status === 'not_directly_comparable' ? [crossYear.reason] : [];
  }).filter((item, index, values) => item && values.indexOf(item) === index);
  const directlyComparable = warnings.length === 0;
  let reportedBounds = 'mixed_or_not_comparable';
  if (lower === 'increased' && upper === 'increased') reportedBounds = 'both_increased';
  else if (lower === 'decreased' && upper === 'decreased') reportedBounds = 'both_decreased';
  else if (lower === 'unchanged' && upper === 'unchanged') reportedBounds = 'unchanged';
  const directionWords = reportedBounds === 'both_increased' ? 'both increased' :
    reportedBounds === 'both_decreased' ? 'both decreased' :
    reportedBounds === 'unchanged' ? 'were unchanged' : 'did not move in one clear direction';
  const caveat = directlyComparable ?
    'The disclosures report ranges rather than exact values, so an exact change cannot be calculated.' :
    `The filing years are not directly comparable: ${warnings.join(' ')}`;
  return {
    from_year: from.year,
    to_year: to.year,
    lower_bound_direction: lower,
    upper_bound_direction: upper,
    reported_bounds_direction: reportedBounds,
    conservative_range_relation: relation,
    directly_comparable: directlyComparable,
    actual_holdings_change: 'cannot_be_inferred',
    warnings,
    answer: `The aggregate reported range's lower and upper bounds ${directionWords}, from ${oldValue.display} in ${from.year} to ${newValue.display} in ${to.year}. ${caveat}`,
  };
}

function genericMatch(row, query) {
  if (String(row.cls || '').toLowerCase() !== 'common stock') return false;
  const name = normalized(row.name);
  const needle = normalized(query);
  return Boolean(needle && (name.includes(needle) || needle.includes(name)));
}

module.exports = async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Accept, Content-Type');
  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method !== 'GET') return res.status(405).json({error: 'GET only'});

  const query = String(one(req.query.entity || req.query.q) || '').trim();
  const requestedYears = String(one(req.query.years) || '2024,2025').split(',').map(value => value.trim()).filter(Boolean);
  const years = [...new Set(requestedYears)];
  if (!query) return res.status(400).json({error: 'entity is required (for example entity=NVDA)'});
  if (years.length < 2 || years.length > 11 || years.some(year => !YEARS.has(year))) {
    return res.status(400).json({error: 'years must contain 2–11 comma-separated filing years from 2016 through 2026'});
  }
  const issuer = resolveIssuer(query);
  const base = origin(req);
  try {
    const responses = await Promise.all(years.flatMap(year => [
      fetch(`${base}/api/v1/years/${year}/assets.json`, {headers: {accept: 'application/json'}}),
      fetch(`${base}/api/v1/years/${year}/summary.json`, {headers: {accept: 'application/json'}}),
    ]));
    if (responses.some(response => !response.ok)) throw new Error('one or more year endpoints failed');
    const payloads = await Promise.all(responses.map(response => response.json()));
    const results = [];
    const facts = [];
    for (let index = 0; index < years.length; index += 1) {
      const rows = payloads[index * 2];
      const yearFacts = payloads[index * 2 + 1];
      facts.push(yearFacts);
      const matched = rows.filter(row => String(row.cls || '').toLowerCase() === 'common stock' &&
        (issuer ? rowMatchesIssuer(row, issuer) : genericMatch(row, query)));
      results.push(aggregate(years[index], matched, base));
    }
    const comparisons = results.slice(1).map((item, index) => comparison(results[index], item, [facts[index], facts[index + 1]]));
    res.setHeader('Cache-Control', 'public, s-maxage=300, stale-while-revalidate=86400');
    return res.status(200).json({
      schema_version: '1.0.0',
      dataset: 'Khanna Disclosure Explorer',
      dataset_version: facts[0] && facts[0].dataset_version || null,
      described_by: `${base}/api/v1/openapi.json`,
      scope: 'Annual Schedule A common-stock holdings aggregated across the household interests and portfolio groups printed in each filing.',
      query,
      entity: absoluteIssuer(issuer, base) || {id: null, slug: null, name: query, ticker: null, aliases: []},
      years: results,
      comparisons,
      interpretation: [
        'Values are statutory reported ranges, not exact market values or share counts.',
        'Owner codes describe household disclosure attribution and do not establish who directed an investment decision.',
        'Raw security names are preserved on each evidence record; issuer identity is a separate curated normalization.',
      ],
    });
  } catch (error) {
    return res.status(502).json({error: 'Could not load the source datasets', detail: error.message});
  }
};
