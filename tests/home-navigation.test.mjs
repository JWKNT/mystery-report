import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const root = new URL("../", import.meta.url);
const dock = "<nav class=\"site-home-dock\" aria-label=\"Site\"><a class=\"site-home\" href=\"https://jehlp.net/\" aria-label=\"Home · jehlp.net\" title=\"Home · jehlp.net\"><span aria-hidden=\"true\">⌂</span></a></nav>";

for (const page of ["index.html"]) {
  test(`${page} keeps one native home dock before its content`, async () => {
    const html = await readFile(new URL(page, root), "utf8");
    const bodyContent = html.split(/<body\b[^>]*>/)[1];
    assert.ok(bodyContent?.trimStart().startsWith(dock), "home remains available without JavaScript");
    assert.equal(html.split(dock).length - 1, 1);
    assert.equal((html.match(/class="site-home-dock"/g) || []).length, 1);
    assert.doesNotMatch(html.replace(dock, ""), /<a\b[^>]*href="(?:https:\/\/jehlp\.net\/|\/)"/);
    assert.match(html, /src="https:\/\/jehlp\.net\/site-theme\/v2\/theme\.js\?v=20260930-home2"/);
    assert.match(html, /href="https:\/\/jehlp\.net\/site-theme\/v2\/base\.css\?v=20260930-home2"/);
  });
}
