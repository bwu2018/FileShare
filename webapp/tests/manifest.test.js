// Cross-checked against real manifest.serialization.serialize_manifest(...) output
// from Python -- the exact thing that matters for this file (byte offsets, endianness,
// UTF-8 name handling) can't be caught by self-consistency alone.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { deserializeManifest, ManifestFormatError } from '../manifest.js';

const fixtures = JSON.parse(
  readFileSync(fileURLToPath(new URL('./fixtures.json', import.meta.url)), 'utf8'),
);

test('deserializeManifest matches real Python-serialized manifests', () => {
  for (const expected of fixtures.manifest) {
    const bytes = Uint8Array.from(Buffer.from(expected.serialized_b64, 'base64'));
    const manifest = deserializeManifest(bytes);

    assert.equal(manifest.version, expected.version);
    assert.equal(manifest.fileName, expected.file_name);
    assert.equal(manifest.fileSize, expected.file_size);
    assert.equal(manifest.chunkCount, expected.chunk_count);
    assert.equal(
      Buffer.from(manifest.contentNonce).toString('base64'),
      expected.content_nonce_b64,
    );
  }
});

test('deserializeManifest handles unicode file names (multi-byte UTF-8)', () => {
  const withUnicode = fixtures.manifest.find((m) => /[^\x00-\x7f]/.test(m.file_name));
  assert.ok(withUnicode, 'fixture set should include a unicode file_name case');
  const bytes = Uint8Array.from(Buffer.from(withUnicode.serialized_b64, 'base64'));
  assert.equal(deserializeManifest(bytes).fileName, withUnicode.file_name);
});

test('deserializeManifest handles empty file_name', () => {
  const empty = fixtures.manifest.find((m) => m.file_name === '');
  assert.ok(empty, 'fixture set should include an empty file_name case');
  const bytes = Uint8Array.from(Buffer.from(empty.serialized_b64, 'base64'));
  assert.equal(deserializeManifest(bytes).fileName, '');
});

test('deserializeManifest rejects truncated data', () => {
  const tooShort = new Uint8Array(10);
  assert.throws(() => deserializeManifest(tooShort), ManifestFormatError);
});

test('deserializeManifest rejects unsupported version', () => {
  const base = Uint8Array.from(Buffer.from(fixtures.manifest[0].serialized_b64, 'base64'));
  const tampered = new Uint8Array(base);
  tampered[0] = 99;
  assert.throws(() => deserializeManifest(tampered), ManifestFormatError);
});

test('deserializeManifest rejects a name_len that overruns the actual data', () => {
  const base = Uint8Array.from(Buffer.from(fixtures.manifest[0].serialized_b64, 'base64'));
  const tampered = new Uint8Array(base);
  // Bump name_len (big-endian uint16 at offset 25) far beyond the real remaining bytes.
  tampered[25] = 0xff;
  tampered[26] = 0xff;
  assert.throws(() => deserializeManifest(tampered), ManifestFormatError);
});
