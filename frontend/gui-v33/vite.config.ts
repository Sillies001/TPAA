import { defineConfig } from "vite";
import { resolve } from "node:path";

export default defineConfig({
  base: "/ui/",
  build: {
    outDir: resolve(__dirname, "../../src/tpaa_gui/web_dist"),
    emptyOutDir: true,
    assetsDir: "assets",
    sourcemap: false,
    manifest: true,
    cssCodeSplit: true,
    rollupOptions: {
      output: {
        entryFileNames: "assets/[name]-[hash].js",
        chunkFileNames: "assets/[name]-[hash].js",
        assetFileNames: "assets/[name]-[hash][extname]"
      }
    }
  }
});
