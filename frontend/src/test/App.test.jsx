import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, test, vi } from "vitest";
import App from "../App";
import { setApiProvider } from "../api/client";
import { LocaleProvider } from "../i18n/locale";
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
    getCurrentUser: vi.fn(),
    getLocalePreference: vi.fn(),
    updateLocalePreference: vi.fn(),
    listAnnouncements: vi.fn(),
    listModels: vi.fn(),
    logout: vi.fn()
  };

  beforeEach(() => {
    provider.getCurrentUser.mockReset();
    provider.getLocalePreference.mockReset();
    provider.updateLocalePreference.mockReset();
    provider.listAnnouncements.mockReset();
    provider.listModels.mockReset();
    provider.logout.mockReset();
    setApiProvider(provider);
    vi.spyOn(navigation, "redirectToLogin").mockImplementation(() => {});
  });

  test("does not call getCurrentUser on /login-denied and renders denied page", async () => {
    renderApp("/login-denied?error=LOGIN_NOT_ELIGIBLE");

    expect(await screen.findByRole("heading", { name: "Login Access Denied" })).toBeInTheDocument();
    expect(provider.getCurrentUser).not.toHaveBeenCalled();
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

  test("shared /usage-examples route renders for non-admin user", async () => {
    provider.getCurrentUser.mockResolvedValueOnce({
      account: "user1",
      name: "User One",
      email: "user1@example.com",
      department: "IT",
      sysid: 2001,
      role: "user"
    });
    provider.getLocalePreference.mockResolvedValueOnce({ preferred_locale: "zh-TW" });
    provider.listModels.mockResolvedValueOnce({
      items: [{ id: "gpt-4o-mini", label: "gpt-4o-mini" }],
      total: 1,
      fetched_at: "2026-06-05T12:00:00Z"
    });

    renderApp("/usage-examples");

    expect((await screen.findAllByRole("heading", { name: "服務使用說明" })).length).toBeGreaterThan(0);
    expect(await screen.findByText("gpt-4o-mini")).toBeInTheDocument();
    expect(await screen.findByText("Python 範例")).toBeInTheDocument();
  });

  test("root route redirects user to /announcements", async () => {
    provider.getCurrentUser.mockResolvedValueOnce({
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

    renderApp("/");

    await waitFor(() => {
      expect(provider.listAnnouncements).toHaveBeenCalled();
    });
    expect(provider.listAnnouncements.mock.calls.some(([params]) => params?.scope === "all")).toBe(false);
    expect(screen.queryByRole("button", { name: "新增" })).not.toBeInTheDocument();
  });

  test("root route redirects admin to /announcements", async () => {
    provider.getCurrentUser.mockResolvedValueOnce({
      account: "admin1",
      name: "Admin One",
      email: "admin1@example.com",
      department: "IT",
      sysid: 1001,
      role: "admin"
    });
    provider.getLocalePreference.mockResolvedValueOnce({ preferred_locale: "zh-TW" });
    provider.listAnnouncements.mockResolvedValue({
      items: [{ id: "ann_1", title: "首頁公告", body: "公告內容" }],
      total: 1,
      page: 1,
      page_size: 20
    });

    renderApp("/");

    await waitFor(() => {
      expect(provider.listAnnouncements).toHaveBeenCalled();
      expect(provider.listAnnouncements.mock.calls.some(([params]) => params?.scope === "all")).toBe(true);
    });
  });
});
