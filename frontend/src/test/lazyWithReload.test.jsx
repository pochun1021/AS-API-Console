import { describe, expect, test, vi, beforeEach } from "vitest";
import { createLazyLoader } from "../utils/lazyWithReload";

describe("lazyWithReload", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });

  test("reloads once when dynamic import fails", async () => {
    const reload = vi.fn();
    const importer = vi.fn().mockRejectedValue(new TypeError("Failed to fetch dynamically imported module"));
    const load = createLazyLoader("ModelsPage", importer, reload);

    load();
    await Promise.resolve();

    expect(reload).toHaveBeenCalledTimes(1);
    expect(window.sessionStorage.getItem("lazy-reload:ModelsPage")).toBe("1");
  });

  test("does not reload repeatedly for the same failed module", async () => {
    const reload = vi.fn();
    const importer = vi.fn().mockRejectedValue(new TypeError("Failed to fetch dynamically imported module"));
    window.sessionStorage.setItem("lazy-reload:ModelsPage", "1");
    const load = createLazyLoader("ModelsPage", importer, reload);

    await expect(load()).rejects.toThrow("Failed to fetch dynamically imported module");

    expect(reload).not.toHaveBeenCalled();
  });

  test("clears reload marker after a successful import", async () => {
    const importer = vi.fn().mockResolvedValue({ default: () => null });
    window.sessionStorage.setItem("lazy-reload:ModelsPage", "1");
    const load = createLazyLoader("ModelsPage", importer, vi.fn());

    await expect(load()).resolves.toEqual({ default: expect.any(Function) });
    expect(window.sessionStorage.getItem("lazy-reload:ModelsPage")).toBeNull();
  });
});
