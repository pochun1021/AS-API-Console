import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import { vi } from "vitest";
import { setApiProvider } from "../api/client";
import ApplyPage from "../pages/ApplyPage";

const auth = {
  account: "jane.doe",
  name: "Jane Doe",
  email: "jane.doe@company.com",
  department: "02",
  sysid: 123
};
const adminAuth = { ...auth, role: "admin" };

function renderPage(ui) {
  return render(<LocalizationProvider dateAdapter={AdapterDayjs}>{ui}</LocalizationProvider>);
}

test("validates purpose is required", async () => {
  const user = userEvent.setup();
  renderPage(<ApplyPage auth={auth} />);

  await user.click(screen.getByRole("button", { name: "送出申請" }));

  expect(await screen.findByText("請填寫用途")).toBeInTheDocument();
});

test("blocks unsafe purpose before submit", async () => {
  const user = userEvent.setup();
  const createApplication = vi.fn();
  setApiProvider({ createApplication });
  renderPage(<ApplyPage auth={auth} />);

  await user.type(screen.getByLabelText("用途"), "<script>alert(1)</script>");
  await user.click(screen.getByRole("button", { name: "送出申請" }));

  expect(await screen.findByText("用途不可包含明顯程式語法。")).toBeInTheDocument();
  expect(createApplication).not.toHaveBeenCalled();
});

test("shows plaintext key once after successful submit", async () => {
  const user = userEvent.setup();
  renderPage(<ApplyPage auth={auth} />);

  await user.type(screen.getByLabelText("用途"), "integration test");
  await user.click(screen.getByRole("button", { name: "送出申請" }));

  expect(await screen.findByText("此明文金鑰只會顯示一次，請立即保存。")).toBeInTheDocument();
  const plaintext = screen.getByText((content) => content.startsWith("AS-"));
  expect(plaintext.textContent).toHaveLength(33);
  await user.click(screen.getByRole("button", { name: "我知道了" }));
  await waitFor(() => {
    expect(screen.queryByText("此明文金鑰只會顯示一次，請立即保存。")).not.toBeInTheDocument();
  });
});

test("issued key dialog stays open on backdrop click and escape", async () => {
  const user = userEvent.setup();
  renderPage(<ApplyPage auth={auth} />);

  await user.type(screen.getByLabelText("用途"), "integration test");
  await user.click(screen.getByRole("button", { name: "送出申請" }));

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

test("copies plaintext key and shows check icon feedback", async () => {
  const writeText = vi.fn().mockResolvedValue(undefined);
  const originalClipboard = window.navigator.clipboard;
  Object.defineProperty(window.navigator, "clipboard", {
    value: { writeText },
    configurable: true
  });

  try {
    const user = userEvent.setup();
    renderPage(<ApplyPage auth={auth} />);
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
    renderPage(<ApplyPage auth={auth} />);
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
  renderPage(<ApplyPage auth={auth} />);

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
          code: "APPLICANT_NOT_ELIGIBLE",
          message: "applicant is not eligible"
        }
      };
      throw error;
    }
  };
  setApiProvider(provider);

  renderPage(<ApplyPage auth={auth} />);
  await user.type(screen.getByLabelText("用途"), "integration test");
  await user.click(screen.getByRole("button", { name: "送出申請" }));
  expect(await screen.findByText("你目前不符合申請資格，無法申請 API Key。")).toBeInTheDocument();
});

test("shows actionable auth-context validation message", async () => {
  const user = userEvent.setup();
  setApiProvider({
    createApplication: vi.fn().mockRejectedValue({
      payload: {
        error: {
          code: "VALIDATION_ERROR",
          message: "missing auth headers: x-name, x-email"
        }
      }
    })
  });

  renderPage(<ApplyPage auth={auth} />);
  await user.type(screen.getByLabelText("用途"), "integration test");
  await user.click(screen.getByRole("button", { name: "送出申請" }));

  expect(await screen.findByText("登入資訊缺少必要欄位：x-name, x-email。請重新登入後再試。")).toBeInTheDocument();
});

