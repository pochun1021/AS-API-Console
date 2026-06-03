import { render, screen } from "@testing-library/react";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import AdminDashboardPage from "../pages/AdminDashboardPage";
import AdminPage from "../pages/AdminPage";
import InstituteViewPage from "../pages/InstituteViewPage";
import OperationAuditLogsPage from "../pages/OperationAuditLogsPage";
import WhitelistAdminPage from "../pages/WhitelistAdminPage";
import { mockApiProvider } from "../mocks/mockApiProvider";

const userAuth = {
  account: "jane.doe",
  name: "Jane Doe",
  email: "jane.doe@company.com",
  department: "Platform Engineering",
  sysid: 123,
  role: "user"
};

function withDateLocalization(ui) {
  return render(<LocalizationProvider dateAdapter={AdapterDayjs}>{ui}</LocalizationProvider>);
}

beforeEach(() => {
  mockApiProvider.resetForTests();
});

test.each([
  {
    name: "admin list page blocks non-admin users",
    renderPage: () => render(<AdminPage auth={userAuth} />),
    expectedText: "僅管理者可使用管理者名單功能。"
  },
  {
    name: "admin dashboard page blocks non-admin users",
    renderPage: () => withDateLocalization(<AdminDashboardPage auth={userAuth} />),
    expectedText: "僅管理者可使用管理者統計功能。"
  },
  {
    name: "whitelist page blocks non-admin users",
    renderPage: () => render(<WhitelistAdminPage auth={userAuth} />),
    expectedText: "僅管理者可使用特殊人員名單管理功能。"
  },
  {
    name: "institute view page blocks non-admin users",
    renderPage: () => render(<InstituteViewPage auth={userAuth} />),
    expectedText: "僅管理者可使用單位代碼資料檢視功能。"
  },
  {
    name: "operation audit logs page blocks non-admin users",
    renderPage: () => withDateLocalization(<OperationAuditLogsPage auth={userAuth} />),
    expectedText: "僅管理者可查看操作稽核 Log。"
  }
])("$name", async ({ renderPage, expectedText }) => {
  renderPage();
  expect(await screen.findByText(expectedText)).toBeInTheDocument();
});
