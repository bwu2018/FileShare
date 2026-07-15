import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { encodeChunk, decodeChunk } from '../encoding.js';

const fixtures = JSON.parse(
  readFileSync(fileURLToPath(new URL('./fixtures.json', import.meta.url)), 'utf8'),
);

test('encodeChunk matches a known base64 vector', () => {
  const bytes = Uint8Array.from(Buffer.from(fixtures.chunk_hash.input_b64, 'base64'));
  assert.equal(encodeChunk(bytes), fixtures.chunk_hash.input_b64);
});

test('decodeChunk then encodeChunk round-trips exactly', () => {
  const original = fixtures.chunk_hash.input_b64;
  assert.equal(encodeChunk(decodeChunk(original)), original);
});

test('encodeChunk then decodeChunk round-trips arbitrary bytes, including a partial-chunk length', () => {
  const bytes = crypto.getRandomValues(new Uint8Array(137)); // not a multiple of 3
  const roundTripped = decodeChunk(encodeChunk(bytes));
  assert.deepEqual(Array.from(roundTripped), Array.from(bytes));
});

test('encodeChunk of empty bytes is an empty string', () => {
  assert.equal(encodeChunk(new Uint8Array(0)), '');
});
