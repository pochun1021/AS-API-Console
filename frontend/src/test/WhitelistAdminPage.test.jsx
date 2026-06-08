import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import WhitelistAdminPage from "../pages/WhitelistAdminPage";
import { mockApiProvider } from "../mocks/mockApiProvider";

const adminAuth = {
  account: "john.admin",
  name: "John Admin",
  email: "john.admin@company.com",
  department: "Security",
  sysid: 1,
  role: "admin"
};

const userAuth = {
  account: "jane.doe",
  name: "Jane Doe",
  email: "jane.doe@company.com",
  department: "Platform Engineering",
  sysid: 123,
  role: "user"
};

beforeEach(() => {
  mockApiProvider.resetForTests();
});

function renderPage(ui) {
  return render(<LocalizationProvider dateAdapter={AdapterDayjs}>{ui}</LocalizationProvider>);
}

async function openSearchDialog(user) {
  await user.click(screen.getByRole("button", { name: "開啟新增特殊人員名單人員" }));
  return screen.findByRole("dialog", { name: "查詢人員" });
}

test("admin can search user and add whitelist item, then sees duplicated error", async () => {
  const user = userEvent.setup();
  renderPage(<WhitelistAdminPage auth={adminAuth} />);

  expect(await screen.findByText("特殊人員名單管理")).toBeInTheDocument();
  expect(screen.queryByText("白名單列表")).not.toBeInTheDocument();
  const searchDialog = await openSearchDialog(user);
  expect(within(searchDialog).getByText("可用帳號 / 姓名查詢")).toBeInTheDocument();
  await user.type(within(searchDialog).getByLabelText("查詢關鍵字"), "alice");
  await user.click(within(searchDialog).getByRole("button", { name: "查詢人員" }));
  expect(await within(searchDialog).findByText("alice.wang@company.com")).toBeInTheDocument();
  await user.click(within(searchDialog).getByRole("button", { name: "加入特殊人員名單" }));
  expect(await within(searchDialog).findByText("特殊人員名單已新增。")).toBeInTheDocument();

  await user.clear(within(searchDialog).getByLabelText("查詢關鍵字"));
  await user.type(within(searchDialog).getByLabelText("查詢關鍵字"), "jane");
  await user.click(within(searchDialog).getByRole("button", { name: "查詢人員" }));
  await user.click((await within(searchDialog).findAllByRole("button", { name: "加入特殊人員名單" }))[0]);
  expect(await within(searchDialog).findByText("SysID 已存在於特殊人員名單")).toBeInTheDocument();
});

test("admin can toggle status with confirm and update remark", async () => {
  const user = userEvent.setup();
  renderPage(<WhitelistAdminPage auth={adminAuth} />);

  expect(await screen.findByText("jane.doe@company.com")).toBeInTheDocument();
  await user.click((await screen.findAllByRole("button", { name: "停用特殊人員名單" }))[0]);
  expect(await screen.findByText("確認變更狀態")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "確認" }));
  expect(await screen.findByText("特殊人員名單已更新。")).toBeInTheDocument();

  const remarkInput = (await screen.findAllByDisplayValue("platform team"))[0];
  await user.clear(remarkInput);
  await user.type(remarkInput, "updated by test");
  await user.click((await screen.findAllByRole("button", { name: "儲存備註" }))[0]);
  expect(await screen.findByText("特殊人員名單已更新。")).toBeInTheDocument();
});

test("admin can save chinese and english mixed note", async () => {
  const user = userEvent.setup();
  renderPage(<WhitelistAdminPage auth={adminAuth} />);

  const remarkInput = (await screen.findAllByDisplayValue("platform team"))[0];
  await user.clear(remarkInput);
  await user.type(remarkInput, "平台 team_備註-2026");
  await user.click((await screen.findAllByRole("button", { name: "儲存備註" }))[0]);

  expect(await screen.findByText("特殊人員名單已更新。")).toBeInTheDocument();
  const { items } = await mockApiProvider.listWhitelists(adminAuth);
  expect(items.find((item) => item.account === "jane.doe")?.note).toBe("平台 team_備註-2026");
});

