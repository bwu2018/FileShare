// Mirrors core/chunking.py::split_into_chunks -- pure Uint8Array slicing, always
// emitting at least one chunk (even for empty input), no padding logic needed (base64
// already round-trips a partial final chunk exactly).
import { CHUNK_SIZE } from './constants.js';

export function splitIntoChunks(data, chunkSize = CHUNK_SIZE) {
  if (data.length === 0) {
    return [data];
  }
  const chunks = [];
  for (let i = 0; i < data.length; i += chunkSize) {
    chunks.push(data.slice(i, i + chunkSize));
  }
  return chunks;
}
