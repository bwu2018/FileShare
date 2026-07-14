// Cross-checked against real core.hashing.compute_chunk_address / compute_chunk_hash
// output from Python -- catches a byte-layout mismatch (e.g. wrong endianness on the
// index) directly, not just internal self-consistency.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { computeChunkAddress, sha256Base32 } from '../hashing.js';

const fixtures = JSON.parse(
  readFileSync(fileURLToPath(new URL('./fixtures.json', import.meta.url)), 'utf8'),
);

test('computeChunkAddress matches Python core.hashing.compute_chunk_address', async () => {
  const nonce = Uint8Array.from(Buffer.from(fixtures.chunk_address.nonce_b64, 'base64'));
  for (const { index, expected_address } of fixtures.chunk_address.cases) {
    const address = await computeChunkAddress(nonce, index);
    assert.equal(address, expected_address, `index=${index}`);
  }
});

test('sha256Base32 matches Python core.hashing.compute_chunk_hash', async () => {
  const input = Uint8Array.from(Buffer.from(fixtures.chunk_hash.input_b64, 'base64'));
  const hash = await sha256Base32(input);
  assert.equal(hash, fixtures.chunk_hash.expected_hash);
});

test('computeChunkAddress is sensitive to index (big-endian uint32, not just any encoding)', async () => {
  const nonce = new Uint8Array(12).fill(1);
  const a0 = await computeChunkAddress(nonce, 0);
  const a1 = await computeChunkAddress(nonce, 1);
  const a256 = await computeChunkAddress(nonce, 256);
  assert.notEqual(a0, a1);
  assert.notEqual(a1, a256);
});
