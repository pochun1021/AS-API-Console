import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import AdminDashboardPage from "../pages/AdminDashboardPage";
import { mockApiProvider } from "../mocks/mockApiProvider";

const adminAuth = {
  account: "john.admin",
  name: "John Admin",
  email: "john.admin@company.com",
  department: "03",
  sysid: 1,
  role: "admin"
};

const userAuth = {
  account: "jane.doe",
  name: "Jane Doe",
  email: "jane.doe@company.com",
  department: "02",
  sysid: 123,
  role: "user"
};

beforeEach(() => {
  mockApiProvider.resetForTests();
});
afterEach(() => vi.restoreAllMocks());

function renderPage(ui) {
  return render(<LocalizationProvider dateAdapter={AdapterDayjs}>{ui}</LocalizationProvider>);
}

test("admin can load and filter statistics", async () => {
  const user = userEvent.setup();
  renderPage(<AdminDashboardPage auth={adminAuth} />);

  expect(await screen.findByText("管理者統計")).toBeInTheDocument();
  expect(screen.getByLabelText("日期區間")).toBeInTheDocument();
  expect(await screen.findByText("jane.doe")).toBeInTheDocument();

  await user.click(screen.getByLabelText("口徑"));
  await user.click(screen.getByRole("option", { name: "revoked" }));

  await waitFor(() => {
    expect(screen.getByText("sam.chen")).toBeInTheDocument();
  });

  await user.click(screen.getByLabelText("口徑"));
  await user.click(screen.getByRole("option", { name: "all" }));

  await user.type(screen.getAllByLabelText("帳號")[0], "alice");

  await waitFor(() => {
    expect(screen.getByText("alice.wang")).toBeInTheDocument();
  });
});

test("admin dashboard sends server sort params when sorting columns", async () => {
  const user = userEvent.setup();
  const spy = vi.spyOn(mockApiProvider, "listApiKeyUserStatistics");
  renderPage(<AdminDashboardPage auth={adminAuth} />);

  expect(await screen.findByText("管理者統計")).toBeInTheDocument();
  await user.click(await screen.findByRole("columnheader", { name: "帳號" }));

  await waitFor(() => {
    expect(spy).toHaveBeenLastCalledWith(
      expect.objectContaining({ sort_by: "owner_account", sort_dir: "asc" }),
      adminAuth
    );
  });
});

test("table pagination sends the next page to the server", async () => {
  const user = userEvent.setup();
  const original = mockApiProvider.listApiKeyUserStatistics.bind(mockApiProvider);
  const spy = vi.spyOn(mockApiProvider, "listApiKeyUserStatistics").mockImplementation(async (params, auth) => ({
    ...await original(params, auth), total: 30
  }));
  renderPage(<AdminDashboardPage auth={adminAuth} />);
  await screen.findByText("jane.doe");
  await user.click(screen.getByRole("button", { name: /下一頁|next page/i }));
  await waitFor(() => expect(spy).toHaveBeenLastCalledWith(
    expect.objectContaining({ page: 2, page_size: 10, sort_by: "total_applications", sort_dir: "desc" }), adminAuth
  ));
});

test("admin dashboard sends custom owner filters without DataGrid filter model", async () => {
  const user = userEvent.setup();
  const spy = vi.spyOn(mockApiProvider, "listApiKeyUserStatistics");
  renderPage(<AdminDashboardPage auth={adminAuth} />);

  expect(await screen.findByText("管理者統計")).toBeInTheDocument();
  await user.type(screen.getAllByLabelText("帳號")[0], "ktu");
  await user.type(screen.getAllByLabelText("姓名")[0], "尤");
  await user.type(screen.getByLabelText("Email"), "ktu@example.com");
  await user.click(screen.getAllByLabelText("單位")[0]);
  await user.click(await screen.findByRole("option", { name: "02 資訊所" }));

  await waitFor(() => {
    expect(spy).toHaveBeenLastCalledWith(
      expect.objectContaining({
        owner_account: "ktu",
        owner_name: "尤",
        owner_email: "ktu@example.com",
        owner_department: "02",
      }),
      adminAuth
    );
  });
});

