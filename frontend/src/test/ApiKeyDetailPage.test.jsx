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
  await user.click(await screen.findByRole("button", { name: "停用金鑰" }));
  expect(await screen.findByText("金鑰已停用。")).toBeInTheDocument();
});

test("shows error for not found key", async () => {
  renderPage("key_999");
  expect(await screen.findByText("id not found")).toBeInTheDocument();
});
