#!/usr/bin/env node
const search = require('../api/v1/search.js');
const evidence = require('../api/v1/evidence.js');

const rows = [
  {id: 'transaction:2025:000001', name: 'APPLE INC CMN', owner: 'DC', cls: 'Common stock',
   tx_type: 'Purchase', doc: '2025-14', page: 151},
  {id: 'transaction:2025:000002', name: 'MICROSOFT CORP CMN', owner: 'SP', cls: 'Common stock',
   tx_type: 'Sale', doc: '2025-14', page: 152},
];

global.fetch = async () => ({ok: true, status: 200, json: async () => rows});

function response() {
  return {
    code: 0, body: null, headers: {},
    setHeader(key, value) { this.headers[key] = value; },
    status(code) { this.code = code; return this; },
    json(body) { this.body = body; return this; },
    end() { return this; },
  };
}

async function main() {
  let res = response();
  await search({method: 'GET', headers: {host: 'localhost:3000'},
    query: {year: '2025', kind: 'transactions', q: 'apple'}}, res);
  if (res.code !== 200 || res.body.total !== 1 ||
      res.body.results[0].id !== 'transaction:2025:000001' ||
      !res.body.results[0].source_document_url) throw new Error('search handler failed');

  res = response();
  await evidence({method: 'GET', headers: {host: 'localhost:3000'},
    query: {id: 'transaction:2025:000002'}}, res);
  if (res.code !== 200 || res.body.id !== 'transaction:2025:000002' ||
      !res.body.source_page_url) throw new Error('evidence handler failed');

  res = response();
  await evidence({method: 'GET', headers: {host: 'localhost:3000'}, query: {id: 'bad'}}, res);
  if (res.code !== 400) throw new Error('invalid evidence ID should return 400');
  console.log('API handler audit: PASS');
}

main().catch(error => { console.error(error); process.exit(1); });
