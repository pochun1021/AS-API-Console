import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, test, vi } from "vitest";
import App from "../App";
import { setApiProvider } from "../api/client";
import { LocaleProvider } from "../i18n/locale";
import * as navigation from "../utils/navigation";

function renderApp(initialPath = "/apply") {
  return render(
    <LocaleProvider>
      <MemoryRouter initialEntries={[initialPath]}>
        <App />
      </MemoryRouter>
    </LocaleProvider>
  );
}

describe("App login-denied flow", () => {
  const provider = {
    getCurrentUser: vi.fn(),
    getLocalePreference: vi.fn(),
    updateLocalePreference: vi.fn(),
    listModels: vi.fn(),
    logout: vi.fn()
  };

  beforeEach(() => {
    provider.getCurrentUser.mockReset();
    provider.getLocalePreference.mockReset();
    provider.updateLocalePreference.mockReset();
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

  test("non-denied routes still redirect to /main/login when getCurrentUser fails", async () => {
    provider.getCurrentUser.mockRejectedValueOnce(new Error("unauthorized"));

    renderApp("/apply");

    await waitFor(() => {
      expect(provider.getCurrentUser).toHaveBeenCalledTimes(1);
      expect(navigation.redirectToLogin).toHaveBeenCalledTimes(1);
    });
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
});
