import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, test, vi } from "vitest";
import { setApiProvider } from "../api/client";
import ModelsPage from "../pages/ModelsPage";

const auth = {
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

test("loads models on mount and renders rows", async () => {
  setApiProvider({
    listModels: async () => ({
      items: [{ id: "gpt-4o-mini", label: "gpt-4o-mini" }],
      total: 1,
      fetched_at: "2026-06-05T12:00:00Z"
    })
  });

  render(<ModelsPage auth={auth} />);

  expect(await screen.findByText("服務使用說明")).toBeInTheDocument();
  expect(await screen.findByText("gpt-4o-mini")).toBeInTheDocument();
});

test("shows empty state", async () => {
  setApiProvider({
    listModels: async () => ({ items: [], total: 0, fetched_at: "2026-06-05T12:00:00Z" })
  });

  render(<ModelsPage auth={auth} />);

  expect(await screen.findByText("目前沒有可用模型。")).toBeInTheDocument();
});

test("shows error state and retries", async () => {
  const user = userEvent.setup();
  const listModels = vi
    .fn()
    .mockRejectedValueOnce(new Error("failed"))
    .mockResolvedValueOnce({ items: [{ id: "gpt-4o", label: "gpt-4o" }], total: 1, fetched_at: "2026-06-05T12:00:00Z" });
  setApiProvider({ listModels });

  render(<ModelsPage auth={auth} />);

  expect(await screen.findByText("載入模型清單失敗")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "重試" }));
  expect(await screen.findByText("gpt-4o")).toBeInTheDocument();
  expect(listModels).toHaveBeenCalledTimes(2);
});

test("manual refresh calls listModels again", async () => {
  const user = userEvent.setup();
  const listModels = vi.fn().mockResolvedValue({ items: [{ id: "gpt-4o", label: "gpt-4o" }], total: 1, fetched_at: "2026-06-05T12:00:00Z" });
  setApiProvider({ listModels });

  render(<ModelsPage auth={auth} />);

  await screen.findByText("gpt-4o");
  await user.click(screen.getByRole("button", { name: "重新整理" }));
  expect(listModels).toHaveBeenCalledTimes(2);
});

test("auto refresh runs every 15 minutes and clears interval on unmount", async () => {
  vi.useFakeTimers();
  const clearIntervalSpy = vi.spyOn(window, "clearInterval");
  const listModels = vi.fn().mockResolvedValue({ items: [{ id: "gpt-4o", label: "gpt-4o" }], total: 1, fetched_at: "2026-06-05T12:00:00Z" });
  setApiProvider({ listModels });

  const { unmount } = render(<ModelsPage auth={auth} />);

  await act(async () => {});
  expect(screen.getByText("gpt-4o")).toBeInTheDocument();
  await act(async () => {
    vi.advanceTimersByTime(15 * 60 * 1000);
  });
  await act(async () => {});
  expect(listModels).toHaveBeenCalledTimes(2);

  unmount();
  expect(clearIntervalSpy).toHaveBeenCalledTimes(1);
});
