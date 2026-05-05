import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import AppLayout from "../components/AppLayout";

const userAuth = {
  account: "jane.doe",
  name: "Jane Doe",
  email: "jane.doe@company.com",
  department: "Platform Engineering",
  sysid: "user_123",
  role: "user"
};

const adminAuth = {
  ...userAuth,
  role: "admin"
};

test("user sees apply and api keys nav only", () => {
  render(
    <MemoryRouter>
      <AppLayout auth={userAuth}>
        <div>content</div>
      </AppLayout>
    </MemoryRouter>
  );

  expect(screen.getByRole("link", { name: "申請" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "API Keys" })).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "白名單管理" })).not.toBeInTheDocument();
});

test("admin sees whitelist nav", () => {
  render(
    <MemoryRouter>
      <AppLayout auth={adminAuth}>
        <div>content</div>
      </AppLayout>
    </MemoryRouter>
  );

  expect(screen.getByRole("link", { name: "白名單管理" })).toBeInTheDocument();
});
