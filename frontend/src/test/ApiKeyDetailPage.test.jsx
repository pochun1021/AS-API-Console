import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import ApiKeyDetailPage from "../pages/ApiKeyDetailPage";
import { mockApiProvider } from "../mocks/mockApiProvider";

const userAuth = {
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

beforeEach(() => {
  mockApiProvider.resetForTests();
});

function renderPage(id, auth = userAuth) {
  render(
    <MemoryRouter initialEntries={[`/api-keys/${id}`]}>
      <Routes>
        <Route path="/api-keys/:id" element={<ApiKeyDetailPage auth={auth} />} />
      </Routes>
    </MemoryRouter>
  );
}

test("shows api key detail and can revoke active key", async () => {
  const user = userEvent.setup();
  renderPage("key_001");

  expect(await screen.findByText("API Key 詳情")).toBeInTheDocument();
  expect(await screen.findByText("ID: key_001")).toBeInTheDocument();
  expect(await screen.findByText("用途: integration test for platform service")).toBeInTheDocument();
  expect(await screen.findByText("單位: Platform Engineering")).toBeInTheDocument();
  expect(screen.queryByText("申請人:")).not.toBeInTheDocument();
  await user.click(await screen.findByRole("button", { name: "停用金鑰" }));
  expect(await screen.findByText("金鑰已停用。")).toBeInTheDocument();
});

test("shows applicant identity for admin", async () => {
  renderPage("key_001", adminAuth);
  expect(await screen.findByText("申請人: jane.doe / Jane Doe")).toBeInTheDocument();
});

test("shows error for not found key", async () => {
  renderPage("key_999");
  expect(await screen.findByText("id not found")).toBeInTheDocument();
});

test("shows dash when purpose is missing", async () => {
  renderPage("key_004", adminAuth);
  expect(await screen.findByText("用途: -")).toBeInTheDocument();
  expect(await screen.findByText("單位: -")).toBeInTheDocument();
});
