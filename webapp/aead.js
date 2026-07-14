// AES-256-GCM decrypt via WebCrypto. Combined ciphertext+tag form (tag appended to
// ciphertext) matches Python's `cryptography` AESGCM output directly -- verified
// empirically (Python-encrypted vectors decrypt correctly here with no reformatting)
// before writing this, not assumed.
export async function decryptAesGcm(keyBytes, nonce, ciphertextWithTag) {
  const cryptoKey = await crypto.subtle.importKey(
    'raw',
    keyBytes,
    { name: 'AES-GCM' },
    false,
    ['decrypt'],
  );
  const plaintext = await crypto.subtle.decrypt(
    { name: 'AES-GCM', iv: nonce },
    cryptoKey,
    ciphertextWithTag,
  );
  return new Uint8Array(plaintext);
}
