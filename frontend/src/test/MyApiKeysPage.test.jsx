import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { mockApiProvider } from "../mocks/mockApiProvider";
import MyApiKeysPage from "../pages/MyApiKeysPage";

const auth = {
  account: "jane.doe",
  name: "Jane Doe",
  email: "jane.doe@company.com",
  department: "Platform Engineering",
  sysid: 123,
  role: "user"
};

const adminAuth = {
  account: "john.admin",
  name: "John Admin",
  email: "john.admin@company.com",
  department: "Security",
  sysid: 1,
  role: "admin"
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
  const revokeButtons = await screen.findAllByRole("button", { name: "停用金鑰" });
  expect(revokeButtons).toHaveLength(1);
  const renewButtons = await screen.findAllByRole("button", { name: "更新金鑰" });
  expect(renewButtons).toHaveLength(1);
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
  expect(await screen.findByText("單位: Platform Engineering")).toBeInTheDocument();
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

test("user renew hides old key from list", async () => {
  const user = userEvent.setup();
  render(
    <MemoryRouter>
      <MyApiKeysPage auth={auth} />
    </MemoryRouter>
  );

  expect(await screen.findByText("AS-...mn56")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "更新金鑰" }));
  expect(await screen.findByText("確認更新")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "確認" }));
  expect(await screen.findByText("金鑰已更新。")).toBeInTheDocument();
  expect(await screen.findByText("金鑰已更新")).toBeInTheDocument();
  await waitFor(() => {
    expect(screen.queryByText("AS-...mn56")).not.toBeInTheDocument();
  });
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
