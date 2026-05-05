import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ApplyPage from "../pages/ApplyPage";

const auth = {
  account: "jane.doe",
  name: "Jane Doe",
  email: "jane.doe@company.com",
  department: "Platform Engineering",
  sysid: "user_123"
};

test("validates purpose is required", async () => {
  const user = userEvent.setup();
  render(<ApplyPage auth={auth} />);

  await user.click(screen.getByRole("button", { name: "送出申請" }));

  expect(await screen.findByText("請填寫用途")).toBeInTheDocument();
});

test("shows plaintext key once after successful submit", async () => {
  const user = userEvent.setup();
  render(<ApplyPage auth={auth} />);

  await user.type(screen.getByLabelText("用途"), "integration test");
  await user.click(screen.getByRole("button", { name: "送出申請" }));

  expect(await screen.findByText("此明文金鑰只會顯示一次，請立即保存。")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "我已保存" }));
  await waitFor(() => {
    expect(screen.queryByText("此明文金鑰只會顯示一次，請立即保存。")).not.toBeInTheDocument();
  });
});

test("hides SysID and uses radio for duration", async () => {
  const user = userEvent.setup();
  render(<ApplyPage auth={auth} />);

  expect(screen.queryByLabelText("SysID")).not.toBeInTheDocument();
  expect(screen.getByRole("radio", { name: "6 個月" })).toBeChecked();

  await user.click(screen.getByRole("radio", { name: "12 個月" }));
  expect(screen.getByRole("radio", { name: "12 個月" })).toBeChecked();
});
