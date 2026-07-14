// Mirrors core/encoding.py -- base64 encode/decode of a single chunk's TXT payload.
// Only decode is needed here (the webapp never publishes), unlike the Python module
// which has both directions.
export function decodeChunk(encoded) {
  const binary = atob(encoded);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}
