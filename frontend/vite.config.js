import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolveFrontendBuildEnvironment } from "./build/environment.js";
import { createSensitiveBundleGuardPlugin } from "./build/sensitiveBundleGuard.js";

const { appEnv } = resolveFrontendBuildEnvironment();
const isProdAppEnv = appEnv === "prod";

function isRouterVendor(id) {
  return (
    id.includes("/react-router/")
    || id.includes("\\react-router\\")
    || id.includes("/react-router-dom/")
    || id.includes("\\react-router-dom\\")
    || id.includes("/@remix-run/router/")
    || id.includes("\\@remix-run\\router\\")
    || id.includes("/history/")
    || id.includes("\\history\\")
  );
}

function isMuiCoreVendor(id) {
  return (
    id.includes("/@mui/material/")
    || id.includes("\\@mui\\material\\")
    || id.includes("/@mui/system/")
    || id.includes("\\@mui\\system\\")
    || id.includes("/@mui/icons-material/")
    || id.includes("\\@mui\\icons-material\\")
    || id.includes("/@mui/utils/")
    || id.includes("\\@mui\\utils\\")
    || id.includes("/@mui/private-theming/")
    || id.includes("\\@mui\\private-theming\\")
    || id.includes("/@mui/styled-engine/")
    || id.includes("\\@mui\\styled-engine\\")
    || id.includes("/@emotion/")
    || id.includes("\\@emotion\\")
  );
}

function isDataGridVendor(id) {
  return (
    id.includes("/@mui/x-data-grid/")
    || id.includes("\\@mui\\x-data-grid\\")
    || id.includes("/@mui/x-internals/")
    || id.includes("\\@mui\\x-internals\\")
    || id.includes("/@mui/x-virtualizer/")
    || id.includes("\\@mui\\x-virtualizer\\")
  );
}

function isChartsVendor(id) {
  return (
    id.includes("/@mui/x-charts/")
    || id.includes("\\@mui\\x-charts\\")
    || id.includes("/d3-")
    || id.includes("\\d3-")
    || id.includes("/internmap/")
    || id.includes("\\internmap\\")
    || id.includes("/robust-predicates/")
    || id.includes("\\robust-predicates\\")
  );
}

function isDateUiVendor(id) {
  return (
    id.includes("/@mui/x-date-pickers/")
    || id.includes("\\@mui\\x-date-pickers\\")
    || id.includes("/react-day-picker/")
    || id.includes("\\react-day-picker\\")
    || id.includes("/dayjs/")
    || id.includes("\\dayjs\\")
    || id.includes("/date-fns/")
    || id.includes("\\date-fns\\")
  );
}

export default defineConfig({
  base: "/main/",
  plugins: [react(), createSensitiveBundleGuardPlugin({ enabled: isProdAppEnv })],
  build: {
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) {
            return undefined;
          }
          if (isRouterVendor(id)) {
            return "router";
          }
          if (isMuiCoreVendor(id)) {
            return "mui-core";
          }
          if (isDataGridVendor(id)) {
            return "mui-data-grid";
          }
          if (isChartsVendor(id)) {
            return "mui-charts";
          }
          if (isDateUiVendor(id)) {
            return "date-ui";
          }
          return undefined;
        }
      }
    }
  },
  server: {
    fs: {
      allow: [".."]
    },
    proxy: {
      "/main/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true
      },
      "/main/login": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true
      },
      "/main/auth": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true
      },
      "/main/logout": {
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
