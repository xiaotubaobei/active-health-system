import { defineConfig, loadEnv } from "vite";
import vue from "@vitejs/plugin-vue";
import { fileURLToPath } from "node:url";
import { prepare } from "./scripts/prepare-pose-assets.mjs";

export default defineConfig(async ({ mode, isPreview }) => {
  const root = fileURLToPath(new URL('.', import.meta.url));
  const env = loadEnv(mode, root, 'VITE_');
  if (!isPreview) {
    await prepare({ root, variant: (env.VITE_POSE_LANDMARKER || 'full').toLowerCase() });
  }
  return {
  plugins: [vue()],
  optimizeDeps: {
    exclude: ["@mediapipe/tasks-vision"],
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ""),
      },
    },
  },
  };
});
