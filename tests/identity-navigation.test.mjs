import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
test('masthead identity is static and the Home destination remains available', () => {
  const header = html.match(/<header\b[\s\S]*?<\/header>/)[0];
  assert.match(header, /<span class="site-title">[^<]+<\/span>/);
  assert.doesNotMatch(header, /<a[^>]*class="site-title"/);
  assert.match(header, /<a class="site-home" href="https:\/\/jehlp.net\/"/);
});
