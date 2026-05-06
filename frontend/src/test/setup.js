import "@testing-library/jest-dom/vitest";
import { beforeEach } from "vitest";
import { setApiProvider } from "../api/client";
import { mockApiProvider } from "../mocks/mockApiProvider";

Object.defineProperty(window, "isSecureContext", {
  value: true,
  configurable: true
});

beforeEach(() => {
  setApiProvider(mockApiProvider);
  mockApiProvider.resetForTests();
});
