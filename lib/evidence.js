'use strict';

const config = require('./evidence-config.json');

function evidenceOrigin(fallback) {
  return String(process.env.EVIDENCE_ORIGIN || config.evidence_origin || fallback || '')
    .replace(/\/$/, '');
}

function evidenceUrl(path, fallback) {
  const value = String(path || '');
  if (/^https?:\/\//i.test(value)) return value;
  return `${evidenceOrigin(fallback)}/${value.replace(/^\//, '')}`;
}

module.exports = {evidenceOrigin, evidenceUrl};
