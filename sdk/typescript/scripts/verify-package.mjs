#!/usr/bin/env node
/**
 * Purpose: verify the TypeScript SDK package surface without network access.
 * Governance scope: private package metadata, generation command contract,
 * dependency pins, and OpenAPI generator configuration presence.
 * Dependencies: Node.js standard library, package.json, openapi-ts.config.ts.
 * Invariants: SDK package remains private, unlicensed for publication, and
 * generation points at the governed OpenAPI source and local src output.
 */

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const sdkRoot = dirname(here);
const packagePath = join(sdkRoot, "package.json");
const configPath = join(sdkRoot, "openapi-ts.config.ts");

const packageJson = JSON.parse(readFileSync(packagePath, "utf8"));
const configText = readFileSync(configPath, "utf8");
const errors = [];

function requireEqual(actual, expected, label) {
  if (actual !== expected) {
    errors.push(`${label} expected ${JSON.stringify(expected)} got ${JSON.stringify(actual)}`);
  }
}

function requireContains(value, needle, label) {
  if (typeof value !== "string" || !value.includes(needle)) {
    errors.push(`${label} must contain ${needle}`);
  }
}

requireEqual(packageJson.name, "@mullusi/client", "package name");
requireEqual(packageJson.private, true, "package private");
requireEqual(packageJson.license, "UNLICENSED", "package license");
requireEqual(packageJson.type, "module", "package type");
requireContains(packageJson.scripts?.generate, "../openapi/mullu.openapi.json", "generate script");
requireContains(packageJson.scripts?.generate, "./src", "generate script");
requireContains(packageJson.scripts?.generate, "./openapi-ts.config.ts", "generate script");
requireEqual(packageJson.scripts?.verify, "node ./scripts/verify-package.mjs", "verify script");
requireContains(packageJson.devDependencies?.["@hey-api/openapi-ts"], "^0.78.0", "openapi-ts dependency");
requireContains(packageJson.devDependencies?.["@hey-api/client-fetch"], "^0.10.0", "client-fetch dependency");
requireContains(configText, "@hey-api/client-fetch", "OpenAPI generator config");

if (errors.length > 0) {
  for (const error of errors) {
    console.error(error);
  }
  process.exit(1);
}

console.log("typescript sdk package verification passed");
