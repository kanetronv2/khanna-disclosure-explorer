'use strict';

const config = require('./evidence-config.json');
const sourceRegistry = require('./source-registry.json');

function evidenceOrigin(fallback) {
  return String(process.env.EVIDENCE_ORIGIN || config.evidence_origin || fallback || '')
    .replace(/\/$/, '');
}

function evidenceUrl(path, fallback) {
  const value = String(path || '');
  if (/^https?:\/\//i.test(value)) return value;
  return `${evidenceOrigin(fallback)}/${value.replace(/^\//, '')}`;
}

function officialSource(doc) {
  return sourceRegistry[String(doc || '')] || null;
}

module.exports = {evidenceOrigin, evidenceUrl, officialSource};