test("admin dashboard can clear table filters", async () => {
  const user = userEvent.setup();
  const spy = vi.spyOn(mockApiProvider, "listApiKeyUserStatistics");
  renderPage(<AdminDashboardPage auth={adminAuth} />);

  expect(await screen.findByText("管理者統計")).toBeInTheDocument();
  const clearButton = screen.getByRole("button", { name: "清除篩選" });
  expect(clearButton).toBeDisabled();

  await user.type(screen.getAllByLabelText("帳號")[0], "alice");

  await waitFor(() => {
    expect(clearButton).not.toBeDisabled();
    expect(spy).toHaveBeenLastCalledWith(
      expect.objectContaining({
        owner_account: "alice",
      }),
      adminAuth
    );
  });

  await user.click(clearButton);

  await waitFor(() => {
    expect(screen.getAllByLabelText("帳號")[0]).toHaveValue("");
    expect(clearButton).toBeDisabled();
    expect(spy).toHaveBeenLastCalledWith(
      expect.objectContaining({
        scope: "all",
        from: undefined,
        to: undefined,
        owner_account: undefined,
        owner_name: undefined,
        owner_email: undefined,
        owner_department: undefined,
        page: 1,
      }),
      adminAuth
    );
  });
});

test("admin can switch to chart view and change axes", async () => {
  const user = userEvent.setup();
  const chartSpy = vi.spyOn(mockApiProvider, "getApiKeyStatisticsChart");
  renderPage(<AdminDashboardPage auth={adminAuth} />);

  expect(await screen.findByText("管理者統計")).toBeInTheDocument();
  expect(screen.getByLabelText("日期區間")).toBeInTheDocument();
  await user.click(screen.getByRole("tab", { name: "圖表" }));

  expect(await screen.findByLabelText("X 軸")).toBeInTheDocument();
  expect(screen.getByLabelText("Y 軸")).toBeInTheDocument();
  expect(screen.getByLabelText("Top N")).toBeInTheDocument();
  expect(screen.getByLabelText("日期區間")).toBeInTheDocument();
  expect(screen.getByLabelText("口徑")).toBeInTheDocument();

  await user.click(screen.getByLabelText("X 軸"));
  await user.click(screen.getByRole("option", { name: "單位" }));

  await user.click(screen.getByLabelText("Y 軸"));
  await user.click(screen.getByRole("option", { name: "已停用" }));

  await user.click(screen.getByLabelText("Top N"));
  await user.click(screen.getByRole("option", { name: "5" }));

  await waitFor(() => expect(chartSpy).toHaveBeenLastCalledWith(
    expect.objectContaining({ x_axis: "department", y_axis: "revoked_count", top_n: 5 }), adminAuth
  ));
  expect(screen.getByRole("tab", { name: "圖表", selected: true })).toBeInTheDocument();
});

test("chart uses its aggregate response instead of the table page, including totals and zero values", async () => {
  const user = userEvent.setup();
  const tableSpy = vi.spyOn(mockApiProvider, "listApiKeyUserStatistics");
  const chartSpy = vi.spyOn(mockApiProvider, "getApiKeyStatisticsChart").mockResolvedValue({
    items: [{ label: "server.aggregate", value: 7 }], x_axis: "account",
    y_axis: "total_applications", top_n: 10, total_value: 31, displayed_value: 7, group_count: 12
  });
  renderPage(<AdminDashboardPage auth={adminAuth} />);
  await screen.findByText("jane.doe");
  await user.click(screen.getByRole("tab", { name: "圖表" }));
  await waitFor(() => expect(chartSpy).toHaveBeenCalledWith(
    expect.objectContaining({ x_axis: "account", y_axis: "total_applications", top_n: 10, scope: "all" }), adminAuth
  ));
  expect(await screen.findByText(/符合條件的指標總量: 31/)).toBeInTheDocument();
  expect(screen.getByText(/Top N 顯示小計: 7/)).toBeInTheDocument();
  expect(screen.getByText(/完整分組數: 12/)).toBeInTheDocument();
  expect(tableSpy).toHaveBeenCalledTimes(1);

  chartSpy.mockResolvedValue({ items: [], x_axis: "account", y_axis: "active_count", top_n: 10,
    total_value: 0, displayed_value: 0, group_count: 0 });
  await user.click(screen.getByLabelText("口徑"));
  await user.click(screen.getByRole("option", { name: "revoked" }));
  await user.click(screen.getByLabelText("Y 軸"));
  await user.click(screen.getByRole("option", { name: "啟用中" }));
  await waitFor(() => expect(chartSpy).toHaveBeenLastCalledWith(
    expect.objectContaining({ scope: "revoked", y_axis: "active_count" }), adminAuth
  ));
  expect(await screen.findByText(/符合條件的指標總量: 0 啟用中/)).toBeInTheDocument();
  expect(screen.getByText(/Top N 顯示小計: 0 啟用中/)).toBeInTheDocument();
});

