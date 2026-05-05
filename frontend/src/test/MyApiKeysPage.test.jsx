import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import MyApiKeysPage from "../pages/MyApiKeysPage";

const auth = {
  account: "jane.doe",
  name: "Jane Doe",
  email: "jane.doe@company.com",
  department: "Platform Engineering",
  sysid: "user_123"
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
});
