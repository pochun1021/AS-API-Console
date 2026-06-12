import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useEffect } from "react";
import { afterEach, test, vi } from "vitest";
import { setApiProvider } from "../api/client";
import { LocaleProvider, useLocale } from "../i18n/locale";
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

function LocaleHarness({ locale, children }) {
  const { setLocale } = useLocale();

  useEffect(() => {
    setLocale(locale);
  }, [locale, setLocale]);

  return children;
}

function renderWithLocale(ui, locale = "zh-TW") {
  return render(
    <LocaleProvider>
      <LocaleHarness locale={locale}>{ui}</LocaleHarness>
    </LocaleProvider>
  );
}

test("loads models on mount and renders rows", async () => {
  setApiProvider({
    listModels: async () => ({
      items: [{ id: "gpt-4o-mini", label: "gpt-4o-mini" }],
      total: 1,
      fetched_at: "2026-06-05T12:00:00Z"
    })
  });

  renderWithLocale(<ModelsPage auth={auth} />);

  expect((await screen.findAllByRole("heading", { name: "服務使用說明" })).length).toBeGreaterThan(0);
  expect(await screen.findByText("以下範本為適合文件顯示與使用者參考的版本：")).toBeInTheDocument();
  expect(await screen.findByText("gpt-4o-mini")).toBeInTheDocument();
});

test("shows empty state", async () => {
  setApiProvider({
    listModels: async () => ({ items: [], total: 0, fetched_at: "2026-06-05T12:00:00Z" })
  });

  renderWithLocale(<ModelsPage auth={auth} />);

  expect(await screen.findByText("目前沒有可用模型。")).toBeInTheDocument();
});

test("shows error state and retries", async () => {
  const user = userEvent.setup();
  const listModels = vi
    .fn()
    .mockRejectedValueOnce(new Error("failed"))
    .mockResolvedValueOnce({ items: [{ id: "gpt-4o", label: "gpt-4o" }], total: 1, fetched_at: "2026-06-05T12:00:00Z" });
  setApiProvider({ listModels });

  renderWithLocale(<ModelsPage auth={auth} />);

  expect(await screen.findByRole("button", { name: "重試" })).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "重試" }));
  expect(await screen.findByText("gpt-4o")).toBeInTheDocument();
  expect(listModels).toHaveBeenCalledTimes(2);
});

test("manual refresh calls listModels again", async () => {
  const user = userEvent.setup();
  const listModels = vi.fn().mockResolvedValue({ items: [{ id: "gpt-4o", label: "gpt-4o" }], total: 1, fetched_at: "2026-06-05T12:00:00Z" });
  setApiProvider({ listModels });

  renderWithLocale(<ModelsPage auth={auth} />);

  await screen.findByText("gpt-4o");
  await user.click(screen.getByRole("button", { name: "重新整理" }));
  expect(listModels).toHaveBeenCalledTimes(2);
});

test("auto refresh runs every 15 minutes and clears interval on unmount", async () => {
  vi.useFakeTimers();
  const clearIntervalSpy = vi.spyOn(window, "clearInterval");
  const listModels = vi.fn().mockResolvedValue({ items: [{ id: "gpt-4o", label: "gpt-4o" }], total: 1, fetched_at: "2026-06-05T12:00:00Z" });
  setApiProvider({ listModels });

  const { unmount } = renderWithLocale(<ModelsPage auth={auth} />);

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

test("renders english guide content when locale is en", async () => {
  setApiProvider({
    listModels: async () => ({
      items: [{ id: "gpt-4o-mini", label: "gpt-4o-mini" }],
      total: 1,
      fetched_at: "2026-06-05T12:00:00Z"
    })
  });

  renderWithLocale(<ModelsPage auth={auth} />, "en");

  expect(await screen.findByRole("heading", { name: "Service Usage Guide" })).toBeInTheDocument();
  expect(await screen.findByText("The example below is a version prepared for documentation display and user reference:")).toBeInTheDocument();
  expect(await screen.findByText("Available Models")).toBeInTheDocument();
});

test("integration steps are rendered as an ordered list", async () => {
  setApiProvider({
    listModels: async () => ({
      items: [{ id: "gpt-4o-mini", label: "gpt-4o-mini" }],
      total: 1,
      fetched_at: "2026-06-05T12:00:00Z"
    })
  });

  renderWithLocale(<ModelsPage auth={auth} />);

  const integrationHeading = await screen.findByRole("heading", { name: "串接步驟摘要" });
  const orderedList = integrationHeading.nextElementSibling;

  expect(orderedList?.tagName).toBe("OL");
  expect(await screen.findByText("先在系統中申請 API Key。")).toBeInTheDocument();
});

test("python example can be copied", async () => {
  const user = userEvent.setup();
  const writeText = vi.fn().mockResolvedValue(undefined);
  const originalClipboard = window.navigator.clipboard;
  Object.defineProperty(window.navigator, "clipboard", {
    configurable: true,
    value: { writeText }
  });

  setApiProvider({
    listModels: async () => ({
      items: [{ id: "gpt-4o-mini", label: "gpt-4o-mini" }],
      total: 1,
      fetched_at: "2026-06-05T12:00:00Z"
    })
  });

  renderWithLocale(<ModelsPage auth={auth} />);

  await user.click(await screen.findByRole("button", { name: "複製程式碼" }));
  expect(writeText).toHaveBeenCalledTimes(1);
  expect(writeText.mock.calls[0][0]).toContain("def chat_with_model");
  expect(await screen.findByRole("button", { name: "已複製程式碼" })).toBeInTheDocument();

  await waitFor(() => {
    expect(screen.queryByText("目前無法複製程式碼，請手動複製。")).not.toBeInTheDocument();
  });

  Object.defineProperty(window.navigator, "clipboard", {
    configurable: true,
    value: originalClipboard
  });
});
