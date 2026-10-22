/**
 * Vercel build script for NavTatva frontend.
 *
 * index.html references all assets as /static/... because FastAPI serves
 * them under that prefix. On Vercel there is no FastAPI, so we replicate
 * the same structure inside dist/:
 *
 *   dist/
 *     index.html          ← served at /
 *     static/             ← served at /static/
 *       app.js
 *       style.css
 *       vendor/
 *         leaflet/
 *
 * __API_URL__ in index.html is replaced with API_BASE_URL env var.
 * __V__ cache-bust stamp is left as-is (harmless literal string on Vercel).
 */

const fs   = require("fs");
const path = require("path");

const SRC       = path.join(__dirname, "app", "static");
const DIST      = path.join(__dirname, "dist");
const DIST_STATIC = path.join(DIST, "static");

const apiUrl = (process.env.API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
console.log(`[build] API_BASE_URL = ${apiUrl}`);

// ── recreate dist ──────────────────────────────────────────────────────────
if (fs.existsSync(DIST)) fs.rmSync(DIST, { recursive: true, force: true });
fs.mkdirSync(DIST_STATIC, { recursive: true });

// ── recursive copy helper ──────────────────────────────────────────────────
function copyDir(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const srcPath  = path.join(src,  entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      copyDir(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

// Copy everything (app.js, style.css, vendor/) into dist/static/
copyDir(SRC, DIST_STATIC);
console.log("[build] Copied app/static → dist/static");

// Move index.html up to dist/ root (Vercel serves / from outputDirectory root)
fs.renameSync(
  path.join(DIST_STATIC, "index.html"),
  path.join(DIST, "index.html")
);
console.log("[build] Moved index.html → dist/index.html");

// ── patch index.html ───────────────────────────────────────────────────────
const indexPath = path.join(DIST, "index.html");
let html = fs.readFileSync(indexPath, "utf8");

if (!html.includes("__API_URL__")) {
  console.warn("[build] WARNING: __API_URL__ placeholder not found — already replaced?");
} else {
  html = html.replace(/__API_URL__/g, apiUrl);
  fs.writeFileSync(indexPath, html, "utf8");
  console.log(`[build] __API_URL__ → ${apiUrl} ✓`);
}

console.log("[build] Done. Output in dist/");
