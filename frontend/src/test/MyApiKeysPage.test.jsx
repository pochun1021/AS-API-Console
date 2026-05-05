import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import MyApiKeysPage from "../pages/MyApiKeysPage";

const auth = {
  account: "jane.doe",
  name: "Jane Doe",
  email: "jane.doe@company.com",
  department: "Platform Engineering",
  sysid: "user_123",
  role: "user"
};

const adminAuth = {
  account: "john.admin",
  name: "John Admin",
  email: "john.admin@company.com",
  department: "Security",
  sysid: "admin_001",
  role: "admin"
};

test("shows revoke icon only for active rows", async () => {
  render(
    <MemoryRouter>
      <MyApiKeysPage auth={auth} />
    </MemoryRouter>
  );

  expect(await screen.findByText("API Keys")).toBeInTheDocument();
  const revokeButtons = await screen.findAllByRole("button", { name: "停用金鑰" });
  expect(revokeButtons).toHaveLength(1);
  expect(await screen.findAllByRole("link", { name: "查看詳情" })).toHaveLength(2);
  expect(screen.queryByRole("columnheader", { name: "建立時間" })).not.toBeInTheDocument();
});

test("shows owner column for admin list", async () => {
  render(
    <MemoryRouter>
      <MyApiKeysPage auth={adminAuth} />
    </MemoryRouter>
  );

  expect(await screen.findByRole("columnheader", { name: "申請人" })).toBeInTheDocument();
  expect((await screen.findAllByText("jane.doe / Jane Doe")).length).toBeGreaterThan(0);
});
