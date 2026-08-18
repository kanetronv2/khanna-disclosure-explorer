'use strict';

const registry = require('../data/issuer-registry.json');

function normalized(value) {
  return String(value == null ? '' : value)
    .normalize('NFKD')
    .toUpperCase()
    .replace(/&/g, ' AND ')
    .replace(/[^A-Z0-9]+/g, ' ')
    .trim()
    .replace(/\s+/g, ' ');
}

const compiled = registry.map(issuer => ({
  ...issuer,
  normalizedAliases: new Set([issuer.name, issuer.ticker, ...(issuer.aliases || [])].map(normalized)),
  patterns: (issuer.security_name_patterns || []).map(pattern => new RegExp(pattern, 'i')),
}));

function publicIssuer(issuer) {
  if (!issuer) return null;
  return {
    id: issuer.id,
    slug: issuer.slug,
    name: issuer.name,
    ticker: issuer.ticker || null,
    aliases: issuer.aliases || [],
    url: `/companies/${issuer.slug}/`,
    markdown_url: `/companies/${issuer.slug}/index.md`,
    data_url: `/api/v1/issuers/${issuer.slug}.json`,
  };
}

function absoluteIssuer(issuer, base) {
  if (!issuer || !base) return issuer;
  const origin = String(base).replace(/\/$/, '');
  return {
    ...issuer,
    url: `${origin}${issuer.url}`,
    markdown_url: `${origin}${issuer.markdown_url}`,
    data_url: `${origin}${issuer.data_url}`,
  };
}

function resolveIssuer(value) {
  const key = normalized(value);
  if (!key) return null;
  const match = compiled.find(issuer => issuer.normalizedAliases.has(key) ||
    issuer.patterns.some(pattern => pattern.test(String(value).trim())));
  return publicIssuer(match);
}

function rowMatchesIssuer(row, issuer) {
  if (!row || !issuer) return false;
  const full = compiled.find(item => item.id === issuer.id);
  if (!full) return false;
  const name = String(row.name || row.asset_name || '').trim();
  return full.patterns.some(pattern => pattern.test(name)) ||
    full.normalizedAliases.has(normalized(name));
}

function enrichWithIssuer(row, base) {
  const issuer = resolveIssuer(row && (row.name || row.asset_name));
  return issuer ? {...row, issuer: absoluteIssuer(issuer, base)} : row;
}

module.exports = {registry: compiled.map(publicIssuer), normalized, resolveIssuer, rowMatchesIssuer, absoluteIssuer, enrichWithIssuer};
