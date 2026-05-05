import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import UsersAdminPage from "../pages/UsersAdminPage";
import { mockApiProvider } from "../mocks/mockApiProvider";

const adminAuth = {
  account: "john.admin",
  name: "John Admin",
  email: "john.admin@company.com",
  department: "Security",
  sysid: "admin_001",
  role: "admin"
};

const userAuth = {
  account: "jane.doe",
  name: "Jane Doe",
  email: "jane.doe@company.com",
  department: "Platform Engineering",
  sysid: "user_123",
  role: "user"
};

beforeEach(() => {
  mockApiProvider.resetForTests();
});

test("admin can search users and grant admin role", async () => {
  const user = userEvent.setup();
  render(<UsersAdminPage auth={adminAuth} />);

  expect(await screen.findByText("使用者管理")).toBeInTheDocument();
  await user.type(screen.getByLabelText("查詢關鍵字（sysid / 帳號 / 姓名 / email）"), "alice");
  await user.click(screen.getByRole("button", { name: "查詢使用者" }));
  await screen.findByRole("button", { name: "查詢使用者" });
  const aliceCell = await screen.findByText("Alice Wang");
  const aliceRow = aliceCell.closest('[role="row"]');
  await user.click(within(aliceRow).getByRole("button", { name: "授權管理者" }));
  expect(await screen.findByText("已授權為管理者。")).toBeInTheDocument();
});

test("admin can revoke other admin role with confirm but cannot revoke self", async () => {
  const user = userEvent.setup();
  render(<UsersAdminPage auth={adminAuth} />);

  const janeCell = await screen.findByText("Jane Doe");
  const janeRow = janeCell.closest('[role="row"]');
  await user.click(within(janeRow).getByRole("button", { name: "授權管理者" }));
  expect(await screen.findByText("已授權為管理者。")).toBeInTheDocument();

  const revokeButtons = await screen.findAllByRole("button", { name: "取消管理者" });
  const enabledRevoke = revokeButtons.find((button) => !button.hasAttribute("disabled"));
  const selfRevoke = revokeButtons.find((button) => button.hasAttribute("disabled"));
  expect(selfRevoke).toBeTruthy();
  expect(enabledRevoke).toBeTruthy();

  await user.click(enabledRevoke);
  expect(await screen.findByText("確認取消管理者")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "確認" }));
  expect(await screen.findByText("已取消管理者權限。")).toBeInTheDocument();
});

test("non-admin user is blocked", async () => {
  render(<UsersAdminPage auth={userAuth} />);
  expect(await screen.findByText("僅管理者可使用使用者管理功能。")).toBeInTheDocument();
});

test("admin can search users by account", async () => {
  const user = userEvent.setup();
  render(<UsersAdminPage auth={adminAuth} />);

  await user.type(screen.getByLabelText("查詢關鍵字（sysid / 帳號 / 姓名 / email）"), "john.admin");
  await user.click(screen.getByRole("button", { name: "查詢使用者" }));
  await screen.findByRole("button", { name: "查詢使用者" });
  expect(await screen.findByText("john.admin")).toBeInTheDocument();
});
