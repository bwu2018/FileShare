// Mirrors zonegen/txt_packing.py::unpack_txt_strings -- plain concatenation of the
// already-separated RFC 1035 character-strings that make up one record's payload.
// Unwrapping Cloudflare's own quoting/spacing convention for multi-string TXT answers
// happens in doh.js, upstream of this -- by the time strings reach here they're already
// a clean list of the original packed segments, same shape dnspython hands the Python
// downloader (downloader/dns_store.py).
export function unpackTxtStrings(strings) {
  return strings.join('');
}
