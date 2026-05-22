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
  expect(await screen.findByText("jane.doe")).toBeInTheDocument();

  await user.click(screen.getByLabelText("口徑"));
  await user.click(screen.getByRole("option", { name: "revoked" }));

  await waitFor(() => {
    expect(screen.getByText("sam.chen")).toBeInTheDocument();
  });

  await user.click(screen.getByLabelText("口徑"));
  await user.click(screen.getByRole("option", { name: "all" }));

  await user.clear(screen.getByLabelText("關鍵字"));
  await user.type(screen.getByLabelText("關鍵字"), "alice");

  await waitFor(() => {
    expect(screen.getByText("alice.wang")).toBeInTheDocument();
  });
});

test("admin can switch to chart view and change axes", async () => {
  const user = userEvent.setup();
  const { container } = renderPage(<AdminDashboardPage auth={adminAuth} />);

  expect(await screen.findByText("管理者統計")).toBeInTheDocument();
  await user.click(screen.getByRole("tab", { name: "圖表" }));

  expect(await screen.findByLabelText("X 軸")).toBeInTheDocument();
  expect(screen.getByLabelText("Y 軸")).toBeInTheDocument();
  expect(screen.getByLabelText("Top N")).toBeInTheDocument();

  await user.click(screen.getByLabelText("X 軸"));
  await user.click(screen.getByRole("option", { name: "單位" }));

  await user.click(screen.getByLabelText("Y 軸"));
  await user.click(screen.getByRole("option", { name: "已停用" }));

  await user.click(screen.getByLabelText("Top N"));
  await user.click(screen.getByRole("option", { name: "5" }));

  expect(container.querySelectorAll(".MuiChartsAxis-tickLabel").length).toBeGreaterThanOrEqual(5);
  expect(screen.getByRole("tab", { name: "圖表", selected: true })).toBeInTheDocument();
});

test("admin can open detail dialog from total applications count", async () => {
  const user = userEvent.setup();
  renderPage(<AdminDashboardPage auth={adminAuth} />);

  expect(await screen.findByText("jane.doe")).toBeInTheDocument();

  const totalButtons = screen.getAllByRole("button", { name: "2" });
  await user.click(totalButtons[0]);
  const totalDialog = await screen.findByRole("dialog", { name: "jane.doe 的申請總數明細" });
  await waitFor(() => {
    expect(within(totalDialog).queryByText("載入 API Key 明細中...")).not.toBeInTheDocument();
  });
  const totalRows = within(totalDialog).getAllByRole("row");
  expect(totalRows.length).toBeGreaterThanOrEqual(3);
  expect(within(totalDialog).getAllByText("for_jane.doe").length).toBeGreaterThanOrEqual(1);
  expect(within(totalDialog).getByText("revoked")).toBeInTheDocument();
});

test("admin can open detail dialog from active count", async () => {
  const user = userEvent.setup();
  renderPage(<AdminDashboardPage auth={adminAuth} />);

  expect(await screen.findByText("jane.doe")).toBeInTheDocument();
  const activeButton = screen.getAllByRole("button", { name: "1" })[0];
  await user.click(activeButton);
  const activeDialog = await screen.findByRole("dialog", { name: "jane.doe 的啟用中明細" });
  await waitFor(() => {
    expect(within(activeDialog).queryByText("載入 API Key 明細中...")).not.toBeInTheDocument();
  });
  expect(within(activeDialog).getByText("active")).toBeInTheDocument();
  expect(within(activeDialog).queryByText("revoked")).not.toBeInTheDocument();
});

test("non-admin user is blocked", async () => {
  renderPage(<AdminDashboardPage auth={userAuth} />);
  expect(await screen.findByText("僅管理者可使用管理者統計功能。")).toBeInTheDocument();
});
