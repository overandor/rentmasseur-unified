import { cp, mkdir, rm, writeFile } from "node:fs/promises";

await rm("dist", { recursive: true, force: true });
await mkdir("dist/client", { recursive: true });
await mkdir("dist/server", { recursive: true });
await cp("site", "dist/client", { recursive: true });
const worker = `export default {\n  async fetch(request, env) {\n    const response = await env.ASSETS.fetch(request);\n    if (response.status !== 404) return response;\n    const url = new URL(request.url);\n    if (!url.pathname.endsWith('/')) url.pathname += '/';\n    url.pathname += 'index.html';\n    return env.ASSETS.fetch(new Request(url, request));\n  }\n};\n`;
await writeFile("dist/server/index.js", worker);
