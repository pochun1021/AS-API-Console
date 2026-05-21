import { render, screen } from "@testing-library/react";
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

test("non-admin user is blocked", async () => {
  renderPage(<OperationAuditLogsPage auth={userAuth} />);
  expect(await screen.findByText("僅管理者可查看操作稽核 Log。")).toBeInTheDocument();
});
