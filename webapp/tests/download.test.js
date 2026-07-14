// Tests the parts of download.js that don't need a real network call: the
// concurrent-fetch-but-ordered-join guarantee. Chunks can *complete* out of order under
// concurrency; joinChunksInOrder must still assemble them in strict index order (the
// same guarantee core/pipeline.py::load_plaintext gets for free from its sequential
// loop -- reconstructed explicitly here since fetching is no longer sequential).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { joinChunksInOrder, fetchChunksConcurrently } from '../download.js';

test('joinChunksInOrder assembles chunks by index, not insertion order', () => {
  const results = new Map();
  // Insert deliberately out of order.
  results.set(2, Uint8Array.from([7, 8, 9]));
  results.set(0, Uint8Array.from([1, 2, 3]));
  results.set(1, Uint8Array.from([4, 5, 6]));

  const joined = joinChunksInOrder(results);
  assert.deepEqual(Array.from(joined), [1, 2, 3, 4, 5, 6, 7, 8, 9]);
});

test('joinChunksInOrder handles a single chunk', () => {
  const results = new Map([[0, Uint8Array.from([42])]]);
  assert.deepEqual(Array.from(joinChunksInOrder(results)), [42]);
});

test('joinChunksInOrder throws if an index is missing', () => {
  const results = new Map([[0, Uint8Array.from([1])], [2, Uint8Array.from([3])]]);
  assert.throws(() => joinChunksInOrder(results), /missing chunk result/);
});

test('fetchChunksConcurrently resolves out of completion order but keys results by index', async () => {
  // Chunk 0 resolves slowest, chunk 4 resolves fastest -- proves the pool doesn't
  // assume completion order matches index order.
  const delays = [50, 40, 30, 20, 10];
  const results = await fetchChunksConcurrently(5, async (i) => {
    await new Promise((resolve) => setTimeout(resolve, delays[i]));
    return Uint8Array.from([i]);
  }, 5);

  assert.equal(results.size, 5);
  for (let i = 0; i < 5; i++) {
    assert.deepEqual(Array.from(results.get(i)), [i]);
  }
});

test('fetchChunksConcurrently respects a concurrency cap lower than the chunk count', async () => {
  let inFlight = 0;
  let maxInFlight = 0;

  await fetchChunksConcurrently(10, async (i) => {
    inFlight++;
    maxInFlight = Math.max(maxInFlight, inFlight);
    await new Promise((resolve) => setTimeout(resolve, 5));
    inFlight--;
    return Uint8Array.from([i]);
  }, 3);

  assert.ok(maxInFlight <= 3, `expected max 3 concurrent, saw ${maxInFlight}`);
});
