import { test } from 'node:test';
import assert from 'node:assert/strict';
import { buildUploadRecords, postRecordsInBatches, uploadFile } from '../upload.js';
import { decodeChunk } from '../encoding.js';
import { computeChunkAddress, sha256Base32 } from '../hashing.js';
import { deserializeManifest } from '../manifest.js';
import { decryptAesGcm } from '../aead.js';
import { UPLOAD_BATCH_SIZE, CHUNK_SIZE, NONCE_SIZE } from '../constants.js';

// Reassembles a fake backend's received records back into plaintext, purely in JS --
// used by multiple tests below to confirm nothing is dropped/corrupted across the
// encrypt -> chunk -> address -> manifest -> (batched POST) pipeline.
async function recoverPlaintext(allRecords, pointerHash, key) {
  const manifestRecord = allRecords.find((r) => r.hash === pointerHash);
  assert.ok(manifestRecord, 'manifest record must be present among the uploaded records');

  const wrapped = decodeChunk(manifestRecord.payload);
  assert.equal(await sha256Base32(wrapped), pointerHash);

  const manifestNonce = wrapped.slice(0, NONCE_SIZE);
  const manifestCiphertext = wrapped.slice(NONCE_SIZE);
  const serializedManifest = await decryptAesGcm(key, manifestNonce, manifestCiphertext);
  const manifest = deserializeManifest(serializedManifest);

  const chunkRecords = allRecords.filter((r) => r.hash !== pointerHash);
  assert.equal(chunkRecords.length, manifest.chunkCount);

  const byAddress = new Map(chunkRecords.map((r) => [r.hash, decodeChunk(r.payload)]));

  let totalLength = 0;
  const ordered = [];
  for (let i = 0; i < manifest.chunkCount; i++) {
    const address = await computeChunkAddress(manifest.contentNonce, i);
    const chunk = byAddress.get(address);
    assert.ok(chunk, `missing chunk at index ${i}`);
    ordered.push(chunk);
    totalLength += chunk.length;
  }

  const ciphertext = new Uint8Array(totalLength);
  let offset = 0;
  for (const chunk of ordered) {
    ciphertext.set(chunk, offset);
    offset += chunk.length;
  }

  return decryptAesGcm(key, manifest.contentNonce, ciphertext);
}

test('buildUploadRecords round-trips through the full JS pipeline with no network', async () => {
  const fileName = 'roundtrip.txt';
  const plaintext = new TextEncoder().encode('the quick brown fox jumps over the lazy dog'.repeat(50));

  const { pointerHash, key, records } = await buildUploadRecords(fileName, plaintext);
  const recovered = await recoverPlaintext(records, pointerHash, key);

  assert.deepEqual(Array.from(recovered), Array.from(plaintext));
});

test('buildUploadRecords handles empty plaintext', async () => {
  const { pointerHash, key, records } = await buildUploadRecords('empty.txt', new Uint8Array(0));
  const recovered = await recoverPlaintext(records, pointerHash, key);
  assert.equal(recovered.length, 0);
});

test('postRecordsInBatches splits large record sets into multiple bounded, ordered requests', async () => {
  const recordCount = UPLOAD_BATCH_SIZE * 2 + 3;
  const records = Array.from({ length: recordCount }, (_, i) => ({ hash: `HASH${i}`, payload: `payload${i}` }));

  const calls = [];
  const fakeFetch = async (_url, options) => {
    calls.push(JSON.parse(options.body).records);
    return { ok: true, json: async () => ({ status: 'ok' }) };
  };

  const batchCount = await postRecordsInBatches(records, { fetchImpl: fakeFetch });

  assert.equal(batchCount, 3);
  assert.equal(calls.length, 3);
  for (const batch of calls) {
    assert.ok(batch.length <= UPLOAD_BATCH_SIZE);
  }
  assert.deepEqual(calls.flat(), records); // nothing dropped, duplicated, or reordered
});

test('postRecordsInBatches calls onProgress with 1-based batch numbers', async () => {
  const records = Array.from({ length: UPLOAD_BATCH_SIZE + 1 }, (_, i) => ({ hash: `H${i}`, payload: 'p' }));
  const progress = [];
  const fakeFetch = async () => ({ ok: true, json: async () => ({}) });

  await postRecordsInBatches(records, {
    fetchImpl: fakeFetch,
    onProgress: (cur, total) => progress.push([cur, total]),
  });

  assert.deepEqual(progress, [[1, 2], [2, 2]]);
});

test('postRecordsInBatches maps a failed batch to a tagged error, without sending later batches', async () => {
  const records = Array.from({ length: UPLOAD_BATCH_SIZE + 1 }, (_, i) => ({ hash: `H${i}`, payload: 'p' }));
  let callCount = 0;
  const fakeFetch = async () => {
    callCount++;
    return { ok: false, status: 429, json: async () => ({ error: 'rate limit exceeded' }) };
  };

  await assert.rejects(
    () => postRecordsInBatches(records, { fetchImpl: fakeFetch }),
    (err) => {
      assert.equal(err.code, 'RATE_LIMITED');
      return true;
    },
  );
  assert.equal(callCount, 1); // stopped after the first failing batch, didn't try batch 2
});

test('postRecordsInBatches maps a network failure to NETWORK_ERROR', async () => {
  const fakeFetch = async () => {
    throw new Error('connection refused');
  };

  await assert.rejects(
    () => postRecordsInBatches([{ hash: 'H', payload: 'p' }], { fetchImpl: fakeFetch }),
    (err) => {
      assert.equal(err.code, 'NETWORK_ERROR');
      return true;
    },
  );
});

// Regression test for the 65,535-byte RFC 2136 UPDATE message ceiling identified
// during planning: a real file large enough to need many chunks must be split into
// multiple sequential, bounded requests -- exactly mirroring what backend/'s own
// large-file test proves server-side. This must fail loudly if a future change
// accidentally reverts uploadFile() to sending everything in one request.
test('uploadFile with a large real file issues multiple bounded batches and reassembles exactly', async () => {
  const plaintext = crypto.getRandomValues(new Uint8Array(CHUNK_SIZE * (UPLOAD_BATCH_SIZE * 2 + 3)));

  const calls = [];
  const fakeFetch = async (_url, options) => {
    calls.push(JSON.parse(options.body).records);
    return { ok: true, json: async () => ({ status: 'ok' }) };
  };

  const { pointerHash, key } = await uploadFile('large.bin', plaintext, { fetchImpl: fakeFetch });

  assert.ok(calls.length > 1, `expected multiple batches, got ${calls.length}`);
  for (const batch of calls) {
    assert.ok(batch.length <= UPLOAD_BATCH_SIZE);
  }

  const recovered = await recoverPlaintext(calls.flat(), pointerHash, key);
  assert.deepEqual(Array.from(recovered), Array.from(plaintext));
});
