import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

for (const page of ["index.html", "developers/index.html", "storage/index.html"]) {
  test(`${page} has a complete document`, async () => {
    const html = await readFile(`dist/client/${page}`, "utf8");
    assert.match(html, /<!doctype html>/i);
    assert.match(html, /<title>.+<\/title>/i);
    assert.match(html, /MirrorLease/);
    assert.match(html, /<\/html>/i);
  });
}

test("storage boundary is explicit", async () => {
  const html = await readFile("dist/client/storage/index.html", "utf8");
  assert.match(html, /original/i);
  assert.match(html, /Application Support\/MirrorLease\/leases/);
  assert.match(html, /macOS Keychain/);
  assert.match(html, /Application Support\/MirrorLease\/keys/);
  assert.match(html, /no route that accepts your private file/i);
});

test("developer portal lists every adapter", async () => {
  const html = await readFile("dist/client/developers/index.html", "utf8");
  for (const label of ["Finder right-click", "Local CLI", "Guarded HTTPS", "GPT Action", "MCP", "Disposable email", "Owner approval"]) {
    assert.match(html, new RegExp(label, "i"));
  }
});

test("homepage exposes the real local mechanism", async () => {
  const html = await readFile("dist/client/index.html", "utf8");
  assert.match(html, /python -m mirrorlease_protocol\.local_cli create/);
  assert.match(html, /python -m mirrorlease_protocol\.local_cli serve/);
  assert.match(html, /Application Support\/MirrorLease\/leases/);
  assert.match(html, /Owner approval/i);
  assert.doesNotMatch(html, /Quick Actions/i);
});