test("shows actionable sysid validation message", async () => {
  const user = userEvent.setup();
  setApiProvider({
    createApplication: vi.fn().mockRejectedValue({
      payload: {
        error: {
          code: "VALIDATION_ERROR",
          message: "x-sysid must be numeric"
        }
      }
    })
  });

  renderPage(<ApplyPage auth={auth} />);
  await user.type(screen.getByLabelText("用途"), "integration test");
  await user.click(screen.getByRole("button", { name: "送出申請" }));

  expect(await screen.findByText("登入資訊中的 SysID 格式錯誤，必須是數字。")).toBeInTheDocument();
});

test("admin proxy mode sends target_identity", async () => {
  const user = userEvent.setup();
  const searchUsers = vi.fn().mockResolvedValue({
    items: [{ id: "u1", account: "target.user", name: "Target User", email: "target.user@company.com", department: "02", sysid: 9999 }]
  });
  const createApplication = vi.fn().mockResolvedValue({
    application: { id: "app-1", account: "target.user", status: "active", issued_at: new Date().toISOString(), expires_at: new Date().toISOString() },
    api_key_plaintext: "AS-abcdefghijklmnopqrstuvwxyz1234"
  });
  setApiProvider({ createApplication, searchUsers });
  renderPage(<ApplyPage auth={adminAuth} />);

  await user.click(screen.getByRole("radio", { name: "協助他人申請" }));
  const accountInput = screen.getByLabelText("帳號");
  await user.type(accountInput, "target.user");
  await user.tab();
  await waitFor(() => {
    expect(searchUsers).toHaveBeenCalledWith("target.user", adminAuth);
  });
  await user.type(screen.getByLabelText("用途"), "proxy apply");
  await user.click(screen.getByRole("button", { name: "送出申請" }));

  await waitFor(() => {
    expect(createApplication).toHaveBeenCalled();
  });
  expect(createApplication.mock.calls[0][0].target_identity).toEqual({
    account: "target.user"
  });
});

test("proxy account blur auto-fills identity fields", async () => {
  const user = userEvent.setup();
  const searchUsers = vi.fn().mockResolvedValue({
    items: [{ id: "u1", account: "target.user", name: "Target User", email: "target.user@company.com", department: "02", sysid: 9999 }]
  });
  setApiProvider({ searchUsers, createApplication: vi.fn() });
  renderPage(<ApplyPage auth={adminAuth} />);

  await user.click(screen.getByRole("radio", { name: "協助他人申請" }));
  const accountInput = screen.getByLabelText("帳號");
  await user.type(accountInput, "target.user");
  await user.tab();

  expect(await screen.findByDisplayValue("Target User")).toBeInTheDocument();
  expect(screen.getByDisplayValue("target.user@company.com")).toBeInTheDocument();
});

test("blocks unsafe proxy account before lookup", async () => {
  const user = userEvent.setup();
  const searchUsers = vi.fn();
  setApiProvider({ searchUsers, createApplication: vi.fn() });
  renderPage(<ApplyPage auth={adminAuth} />);

  await user.click(screen.getByRole("radio", { name: "協助他人申請" }));
  const accountInput = screen.getByLabelText("帳號");
  await user.type(accountInput, "foo => bar");
  await user.tab();

  expect(await screen.findByText("代申請帳號不可包含明顯程式語法。")).toBeInTheDocument();
  expect(searchUsers).not.toHaveBeenCalled();
});

test("proxy account lookup opens picker when multiple candidates", async () => {
  const user = userEvent.setup();
  const searchUsers = vi.fn().mockResolvedValue({
    items: [
      { id: "u1", account: "target.user", name: "Target User A", email: "a@company.com", department: "01", sysid: 1001 },
      { id: "u2", account: "target.user", name: "Target User B", email: "b@company.com", department: "02", sysid: 1002 }
    ]
  });
  setApiProvider({ searchUsers, createApplication: vi.fn() });
  renderPage(<ApplyPage auth={adminAuth} />);

  await user.click(screen.getByRole("radio", { name: "協助他人申請" }));
  const accountInput = screen.getByLabelText("帳號");
  await user.type(accountInput, "target.user");
  await user.tab();

  expect(await screen.findByText("請選擇目標人員")).toBeInTheDocument();
  await user.click(screen.getAllByRole("button", { name: "選擇此人" })[1]);
  expect(await screen.findByDisplayValue("Target User B")).toBeInTheDocument();
});

