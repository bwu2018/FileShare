// DNS-over-HTTPS transport via Cloudflare's JSON API -- deliberately not RFC 8484
// wire-format, to avoid needing a binary DNS-message encoder/decoder in the browser.
// A wire-format library (e.g. dohjs) was considered and rejected: it solves a binary
// parsing problem this approach sidesteps entirely, while adding a stale, GPLv3
// dependency.
import { DEFAULT_RESOLVER_URL } from './constants.js';

const DNS_TYPE_TXT = 16;
const RCODE_NOERROR = 0;
const RCODE_NXDOMAIN = 3;

export class DnsQueryError extends Error {}

// Cloudflare represents a multi-string TXT record's `data` field as multiple
// individually double-quoted, space-separated RFC 1035 character-strings within one
// string, e.g. `"part1" "part2"` -- the same convention `dig` displays. Verified
// empirically against real multi-string DKIM records (outlook.com, sendgrid.net) before
// writing this, not assumed. Safe to parse with a simple quote-delimited regex (no
// escaping to worry about) since every payload this project ever puts in a TXT record
// is base64, whose alphabet (A-Za-z0-9+/=) contains no `"` or `\` characters.
function splitQuotedStrings(data) {
  return [...data.matchAll(/"([^"]*)"/g)].map((match) => match[1]);
}

// Returns the record's unwrapped character-strings, or null if the name is confirmed
// absent (NOERROR/NXDOMAIN with an empty answer -- mirrors downloader/dns_store.py's
// DnsChunkStore.get() distinguishing "confirmed absent" from "query failed").
export async function queryTxt(qname, resolverUrl = DEFAULT_RESOLVER_URL) {
  const url = `${resolverUrl}?name=${encodeURIComponent(qname)}&type=TXT`;
  let response;
  try {
    response = await fetch(url, { headers: { Accept: 'application/dns-json' } });
  } catch (e) {
    throw new DnsQueryError(`DoH request failed for ${qname}: ${e.message}`);
  }
  if (!response.ok) {
    throw new DnsQueryError(`DoH request for ${qname} returned HTTP ${response.status}`);
  }

  const body = await response.json();
  if (body.Status !== RCODE_NOERROR && body.Status !== RCODE_NXDOMAIN) {
    throw new DnsQueryError(`DNS query for ${qname} failed: Status=${body.Status}`);
  }

  const answers = (body.Answer || []).filter((a) => a.type === DNS_TYPE_TXT);
  if (answers.length === 0) {
    return null;
  }

  return splitQuotedStrings(answers[0].data);
}
