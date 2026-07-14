// Mirrors core/hashing.py exactly: SHA-256 digest, base32-encoded.
import { base32Encode } from './base32.js';

// Mirrors compute_chunk_hash(chunk) -- generic hash-then-base32 of arbitrary bytes.
// Used both here (indirectly, via computeChunkAddress) and by download.js to verify
// the manifest pointer record's own hash.
export async function sha256Base32(bytes) {
  const digest = await crypto.subtle.digest('SHA-256', bytes);
  return base32Encode(new Uint8Array(digest));
}

// Mirrors compute_chunk_address(nonce, index):
//   hashlib.sha256(nonce + struct.pack(">I", index)).digest(), base32-encoded.
export async function computeChunkAddress(nonce, index) {
  const indexBytes = new Uint8Array(4);
  new DataView(indexBytes.buffer).setUint32(0, index, false); // big-endian, matches ">I"
  const combined = new Uint8Array(nonce.length + 4);
  combined.set(nonce, 0);
  combined.set(indexBytes, nonce.length);
  return sha256Base32(combined);
}
