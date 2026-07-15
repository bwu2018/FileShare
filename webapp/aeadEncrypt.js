// Mirrors core/crypto.py::generate_key / encrypt via WebCrypto AES-256-GCM. The
// combined ciphertext+tag layout WebCrypto produces is already confirmed
// wire-compatible with Python's `cryptography` AESGCM output (see aead.js's
// decrypt-side comment) -- that equivalence holds in this, the encrypt direction, too.
import { KEY_SIZE, NONCE_SIZE } from './constants.js';

export function generateKey() {
  return crypto.getRandomValues(new Uint8Array(KEY_SIZE));
}

export async function encryptAesGcm(keyBytes, plaintext) {
  const nonce = crypto.getRandomValues(new Uint8Array(NONCE_SIZE));
  const cryptoKey = await crypto.subtle.importKey(
    'raw',
    keyBytes,
    { name: 'AES-GCM' },
    false,
    ['encrypt'],
  );
  const ciphertext = await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv: nonce },
    cryptoKey,
    plaintext,
  );
  return { nonce, ciphertext: new Uint8Array(ciphertext) };
}
