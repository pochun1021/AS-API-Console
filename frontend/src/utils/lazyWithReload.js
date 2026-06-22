import { lazy } from "react";

function isDynamicImportFailure(error) {
  const message = String(error?.message || error || "");
  return (
    message.includes("Failed to fetch dynamically imported module") ||
    message.includes("Importing a module script failed")
  );
}

function buildReloadKey(moduleKey) {
  return `lazy-reload:${moduleKey}`;
}

function markReloadAttempted(moduleKey) {
  window.sessionStorage.setItem(buildReloadKey(moduleKey), "1");
}

function hasReloadAttempted(moduleKey) {
  return window.sessionStorage.getItem(buildReloadKey(moduleKey)) === "1";
}

function clearReloadAttempt(moduleKey) {
  window.sessionStorage.removeItem(buildReloadKey(moduleKey));
}

export function createLazyLoader(moduleKey, importer, reload = () => window.location.reload()) {
  return async () => {
    try {
      const module = await importer();
      clearReloadAttempt(moduleKey);
      return module;
    } catch (error) {
      if (isDynamicImportFailure(error) && !hasReloadAttempted(moduleKey)) {
        markReloadAttempted(moduleKey);
        reload();
        return new Promise(() => {});
      }
      throw error;
    }
  };
}

export function lazyWithReload(moduleKey, importer) {
  return lazy(createLazyLoader(moduleKey, importer));
}
