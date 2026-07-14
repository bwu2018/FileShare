// Extension-driven preview -- exactly two cases (text, image) for v1. Everything else
// falls back to a plain download prompt, no preview attempted. Video is explicitly out
// of scope for v1 (would need a streaming/MediaSource design, not "buffer full file
// then render" like this).
const EXTENSION_MIME_MAP = {
  txt: 'text/plain',
  md: 'text/markdown',
  csv: 'text/csv',
  json: 'application/json',
  log: 'text/plain',
  png: 'image/png',
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  gif: 'image/gif',
  webp: 'image/webp',
  svg: 'image/svg+xml',
};

function extensionOf(fileName) {
  const idx = fileName.lastIndexOf('.');
  if (idx <= 0 || idx === fileName.length - 1) return null;
  return fileName.slice(idx + 1).toLowerCase();
}

export function renderPreview(fileName, bytes) {
  const container = document.createElement('div');
  container.className = 'result-panel';

  const ext = extensionOf(fileName);
  const mime = ext ? EXTENSION_MIME_MAP[ext] : undefined;
  const blob = mime ? new Blob([bytes], { type: mime }) : new Blob([bytes]);
  const objectUrl = URL.createObjectURL(blob);

  if (mime && mime.startsWith('text/')) {
    const pre = document.createElement('pre');
    pre.className = 'preview preview-text';
    pre.textContent = new TextDecoder('utf-8').decode(bytes);
    container.appendChild(pre);
  } else if (mime && mime.startsWith('image/')) {
    const img = document.createElement('img');
    img.className = 'preview preview-image';
    img.src = objectUrl;
    img.alt = fileName;
    container.appendChild(img);
  } else {
    const note = document.createElement('p');
    note.className = 'preview-unsupported';
    note.textContent = `No preview available for "${fileName}" -- download to view.`;
    container.appendChild(note);
  }

  const downloadLink = document.createElement('a');
  downloadLink.href = objectUrl;
  downloadLink.download = fileName;
  downloadLink.className = 'download-button';
  downloadLink.textContent = `Download ${fileName || '(unnamed file)'}`;
  container.appendChild(downloadLink);

  return container;
}