test("whitelist note keeps chinese draft during ime composition", async () => {
  const user = userEvent.setup();
  renderPage(<WhitelistAdminPage auth={adminAuth} />);

  const remarkInput = (await screen.findAllByDisplayValue("platform team"))[0];
  await user.clear(remarkInput);

  fireEvent.compositionStart(remarkInput);
  fireEvent.change(remarkInput, { target: { value: "平" } });
  expect(remarkInput).toHaveValue("平");

  fireEvent.change(remarkInput, { target: { value: "平台 team" } });
  expect(remarkInput).toHaveValue("平台 team");

  fireEvent.compositionEnd(remarkInput, { data: "台", target: { value: "平台 team" } });
  await user.click((await screen.findAllByRole("button", { name: "儲存備註" }))[0]);

  expect(await screen.findByText("特殊人員名單已更新。")).toBeInTheDocument();
  const { items } = await mockApiProvider.listWhitelists(adminAuth);
  expect(items.find((item) => item.account === "jane.doe")?.note).toBe("平台 team");
});

test("admin cannot save unsafe whitelist note", async () => {
  const user = userEvent.setup();
  renderPage(<WhitelistAdminPage auth={adminAuth} />);

  const remarkInput = (await screen.findAllByDisplayValue("platform team"))[0];
  await user.clear(remarkInput);
  await user.type(remarkInput, "<script>alert(1)</script>");
  await user.click((await screen.findAllByRole("button", { name: "儲存備註" }))[0]);

  expect(await screen.findByText("備註不可包含明顯程式語法。")).toBeInTheDocument();
});

test("admin cannot save whitelist note with invalid characters", async () => {
  const user = userEvent.setup();
  renderPage(<WhitelistAdminPage auth={adminAuth} />);

  const remarkInput = (await screen.findAllByDisplayValue("platform team"))[0];
  await user.clear(remarkInput);
  await user.type(remarkInput, "平台備註.2026");
  await user.click((await screen.findAllByRole("button", { name: "儲存備註" }))[0]);

  expect(await screen.findByText("備註僅允許中英文、數字、空白、_、-、全形頓號（、）。")).toBeInTheDocument();
});

test("admin can save whitelist note with ideographic comma", async () => {
  const user = userEvent.setup();
  renderPage(<WhitelistAdminPage auth={adminAuth} />);

  const remarkInput = (await screen.findAllByDisplayValue("platform team"))[0];
  await user.clear(remarkInput);
  await user.type(remarkInput, "平台、批次作業");
  await user.click((await screen.findAllByRole("button", { name: "儲存備註" }))[0]);

  await waitFor(() => {
    expect(screen.getByRole("alert")).toHaveTextContent("特殊人員名單已更新。");
  });
});

test.each([
  { name: "admin can search by name", query: "Alice", expectedText: "Alice Wang" },
  { name: "admin can search by account", query: "alice.wang", expectedText: "alice.wang" },
])("$name", async ({ query, expectedText }) => {
  const user = userEvent.setup();
  renderPage(<WhitelistAdminPage auth={adminAuth} />);

  const searchDialog = await openSearchDialog(user);
  await user.type(within(searchDialog).getByLabelText("查詢關鍵字"), query);
  await user.click(within(searchDialog).getByRole("button", { name: "查詢人員" }));
  expect(await within(searchDialog).findByText(expectedText)).toBeInTheDocument();
});

test("candidate search dialog resets after close", async () => {
  const user = userEvent.setup();
  renderPage(<WhitelistAdminPage auth={adminAuth} />);

  const firstDialog = await openSearchDialog(user);
  await user.type(within(firstDialog).getByLabelText("查詢關鍵字"), "alice");
  await user.click(within(firstDialog).getByRole("button", { name: "查詢人員" }));
  expect(await within(firstDialog).findByText("Alice Wang")).toBeInTheDocument();
  await user.click(within(firstDialog).getByRole("button", { name: "關閉" }));
  await screen.findByRole("button", { name: "開啟新增特殊人員名單人員" });

  const secondDialog = await openSearchDialog(user);
  expect(within(secondDialog).getByLabelText("查詢關鍵字")).toHaveValue("");
  expect(within(secondDialog).queryByText("Alice Wang")).not.toBeInTheDocument();
});

test("admin can search by pressing enter in dialog input", async () => {
  const user = userEvent.setup();
  renderPage(<WhitelistAdminPage auth={adminAuth} />);

  const searchDialog = await openSearchDialog(user);
  await user.type(within(searchDialog).getByLabelText("查詢關鍵字"), "alice{enter}");
  expect(await within(searchDialog).findByText("Alice Wang")).toBeInTheDocument();
});

test("search requires keyword in whitelist dialog", async () => {
  const user = userEvent.setup();
  renderPage(<WhitelistAdminPage auth={adminAuth} />);

  const searchDialog = await openSearchDialog(user);
  await user.click(within(searchDialog).getByRole("button", { name: "查詢人員" }));
  expect(await within(searchDialog).findByText("請輸入查詢關鍵字。")).toBeInTheDocument();
});
