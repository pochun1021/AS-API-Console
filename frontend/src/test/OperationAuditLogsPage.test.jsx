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

test("admin can switch to scheduler logs tab and view scheduler entries", async () => {
  const user = userEvent.setup();
  renderPage(<OperationAuditLogsPage auth={adminAuth} />);

  expect(await screen.findByText("操作稽核 Log")).toBeInTheDocument();
  await user.click(screen.getByRole("tab", { name: "排程器 Log" }));

  expect(await screen.findByText("event=usage_sync mode=sync processed_keys=10 success=8 failed=2")).toBeInTheDocument();
  expect(screen.getByRole("columnheader", { name: "Job" })).toBeInTheDocument();
  expect(screen.getByRole("columnheader", { name: "檔案" })).toBeInTheDocument();
  expect(screen.getByLabelText("檔案日期")).toHaveAttribute("aria-disabled", "true");
});

test("scheduler file scope hides file picker outside date mode", async () => {
  const user = userEvent.setup();
  renderPage(<OperationAuditLogsPage auth={adminAuth} />);

  expect(await screen.findByText("操作稽核 Log")).toBeInTheDocument();
  await user.click(screen.getByRole("tab", { name: "排程器 Log" }));
  await user.click(screen.getByLabelText("查詢檔案"));
  await user.click(await screen.findByRole("option", { name: "最新 log" }));

  expect(screen.queryByLabelText("檔案日期")).not.toBeInTheDocument();

  await user.click(screen.getByLabelText("查詢檔案"));
  await user.click(await screen.findByRole("option", { name: "全部 log" }));

  expect(screen.queryByLabelText("檔案日期")).not.toBeInTheDocument();
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
  await user.click(screen.getByLabelText("事件類型"));
  await user.click(await screen.findByRole("option", { name: "whitelist" }));
  await user.click(screen.getByLabelText("動作"));
  await user.click(await screen.findByRole("option", { name: "update" }));
  await user.type(screen.getByLabelText("操作者帳號"), "john");
  await user.click(screen.getByLabelText("目標類型"));
  await user.click(await screen.findByRole("option", { name: "whitelist" }));
  await user.click(await screen.findByRole("columnheader", { name: "操作者" }));

  await waitFor(() => {
    expect(spy).toHaveBeenLastCalledWith(
      expect.objectContaining({
        event_type: "whitelist",
        action: "update",
        actor_account: "john",
        target_type: "whitelist",
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
  await user.click(await screen.findByRole("columnheader", { name: "帳號" }));

  await waitFor(() => {
    expect(spy).toHaveBeenLastCalledWith(
      expect.objectContaining({
        account: "jane",
        sysid: "123",
        role: "user",
        sort_by: "account",
        sort_dir: "asc"
      }),
      adminAuth
    );
  });
});

test("scheduler audit filters send full server-side query params and open raw line dialog", async () => {
  const user = userEvent.setup();
  const spy = vi.spyOn(mockApiProvider, "listSchedulerLogs");
  renderPage(<OperationAuditLogsPage auth={adminAuth} />);

  expect(await screen.findByText("操作稽核 Log")).toBeInTheDocument();
  await user.click(screen.getByRole("tab", { name: "排程器 Log" }));
  expect(await screen.findByText("event=usage_sync mode=sync processed_keys=10 success=8 failed=2")).toBeInTheDocument();

  await user.click(screen.getByLabelText("Job"));
  await user.click(await screen.findByRole("option", { name: "sync_api_key_usage" }));
  await waitFor(() => {
    expect(screen.getByLabelText("檔案日期")).toHaveTextContent("2026-06-17.log");
  });
  await user.click(screen.getByLabelText("Level"));
  await user.click(await screen.findByRole("option", { name: "ERROR" }));
  await user.type(screen.getByLabelText("關鍵字"), "failed=2");
  await user.click(await screen.findByRole("button", { name: "查看原始行" }));

  expect(await screen.findByRole("dialog", { name: "排程器 Log 詳情" })).toBeInTheDocument();
  expect(screen.getByDisplayValue("[2026-06-17T00:15:01+08:00] level=ERROR event=usage_sync mode=sync processed_keys=10 success=8 failed=2")).toBeInTheDocument();
  expect(screen.getAllByDisplayValue("2026-06-17.log").length).toBeGreaterThan(0);

  await waitFor(() => {
    expect(spy).toHaveBeenLastCalledWith(
      expect.objectContaining({
        file_mode: "date",
        from: "2026-06-17",
        to: "2026-06-17",
        job: "sync_api_key_usage",
        level: "ERROR",
        q: "failed=2",
        sort_dir: "desc"
      }),
      adminAuth
    );
  });
});
