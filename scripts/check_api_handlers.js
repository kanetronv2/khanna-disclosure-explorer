#!/usr/bin/env node
const search = require('../api/v1/search.js');
const evidence = require('../api/v1/evidence.js');
const compare = require('../api/v1/compare.js');

const rows = [
  {id: 'transaction:2025:000001', name: 'APPLE INC CMN', owner: 'DC', cls: 'Common stock',
   tx_type: 'Purchase', doc: '2025-14', page: 151},
  {id: 'transaction:2025:000002', name: 'MICROSOFT CORP CMN', owner: 'SP', cls: 'Common stock',
   tx_type: 'Sale', doc: '2025-14', page: 152},
];

const fetched = [];
global.fetch = async endpoint => {
  fetched.push(endpoint);
  let body = rows;
  if (endpoint.includes('/assets.json')) {
    body = endpoint.includes('/2024/') ? [
      {id: 'asset:2024:000001', name: 'NVIDIA CORPORATION CMN', owner: 'DC', cls: 'Common stock',
       value: '$100,001-$250,000', vlo: 100001, vhi: 250000, doc: '2024-1', page: 11},
      {id: 'asset:2024:000002', name: 'NVIDIA CORPORATION COM', owner: 'SP', cls: 'Common stock',
       value: '$250,001-$500,000', vlo: 250001, vhi: 500000, doc: '2024-1', page: 86},
    ] : [
      {id: 'asset:2025:000001', name: 'NVIDIA CORPORATION CMN', owner: 'DC', cls: 'Common stock',
       value: '$50,001-$100,000', vlo: 50001, vhi: 100000, doc: '2025-14', page: 22},
      {id: 'asset:2025:000002', name: 'NVIDIA CORPORATION COM', owner: 'SP', cls: 'Common stock',
       value: '$500,001-$1,000,000', vlo: 500001, vhi: 1000000, doc: '2025-14', page: 140},
    ];
  } else if (endpoint.includes('/summary.json')) {
    body = endpoint.includes('/2025/') ? {
      comparability: {cross_year_holdings: {status: 'not_directly_comparable', reason: '2025 basis differs.'}},
    } : {comparability: {cross_year_holdings: {status: 'no_year_specific_basis_warning', reason: 'No warning.'}}};
  }
  return {ok: true, status: 200, json: async () => body};
};

function response() {
  return {
    code: 0, body: null, headers: {},
    setHeader(key, value) { this.headers[key] = value; },
    status(code) { this.code = code; return this; },
    json(body) { this.body = body; return this; },
    send(body) { this.body = body; return this; },
    end() { return this; },
  };
}

async function main() {
  process.env.VERCEL_URL = 'protected-preview.example.test';
  process.env.EVIDENCE_ORIGIN = 'https://evidence.example.test';
  let res = response();
  await search({method: 'GET', headers: {host: 'localhost:3000'},
    query: {year: '2025', kind: 'transactions', q: 'apple'}}, res);
  if (res.code !== 200 || res.body.total !== 1 ||
      res.body.results[0].id !== 'transaction:2025:000001' ||
      res.body.results[0].source_document_url !== 'https://disclosures-clerk.house.gov/public_disc/financial-pdfs/2025/9116272.pdf' ||
      res.body.results[0].source_document_mirror_url !== 'https://evidence.example.test/docs/src/2025-14.pdf' ||
      res.body.results[0].house_filing_id !== '9116272') {
    throw new Error('search handler failed');
  }
  if (fetched[0] !== 'http://localhost:3000/api/v1/years/2025/transactions.json') {
    throw new Error(`search handler used the wrong request origin: ${fetched[0]}`);
  }

  res = response();
  await evidence({method: 'GET', headers: {host: 'localhost:3000'},
    query: {id: 'transaction:2025:000002'}}, res);
  if (res.code !== 200 || res.body.id !== 'transaction:2025:000002' ||
      !res.body.source_page_url ||
      res.body.source_document_url !== 'https://disclosures-clerk.house.gov/public_disc/financial-pdfs/2025/9116272.pdf' ||
      res.body.source_document_mirror_url !== 'https://evidence.example.test/docs/src/2025-14.pdf') {
    throw new Error('evidence handler failed');
  }
  if (fetched[1] !== 'http://localhost:3000/api/v1/years/2025/transactions.json') {
    throw new Error(`evidence handler used the wrong request origin: ${fetched[1]}`);
  }

  res = response();
  await evidence({method: 'GET', headers: {host: 'localhost:3000'}, query: {id: 'bad'}}, res);
  if (res.code !== 400) throw new Error('invalid evidence ID should return 400');

  res = response();
  await compare({method: 'GET', headers: {host: 'localhost:3000'},
    query: {entity: 'nvidia', years: '2024-2025', resource: '1'}}, res);
  if (res.code !== 200 || res.body.entity.ticker !== 'NVDA' ||
      res.body.years[0].holding_count !== 2 || res.body.years[1].holding_count !== 2 ||
      res.body.comparisons[0].reported_bounds_direction !== 'both_increased' ||
      res.body.comparisons[0].directly_comparable !== false ||
      !res.body.years[1].records[0].issuer || !res.body.answer ||
      !res.body.comparisons[0].calculation || !res.body.comparisons[0].evidence.length ||
      res.body.canonical_url !== 'http://localhost:3000/api/v1/issuers/nvidia/comparisons/2024-2025.json' ||
      !res.headers.ETag || !res.headers.Link || !res.headers['Last-Modified']) {
    throw new Error('issuer comparison handler failed');
  }

  const etag = res.headers.ETag;
  res = response();
  await compare({method: 'GET', headers: {host: 'localhost:3000', accept: 'text/plain'},
    query: {entity: 'nvidia', years: '2024-2025', resource: '1'}}, res);
  if (res.code !== 200 || typeof res.body !== 'string' ||
      !res.body.includes('# NVIDIA Corporation reported holdings comparison') ||
      !res.body.includes('### Evidence') || res.headers['Content-Type'] !== 'text/plain; charset=utf-8') {
    throw new Error('issuer comparison text representation failed');
  }

  res = response();
  await compare({method: 'GET', headers: {host: 'localhost:3000', 'if-none-match': etag},
    query: {entity: 'nvidia', years: '2024-2025', resource: '1'}}, res);
  if (res.code !== 304) throw new Error('issuer comparison ETag revalidation failed');

  res = response();
  await compare({method: 'GET', headers: {host: 'localhost:3000'},
    query: {entity: 'unknown-slug', years: '2024-2025', resource: '1'}}, res);
  if (res.code !== 404) throw new Error('unknown canonical issuer resource should return 404');
  console.log('API handler audit: PASS');
}

main().catch(error => { console.error(error); process.exit(1); });
