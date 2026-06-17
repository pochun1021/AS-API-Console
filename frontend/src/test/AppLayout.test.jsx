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

function renderAppLayout({ path = "/", auth = userAuth, props = {} } = {}) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppLayout auth={auth} {...props}>
        <div>content</div>
      </AppLayout>
    </MemoryRouter>
  );
}

test("user sees shared navigation including models", () => {
  renderAppLayout();

  const navLinks = screen.getAllByRole("link");
  expect(navLinks[0]).toHaveTextContent("系統公告");
  expect(navLinks[1]).toHaveTextContent("服務使用說明");
  expect(screen.getByRole("link", { name: "系統公告" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "申請" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "API Keys" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "使用量" })).toBeInTheDocument();
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

  renderAppLayout({ props: { onChangeLocale } });

  fireEvent.click(screen.getByLabelText("語言"));
  fireEvent.click(screen.getByRole("menuitem", { name: "EN" }));

  expect(onChangeLocale).toHaveBeenCalledWith("en");
});

test("locale menu shows checkmark for current locale", () => {
  renderAppLayout();

  fireEvent.click(screen.getByLabelText("語言"));

  expect(screen.getByTestId("locale-check-zh-TW").querySelector("svg")).toBeInTheDocument();
  expect(screen.getByTestId("locale-check-en").querySelector("svg")).not.toBeInTheDocument();
});

test("admin sees whitelist nav", () => {
  renderAppLayout({ auth: adminAuth });

  const navLinks = screen.getAllByRole("link");
  expect(navLinks[0]).toHaveTextContent("系統公告");
  expect(navLinks[1]).toHaveTextContent("服務使用說明");
  expect(screen.getByRole("link", { name: "特殊人員名單管理" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "系統公告" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "使用量" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "服務使用說明" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "服務使用說明" })).toHaveAttribute("href", "/usage-examples");
  expect(screen.getByRole("link", { name: "單位代碼" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "管理者名單" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "管理者統計" })).toBeInTheDocument();
});

test("clicking logout icon triggers onLogout", () => {
  const onLogout = vi.fn();
  renderAppLayout({ props: { onLogout } });

  fireEvent.click(screen.getByLabelText("登出"));
  expect(onLogout).toHaveBeenCalledTimes(1);
});

test("usage route only highlights usage nav item", () => {
  renderAppLayout({ path: "/usage" });

  expect(screen.getByRole("link", { name: "使用量" })).toHaveClass("MuiButton-colorSecondary");
  expect(screen.getByRole("link", { name: "服務使用說明" })).not.toHaveClass("MuiButton-colorSecondary");
});

test("usage examples route only highlights usage examples nav item", () => {
  renderAppLayout({ path: "/usage-examples" });

  expect(screen.getByRole("link", { name: "服務使用說明" })).toHaveClass("MuiButton-colorSecondary");
  expect(screen.getByRole("link", { name: "使用量" })).not.toHaveClass("MuiButton-colorSecondary");
});

test("nested api key route keeps api keys nav active", () => {
  renderAppLayout({ path: "/api-keys/123" });

  expect(screen.getByRole("link", { name: "API Keys" })).toHaveClass("MuiButton-colorSecondary");
  expect(screen.getByRole("link", { name: "使用量" })).not.toHaveClass("MuiButton-colorSecondary");
});
