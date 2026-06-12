import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolveFrontendBuildEnvironment } from "./build/environment.js";
import { createSensitiveBundleGuardPlugin } from "./build/sensitiveBundleGuard.js";

const { appEnv } = resolveFrontendBuildEnvironment();
const isProdAppEnv = appEnv === "prod";

export default defineConfig({
  base: "/main/",
  plugins: [react(), createSensitiveBundleGuardPlugin({ enabled: isProdAppEnv })],
  server: {
    fs: {
      allow: [".."]
    },
    proxy: {
      "/main/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true
      }
    }
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./src/test/setup.js"
  }
});
