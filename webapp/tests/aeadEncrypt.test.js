// Cross-language compatibility (WebCrypto AES-GCM output decrypting correctly under
// Python's `cryptography` AESGCM) was verified empirically during development by
// encrypting here and decrypting with core.crypto.decrypt directly, not assumed --
// mirrors aead.js's own decrypt-direction verification note. These tests cover the
// properties an automated suite can check without shelling out to Python: round-trip
// correctness (via the existing decryptAesGcm), nonce freshness, and tamper detection.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { generateKey, encryptAesGcm } from '../aeadEncrypt.js';
import { decryptAesGcm } from '../aead.js';
import { KEY_SIZE, NONCE_SIZE } from '../constants.js';

test('generateKey produces KEY_SIZE random bytes', () => {
  const key = generateKey();
  assert.equal(key.length, KEY_SIZE);
});

test('generateKey produces different keys on successive calls', () => {
  const a = generateKey();
  const b = generateKey();
  assert.notDeepEqual(Array.from(a), Array.from(b));
});

test('encryptAesGcm produces a NONCE_SIZE nonce', async () => {
  const key = generateKey();
  const { nonce } = await encryptAesGcm(key, new Uint8Array([1, 2, 3]));
  assert.equal(nonce.length, NONCE_SIZE);
});

test('two encrypt calls with the same key produce different nonces', async () => {
  const key = generateKey();
  const first = await encryptAesGcm(key, new Uint8Array([1, 2, 3]));
  const second = await encryptAesGcm(key, new Uint8Array([1, 2, 3]));
  assert.notDeepEqual(Array.from(first.nonce), Array.from(second.nonce));
});

test('encrypt then decrypt round-trips for empty plaintext', async () => {
  const key = generateKey();
  const { nonce, ciphertext } = await encryptAesGcm(key, new Uint8Array(0));
  const recovered = await decryptAesGcm(key, nonce, ciphertext);
  assert.equal(recovered.length, 0);
});

test('encrypt then decrypt round-trips for a larger multi-chunk-sized plaintext', async () => {
  const key = generateKey();
  const plaintext = crypto.getRandomValues(new Uint8Array(5000));
  const { nonce, ciphertext } = await encryptAesGcm(key, plaintext);
  const recovered = await decryptAesGcm(key, nonce, ciphertext);
  assert.deepEqual(Array.from(recovered), Array.from(plaintext));
});

test('tampering with the ciphertext breaks decryption (AEAD tag catches it)', async () => {
  const key = generateKey();
  const plaintext = new TextEncoder().encode('authenticate me');
  const { nonce, ciphertext } = await encryptAesGcm(key, plaintext);

  const tampered = new Uint8Array(ciphertext);
  tampered[0] ^= 0xff;

  await assert.rejects(() => decryptAesGcm(key, nonce, tampered));
});

test('decrypting with the wrong key fails', async () => {
  const key = generateKey();
  const wrongKey = generateKey();
  const plaintext = new TextEncoder().encode('secret');
  const { nonce, ciphertext } = await encryptAesGcm(key, plaintext);

  await assert.rejects(() => decryptAesGcm(wrongKey, nonce, ciphertext));
});
