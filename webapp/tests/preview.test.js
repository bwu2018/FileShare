import { test } from 'node:test';
import assert from 'node:assert/strict';
import { extensionOf } from '../preview.js';

test('extensionOf returns the lowercased extension', () => {
  assert.equal(extensionOf('photo.PNG'), 'png');
  assert.equal(extensionOf('notes.txt'), 'txt');
});

test('extensionOf returns null for a file with no extension', () => {
  assert.equal(extensionOf('README'), null);
  assert.equal(extensionOf('Makefile'), null);
});

test('extensionOf returns null for a dotfile with no real extension', () => {
  assert.equal(extensionOf('.gitignore'), null);
});

test('extensionOf returns null for a trailing dot with nothing after it', () => {
  assert.equal(extensionOf('file.'), null);
});

test('extensionOf handles multiple dots by using the last segment', () => {
  assert.equal(extensionOf('archive.tar.gz'), 'gz');
});