test("proxy submit is blocked when target identity lookup is not confirmed", async () => {
  const user = userEvent.setup();
  const createApplication = vi.fn();
  setApiProvider({ createApplication, searchUsers: vi.fn().mockResolvedValue({ items: [] }) });
  renderPage(<ApplyPage auth={adminAuth} />);

  await user.click(screen.getByRole("radio", { name: "協助他人申請" }));
  await user.type(screen.getByLabelText("帳號"), "missing.user");
  await user.type(screen.getByLabelText("用途"), "proxy apply");
  await user.click(screen.getByRole("button", { name: "送出申請" }));

  expect(await screen.findByText("請先完成帳號查詢並確認目標人員。")).toBeInTheDocument();
  expect(createApplication).not.toHaveBeenCalled();
});

test("proxy lookup not found shows error alert after info alert", async () => {
  const user = userEvent.setup();
  setApiProvider({ createApplication: vi.fn(), searchUsers: vi.fn().mockResolvedValue({ items: [] }) });
  renderPage(<ApplyPage auth={adminAuth} />);

  await user.click(screen.getByRole("radio", { name: "協助他人申請" }));
  const accountInput = screen.getByLabelText("帳號");
  await user.type(accountInput, "missing.user");
  await user.tab();

  expect(await screen.findByText("系統會依帳號自動查詢姓名、Email、單位與 SysID。")).toBeInTheDocument();
  expect(await screen.findByText("查無帳號")).toBeInTheDocument();
});

test("proxy lookup service unavailable shows soap service unavailable", async () => {
  const user = userEvent.setup();
  const searchUsers = vi.fn().mockRejectedValue({
    payload: { error: { code: "SOAP_SERVICE_UNAVAILABLE", message: "service down" } }
  });
  setApiProvider({ createApplication: vi.fn(), searchUsers });
  renderPage(<ApplyPage auth={adminAuth} />);

  await user.click(screen.getByRole("radio", { name: "協助他人申請" }));
  const accountInput = screen.getByLabelText("帳號");
  await user.type(accountInput, "target.user");
  await user.tab();

  expect(await screen.findByText("帳號查詢服務暫時不可用，請稍後再試。")).toBeInTheDocument();
});

test("proxy submit shows target-not-unique validation detail", async () => {
  const user = userEvent.setup();
  setApiProvider({
    searchUsers: vi.fn().mockResolvedValue({
      items: [{ id: "u1", account: "target.user", name: "Target User", email: "target.user@company.com", department: "02", sysid: 9999 }]
    }),
    createApplication: vi.fn().mockRejectedValue({
      payload: {
        error: {
          code: "VALIDATION_ERROR",
          message: "target account is not unique"
        }
      }
    })
  });

  renderPage(<ApplyPage auth={adminAuth} />);

  await user.click(screen.getByRole("radio", { name: "協助他人申請" }));
  const accountInput = screen.getByLabelText("帳號");
  await user.type(accountInput, "target.user");
  await user.tab();
  await user.type(screen.getByLabelText("用途"), "proxy apply");
  await user.click(screen.getByRole("button", { name: "送出申請" }));

  expect(await screen.findByText("查詢到多筆相同帳號，請重新查詢並選擇正確人員。")).toBeInTheDocument();
});

test("proxy account lookup hint is visible only in proxy mode", async () => {
  const user = userEvent.setup();
  renderPage(<ApplyPage auth={adminAuth} />);

  expect(screen.queryByText("系統會依帳號自動查詢姓名、Email、單位與 SysID。")).not.toBeInTheDocument();

  await user.click(screen.getByRole("radio", { name: "協助他人申請" }));
  expect(screen.getByText("系統會依帳號自動查詢姓名、Email、單位與 SysID。")).toBeInTheDocument();

  await user.click(screen.getByRole("radio", { name: "為自己申請" }));
  expect(screen.queryByText("系統會依帳號自動查詢姓名、Email、單位與 SysID。")).not.toBeInTheDocument();
});
