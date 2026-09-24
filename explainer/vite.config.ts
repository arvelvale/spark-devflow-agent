import { defineConfig } from "vite";

// base: "./" 让构建产物放在任何子路径（仓库 Pages、面板静态目录）都能直接打开
export default defineConfig({
  base: "./",
  server: { port: 5180 },
  build: { outDir: "dist", emptyOutDir: true, chunkSizeWarningLimit: 900 },
});
