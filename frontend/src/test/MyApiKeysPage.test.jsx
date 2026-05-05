import { render, screen } from "@testing-library/react";
import MyApiKeysPage from "../pages/MyApiKeysPage";

const auth = {
  account: "jane.doe",
  name: "Jane Doe",
  email: "jane.doe@company.com",
  department: "Platform Engineering",
  sysid: "user_123"
};

test("shows revoke button only for active rows", async () => {
  render(<MyApiKeysPage auth={auth} />);

  expect(await screen.findByText("API Keys")).toBeInTheDocument();
  const revokeButtons = await screen.findAllByRole("button", { name: "停用" });
  expect(revokeButtons).toHaveLength(1);
});
