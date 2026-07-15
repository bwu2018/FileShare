// DOM wiring only -- reads the URL fragment on load -> download.js's orchestration ->
// preview.js's rendering. There is no manual paste-in form here at all: every
// download is reached via a share link produced by uploadPage.js, which carries both
// pointer_hash and key in the fragment, never the query string, so neither value is
// ever sent to the server or written to a server access log.
import { downloadFromDns } from './download.js';
import { renderPreview } from './preview.js';
import { DEFAULT_RESOLVER_URL } from './constants.js';

const ORIGIN = 'dnsfileshare.com';

const ERROR_MESSAGES = {
  NOT_FOUND: 'That file could not be found. The link may be broken.',
  HASH_MISMATCH: 'That record looks corrupted or tampered with.',
  DECRYPT_FAILED: "Could not decrypt -- the link may be broken, or the file data may be corrupted.",
  DnsQueryError: 'The DNS query failed. Try again in a moment.',
};

function messageFor(error) {
  if (error && error.code && ERROR_MESSAGES[error.code]) {
    return ERROR_MESSAGES[error.code];
  }
  if (error && error.constructor && ERROR_MESSAGES[error.constructor.name]) {
    return ERROR_MESSAGES[error.constructor.name];
  }
  return 'Something went wrong.';
}

function base64ToBytes(b64) {
  const binary = atob(b64.trim());
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

function setResult(node) {
  const resultEl = document.getElementById('result');
  resultEl.replaceChildren(node);
}

function statusNode(text, className) {
  const p = document.createElement('p');
  p.className = className;
  p.textContent = text;
  return p;
}

function parseFragment() {
  const params = new URLSearchParams(location.hash.slice(1));
  return { pointerHash: params.get('pointer_hash'), keyB64: params.get('key') };
}

async function run() {
  const { pointerHash, keyB64 } = parseFragment();

  if (!pointerHash || !keyB64) {
    setResult(statusNode("This link is missing its pointer hash or key.", 'error'));
    return;
  }

  let keyBytes;
  try {
    keyBytes = base64ToBytes(keyB64);
  } catch (e) {
    setResult(statusNode("This link's key doesn't look like valid base64.", 'error'));
    console.error(e);
    return;
  }

  setResult(statusNode('Resolving and decrypting…', 'status'));

  try {
    const { fileName, plaintext } = await downloadFromDns(
      ORIGIN,
      pointerHash,
      keyBytes,
      DEFAULT_RESOLVER_URL,
    );
    setResult(renderPreview(fileName, plaintext));
  } catch (e) {
    setResult(statusNode(messageFor(e), 'error'));
    console.error(e);
  }
}

run();