test("table and chart keep independent scope, dates and department across tabs and resets", async () => {
  const user = userEvent.setup();
  const tableSpy = vi.spyOn(mockApiProvider, "listApiKeyUserStatistics");
  const chartSpy = vi.spyOn(mockApiProvider, "getApiKeyStatisticsChart");
  renderPage(<AdminDashboardPage auth={adminAuth} />);
  await screen.findByText("jane.doe");
  await user.click(screen.getByLabelText("口徑"));
  await user.click(screen.getByRole("option", { name: "active" }));
  await user.click(screen.getByRole("button", { name: "日期區間 picker" }));
  fireEvent.change(await screen.findByLabelText("起始日期"), { target: { value: "2026-01-01" } });
  fireEvent.change(screen.getByLabelText("結束日期"), { target: { value: "2026-01-31" } });
  await user.keyboard("{Escape}");
  await waitFor(() => expect(tableSpy).toHaveBeenLastCalledWith(
    expect.objectContaining({ scope: "active", from: "2026-01-01", to: "2026-01-31" }), adminAuth
  ));
  const tableCalls = tableSpy.mock.calls.length;
  await user.click(screen.getByRole("tab", { name: "圖表" }));
  await waitFor(() => expect(chartSpy).toHaveBeenLastCalledWith(
    expect.objectContaining({ scope: "all", from: undefined, owner_department: undefined }), adminAuth
  ));
  await user.click(screen.getByLabelText("口徑"));
  await user.click(screen.getByRole("option", { name: "revoked" }));
  await user.click(screen.getByRole("button", { name: "日期區間 picker" }));
  fireEvent.change(await screen.findByLabelText("起始日期"), { target: { value: "2026-02-01" } });
  fireEvent.change(screen.getByLabelText("結束日期"), { target: { value: "2026-02-28" } });
  await user.keyboard("{Escape}");
  await user.click(screen.getByLabelText("單位"));
  await user.click(await screen.findByRole("option", { name: "02 資訊所" }));
  await waitFor(() => expect(chartSpy).toHaveBeenLastCalledWith(
    expect.objectContaining({ scope: "revoked", from: "2026-02-01", to: "2026-02-28", owner_department: "02" }), adminAuth
  ));
  expect(tableSpy).toHaveBeenCalledTimes(tableCalls);
  await user.click(screen.getByRole("tab", { name: "表格" }));
  expect(screen.getByLabelText("日期區間")).toHaveValue("2026-01-01 - 2026-01-31");
  expect(screen.getByLabelText("口徑")).toHaveTextContent("active");
  await user.click(screen.getByRole("button", { name: "清除篩選" }));
  await waitFor(() => expect(tableSpy).toHaveBeenLastCalledWith(
    expect.objectContaining({ scope: "all", from: undefined, page: 1 }), adminAuth
  ));
  await user.click(screen.getByRole("tab", { name: "圖表" }));
  expect(screen.getByLabelText("日期區間")).toHaveValue("2026-02-01 - 2026-02-28");
  expect(screen.getByLabelText("口徑")).toHaveTextContent("revoked");
  await user.click(screen.getByRole("button", { name: "清除篩選" }));
  await waitFor(() => expect(chartSpy).toHaveBeenLastCalledWith(
    expect.objectContaining({ scope: "all", from: undefined, owner_department: undefined, x_axis: "account", top_n: 10 }), adminAuth
  ));
});

test("late chart response cannot replace a newer filter result", async () => {
  const user = userEvent.setup();
  const pending = [];
  const chartSpy = vi.spyOn(mockApiProvider, "getApiKeyStatisticsChart").mockImplementation(() =>
    new Promise((resolve) => pending.push(resolve))
  );
  renderPage(<AdminDashboardPage auth={adminAuth} />);
  await user.click(screen.getByRole("tab", { name: "圖表" }));
  await waitFor(() => expect(chartSpy).toHaveBeenCalledTimes(1));
  await user.click(screen.getByLabelText("口徑"));
  await user.click(screen.getByRole("option", { name: "revoked" }));
  await waitFor(() => expect(chartSpy).toHaveBeenCalledTimes(2));
  await act(async () => pending[1]({ items: [], total_value: 2, displayed_value: 2, group_count: 1 }));
  expect(await screen.findByText(/符合條件的指標總量: 2/)).toBeInTheDocument();
  await act(async () => pending[0]({ items: [], total_value: 99, displayed_value: 99, group_count: 99 }));
  expect(screen.getByText(/符合條件的指標總量: 2/)).toBeInTheDocument();
  expect(screen.queryByText(/符合條件的指標總量: 99/)).not.toBeInTheDocument();
});

