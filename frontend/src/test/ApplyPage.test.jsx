import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { setApiProvider } from "../api/client";
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
  const plaintext = screen.getByText((content) => content.startsWith("AS-"));
  expect(plaintext.textContent).toHaveLength(33);
  await user.click(screen.getByRole("button", { name: "我已保存" }));
  await waitFor(() => {
    expect(screen.queryByText("此明文金鑰只會顯示一次，請立即保存。")).not.toBeInTheDocument();
  });
});

test("copies plaintext key and shows check icon feedback", async () => {
  const writeText = vi.fn().mockResolvedValue(undefined);
  const originalClipboard = window.navigator.clipboard;
  Object.defineProperty(window.navigator, "clipboard", {
    value: { writeText },
    configurable: true
  });

  try {
    const user = userEvent.setup();
    render(<ApplyPage auth={auth} />);
    await user.type(screen.getByLabelText("用途"), "integration test");
    await user.click(screen.getByRole("button", { name: "送出申請" }));
    await screen.findByText("此明文金鑰只會顯示一次，請立即保存。");

    await user.click(screen.getByRole("button", { name: "複製金鑰" }));
    expect(await screen.findByRole("button", { name: "已複製金鑰" })).toBeInTheDocument();
    expect(screen.queryByText("目前無法複製金鑰，請手動複製。")).not.toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "複製金鑰" })).toBeInTheDocument();
    }, { timeout: 2500 });
  } finally {
    Object.defineProperty(window.navigator, "clipboard", {
      value: originalClipboard,
      configurable: true
    });
  }
});

test("copies key by icon click even when key text is already selected", async () => {
  const writeText = vi.fn().mockResolvedValue(undefined);
  const originalClipboard = window.navigator.clipboard;
  Object.defineProperty(window.navigator, "clipboard", {
    value: { writeText },
    configurable: true
  });

  try {
    const user = userEvent.setup();
    render(<ApplyPage auth={auth} />);
    await user.type(screen.getByLabelText("用途"), "integration test");
    await user.click(screen.getByRole("button", { name: "送出申請" }));
    const plaintext = await screen.findByText((content) => content.startsWith("AS-"));

    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(plaintext);
    selection?.removeAllRanges();
    selection?.addRange(range);

    await user.click(screen.getByRole("button", { name: "複製金鑰" }));
    expect(await screen.findByRole("button", { name: "已複製金鑰" })).toBeInTheDocument();
  } finally {
    Object.defineProperty(window.navigator, "clipboard", {
      value: originalClipboard,
      configurable: true
    });
  }
});

test("hides SysID and uses radio for duration", async () => {
  const user = userEvent.setup();
  render(<ApplyPage auth={auth} />);

  expect(screen.queryByLabelText("SysID")).not.toBeInTheDocument();
  expect(screen.getByRole("radio", { name: "6 個月" })).toBeChecked();

  await user.click(screen.getByRole("radio", { name: "12 個月" }));
  expect(screen.getByRole("radio", { name: "12 個月" })).toBeChecked();
});

test("shows Chinese error message when API returns English message", async () => {
  const user = userEvent.setup();
  const provider = {
    async createApplication() {
      const error = new Error("email is not in active whitelist");
      error.payload = {
        error: {
          code: "APPLICANT_NOT_WHITELISTED",
          message: "email is not in active whitelist"
        }
      };
      throw error;
    }
  };
  setApiProvider(provider);

  render(<ApplyPage auth={auth} />);
  await user.type(screen.getByLabelText("用途"), "integration test");
  await user.click(screen.getByRole("button", { name: "送出申請" }));
  expect(await screen.findByText("你的 Email 不在白名單中，無法申請 API Key。")).toBeInTheDocument();
});
