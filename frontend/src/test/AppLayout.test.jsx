import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import AppLayout from "../components/AppLayout";

const userAuth = {
  account: "jane.doe",
  name: "Jane Doe",
  email: "jane.doe@company.com",
  department: "Platform Engineering",
  sysid: 123,
  role: "user"
};

const adminAuth = {
  ...userAuth,
  role: "admin"
};

test("user sees shared navigation including models", () => {
  render(
    <MemoryRouter>
      <AppLayout auth={userAuth}>
        <div>content</div>
      </AppLayout>
    </MemoryRouter>
  );

  expect(screen.getByRole("link", { name: "系統公告" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "申請" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "API Keys" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "服務使用說明" })).toBeInTheDocument();
  expect(screen.getByAltText("AS API Console logo")).toBeInTheDocument();
  expect(screen.getByLabelText("語言")).toBeInTheDocument();
  expect(screen.getByLabelText("登出")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "特殊人員名單管理" })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "服務使用說明" })).toHaveAttribute("href", "/usage-examples");
  expect(screen.queryByRole("heading", { name: "服務使用說明" })).not.toBeInTheDocument();
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

  const navLinks = screen.getAllByRole("link");
  expect(navLinks[0]).toHaveTextContent("系統公告");
  expect(screen.getByRole("link", { name: "特殊人員名單管理" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "系統公告" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "服務使用說明" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "服務使用說明" })).toHaveAttribute("href", "/usage-examples");
  expect(screen.getByRole("link", { name: "單位代碼" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "管理者名單" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "管理者統計" })).toBeInTheDocument();
});

test("layout renders announcement surface when items are provided", () => {
  render(
    <MemoryRouter>
      <AppLayout
        auth={userAuth}
        announcementState={{
          items: [{ id: "ann_1", title: "維護公告", body: "請留意維護時段" }],
          loading: false,
          error: ""
        }}
      >
        <div>content</div>
      </AppLayout>
    </MemoryRouter>
  );

  expect(screen.getByText("維護公告")).toBeInTheDocument();
  expect(screen.getByText("請留意維護時段")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "查看說明" })).not.toBeInTheDocument();
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