test("late table response cannot replace newer filter results", async () => {
  const user = userEvent.setup();
  const pending = [];
  vi.spyOn(mockApiProvider, "listApiKeyUserStatistics").mockImplementation(() =>
    new Promise((resolve) => pending.push(resolve))
  );
  renderPage(<AdminDashboardPage auth={adminAuth} />);
  await waitFor(() => expect(pending).toHaveLength(1));
  await user.type(screen.getAllByLabelText("帳號")[0], "x");
  await waitFor(() => expect(pending).toHaveLength(2));
  await act(async () => pending[1]({ items: [], total: 0 }));
  expect(await screen.findByText("目前沒有統計資料")).toBeInTheDocument();
  await act(async () => pending[0]({ items: [{ owner_account: "stale.owner" }], total: 1 }));
  expect(screen.queryByText("stale.owner")).not.toBeInTheDocument();
});

test("detail dialog uses table dates after chart dates change", async () => {
  const user = userEvent.setup();
  const detailSpy = vi.spyOn(mockApiProvider, "listApiKeys");
  renderPage(<AdminDashboardPage auth={adminAuth} />);
  await screen.findByText("jane.doe");
  await user.click(screen.getByRole("tab", { name: "圖表" }));
  await user.click(screen.getByRole("button", { name: "日期區間 picker" }));
  fireEvent.change(await screen.findByLabelText("起始日期"), { target: { value: "2026-02-01" } });
  await user.keyboard("{Escape}");
  await user.click(screen.getByRole("tab", { name: "表格" }));
  const row = (await screen.findByText("jane.doe")).closest('[role="row"]');
  await user.click(within(row).getAllByRole("button")[0]);
  await waitFor(() => expect(detailSpy).toHaveBeenLastCalledWith(
    expect.objectContaining({ owner_account: "jane.doe", from: undefined, to: undefined }), adminAuth
  ));
});

test("ordinary user cannot request either statistics endpoint", async () => {
  const tableSpy = vi.spyOn(mockApiProvider, "listApiKeyUserStatistics");
  const chartSpy = vi.spyOn(mockApiProvider, "getApiKeyStatisticsChart");
  renderPage(<AdminDashboardPage auth={userAuth} />);
  expect(screen.getByText(/僅管理者可使用/)).toBeInTheDocument();
  expect(tableSpy).not.toHaveBeenCalled();
  expect(chartSpy).not.toHaveBeenCalled();
});

test.each([
  {
    name: "admin can open detail dialog from total applications count",
    buttonName: "2",
    dialogName: "jane.doe 的申請總數明細",
    visibleText: "已停用",
    hiddenText: null,
    minRowCount: 3,
  },
  {
    name: "admin can open detail dialog from active count",
    buttonName: "1",
    dialogName: "jane.doe 的啟用中明細",
    visibleText: "啟用中",
    hiddenText: "已停用",
    minRowCount: null,
  },
])("$name", async ({ buttonName, dialogName, visibleText, hiddenText, minRowCount }) => {
  const user = userEvent.setup();
  renderPage(<AdminDashboardPage auth={adminAuth} />);

  expect(await screen.findByText("jane.doe")).toBeInTheDocument();
  const ownerCell = screen.getByText("jane.doe");
  const ownerRow = ownerCell.closest('[role="row"]');
  await user.click(within(ownerRow).getByRole("button", { name: buttonName }));
  const dialog = await screen.findByRole("dialog", { name: dialogName });
  await waitFor(() => {
    expect(within(dialog).queryByText("載入 API Key 明細中...")).not.toBeInTheDocument();
  });
  if (minRowCount !== null) {
    expect(within(dialog).getAllByRole("row").length).toBeGreaterThanOrEqual(minRowCount);
    expect(within(dialog).getAllByText("for_jane.doe").length).toBeGreaterThanOrEqual(1);
  }
  expect(within(dialog).getByText(visibleText)).toBeInTheDocument();
  if (hiddenText) {
    expect(within(dialog).queryByText(hiddenText)).not.toBeInTheDocument();
  }
});
