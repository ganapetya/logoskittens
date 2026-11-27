import path from "node:path";
import { fileURLToPath } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const root = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "protobufjs/minimal.js": path.join(root, "node_modules/protobufjs/minimal.js"),
    },
  },
  server: {
    host: "0.0.0.0",
    port: 5174,
    fs: { allow: [path.join(root, "..")] },
  },
});
