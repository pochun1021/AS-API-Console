import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { mockApiProvider } from "../mocks/mockApiProvider";
import MyApiKeysPage from "../pages/MyApiKeysPage";

const auth = {
  account: "jane.doe",
  name: "Jane Doe",
  email: "jane.doe@company.com",
  department: "02",
  sysid: 123,
  role: "user"
};

const adminAuth = {
  account: "john.admin",
  name: "John Admin",
  email: "john.admin@company.com",
  department: "03",
  sysid: 1,
  role: "admin"
};

const devUserAuth = {
  account: "dev.user",
  name: "Dev User",
  email: "dev.user@example.com",
  department: "02",
  sysid: 200001,
  role: "user"
};

beforeEach(() => {
  mockApiProvider.resetForTests();
});

test("shows revoke button only for active rows", async () => {
  render(
    <MemoryRouter>
      <MyApiKeysPage auth={auth} />
    </MemoryRouter>
  );

  expect(await screen.findByText("API Keys")).toBeInTheDocument();
  const moreActionButtons = await screen.findAllByRole("button", { name: "更多操作" });
  expect(moreActionButtons.length).toBeGreaterThan(0);
  expect(screen.queryByRole("button", { name: "停用金鑰" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "更新金鑰" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "展延金鑰" })).not.toBeInTheDocument();
  expect(await screen.findAllByRole("button", { name: "查看詳情" })).toHaveLength(2);
  expect(screen.queryByRole("columnheader", { name: "建立時間" })).not.toBeInTheDocument();
});

test("shows owner column for admin list", async () => {
  render(
    <MemoryRouter>
      <MyApiKeysPage auth={adminAuth} />
    </MemoryRouter>
  );

  expect(await screen.findByRole("columnheader", { name: "申請人" })).toBeInTheDocument();
  expect(await screen.findByRole("columnheader", { name: "Key Alias" })).toBeInTheDocument();
  expect((await screen.findAllByText("jane.doe / Jane Doe")).length).toBeGreaterThan(0);
});

test("shows detail in dialog and can revoke active key with confirm", async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <MyApiKeysPage auth={auth} />
    </MemoryRouter>
  );

  await user.click((await screen.findAllByRole("button", { name: "查看詳情" }))[0]);
  expect(await screen.findByText("API Key 詳情")).toBeInTheDocument();
  expect(await screen.findByText("ID: key_001")).toBeInTheDocument();
  expect(await screen.findByText("用途: integration test for platform service")).toBeInTheDocument();
  expect(await screen.findByText("單位: 資訊所")).toBeInTheDocument();
  expect(screen.queryByText("申請人:")).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "停用金鑰" }));
  expect(await screen.findByText("確認停用")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "確認" }));
  expect(await screen.findByText("金鑰已停用。")).toBeInTheDocument();
  await waitFor(() => {
    expect(screen.queryByRole("dialog", { name: "API Key 詳情" })).not.toBeInTheDocument();
  });
});

test("shows applicant identity in detail dialog for admin", async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <MyApiKeysPage auth={adminAuth} />
    </MemoryRouter>
  );

  await user.click((await screen.findAllByRole("button", { name: "查看詳情" }))[0]);
  expect(await screen.findByText("申請人: jane.doe / Jane Doe")).toBeInTheDocument();
});

test("admin can edit key alias in list dialog", async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <MyApiKeysPage auth={adminAuth} />
    </MemoryRouter>
  );

  await user.click((await screen.findAllByRole("button", { name: "編輯 Key Alias" }))[0]);
  const aliasInput = await screen.findByLabelText("Key Alias");
  await user.clear(aliasInput);
  await user.type(aliasInput, "service_ops");
  await user.click(screen.getByRole("button", { name: "儲存" }));
  expect(await screen.findByText("Key Alias 已更新。")).toBeInTheDocument();
  expect(await screen.findByText("service_ops")).toBeInTheDocument();
});

test("admin sees duplicate prompt when key alias already exists", async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <MyApiKeysPage auth={adminAuth} />
    </MemoryRouter>
  );

  await user.click((await screen.findAllByRole("button", { name: "編輯 Key Alias" }))[0]);
  const aliasInput = await screen.findByLabelText("Key Alias");
  await user.clear(aliasInput);
  await user.type(aliasInput, "for_john.admin");
  await user.click(screen.getByRole("button", { name: "儲存" }));
  expect(await screen.findByText("Key Alias 重複，請改用其他名稱。")).toBeInTheDocument();
});

