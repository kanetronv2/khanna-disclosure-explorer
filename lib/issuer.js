'use strict';

// Keep the registry beside the runtime helper: /data is intentionally excluded from Vercel.
const registry = require('./issuer-registry.json');

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
  const dataUrl = `/api/v1/issuers/${issuer.slug}.json`;
  const textUrl = `/api/v1/issuers/${issuer.slug}.txt`;
  const featured = issuer.featured_comparison;
  return {
    id: issuer.id,
    slug: issuer.slug,
    name: issuer.name,
    ticker: issuer.ticker || null,
    aliases: issuer.aliases || [],
    url: dataUrl,
    data_url: dataUrl,
    text_url: textUrl,
    comparison_url_template: `/api/v1/issuers/${issuer.slug}/comparisons/{from_year}-{to_year}.json`,
    featured_comparison_url: Array.isArray(featured) && featured.length === 2 ?
      `/api/v1/issuers/${issuer.slug}/comparisons/${featured[0]}-${featured[1]}.json` : null,
  };
}

function absoluteIssuer(issuer, base) {
  if (!issuer || !base) return issuer;
  const origin = String(base).replace(/\/$/, '');
  return {
    ...issuer,
    url: `${origin}${issuer.url}`,
    data_url: `${origin}${issuer.data_url}`,
    text_url: `${origin}${issuer.text_url}`,
    comparison_url_template: `${origin}${issuer.comparison_url_template}`,
    featured_comparison_url: issuer.featured_comparison_url ? `${origin}${issuer.featured_comparison_url}` : null,
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
