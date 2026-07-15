// Orchestration: mirrors downloader/pipeline.py::download_from_store combined with
// manifest/publish.py::fetch_manifest's verification steps, but fetches content chunks
// concurrently (bounded pool) rather than downloader/pipeline.py's sequential loop --
// see constants.js's DEFAULT_CONCURRENCY comment for why.
import { queryTxt } from './doh.js';
import { unpackTxtStrings } from './txtPacking.js';
import { decodeChunk } from './encoding.js';
import { sha256Base32, computeChunkAddress } from './hashing.js';
import { decryptAesGcm } from './aead.js';
import { deserializeManifest } from './manifest.js';
import { CHUNKS_LABEL, DEFAULT_CONCURRENCY } from './constants.js';

// Distinct, clear error codes -- mirrors the conceptual shape of core.exceptions'
// DnsStoreError hierarchy without needing a formal JS exception hierarchy. main.js maps
// these to user-facing messages.
function taggedError(code, message) {
  const err = new Error(message);
  err.code = code;
  return err;
}

async function fetchRecord(qname, origin, resolverUrl, notFoundHash) {
  const strings = await queryTxt(`${qname}.${CHUNKS_LABEL}.${origin}`, resolverUrl);
  if (strings === null) {
    throw taggedError('NOT_FOUND', `record not found: ${notFoundHash}`);
  }
  return decodeChunk(unpackTxtStrings(strings));
}

// Fetches every content chunk concurrently (bounded worker pool), but each result is
// stored keyed by its own index -- completion order is not assembly order. Exported
// separately from downloadFromDns so the pool-scheduling logic itself can be
// unit-tested without a real network call, alongside joinChunksInOrder below.
export async function fetchChunksConcurrently(chunkCount, fetchOne, concurrency = DEFAULT_CONCURRENCY) {
  const results = new Map();
  let next = 0;

  async function worker() {
    while (next < chunkCount) {
      const i = next++;
      results.set(i, await fetchOne(i));
    }
  }

  const workerCount = Math.max(1, Math.min(concurrency, chunkCount));
  await Promise.all(Array.from({ length: workerCount }, worker));
  return results;
}

// Joins per-chunk-index results back into the original byte order. Concurrency means
// chunks can *complete* out of order; this guarantees they're *joined* in strict index
// order regardless -- the same ordering guarantee core/pipeline.py::load_plaintext gets
// for free from its sequential loop, reconstructed here explicitly since fetching is no
// longer sequential. Pure and synchronous, so it's independently testable by feeding it
// a Map built out of order.
export function joinChunksInOrder(resultsByIndex) {
  const count = resultsByIndex.size;
  let totalLength = 0;
  for (let i = 0; i < count; i++) {
    const chunk = resultsByIndex.get(i);
    if (!chunk) {
      throw taggedError('INTERNAL', `missing chunk result at index ${i} of ${count}`);
    }
    totalLength += chunk.length;
  }

  const joined = new Uint8Array(totalLength);
  let offset = 0;
  for (let i = 0; i < count; i++) {
    const chunk = resultsByIndex.get(i);
    joined.set(chunk, offset);
    offset += chunk.length;
  }
  return joined;
}

export async function downloadFromDns(origin, pointerHash, keyBytes, resolverUrl) {
  // 1-2: fetch + unpack the manifest pointer record.
  const wrapped = await fetchRecord(pointerHash, origin, resolverUrl, pointerHash);

  // 3: verify the pointer hash matches the wrapped blob's own hash (mirrors
  // manifest/publish.py::fetch_manifest's ChunkHashMismatchError check).
  const recomputedHash = await sha256Base32(wrapped);
  if (recomputedHash !== pointerHash) {
    throw taggedError('HASH_MISMATCH', 'manifest record is corrupted or has been tampered with');
  }

  // 4: decrypt the manifest (manifest_nonce(12B) || ciphertext -- core/constants.py's
  // NONCE_SIZE).
  const manifestNonce = wrapped.slice(0, 12);
  const manifestCiphertext = wrapped.slice(12);
  let serializedManifest;
  try {
    serializedManifest = await decryptAesGcm(keyBytes, manifestNonce, manifestCiphertext);
  } catch {
    throw taggedError('DECRYPT_FAILED', 'wrong key, or the manifest data is corrupted');
  }

  // 5: parse the manifest.
  const manifest = deserializeManifest(serializedManifest);

  // 6: fetch every content chunk concurrently.
  const chunkResults = await fetchChunksConcurrently(manifest.chunkCount, async (i) => {
    const address = await computeChunkAddress(manifest.contentNonce, i);
    return fetchRecord(address, origin, resolverUrl, address);
  });

  // 7: join in strict index order.
  const ciphertext = joinChunksInOrder(chunkResults);

  // 8: final decrypt -- the authoritative integrity check (mirrors DecryptionError
  // being the ultimate authority in core's error-handling design). Deliberately
  // doesn't distinguish "wrong key" from "corrupted chunk data" -- same ambiguity the
  // Python side already accepts.
  let plaintext;
  try {
    plaintext = await decryptAesGcm(keyBytes, manifest.contentNonce, ciphertext);
  } catch {
    throw taggedError('DECRYPT_FAILED', 'wrong key, or file data is corrupted');
  }

  return { fileName: manifest.fileName, plaintext };
}
