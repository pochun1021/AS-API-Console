import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import WhitelistAdminPage from "../pages/WhitelistAdminPage";
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

test("admin can search user and add whitelist item, then sees duplicated error", async () => {
  const user = userEvent.setup();
  render(<WhitelistAdminPage auth={adminAuth} />);

  expect(await screen.findByText("白名單管理")).toBeInTheDocument();
  await user.type(screen.getByLabelText("查詢關鍵字（sysid / 姓名 / email）"), "alice");
  await user.click(screen.getByRole("button", { name: "查詢人員" }));
  expect(await screen.findByText("alice.wang@company.com")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "加入白名單" }));
  expect(await screen.findByText("白名單已新增。")).toBeInTheDocument();

  await user.clear(screen.getByLabelText("查詢關鍵字（sysid / 姓名 / email）"));
  await user.type(screen.getByLabelText("查詢關鍵字（sysid / 姓名 / email）"), "jane");
  await user.click(screen.getByRole("button", { name: "查詢人員" }));
  await user.click((await screen.findAllByRole("button", { name: "加入白名單" }))[0]);
  expect(await screen.findByText("Email 已存在於白名單")).toBeInTheDocument();
});

test("admin can toggle status and update remark", async () => {
  const user = userEvent.setup();
  render(<WhitelistAdminPage auth={adminAuth} />);

  expect(await screen.findByText("jane.doe@company.com")).toBeInTheDocument();
  await user.click((await screen.findAllByRole("button", { name: "停用" }))[0]);
  expect(await screen.findByText("白名單已更新。")).toBeInTheDocument();

  const remarkInput = (await screen.findAllByDisplayValue("platform team"))[0];
  await user.clear(remarkInput);
  await user.type(remarkInput, "updated by test");
  await user.click((await screen.findAllByRole("button", { name: "儲存備註" }))[0]);
  expect(await screen.findByText("白名單已更新。")).toBeInTheDocument();
});

test("admin can search by sysid", async () => {
  const user = userEvent.setup();
  render(<WhitelistAdminPage auth={adminAuth} />);

  await user.type(screen.getByLabelText("查詢關鍵字（sysid / 姓名 / email）"), "user_456");
  await user.click(screen.getByRole("button", { name: "查詢人員" }));
  expect(await screen.findByText("Alice Wang")).toBeInTheDocument();
});

test("non-admin user is blocked", async () => {
  render(<WhitelistAdminPage auth={userAuth} />);
  expect(await screen.findByText("僅管理者可使用白名單管理功能。")).toBeInTheDocument();
});
