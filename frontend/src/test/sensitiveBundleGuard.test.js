import { describe, expect, test } from "vitest";

import { findForbiddenBundleInputs } from "../../build/sensitiveBundleGuard.js";

describe("findForbiddenBundleInputs", () => {
  test("flags mock and test modules in production bundles", () => {
    const violations = findForbiddenBundleInputs({
      "assets/index.js": {
        type: "chunk",
        moduleIds: [
          "/workspace/frontend/src/main.jsx",
          "/workspace/frontend/src/mocks/mockApiProvider.js",
          "/workspace/frontend/src/test/setup.js"
        ]
      }
    });

    expect(violations).toEqual([
      "assets/index.js includes forbidden module /workspace/frontend/src/mocks/mockApiProvider.js",
      "assets/index.js includes forbidden module /workspace/frontend/src/test/setup.js"
    ]);
  });

  test("ignores normal application modules", () => {
    const violations = findForbiddenBundleInputs({
      "assets/index.js": {
        type: "chunk",
        moduleIds: ["/workspace/frontend/src/main.jsx", "/workspace/frontend/src/api/client.js"]
      }
    });

    expect(violations).toEqual([]);
  });
});
