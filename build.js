/**
 * Vercel build script for NavTatva frontend.
 *
 * Vercel serves static files only — FastAPI does not run here.
 * This script replaces the __API_URL__ placeholder in index.html
 * with the value of the API_BASE_URL environment variable so the
 * browser knows where to send API calls.
 *
 * Run automatically by Vercel via buildCommand in vercel.json.
 * Safe to run locally too: node build.js
 */

const fs = require("fs");
const path = require("path");

const apiUrl = process.env.API_BASE_URL || "http://localhost:8000";
const indexPath = path.join(__dirname, "app", "static", "index.html");

console.log(`[build] API_BASE_URL = ${apiUrl}`);

let html = fs.readFileSync(indexPath, "utf8");

if (!html.includes("__API_URL__")) {
  console.warn("[build] WARNING: __API_URL__ placeholder not found in index.html — was it already replaced?");
} else {
  html = html.replace(/__API_URL__/g, apiUrl);
  fs.writeFileSync(indexPath, html, "utf8");
  console.log("[build] __API_URL__ replaced successfully in index.html");
}
