const FORBIDDEN_SOURCE_SEGMENTS = ["/src/mocks/", "/src/test/"];

function normalizeModuleId(moduleId) {
  return String(moduleId || "").replaceAll("\\", "/");
}

export function findForbiddenBundleInputs(bundle) {
  const violations = [];

  for (const [fileName, output] of Object.entries(bundle)) {
    if (output.type !== "chunk") continue;
    for (const moduleId of output.moduleIds || []) {
      const normalizedModuleId = normalizeModuleId(moduleId);
      if (FORBIDDEN_SOURCE_SEGMENTS.some((segment) => normalizedModuleId.includes(segment))) {
        violations.push(`${fileName} includes forbidden module ${normalizedModuleId}`);
      }
    }
  }

  return violations;
}

export function createSensitiveBundleGuardPlugin({ enabled }) {
  return {
    name: "sensitive-bundle-guard",
    generateBundle(_options, bundle) {
      if (!enabled) return;
      const violations = findForbiddenBundleInputs(bundle);
      if (violations.length === 0) return;
      this.error(
        [
          "Production frontend build cannot include src/mocks or src/test modules.",
          ...violations
        ].join("\n")
      );
    }
  };
}
