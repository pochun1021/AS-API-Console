import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import InstituteViewPage from "../pages/InstituteViewPage";
import { setApiProvider } from "../api/client";

const adminAuth = {
  account: "john.admin",
  name: "John Admin",
  email: "john.admin@company.com",
  department: "Security",
  sysid: 1,
  role: "admin"
};

const userAuth = {
  account: "jane.doe",
  name: "Jane Doe",
  email: "jane.doe@company.com",
  department: "Platform Engineering",
  sysid: 123,
  role: "user"
};

afterEach(() => {
  vi.useRealTimers();
});

test.each([
  {
    name: "admin can load institute data",
    provider: {
      listInstitutes: async () => ({
        items: [
          { inst_code: "01", inst_name: "Institute A", abb_inst_name: "Inst A", einst_name: "Institute A", division: "D1" }
        ],
        total: 1
      }),
      getInstituteSyncStatus: async () => ({ status: "idle", retry_after_seconds: 0, next_allowed_at: null })
    },
    expectedText: "01",
    secondaryText: "目前有效單位代碼筆數：1",
  },
  {
    name: "empty state is shown when no data",
    provider: {
      listInstitutes: async () => ({ items: [], total: 0 }),
      getInstituteSyncStatus: async () => ({ status: "idle", retry_after_seconds: 0, next_allowed_at: null })
    },
    expectedText: "目前沒有單位代碼資料。",
    secondaryText: null,
  },
  {
    name: "error state is shown when request fails",
    provider: {
      listInstitutes: async () => {
        throw new Error("failed");
      },
      getInstituteSyncStatus: async () => ({ status: "idle", retry_after_seconds: 0, next_allowed_at: null })
    },
    expectedText: "載入單位代碼資料失敗",
    secondaryText: null,
  },
])("$name", async ({ provider, expectedText, secondaryText }) => {
  setApiProvider(provider);
  render(<InstituteViewPage auth={adminAuth} />);
  expect(await screen.findByText("單位代碼資料檢視")).toBeInTheDocument();
  expect(await screen.findByText(expectedText)).toBeInTheDocument();
  if (secondaryText) {
    expect(screen.getByText(secondaryText)).toBeInTheDocument();
  }
});

test("admin can trigger manual sync and reload data", async () => {
  const user = userEvent.setup();
  let listCalls = 0;
  setApiProvider({
    listInstitutes: async () => {
      listCalls += 1;
      return {
        items: [{ inst_code: "01", inst_name: "Institute A", abb_inst_name: "Inst A", einst_name: "Institute A", division: "D1" }],
        total: 1
      };
    },
    getInstituteSyncStatus: async () => ({ status: "idle", retry_after_seconds: 0, next_allowed_at: null }),
    syncInstitutes: async () => ({
      fetched_count: 10,
      inserted_count: 1,
      updated_count: 2,
      unchanged_count: 7,
      deactivated_count: 0
    })
  });
  render(<InstituteViewPage auth={adminAuth} />);
  expect(await screen.findByText("單位代碼資料檢視")).toBeInTheDocument();
  await screen.findByText("01");
  await user.click(screen.getByRole("button", { name: "手動同步" }));
  expect(await screen.findByText("同步完成：fetched=10, inserted=1, updated=2, unchanged=7, deactivated=0")).toBeInTheDocument();
  expect(listCalls).toBe(2);
});

test("manual sync shows error message on failure", async () => {
  const user = userEvent.setup();
  setApiProvider({
    listInstitutes: async () => ({ items: [], total: 0 }),
    getInstituteSyncStatus: async () => ({ status: "idle", retry_after_seconds: 0, next_allowed_at: null }),
    syncInstitutes: async () => {
      throw new Error("failed");
    }
  });
  render(<InstituteViewPage auth={adminAuth} />);
  expect(await screen.findByText("目前沒有單位代碼資料。")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "手動同步" }));
  expect(await screen.findByText("手動同步失敗")).toBeInTheDocument();
});

test("manual sync shows in-progress message and does not reload list", async () => {
  const user = userEvent.setup();
  const listInstitutes = vi.fn().mockResolvedValue({ items: [], total: 0 });
  setApiProvider({
    listInstitutes,
    getInstituteSyncStatus: async () => ({ status: "idle", retry_after_seconds: 0, next_allowed_at: null }),
    syncInstitutes: async () => {
      throw {
        payload: {
          error: {
            code: "INSTITUTE_SYNC_IN_PROGRESS",
            message: "in progress"
          }
        }
      };
    }
  });

  render(<InstituteViewPage auth={adminAuth} />);
  expect(await screen.findByText("目前沒有單位代碼資料。")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "手動同步" }));
  expect(await screen.findByText("目前已有手動同步作業執行中，請稍後再試。")).toBeInTheDocument();
  expect(listInstitutes).toHaveBeenCalledTimes(1);
});

test("manual sync cooldown initializes from status and re-enables after countdown", async () => {
  vi.useFakeTimers();
  const listInstitutes = vi.fn().mockResolvedValue({ items: [], total: 0 });
  setApiProvider({
    listInstitutes,
    getInstituteSyncStatus: async () => ({
      status: "idle",
      retry_after_seconds: 75,
      next_allowed_at: new Date(Date.now() + 75_000).toISOString()
    }),
    syncInstitutes: async () => ({})
  });

  render(<InstituteViewPage auth={adminAuth} />);
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
  });
  expect(screen.getByText("目前沒有單位代碼資料。")).toBeInTheDocument();
  expect(screen.getByText("手動同步冷卻中，剩餘 1 分 15 秒")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "手動同步" })).toBeDisabled();

  await act(async () => {
    await vi.advanceTimersByTimeAsync(75_000);
  });

  expect(screen.getByRole("button", { name: "手動同步" })).toBeEnabled();
});

test("manual sync cooldown response shows remaining time and does not reload list", async () => {
  const user = userEvent.setup();
  const listInstitutes = vi.fn().mockResolvedValue({ items: [], total: 0 });
  setApiProvider({
    listInstitutes,
    getInstituteSyncStatus: async () => ({ status: "idle", retry_after_seconds: 0, next_allowed_at: null }),
    syncInstitutes: async () => {
      throw {
        payload: {
          error: {
            code: "INSTITUTE_SYNC_COOLDOWN",
            message: "cooldown"
          },
          retry_after_seconds: 45,
          next_allowed_at: new Date(Date.now() + 45_000).toISOString()
        }
      };
    }
  });

  render(<InstituteViewPage auth={adminAuth} />);
  expect(await screen.findByText("目前沒有單位代碼資料。")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "手動同步" }));
  expect(await screen.findByText(/手動同步仍在冷卻中，請於\d+\s*秒後再試。/)).toBeInTheDocument();
  expect(screen.getByText(/手動同步冷卻中，剩餘 \d+\s*秒/)).toBeInTheDocument();
  expect(listInstitutes).toHaveBeenCalledTimes(1);
});
