// Mirrors tests/zonegen/test_txt_packing.py's boundary cases on the Python side, and
// exercises the small/medium/large size tiers used for manual verification
// (TXT_STRING_MAX_LEN=255 in zonegen/constants.py, CHUNK_SIZE=1200 in
// core/constants.py).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { unpackTxtStrings } from '../txtPacking.js';

test('unpackTxtStrings joins a single string unchanged (small tier: 1 string)', () => {
  assert.equal(unpackTxtStrings(['hello world']), 'hello world');
});

test('unpackTxtStrings joins multiple strings in order (medium tier: ~5 strings)', () => {
  const parts = Array.from({ length: 5 }, (_, i) => 'x'.repeat(255) + i);
  const expected = parts.join('');
  assert.equal(unpackTxtStrings(parts), expected);
});

test('unpackTxtStrings reconstructs an exact full-chunk payload (large tier: 7 strings, 1600 chars total)', () => {
  // CHUNK_SIZE=1200 base64-encodes to exactly 1600 chars (core/constants.py);
  // TXT_STRING_MAX_LEN=255 (zonegen/constants.py) -> ceil(1600/255) = 7 strings.
  const payload = Array.from({ length: 1600 }, (_, i) => String.fromCharCode(65 + (i % 26))).join('');
  const parts = [];
  for (let i = 0; i < payload.length; i += 255) {
    parts.push(payload.slice(i, i + 255));
  }
  assert.equal(parts.length, 7);
  assert.equal(unpackTxtStrings(parts), payload);
});

test('unpackTxtStrings on an empty list returns an empty string', () => {
  assert.equal(unpackTxtStrings([]), '');
});

test('unpackTxtStrings does not add separators between strings', () => {
  assert.equal(unpackTxtStrings(['ab', 'cd', 'ef']), 'abcdef');
});
