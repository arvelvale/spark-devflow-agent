import { defineConfig } from "vite";

// 开发时把 /api 代理到本机 9000（节点上的面板后端经 SSH 隧道映射过来，见 README）
export default defineConfig({
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://127.0.0.1:9000", changeOrigin: false } },
  },
  build: { outDir: "dist", emptyOutDir: true, sourcemap: false, chunkSizeWarningLimit: 900 },
});
