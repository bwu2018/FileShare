// DOM wiring only -- form submit -> download.js's orchestration -> preview.js's
// rendering. No logic that belongs in a pure module lives here.
import { downloadFromDns } from './download.js';
import { renderPreview } from './preview.js';
import { DEFAULT_RESOLVER_URL } from './constants.js';

// This webapp only ever talks to one origin -- the live deployment from Phase 5.
const ORIGIN = 'dnsfileshare.com';

// Maps download.js's error codes to short, plain user-facing text. Full detail always
// goes to the console for debugging; on-page text stays deliberately non-technical.
const ERROR_MESSAGES = {
  NOT_FOUND: 'That file could not be found. Double-check the pointer hash.',
  HASH_MISMATCH: 'That record looks corrupted or tampered with.',
  DECRYPT_FAILED: 'Could not decrypt -- check the key, or the file data may be corrupted.',
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

const form = document.getElementById('download-form');
form.addEventListener('submit', async (event) => {
  event.preventDefault();

  const pointerHash = document.getElementById('pointer-hash').value.trim();
  const keyB64 = document.getElementById('key').value.trim();

  if (!pointerHash || !keyB64) {
    setResult(statusNode('Enter both the pointer hash and the key.', 'error'));
    return;
  }

  let keyBytes;
  try {
    keyBytes = base64ToBytes(keyB64);
  } catch (e) {
    setResult(statusNode("The key doesn't look like valid base64.", 'error'));
    console.error(e);
    return;
  }

  setResult(statusNode('Resolving and decrypting…', 'status'));

  try {
    const { fileName, plaintext } = await downloadFromDns(ORIGIN, pointerHash, keyBytes, DEFAULT_RESOLVER_URL);
    setResult(renderPreview(fileName, plaintext));
  } catch (e) {
    setResult(statusNode(messageFor(e), 'error'));
    console.error(e);
  }
});
