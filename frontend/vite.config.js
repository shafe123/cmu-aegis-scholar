import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import fs from "node:fs";

const certPath = process.env.VITE_SSL_CERT;
const keyPath = process.env.VITE_SSL_KEY;

const https =
  certPath &&
  keyPath &&
  fs.existsSync(certPath) &&
  fs.existsSync(keyPath)
    ? {
        cert: fs.readFileSync(certPath),
        key: fs.readFileSync(keyPath),
      }
    : false;

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    https,
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./src/tests/setup.js",
  },
});
