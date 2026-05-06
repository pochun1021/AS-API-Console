import { render, screen, within } from "@testing-library/react";
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
  expect(screen.queryByText("白名單列表")).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "開啟新增白名單人員" }));
  const searchDialog = await screen.findByRole("dialog", { name: "查詢人員" });
  expect(within(searchDialog).getByText("可用 sysid / 帳號 / 姓名 / email")).toBeInTheDocument();
  await user.type(within(searchDialog).getByLabelText("查詢關鍵字"), "alice");
  await user.click(within(searchDialog).getByRole("button", { name: "查詢人員" }));
  expect(await within(searchDialog).findByText("alice.wang@company.com")).toBeInTheDocument();
  await user.click(within(searchDialog).getByRole("button", { name: "加入白名單" }));
  expect(await within(searchDialog).findByText("白名單已新增。")).toBeInTheDocument();

  await user.clear(within(searchDialog).getByLabelText("查詢關鍵字"));
  await user.type(within(searchDialog).getByLabelText("查詢關鍵字"), "jane");
  await user.click(within(searchDialog).getByRole("button", { name: "查詢人員" }));
  await user.click((await within(searchDialog).findAllByRole("button", { name: "加入白名單" }))[0]);
  expect(await within(searchDialog).findByText("Email 已存在於白名單")).toBeInTheDocument();
});

test("admin can toggle status with confirm and update remark", async () => {
  const user = userEvent.setup();
  render(<WhitelistAdminPage auth={adminAuth} />);

  expect(await screen.findByText("jane.doe@company.com")).toBeInTheDocument();
  await user.click((await screen.findAllByRole("button", { name: "停用白名單" }))[0]);
  expect(await screen.findByText("確認變更狀態")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "確認" }));
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

  await user.click(screen.getByRole("button", { name: "開啟新增白名單人員" }));
  const searchDialog = await screen.findByRole("dialog", { name: "查詢人員" });
  await user.type(within(searchDialog).getByLabelText("查詢關鍵字"), "user_456");
  await user.click(within(searchDialog).getByRole("button", { name: "查詢人員" }));
  expect(await within(searchDialog).findByText("Alice Wang")).toBeInTheDocument();
});

test("admin can search by account", async () => {
  const user = userEvent.setup();
  render(<WhitelistAdminPage auth={adminAuth} />);

  await user.click(screen.getByRole("button", { name: "開啟新增白名單人員" }));
  const searchDialog = await screen.findByRole("dialog", { name: "查詢人員" });
  await user.type(within(searchDialog).getByLabelText("查詢關鍵字"), "alice.wang");
  await user.click(within(searchDialog).getByRole("button", { name: "查詢人員" }));
  expect(await within(searchDialog).findByText("alice.wang")).toBeInTheDocument();
});

test("candidate search dialog resets after close", async () => {
  const user = userEvent.setup();
  render(<WhitelistAdminPage auth={adminAuth} />);

  await user.click(screen.getByRole("button", { name: "開啟新增白名單人員" }));
  const firstDialog = await screen.findByRole("dialog", { name: "查詢人員" });
  await user.type(within(firstDialog).getByLabelText("查詢關鍵字"), "alice");
  await user.click(within(firstDialog).getByRole("button", { name: "查詢人員" }));
  expect(await within(firstDialog).findByText("Alice Wang")).toBeInTheDocument();
  await user.click(within(firstDialog).getByRole("button", { name: "關閉" }));
  await screen.findByRole("button", { name: "開啟新增白名單人員" });

  await user.click(screen.getByRole("button", { name: "開啟新增白名單人員" }));
  const secondDialog = await screen.findByRole("dialog", { name: "查詢人員" });
  expect(within(secondDialog).getByLabelText("查詢關鍵字")).toHaveValue("");
  expect(within(secondDialog).queryByText("Alice Wang")).not.toBeInTheDocument();
});

test("admin can search by pressing enter in dialog input", async () => {
  const user = userEvent.setup();
  render(<WhitelistAdminPage auth={adminAuth} />);

  await user.click(screen.getByRole("button", { name: "開啟新增白名單人員" }));
  const searchDialog = await screen.findByRole("dialog", { name: "查詢人員" });
  await user.type(within(searchDialog).getByLabelText("查詢關鍵字"), "alice{enter}");
  expect(await within(searchDialog).findByText("Alice Wang")).toBeInTheDocument();
});

test("non-admin user is blocked", async () => {
  render(<WhitelistAdminPage auth={userAuth} />);
  expect(await screen.findByText("僅管理者可使用白名單管理功能。")).toBeInTheDocument();
});
