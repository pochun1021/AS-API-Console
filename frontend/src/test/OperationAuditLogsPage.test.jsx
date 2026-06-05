import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import OperationAuditLogsPage from "../pages/OperationAuditLogsPage";
import { mockApiProvider } from "../mocks/mockApiProvider";

const adminAuth = {
  account: "john.admin",
  name: "John Admin",
  email: "john.admin@company.com",
  department: "Security",
  sysid: 1,
  role: "admin"
};

const userAuth = {
  account: "jane.doe",
  name: "Jane Doe",
  email: "jane.doe@company.com",
  department: "Platform Engineering",
  sysid: 123,
  role: "user"
};

beforeEach(() => {
  mockApiProvider.resetForTests();
});

function renderPage(ui) {
  return render(<LocalizationProvider dateAdapter={AdapterDayjs}>{ui}</LocalizationProvider>);
}

test("admin can switch to login logs tab and view login entries", async () => {
  const user = userEvent.setup();
  renderPage(<OperationAuditLogsPage auth={adminAuth} />);

  expect(await screen.findByText("操作稽核 Log")).toBeInTheDocument();
  await user.click(screen.getByRole("tab", { name: "登入紀錄" }));

  expect(await screen.findByText("jane.doe")).toBeInTheDocument();
  expect(screen.getByText("req-auth-001")).toBeInTheDocument();
  expect(screen.getByRole("columnheader", { name: "Provider" })).toBeInTheDocument();
});

test("admin can open failure detail dialog for operation audit logs", async () => {
  const user = userEvent.setup();
  renderPage(<OperationAuditLogsPage auth={adminAuth} />);

  expect(await screen.findByText("操作稽核 Log")).toBeInTheDocument();
  expect(await screen.findByText("VALIDATION_ERROR")).toBeInTheDocument();
  await user.click(screen.getByText("查看詳情"));

  expect(await screen.findByRole("dialog", { name: "操作稽核詳情" })).toBeInTheDocument();
  expect(screen.getByDisplayValue("VALIDATION_ERROR")).toBeInTheDocument();
  expect(screen.getByDisplayValue("req-op-002")).toBeInTheDocument();
  expect(screen.getByDisplayValue("status must be active or inactive")).toBeInTheDocument();
});

test("non-admin user is blocked", async () => {
  renderPage(<OperationAuditLogsPage auth={userAuth} />);
  expect(await screen.findByText("僅管理者可查看操作稽核 Log。")).toBeInTheDocument();
});

test("operation audit filters send full server-side query params", async () => {
  const user = userEvent.setup();
  const spy = vi.spyOn(mockApiProvider, "listOperationAuditLogs");
  renderPage(<OperationAuditLogsPage auth={adminAuth} />);

  expect(await screen.findByText("操作稽核 Log")).toBeInTheDocument();
  await user.type(screen.getByLabelText("動作"), "up");
  await user.type(screen.getByLabelText("操作者帳號"), "john");
  await user.type(screen.getByLabelText("目標 ID"), "wl");
  await user.type(screen.getByLabelText("錯誤碼"), "VALID");
  await user.click(await screen.findByRole("columnheader", { name: "操作者" }));

  await waitFor(() => {
    expect(spy).toHaveBeenLastCalledWith(
      expect.objectContaining({
        action: "up",
        actor_account: "john",
        target_id: "wl",
        error_code: "VALID",
        sort_by: "actor_account",
        sort_dir: "asc"
      }),
      adminAuth
    );
  });
});

test("login audit filters send full server-side query params", async () => {
  const user = userEvent.setup();
  const spy = vi.spyOn(mockApiProvider, "listAuthAuditLogs");
  renderPage(<OperationAuditLogsPage auth={adminAuth} />);

  expect(await screen.findByText("操作稽核 Log")).toBeInTheDocument();
  await user.click(screen.getByRole("tab", { name: "登入紀錄" }));
  expect(await screen.findByText("jane.doe")).toBeInTheDocument();

  await user.type(screen.getByLabelText("帳號"), "jane");
  await user.type(screen.getByLabelText("SysID"), "123");
  await user.type(screen.getByLabelText("角色"), "user");
  await user.type(screen.getByLabelText("Request ID"), "001");
  await user.click(await screen.findByRole("columnheader", { name: "Provider" }));

  await waitFor(() => {
    expect(spy).toHaveBeenLastCalledWith(
      expect.objectContaining({
        account: "jane",
        sysid: "123",
        role: "user",
        request_id: "001",
        sort_by: "provider",
        sort_dir: "asc"
      }),
      adminAuth
    );
  });
});
