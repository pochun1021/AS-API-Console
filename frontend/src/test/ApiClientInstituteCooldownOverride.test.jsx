import { afterEach, expect, test, vi } from "vitest";
import { apiClient, setApiProvider } from "../api/client";

const auth = {
  account: "john.admin",
  name: "John Admin",
  email: "john.admin@company.com",
  department: "Security",
  sysid: 1,
  role: "admin"
};

afterEach(() => {
  window.history.replaceState({}, "", "/");
});

test("dev query string overrides institute sync status", async () => {
  const provider = {
    listInstitutes: vi.fn(),
    getInstituteSyncStatus: vi.fn(),
    syncInstitutes: vi.fn()
  };
  setApiProvider(provider);
  window.history.replaceState({}, "", "/?mockInstituteCooldown=1");

  const result = await apiClient.getInstituteSyncStatus(auth);

  expect(result.status).toBe("idle");
  expect(result.retry_after_seconds).toBe(75);
  expect(typeof result.next_allowed_at).toBe("string");
  expect(provider.getInstituteSyncStatus).not.toHaveBeenCalled();
});

test("dev query string overrides institute sync action with cooldown error", async () => {
  const provider = {
    listInstitutes: vi.fn(),
    getInstituteSyncStatus: vi.fn(),
    syncInstitutes: vi.fn()
  };
  setApiProvider(provider);
  window.history.replaceState({}, "", "/?mockInstituteCooldown=45");

  await expect(apiClient.syncInstitutes(auth)).rejects.toMatchObject({
    status: 429,
    payload: {
      error: {
        code: "INSTITUTE_SYNC_COOLDOWN"
      },
      retry_after_seconds: 45
    }
  });
  expect(provider.syncInstitutes).not.toHaveBeenCalled();
});

test("dev query string overrides institute list to avoid backend dependency", async () => {
  const provider = {
    listInstitutes: vi.fn(),
    getInstituteSyncStatus: vi.fn(),
    syncInstitutes: vi.fn()
  };
  setApiProvider(provider);
  window.history.replaceState({}, "", "/?mockInstituteCooldown=1");

  const result = await apiClient.listInstitutes(auth);

  expect(result).toEqual({ items: [], total: 0 });
  expect(provider.listInstitutes).not.toHaveBeenCalled();
});

test("dev institute cooldown keeps a stable countdown window across calls", async () => {
  vi.useFakeTimers();
  const provider = {
    listInstitutes: vi.fn(),
    getInstituteSyncStatus: vi.fn(),
    syncInstitutes: vi.fn()
  };
  setApiProvider(provider);
  window.history.replaceState({}, "", "/?mockInstituteCooldown=45");

  const first = await apiClient.getInstituteSyncStatus(auth);
  expect(first.retry_after_seconds).toBe(45);

  await vi.advanceTimersByTimeAsync(15_000);

  await expect(apiClient.syncInstitutes(auth)).rejects.toMatchObject({
    payload: {
      retry_after_seconds: 30
    }
  });
});

test("dev institute cooldown supports explicit seconds query param", async () => {
  const provider = {
    listInstitutes: vi.fn(),
    getInstituteSyncStatus: vi.fn(),
    syncInstitutes: vi.fn()
  };
  setApiProvider(provider);
  window.history.replaceState({}, "", "/?mockInstituteCooldown=1&mockInstituteCooldownSeconds=180");

  const result = await apiClient.getInstituteSyncStatus(auth);

  expect(result.retry_after_seconds).toBe(180);
});
