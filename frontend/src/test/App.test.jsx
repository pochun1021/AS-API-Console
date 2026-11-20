import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, test, vi } from "vitest";
import App from "../App";
import { setApiProvider } from "../api/client";
import { LocaleProvider } from "../i18n/locale";
import * as apiKeyGoLive from "../utils/apiKeyGoLive";
import * as navigation from "../utils/navigation";

function renderApp(initialPath = "/apply") {
  return render(
    <LocaleProvider>
      <LocalizationProvider dateAdapter={AdapterDayjs}>
        <MemoryRouter initialEntries={[initialPath]}>
          <App />
        </MemoryRouter>
      </LocalizationProvider>
    </LocaleProvider>
  );
}

describe("App public auth pages", () => {
  const provider = {
    getLocalLoginDefaults: vi.fn(),
    createLocalLoginSession: vi.fn(),
    getCurrentUser: vi.fn(),
    getLocalePreference: vi.fn(),
    updateLocalePreference: vi.fn(),
    listAnnouncements: vi.fn(),
    listApiKeys: vi.fn(),
    listApiKeyUsageSeries: vi.fn(),
    getApiKeyUsageTotal: vi.fn(),
    listModels: vi.fn(),
    logout: vi.fn()
  };

  beforeEach(() => {
    provider.getLocalLoginDefaults.mockReset();
    provider.createLocalLoginSession.mockReset();
    provider.getCurrentUser.mockReset();
    provider.getLocalePreference.mockReset();
    provider.updateLocalePreference.mockReset();
    provider.listAnnouncements.mockReset();
    provider.listApiKeys.mockReset();
    provider.listApiKeyUsageSeries.mockReset();
    provider.getApiKeyUsageTotal.mockReset();
    provider.listModels.mockReset();
    provider.logout.mockReset();
    window.sessionStorage.clear();
    vi.restoreAllMocks();
    setApiProvider(provider);
    vi.spyOn(apiKeyGoLive, "isApiKeyApplicationLive").mockReturnValue(true);
    vi.spyOn(navigation, "redirectToLogin").mockImplementation(() => {});
  });

  test("does not call getCurrentUser on /login-denied and renders denied page", async () => {
    renderApp("/login-denied?error=LOGIN_NOT_ELIGIBLE");

    expect(await screen.findByRole("heading", { name: "Login Access Denied" })).toBeInTheDocument();
    expect(provider.getCurrentUser).not.toHaveBeenCalled();
  });

  test("local login pre-fills identity and submits edited account and role", async () => {
    const user = userEvent.setup();
    provider.getLocalLoginDefaults.mockResolvedValue({
      account: "default.user", name: "Default User", email: "default@example.com",
      department: "QA", sysid: 990001, role: "user"
    });
    provider.createLocalLoginSession.mockResolvedValue({ redirect: "/test/announcements", warning: "DATAHUB_CONNECTION_FAILED" });
    provider.getCurrentUser.mockResolvedValue({ account: "edited.user", role: "admin" });
    provider.getLocalePreference.mockResolvedValue({ preferred_locale: "en" });
    provider.listAnnouncements.mockResolvedValue({ items: [], total: 0 });
    renderApp("/local-login");

    expect(await screen.findByRole("heading", { name: "Test Environment Sign-In" })).toBeInTheDocument();
    const account = await screen.findByRole("textbox", { name: "Account" });
    expect(account).toHaveValue("default.user");
    await user.clear(account);
    await user.type(account, "edited.user");
    await user.click(screen.getByRole("radio", { name: "Admin" }));
    await user.click(screen.getByRole("button", { name: "Sign In" }));
    await waitFor(() => expect(provider.createLocalLoginSession).toHaveBeenCalledWith({
      account: "edited.user", name: "Default User", email: "default@example.com",
      department: "QA", sysid: 990001, role: "admin"
    }));
    expect(await screen.findByText(/DataHub .*連線失敗|DataHub connection failed/, {}, { timeout: 10000 })).toBeInTheDocument();
  });

  test("does not call getCurrentUser on /login-coming-soon and renders public coming soon page", async () => {
    vi.spyOn(apiKeyGoLive, "isApiKeyApplicationLive").mockReturnValue(false);
    renderApp("/login-coming-soon");

    expect(await screen.findByRole("heading", { name: "API Key Applications Open on June 30" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View Service Guide" })).toHaveAttribute("href", "/usage-examples");
    expect(provider.getCurrentUser).not.toHaveBeenCalled();
  });

  test("login coming soon page continues to /main/login on button click", async () => {
    const user = userEvent.setup();
    vi.spyOn(apiKeyGoLive, "isApiKeyApplicationLive").mockReturnValue(false);
    vi.spyOn(navigation, "proceedToLogin").mockImplementation(() => {});
    renderApp("/login-coming-soon");

    await user.click(await screen.findByRole("button", { name: "Continue to Sign In" }));
    expect(navigation.proceedToLogin).toHaveBeenCalledTimes(1);
  });

  test("login coming soon page supports locale switching", async () => {
    const user = userEvent.setup();
    vi.spyOn(apiKeyGoLive, "isApiKeyApplicationLive").mockReturnValue(false);
    renderApp("/login-coming-soon");

    await user.click(await screen.findByRole("button", { name: "中文" }));
    expect(await screen.findByRole("heading", { name: "API Key 申請即將於 6 月 30 日上線" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "前往登入" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "查看服務使用說明" })).toHaveAttribute("href", "/usage-examples");
  });

  test("public /usage-examples renders guide without restoring auth or loading models", async () => {
    renderApp("/usage-examples");

    expect(await screen.findByRole("heading", { name: "Service Usage Guide" })).toBeInTheDocument();
    expect(await screen.findByText("The example below is a version prepared for documentation display and user reference:")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign In" })).toBeInTheDocument();
    expect(provider.getCurrentUser).not.toHaveBeenCalled();
    expect(provider.listModels).not.toHaveBeenCalled();
  });

  test("public /usage-examples supports locale switching", async () => {
    const user = userEvent.setup();
    renderApp("/usage-examples");

    await user.click(await screen.findByRole("button", { name: "中文" }));

    expect(await screen.findByRole("heading", { name: "服務使用說明" })).toBeInTheDocument();
    expect(await screen.findByText("以下範本為適合文件顯示與使用者參考的版本：")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "登入" })).toBeInTheDocument();
    expect(provider.getCurrentUser).not.toHaveBeenCalled();
    expect(provider.listModels).not.toHaveBeenCalled();
  });

  test("retry button on denied page redirects to /main/login", async () => {
    const user = userEvent.setup();
    renderApp("/login-denied?error=LOGIN_NOT_ELIGIBLE");

    await user.click(await screen.findByRole("button", { name: "Back to Login" }));
    expect(navigation.redirectToLogin).toHaveBeenCalledTimes(1);
  });

  test("does not call getCurrentUser on /login-error and renders login error page", async () => {
    renderApp("/login-error?route=auth_callback&reason=eligibility_check_failed&request_id=req-123");

    expect(await screen.findByRole("heading", { name: "Sign-In Failed" })).toBeInTheDocument();
    expect(screen.getByText("Failed Route: auth_callback")).toBeInTheDocument();
    expect(screen.getByText("Failure Reason: eligibility_check_failed")).toBeInTheDocument();
    expect(screen.getByText("Request ID: req-123")).toBeInTheDocument();
    expect(provider.getCurrentUser).not.toHaveBeenCalled();
  });

  test("retry button on login error page redirects to /main/login", async () => {
    const user = userEvent.setup();
    renderApp("/login-error?route=auth_callback&reason=audit_log_failed&request_id=req-2");

    await user.click(await screen.findByRole("button", { name: "Sign In Again" }));
    expect(navigation.redirectToLogin).toHaveBeenCalledTimes(1);
  });

  test("non-denied routes still redirect to /main/login when getCurrentUser fails", async () => {
    provider.getCurrentUser.mockRejectedValueOnce(new Error("unauthorized"));

    renderApp("/apply");

    await waitFor(() => {
      expect(provider.getCurrentUser).toHaveBeenCalledTimes(1);
      expect(navigation.redirectToLogin).toHaveBeenCalledTimes(1);
    });
  });

  test("structured 500 from getCurrentUser routes to login error page", async () => {
    const error = new Error("boom");
    error.status = 500;
    error.payload = {
      request_id: "req-users-me-1",
      route: "/main/api/v1/users/me",
      reason: "unexpected_internal_error",
      error: {
        code: "INTERNAL_ERROR",
        message: "unexpected internal error"
      }
    };
    provider.getCurrentUser.mockRejectedValueOnce(error);

    renderApp("/apply");

    expect(await screen.findByRole("heading", { name: "Sign-In Failed" })).toBeInTheDocument();
    expect(await screen.findByText("Failed Route: /main/api/v1/users/me")).toBeInTheDocument();
    expect(await screen.findByText("Request ID: req-users-me-1")).toBeInTheDocument();
    expect(navigation.redirectToLogin).not.toHaveBeenCalled();
  });

  test("shared /usage-examples route renders for non-admin user from authenticated navigation", async () => {
    const user = userEvent.setup();
    provider.getCurrentUser.mockResolvedValue({
      account: "user1",
      name: "User One",
      email: "user1@example.com",
      department: "IT",
      sysid: 2001,
      role: "user"
    });
    provider.getLocalePreference.mockResolvedValueOnce({ preferred_locale: "zh-TW" });
    provider.listAnnouncements.mockResolvedValue({
      items: [{ id: "ann_1", title: "首頁公告", body: "公告內容", updated_at: "2026-06-15T08:00:00Z" }],
      total: 1,
      page: 1,
      page_size: 20
    });
    provider.listModels.mockResolvedValueOnce({
      items: [{ id: "gpt-4o-mini", label: "gpt-4o-mini" }],
      total: 1,
      fetched_at: "2026-06-05T12:00:00Z"
    });

    renderApp("/announcements");

    await user.click(await screen.findByRole("link", { name: "服務使用說明" }));

    expect((await screen.findAllByRole("heading", { name: "服務使用說明" })).length).toBeGreaterThan(0);
    expect(await screen.findByText("gpt-4o-mini")).toBeInTheDocument();
    expect(await screen.findByText("Python 範例")).toBeInTheDocument();
  });

  test("shared /usage route renders for non-admin user", async () => {
    provider.getCurrentUser.mockResolvedValue({
      account: "user1",
      name: "User One",
      email: "user1@example.com",
      department: "IT",
      sysid: 2001,
      role: "user"
    });
    provider.getLocalePreference.mockResolvedValueOnce({ preferred_locale: "zh-TW" });
    provider.listApiKeys.mockResolvedValueOnce({
      items: [{ id: "key_1", key_alias: "for_user1", masked_key: "AS-...1234" }]
    });

    renderApp("/usage");

    expect(await screen.findByText("API Key 使用量", {}, { timeout: 3000 })).toBeInTheDocument();
    expect(await screen.findByLabelText("API Key", {}, { timeout: 3000 })).toBeInTheDocument();
  });

  test("root route redirects unauthenticated visitors to the public service guide", async () => {
    renderApp("/");

    expect(await screen.findByRole("heading", { name: "Service Usage Guide" })).toBeInTheDocument();
    expect(provider.getCurrentUser).not.toHaveBeenCalled();
    expect(provider.listModels).not.toHaveBeenCalled();
    expect(provider.listAnnouncements).not.toHaveBeenCalled();
  });

  test("authenticated root route redirects to announcements", async () => {
    provider.getCurrentUser.mockResolvedValue({
      account: "user1",
      name: "User One",
      email: "user1@example.com",
      department: "IT",
      sysid: 2001,
      role: "user"
    });
    provider.getLocalePreference.mockResolvedValueOnce({ preferred_locale: "zh-TW" });
    provider.listAnnouncements.mockResolvedValue({
      items: [{ id: "ann_1", title: "登入後公告", body: "公告內容", updated_at: "2026-06-15T08:00:00Z" }],
      total: 1,
      page: 1,
      page_size: 20
    });
    window.sessionStorage.setItem("as-api-console-service-guide-auth-hint", "1");

    renderApp("/");

    expect(await screen.findByText("登入後公告")).toBeInTheDocument();
    expect(provider.listAnnouncements).toHaveBeenCalled();
    expect(provider.listModels).not.toHaveBeenCalled();
  });
});
