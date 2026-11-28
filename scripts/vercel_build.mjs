// Vercel build for the static frontend (Build Output API v3).
// Copies src/wasl/static to the same URLs the FastAPI app serves (/ and /static/*), and when WASL_API_URL is set
// (e.g. https://<user>-wasl.hf.space) proxies /api/* to that backend, so app.js keeps using same-origin /api paths
// and no CORS is needed. Set WASL_API_URL in Vercel > Project > Settings > Environment Variables, then redeploy.
import { cpSync, mkdirSync, rmSync, writeFileSync } from "node:fs";

const out = ".vercel/output";
const api = (process.env.WASL_API_URL || "").trim().replace(/\/+$/, "");
if (api && !/^https:\/\/[^\s/]+$/.test(api)) throw new Error(`WASL_API_URL must be an https origin, got: ${api}`);

rmSync(out, { recursive: true, force: true });
mkdirSync(`${out}/static/static`, { recursive: true });
cpSync("src/wasl/static", `${out}/static/static`, { recursive: true });
cpSync("src/wasl/static/index.html", `${out}/static/index.html`);

const routes = [
  { src: "^/static/portfolio/(.*)$", headers: { "Cache-Control": "public, max-age=604800, immutable" }, continue: true },
  ...(api ? [{ src: "^/api/(.*)$", dest: `${api}/api/$1` }] : []),
  { handle: "filesystem" },
];
writeFileSync(`${out}/config.json`, JSON.stringify({ version: 3, routes }, null, 2));
console.log(api ? `frontend built; /api/* -> ${api}` : "frontend built; WASL_API_URL not set, /api/* has no backend yet");
