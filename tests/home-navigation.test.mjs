import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../", import.meta.url);
const home = "<a class=\"site-home\" href=\"https://jehlp.net/\" aria-label=\"Home — jehlp.net\" title=\"Home — jehlp.net\"><span aria-hidden=\"true\">✳</span></a>";

for (const page of ["index.html"]) {
  test(`${page} keeps one native home link beside its header theme control`, async () => {
    const html = await readFile(new URL(page, root), "utf8");
    const header = html.match(/<header\b[^>]*>[\s\S]*?<\/header>/)?.[0];
    assert.ok(header?.includes(home), "home remains in the existing header without JavaScript");
    const pair = header.match(/<span class="site-utility-pair">[\s\S]*?<\/button>\s*<\/span>/)?.[0];
    assert.ok(pair?.includes(home), "home and theme share one utility group");
    assert.match(pair.slice(pair.indexOf(home) + home.length), /^\s*<button\b[^>]*data-theme-toggle\b/);
    assert.equal(html.split(home).length - 1, 1);
    assert.equal((html.match(/class="site-utility-pair"/g) || []).length, 1);
    assert.doesNotMatch(html, /site-home-dock|site-home-clearance/);
    assert.doesNotMatch(html.replace(home, ""), /<a\b[^>]*href="(?:https:\/\/jehlp\.net\/|\/)"/);
    assert.match(html, /src="https:\/\/jehlp\.net\/site-theme\/v2\/theme\.js\?v=20260930-header-home"/);
    assert.match(html, /href="https:\/\/jehlp\.net\/site-theme\/v2\/base\.css\?v=20260930-mobile-header"/);
  });
}
