// DOM wiring only -- form submit -> upload.js's orchestration -> render the resulting
// share link. No logic that belongs in a pure module lives here.
import { uploadFile } from './upload.js';
import { encodeChunk } from './encoding.js';
import { extensionOf } from './preview.js';

// This webapp only ever talks to one origin -- the live deployment from Phase 5.
const ORIGIN = 'dnsfileshare.com';

const ERROR_MESSAGES = {
  INVALID_UPLOAD: 'That file could not be uploaded -- the request was rejected.',
  AUTH_REQUIRED: 'Uploading requires authentication.',
  RATE_LIMITED: 'Too many uploads right now -- try again in a moment.',
  SERVER_ERROR: 'The server failed to publish this file. Try again in a moment.',
  NETWORK_ERROR: 'The upload request failed. Check your connection and try again.',
};

function messageFor(error) {
  if (error && error.code && ERROR_MESSAGES[error.code]) {
    return ERROR_MESSAGES[error.code];
  }
  return 'Something went wrong.';
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

function shareLinkNode(pointerHash, keyB64) {
  const container = document.createElement('div');
  container.className = 'result-panel';

  const url =
    `https://${ORIGIN}/download/#pointer_hash=${encodeURIComponent(pointerHash)}` +
    `&key=${encodeURIComponent(keyB64)}`;

  const label = document.createElement('p');
  label.textContent =
    "Share this link -- it's the only way to access this file, and nothing else " +
    'stores it:';
  container.appendChild(label);

  const linkBox = document.createElement('input');
  linkBox.type = 'text';
  linkBox.readOnly = true;
  linkBox.value = url;
  linkBox.className = 'share-link';
  container.appendChild(linkBox);

  const copyButton = document.createElement('button');
  copyButton.type = 'button';
  copyButton.textContent = 'Copy link';
  copyButton.addEventListener('click', async () => {
    await navigator.clipboard.writeText(url);
    copyButton.textContent = 'Copied!';
    setTimeout(() => {
      copyButton.textContent = 'Copy link';
    }, 1500);
  });
  container.appendChild(copyButton);

  return container;
}

const form = document.getElementById('upload-form');
form.addEventListener('submit', async (event) => {
  event.preventDefault();

  const fileInput = document.getElementById('file-input');
  const nameInput = document.getElementById('file-name');
  const file = fileInput.files[0];

  if (!file) {
    setResult(statusNode('Choose a file to upload.', 'error'));
    return;
  }

  const fileName = nameInput.value.trim() || file.name;

  // Enforced client-side only -- the backend never sees this file name, it's
  // encrypted inside the manifest before anything leaves the browser (see
  // backend/README.md). A missing extension isn't just cosmetic: preview.js's
  // extension-driven MIME detection silently falls back to no-preview for it, and
  // some browsers handle downloading/opening an extensionless file inconsistently.
  if (!extensionOf(fileName)) {
    setResult(
      statusNode(
        'Please give this file a name with an extension (e.g. "notes.txt" or "photo.png").',
        'error',
      ),
    );
    return;
  }

  setResult(statusNode('Encrypting…', 'status'));

  try {
    const plaintext = new Uint8Array(await file.arrayBuffer());
    const { pointerHash, key } = await uploadFile(fileName, plaintext, {
      onProgress: (current, total) => {
        if (total > 1) {
          setResult(statusNode(`Uploading batch ${current} of ${total}…`, 'status'));
        }
      },
    });
    setResult(shareLinkNode(pointerHash, encodeChunk(key)));
  } catch (e) {
    setResult(statusNode(messageFor(e), 'error'));
    console.error(e);
  }
});
