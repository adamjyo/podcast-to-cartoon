import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";

const rootDir = fileURLToPath(new URL(".", import.meta.url));

export default defineConfig({
  root: fileURLToPath(new URL("./mac", import.meta.url)),
  publicDir: fileURLToPath(new URL("./public", import.meta.url)),
  base: "/",
  resolve: {
    alias: [
      { find: "@/lib/draw", replacement: fileURLToPath(new URL("./mac/draw-stub.ts", import.meta.url)) },
      { find: "@", replacement: fileURLToPath(new URL("./src", import.meta.url)) },
    ],
  },
  plugins: [tailwindcss(), react()],
  build: {
    outDir: fileURLToPath(new URL("./mac/dist", import.meta.url)),
    emptyOutDir: true,
  },
});
