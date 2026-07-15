// Mirrors tests/core/test_roundtrip.py's chunking-related cases.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { splitIntoChunks } from '../chunking.js';

test('empty data still produces exactly one (empty) chunk', () => {
  const chunks = splitIntoChunks(new Uint8Array(0), 189);
  assert.equal(chunks.length, 1);
  assert.equal(chunks[0].length, 0);
});

test('exact multiple of chunk size produces only full chunks', () => {
  const data = new Uint8Array(189 * 2);
  const chunks = splitIntoChunks(data, 189);
  assert.equal(chunks.length, 2);
  assert.equal(chunks[0].length, 189);
  assert.equal(chunks[1].length, 189);
});

test('partial final chunk keeps the remainder length', () => {
  const data = new Uint8Array(500);
  const chunks = splitIntoChunks(data, 189);
  assert.deepEqual(
    chunks.map((c) => c.length),
    [189, 189, 122],
  );
});

test('chunk order and content are preserved', () => {
  const data = Uint8Array.from({ length: 10 }, (_, i) => i);
  const chunks = splitIntoChunks(data, 3);
  assert.equal(chunks.length, 4);
  assert.deepEqual(Array.from(chunks[0]), [0, 1, 2]);
  assert.deepEqual(Array.from(chunks[1]), [3, 4, 5]);
  assert.deepEqual(Array.from(chunks[2]), [6, 7, 8]);
  assert.deepEqual(Array.from(chunks[3]), [9]);
});

test('defaults to CHUNK_SIZE when no size is given', async () => {
  const { CHUNK_SIZE } = await import('../constants.js');
  const data = new Uint8Array(CHUNK_SIZE + 1);
  const chunks = splitIntoChunks(data);
  assert.equal(chunks.length, 2);
  assert.equal(chunks[0].length, CHUNK_SIZE);
  assert.equal(chunks[1].length, 1);
});
