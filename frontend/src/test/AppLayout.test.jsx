import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import AppLayout from "../components/AppLayout";

const userAuth = {
  account: "jane.doe",
  name: "Jane Doe",
  email: "jane.doe@company.com",
  department: "Platform Engineering",
  sysid: "user_123",
  role: "user"
};

const adminAuth = {
  ...userAuth,
  role: "admin"
};

test("user sees apply and api keys nav only", () => {
  render(
    <MemoryRouter>
      <AppLayout auth={userAuth}>
        <div>content</div>
      </AppLayout>
    </MemoryRouter>
  );

  expect(screen.getByRole("link", { name: "申請" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "API Keys" })).toBeInTheDocument();
  expect(screen.getByLabelText("語言")).toBeInTheDocument();
  expect(screen.getByLabelText("登出")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "特殊人員名單管理" })).not.toBeInTheDocument();
});

test("locale menu triggers onChangeLocale with selected value", () => {
  const onChangeLocale = vi.fn();

  render(
    <MemoryRouter>
      <AppLayout auth={userAuth} onChangeLocale={onChangeLocale}>
        <div>content</div>
      </AppLayout>
    </MemoryRouter>
  );

  fireEvent.click(screen.getByLabelText("語言"));
  fireEvent.click(screen.getByRole("menuitem", { name: "EN" }));

  expect(onChangeLocale).toHaveBeenCalledWith("en");
});

test("locale menu shows checkmark for current locale", () => {
  render(
    <MemoryRouter>
      <AppLayout auth={userAuth}>
        <div>content</div>
      </AppLayout>
    </MemoryRouter>
  );

  fireEvent.click(screen.getByLabelText("語言"));

  expect(screen.getByTestId("locale-check-zh-TW").querySelector("svg")).toBeInTheDocument();
  expect(screen.getByTestId("locale-check-en").querySelector("svg")).not.toBeInTheDocument();
});

test("admin sees whitelist nav", () => {
  render(
    <MemoryRouter>
      <AppLayout auth={adminAuth}>
        <div>content</div>
      </AppLayout>
    </MemoryRouter>
  );

  expect(screen.getByRole("link", { name: "特殊人員名單管理" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "管理者名單" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "管理者統計" })).toBeInTheDocument();
});

test("clicking logout icon triggers onLogout", () => {
  const onLogout = vi.fn();
  render(
    <MemoryRouter>
      <AppLayout auth={userAuth} onLogout={onLogout}>
        <div>content</div>
      </AppLayout>
    </MemoryRouter>
  );

  fireEvent.click(screen.getByLabelText("登出"));
  expect(onLogout).toHaveBeenCalledTimes(1);
});
