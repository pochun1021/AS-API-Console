import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import { vi } from "vitest";
import AdminPage from "../pages/AdminPage";
import { mockApiProvider } from "../mocks/mockApiProvider";

const adminAuth = {
  account: "john.admin",
  name: "John Admin",
  email: "john.admin@company.com",
  department: "03",
  sysid: 1,
  role: "admin"
};

function renderPage(ui) {
  return render(
    <LocalizationProvider dateAdapter={AdapterDayjs}>
      {ui}
    </LocalizationProvider>
  );
}

async function setDateRange(triggerLabel, startLabel, endLabel, startValue, endValue) {
  await userEvent.setup().click(screen.getByLabelText(triggerLabel));
  if (startValue != null) {
    fireEvent.change(screen.getByLabelText(startLabel), { target: { value: startValue } });
  }
  if (endValue != null) {
    fireEvent.change(screen.getByLabelText(endLabel), { target: { value: endValue } });
  }
}

beforeEach(() => {
  mockApiProvider.resetForTests();
});

test("admin list sends custom filter params without DataGrid filter model", async () => {
  const user = userEvent.setup();
  const spy = vi.spyOn(mockApiProvider, "listAdmins");
  renderPage(<AdminPage auth={adminAuth} />);

  expect(await screen.findByText("管理者名單")).toBeInTheDocument();
  await user.type(screen.getByLabelText("SysID"), "1");
  await user.type(screen.getByLabelText("帳號"), "john");
  await user.type(screen.getByLabelText("姓名"), "John");
  await user.type(screen.getByLabelText("Email"), "admin");
  await user.click(screen.getByLabelText("狀態"));
  await user.click(screen.getByRole("option", { name: "啟用中" }));
  await setDateRange("建立時間", "建立時間（起）", "建立時間（迄）", "2026-06-01", "2026-06-30");
  await setDateRange("更新時間", "更新時間（起）", "更新時間（迄）", "2026-06-01", "2026-06-30");

  await waitFor(() => {
    expect(spy).toHaveBeenLastCalledWith(
      expect.objectContaining({
        sysid: 1,
        account: "john",
        name: "John",
        email: "admin",
        status: "active",
        created_from: "2026-05-31T16:00:00.000Z",
        created_to: "2026-06-30T15:59:59.999Z",
        updated_from: "2026-05-31T16:00:00.000Z",
        updated_to: "2026-06-30T15:59:59.999Z",
      }),
      adminAuth
    );
  });
});

test("clear filters button resets admin list filters", async () => {
  const user = userEvent.setup();
  const spy = vi.spyOn(mockApiProvider, "listAdmins");
  renderPage(<AdminPage auth={adminAuth} />);

  expect(await screen.findByText("管理者名單")).toBeInTheDocument();
  const clearButton = screen.getByRole("button", { name: "清除篩選" });
  expect(clearButton).toBeDisabled();

  await user.type(screen.getByLabelText("帳號"), "john");

  await waitFor(() => {
    expect(clearButton).toBeEnabled();
    expect(spy).toHaveBeenLastCalledWith(
      expect.objectContaining({ account: "john" }),
      adminAuth
    );
  });

  await user.click(clearButton);

  await waitFor(() => {
    expect(screen.getByLabelText("帳號")).toHaveValue("");
    expect(spy).toHaveBeenLastCalledWith(
      expect.objectContaining({
        status: undefined,
        sysid: undefined,
        account: undefined,
        name: undefined,
        email: undefined,
        created_from: undefined,
        created_to: undefined,
        updated_from: undefined,
        updated_to: undefined,
      }),
      adminAuth
    );
  });
});
