// Orchestration: mirrors core/pipeline.py::store_plaintext combined with
// manifest/pipeline.py::create_manifest, but instead of writing into a ChunkStore
// directly (this webapp has no DNS write credentials -- see backend/README.md), it
// builds the same (hash, payload) records in memory and POSTs them in bounded batches
// to the backend, which performs the actual signed DNS update on the browser's behalf.
import { encryptAesGcm, generateKey } from './aeadEncrypt.js';
import { splitIntoChunks } from './chunking.js';
import { encodeChunk } from './encoding.js';
import { sha256Base32, computeChunkAddress } from './hashing.js';
import { serializeManifest, MANIFEST_VERSION } from './manifest.js';
import { CHUNK_SIZE, DEFAULT_PUBLISH_URL, UPLOAD_BATCH_SIZE } from './constants.js';

// Mirrors download.js's taggedError pattern -- distinct, plain error codes a page
// script can map to user-facing text without needing a formal exception hierarchy.
function taggedError(code, message) {
  const err = new Error(message);
  err.code = code;
  return err;
}

function codeForStatus(status) {
  if (status === 400 || status === 422) return 'INVALID_UPLOAD';
  if (status === 401) return 'AUTH_REQUIRED';
  if (status === 429) return 'RATE_LIMITED';
  if (status === 502) return 'SERVER_ERROR';
  return 'UPLOAD_FAILED';
}

function concatBytes(a, b) {
  const joined = new Uint8Array(a.length + b.length);
  joined.set(a, 0);
  joined.set(b, a.length);
  return joined;
}

// Encrypts + chunks + hashes a file exactly like the Python publish path
// (core.pipeline.store_plaintext + manifest.publish.publish_manifest), but returns the
// resulting records instead of writing them anywhere -- kept separate from the batched
// POSTing below so the pure encode step is independently testable without a network
// call, mirroring how download.js splits fetching from decoding.
export async function buildUploadRecords(fileName, plaintext) {
  const key = generateKey();
  const { nonce: contentNonce, ciphertext } = await encryptAesGcm(key, plaintext);

  const chunks = splitIntoChunks(ciphertext, CHUNK_SIZE);
  const records = [];
  for (let i = 0; i < chunks.length; i++) {
    const hash = await computeChunkAddress(contentNonce, i);
    records.push({ hash, payload: encodeChunk(chunks[i]) });
  }

  const manifestBytes = serializeManifest({
    version: MANIFEST_VERSION,
    fileName,
    fileSize: plaintext.length,
    chunkCount: chunks.length,
    contentNonce,
  });
  const { nonce: manifestNonce, ciphertext: manifestCiphertext } = await encryptAesGcm(
    key,
    manifestBytes,
  );
  const wrapped = concatBytes(manifestNonce, manifestCiphertext);
  const pointerHash = await sha256Base32(wrapped);
  records.push({ hash: pointerHash, payload: encodeChunk(wrapped) });

  return { pointerHash, key, records };
}

// Splits records into fixed-size batches and POSTs each sequentially to the backend --
// sequential, not concurrent, since each batch is one real DNS UPDATE and ordering
// doesn't matter for correctness, only for keeping request count/memory bounded. Kept
// separate from buildUploadRecords so batching/error-mapping is independently testable
// with a stubbed fetch, without needing real WebCrypto output.
export async function postRecordsInBatches(
  records,
  { publishUrl = DEFAULT_PUBLISH_URL, batchSize = UPLOAD_BATCH_SIZE, onProgress, fetchImpl = fetch } = {},
) {
  const batches = [];
  for (let i = 0; i < records.length; i += batchSize) {
    batches.push(records.slice(i, i + batchSize));
  }

  for (let i = 0; i < batches.length; i++) {
    if (onProgress) onProgress(i + 1, batches.length);

    let response;
    try {
      response = await fetchImpl(publishUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ records: batches[i] }),
      });
    } catch (e) {
      throw taggedError('NETWORK_ERROR', `upload request failed: ${e.message}`);
    }

    if (!response.ok) {
      let detail = '';
      try {
        const body = await response.json();
        detail = body.error || '';
      } catch {
        // non-JSON error body -- fall back to the generic message below
      }
      throw taggedError(
        codeForStatus(response.status),
        detail || `upload failed with HTTP ${response.status}`,
      );
    }
  }

  return batches.length;
}

export async function uploadFile(fileName, plaintext, options = {}) {
  const { pointerHash, key, records } = await buildUploadRecords(fileName, plaintext);
  await postRecordsInBatches(records, options);
  return { pointerHash, key };
}