test("user renew hides old key from list", async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <MyApiKeysPage auth={auth} />
    </MemoryRouter>
  );

  expect(await screen.findByText("AS-...mn56")).toBeInTheDocument();
  const moreActionButtons = await screen.findAllByRole("button", { name: "更多操作" });
  await user.click(moreActionButtons[1]);
  await user.click(await screen.findByRole("menuitem", { name: "更新金鑰" }));
  expect(await screen.findByText("確認更新")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "確認" }));
  expect(await screen.findByText("金鑰已更新。")).toBeInTheDocument();
  expect(await screen.findByText("金鑰已更新")).toBeInTheDocument();
  await waitFor(() => {
    expect(screen.queryByText("AS-...mn56")).not.toBeInTheDocument();
  });
});

test("renewed key dialog stays open on backdrop click and escape", async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <MyApiKeysPage auth={auth} />
    </MemoryRouter>
  );

  const moreActionButtons = await screen.findAllByRole("button", { name: "更多操作" });
  await user.click(moreActionButtons[1]);
  await user.click(await screen.findByRole("menuitem", { name: "更新金鑰" }));
  await user.click(screen.getByRole("button", { name: "確認" }));

  expect(await screen.findByText("此明文金鑰只會顯示一次，請立即保存。")).toBeInTheDocument();

  const backdrop = document.querySelector(".MuiBackdrop-root");
  expect(backdrop).not.toBeNull();
  fireEvent.mouseDown(backdrop);
  fireEvent.click(backdrop);
  expect(screen.getByText("此明文金鑰只會顯示一次，請立即保存。")).toBeInTheDocument();

  fireEvent.keyDown(document.activeElement || document.body, { key: "Escape" });
  expect(screen.getByText("此明文金鑰只會顯示一次，請立即保存。")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "我知道了" }));
  await waitFor(() => {
    expect(screen.queryByText("此明文金鑰只會顯示一次，請立即保存。")).not.toBeInTheDocument();
  });
});

test("user can extend active key with selected duration", async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <MyApiKeysPage auth={auth} />
    </MemoryRouter>
  );

  const moreActionButtons = await screen.findAllByRole("button", { name: "更多操作" });
  await user.click(moreActionButtons[0]);
  await user.click(await screen.findByRole("menuitem", { name: "展延金鑰" }));
  expect(await screen.findByText("確認展延")).toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText("展延時長"), "12");
  await user.click(screen.getByRole("button", { name: "確認" }));
  expect(await screen.findByText("金鑰已展延。")).toBeInTheDocument();
  expect(screen.queryByRole("dialog", { name: "確認展延" })).not.toBeInTheDocument();
});

test.each([
  {
    name: "user cannot see extend action before expiration notice",
    buttonIndex: 0,
    shouldSeeExtend: false,
  },
  {
    name: "user can see extend action for expired key even without notice",
    buttonIndex: 2,
    shouldSeeExtend: true,
  },
])("$name", async ({ buttonIndex, shouldSeeExtend }) => {
  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <MyApiKeysPage auth={devUserAuth} />
    </MemoryRouter>
  );

  const moreActionButtons = await screen.findAllByRole("button", { name: "更多操作" });
  await user.click(moreActionButtons[buttonIndex]);
  if (shouldSeeExtend) {
    expect(await screen.findByRole("menuitem", { name: "展延金鑰" })).toBeInTheDocument();
  } else {
    expect(screen.queryByRole("menuitem", { name: "展延金鑰" })).not.toBeInTheDocument();
  }
});

test("renders timestamps in Asia/Taipei on list and detail views", async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <MyApiKeysPage auth={devUserAuth} />
    </MemoryRouter>
  );

  expect(await screen.findByText("2026-03-10 19:00:00")).toBeInTheDocument();

  const detailButtons = await screen.findAllByRole("button", { name: "查看詳情" });
  await user.click(detailButtons[2]);

  expect(await screen.findByText("建立時間: 2026-02-10 19:00:00")).toBeInTheDocument();
  expect(await screen.findByText("到期時間: 2026-03-10 19:00:00")).toBeInTheDocument();
});

test("list uses server pagination params", async () => {
  const user = userEvent.setup();
  const spy = vi.spyOn(mockApiProvider, "listApiKeys");
  render(
    <MemoryRouter>
      <MyApiKeysPage auth={adminAuth} />
    </MemoryRouter>
  );

  expect(await screen.findByText("API Keys")).toBeInTheDocument();
  expect((await screen.findAllByText("jane.doe / Jane Doe")).length).toBeGreaterThan(0);
  await waitFor(() => {
    expect(spy).toHaveBeenCalledWith(expect.objectContaining({ page: 1, page_size: 10 }), adminAuth);
  });

  await user.click(screen.getByRole("combobox", { name: /每頁數量|Rows per page/i }));
  await user.click(screen.getByRole("option", { name: "20" }));
  await waitFor(() => {
    expect(spy).toHaveBeenCalledWith(expect.objectContaining({ page: 1, page_size: 20 }), adminAuth);
  });
});
