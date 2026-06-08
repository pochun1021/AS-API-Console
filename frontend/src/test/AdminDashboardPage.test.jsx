import { render, screen, waitFor } from "@testing-library/react";
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
  const { container } = renderPage(<AdminDashboardPage auth={adminAuth} />);

  expect(await screen.findByText("管理者統計")).toBeInTheDocument();
  expect(screen.getByLabelText("日期區間")).toBeInTheDocument();
  await user.click(screen.getByRole("tab", { name: "圖表" }));

  expect(await screen.findByLabelText("X 軸")).toBeInTheDocument();
  expect(screen.getByLabelText("Y 軸")).toBeInTheDocument();
  expect(screen.getByLabelText("Top N")).toBeInTheDocument();
  expect(screen.queryByLabelText("日期區間")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("口徑")).not.toBeInTheDocument();

  await user.click(screen.getByLabelText("X 軸"));
  await user.click(screen.getByRole("option", { name: "單位" }));

  await user.click(screen.getByLabelText("Y 軸"));
  await user.click(screen.getByRole("option", { name: "已停用" }));

  await user.click(screen.getByLabelText("Top N"));
  await user.click(screen.getByRole("option", { name: "5" }));

  expect(container.querySelectorAll(".MuiChartsAxis-tickLabel").length).toBeGreaterThanOrEqual(5);
  expect(screen.getByRole("tab", { name: "圖表", selected: true })).toBeInTheDocument();
});

test.each([
  {
    name: "admin can open detail dialog from total applications count",
    buttonName: "2",
    dialogName: "jane.doe 的申請總數明細",
    visibleText: "revoked",
    hiddenText: null,
    minRowCount: 3,
  },
  {
    name: "admin can open detail dialog from active count",
    buttonName: "1",
    dialogName: "jane.doe 的啟用中明細",
    visibleText: "active",
    hiddenText: "revoked",
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
