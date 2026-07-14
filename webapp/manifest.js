// Mirrors manifest/serialization.py::deserialize_manifest's CURRENT byte layout --
// confirmed directly against that file's source, not the superseded phase2.md
// description (no root_hash field; header is 25 bytes, not 81):
//   [0]      version       uint8
//   [1:9]    file_size     uint64 BE
//   [9:13]   chunk_count   uint32 BE
//   [13:25]  content_nonce 12 raw bytes
//   [25:27]  name_len      uint16 BE
//   [27:27+name_len]  file_name, UTF-8
const MANIFEST_HEADER_SIZE = 25;
const MANIFEST_VERSION = 1;

export class ManifestFormatError extends Error {}

export function deserializeManifest(bytes) {
  const prefixSize = MANIFEST_HEADER_SIZE + 2; // +2 for the name_len field itself
  if (bytes.length < prefixSize) {
    throw new ManifestFormatError(
      `Manifest data truncated: ${bytes.length} bytes < minimum ${prefixSize}`,
    );
  }

  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);

  const version = view.getUint8(0);
  if (version !== MANIFEST_VERSION) {
    throw new ManifestFormatError(`unsupported manifest version: ${version}`);
  }

  // file_size is a real uint64 -- read as BigInt for no precision loss, then convert.
  // Safe to Number()-cast: realistic file sizes are far below Number.MAX_SAFE_INTEGER.
  const fileSize = Number(view.getBigUint64(1, false));
  const chunkCount = view.getUint32(9, false);
  const contentNonce = bytes.slice(13, 25);

  const nameLen = view.getUint16(25, false);
  if (bytes.length !== prefixSize + nameLen) {
    throw new ManifestFormatError(
      `Manifest data length ${bytes.length} does not match expected=${prefixSize + nameLen}`,
    );
  }

  const nameBytes = bytes.slice(27, 27 + nameLen);
  const fileName = new TextDecoder('utf-8', { fatal: true }).decode(nameBytes);

  return { version, fileName, fileSize, chunkCount, contentNonce };
}
