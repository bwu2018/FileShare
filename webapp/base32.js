// Hand-rolled RFC 4648 base32 encoder -- no native browser/Node support. Must match
// Python's base64.b32encode exactly (alphabet + '=' padding to a multiple of 8 chars),
// since it's used to compute DNS labels that have to match what the publisher
// (core/hashing.py) already put in DNS. Cross-checked against real base64.b32encode
// output in tests/base32.test.js, not just self-consistency.
const ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';

export function base32Encode(bytes) {
  let bits = 0;
  let value = 0;
  let output = '';

  for (let i = 0; i < bytes.length; i++) {
    value = (value << 8) | bytes[i];
    bits += 8;
    while (bits >= 5) {
      output += ALPHABET[(value >>> (bits - 5)) & 0x1f];
      bits -= 5;
    }
  }

  if (bits > 0) {
    output += ALPHABET[(value << (5 - bits)) & 0x1f];
  }

  while (output.length % 8 !== 0) {
    output += '=';
  }

  return output;
}
