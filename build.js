/**
 * Vercel build script for NavTatva frontend.
 *
 * Copies app/static → dist, replacing __API_URL__ in index.html
 * with the API_BASE_URL environment variable value.
 * Vercel then serves the dist folder as the output directory.
 */

const fs   = require("fs");
const path = require("path");

const SRC  = path.join(__dirname, "app", "static");
const DIST = path.join(__dirname, "dist");

const apiUrl = (process.env.API_BASE_URL || "http://localhost:8000").replace(/\/$/, "");
console.log(`[build] API_BASE_URL = ${apiUrl}`);

// ── recreate dist ──────────────────────────────────────────────────────────
if (fs.existsSync(DIST)) fs.rmSync(DIST, { recursive: true, force: true });
fs.mkdirSync(DIST, { recursive: true });

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

copyDir(SRC, DIST);
console.log("[build] Copied app/static → dist");

// ── patch index.html ───────────────────────────────────────────────────────
const indexPath = path.join(DIST, "index.html");
let html = fs.readFileSync(indexPath, "utf8");

if (!html.includes("__API_URL__")) {
  console.warn("[build] WARNING: __API_URL__ placeholder not found — already replaced?");
} else {
  html = html.replace(/__API_URL__/g, apiUrl);
  fs.writeFileSync(indexPath, html, "utf8");
  console.log("[build] __API_URL__ injected into dist/index.html ✓");
}
