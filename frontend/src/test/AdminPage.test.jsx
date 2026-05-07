import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AdminPage from "../pages/AdminPage";
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

const delegatedAdminAuth = {
  account: "ops.admin",
  name: "Ops Admin",
  email: "ops.admin@company.com",
  department: "Security",
  sysid: "admin_999",
  role: "admin"
};

beforeEach(() => {
  mockApiProvider.resetForTests();
});

test("admin can search users and enable admin role", async () => {
  const user = userEvent.setup();
  render(<AdminPage auth={adminAuth} />);

  expect(await screen.findByText("管理者名單")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "開啟新增管理者查詢" }));
  const searchDialog = await screen.findByRole("dialog", { name: "查詢使用者" });
  expect(within(searchDialog).getByText("可用 sysid / 帳號 / 姓名 / email")).toBeInTheDocument();
  await user.type(within(searchDialog).getByLabelText("查詢關鍵字"), "alice");
  await user.click(within(searchDialog).getByRole("button", { name: "查詢使用者" }));
  const aliceCell = await within(searchDialog).findByText("Alice Wang");
  const aliceRow = aliceCell.closest('[role="row"]');
  await user.click(within(aliceRow).getByRole("button", { name: "加入管理者" }));
  expect(await screen.findByText("Alice Wang 已加入管理者權限。")).toBeInTheDocument();
});

test("self admin cannot disable self", async () => {
  render(<AdminPage auth={adminAuth} />);
  const johnCell = await screen.findByText("John Admin");
  const johnRow = johnCell.closest('[role="row"]');
  expect(within(johnRow).getByRole("button", { name: "停用管理者" })).toBeDisabled();
});

test("admin list only shows admins and can disable other admin", async () => {
  const user = userEvent.setup();
  render(<AdminPage auth={delegatedAdminAuth} />);

  expect(screen.queryByText("Alice Wang")).not.toBeInTheDocument();
  expect(await screen.findByText("John Admin")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "開啟新增管理者查詢" }));
  const searchDialog = await screen.findByRole("dialog", { name: "查詢使用者" });
  await user.type(within(searchDialog).getByLabelText("查詢關鍵字"), "jane");
  await user.click(within(searchDialog).getByRole("button", { name: "查詢使用者" }));
  const janeCell = await within(searchDialog).findByText("Jane Doe");
  const janeRow = janeCell.closest('[role="row"]');
  await user.click(within(janeRow).getByRole("button", { name: "加入管理者" }));
  await user.click(within(searchDialog).getByRole("button", { name: "關閉" }));
  expect(await screen.findByText("Jane Doe 已加入管理者權限。")).toBeInTheDocument();

  const johnCell = await screen.findByText("John Admin");
  const johnRow = johnCell.closest('[role="row"]');
  await user.click(within(johnRow).getByRole("button", { name: "停用管理者" }));
  expect(await screen.findByText("確認停用管理者")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "確認停用" }));
  expect(await screen.findByText("已停用管理者權限。")).toBeInTheDocument();
  expect(await screen.findByText("John Admin")).toBeInTheDocument();
  expect(await screen.findByText("已停用")).toBeInTheDocument();
});

test("non-admin user is blocked", async () => {
  render(<AdminPage auth={userAuth} />);
  expect(await screen.findByText("僅管理者可使用管理者名單功能。")).toBeInTheDocument();
});

test("admin can search users by account", async () => {
  const user = userEvent.setup();
  render(<AdminPage auth={adminAuth} />);

  await user.click(screen.getByRole("button", { name: "開啟新增管理者查詢" }));
  const searchDialog = await screen.findByRole("dialog", { name: "查詢使用者" });
  await user.type(within(searchDialog).getByLabelText("查詢關鍵字"), "john.admin");
  await user.click(within(searchDialog).getByRole("button", { name: "查詢使用者" }));
  expect(await within(searchDialog).findByText("john.admin")).toBeInTheDocument();
});

test("search dialog resets keyword and results after close", async () => {
  const user = userEvent.setup();
  render(<AdminPage auth={adminAuth} />);

  await user.click(screen.getByRole("button", { name: "開啟新增管理者查詢" }));
  const firstDialog = await screen.findByRole("dialog", { name: "查詢使用者" });
  await user.type(within(firstDialog).getByLabelText("查詢關鍵字"), "alice");
  await user.click(within(firstDialog).getByRole("button", { name: "查詢使用者" }));
  expect(await within(firstDialog).findByText("Alice Wang")).toBeInTheDocument();
  await user.click(within(firstDialog).getByRole("button", { name: "關閉" }));
  await screen.findByRole("button", { name: "開啟新增管理者查詢" });

  await user.click(screen.getByRole("button", { name: "開啟新增管理者查詢" }));
  const secondDialog = await screen.findByRole("dialog", { name: "查詢使用者" });
  expect(within(secondDialog).getByLabelText("查詢關鍵字")).toHaveValue("");
  expect(within(secondDialog).queryByText("Alice Wang")).not.toBeInTheDocument();
});

test("admin can search users by pressing enter in dialog input", async () => {
  const user = userEvent.setup();
  render(<AdminPage auth={adminAuth} />);

  await user.click(screen.getByRole("button", { name: "開啟新增管理者查詢" }));
  const searchDialog = await screen.findByRole("dialog", { name: "查詢使用者" });
  await user.type(within(searchDialog).getByLabelText("查詢關鍵字"), "alice{enter}");
  expect(await within(searchDialog).findByText("Alice Wang")).toBeInTheDocument();
});
