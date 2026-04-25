import { defineConfig } from "@hey-api/openapi-ts";

export default defineConfig({
  input: "../openapi/mullu.openapi.json",
  output: {
    path: "./src",
    format: "prettier",
    lint: "eslint",
  },
  client: "@hey-api/client-fetch",
  schemas: true,
  services: true,
  types: true,
});
