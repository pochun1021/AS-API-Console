import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import SystemAnnouncementsPage from "../pages/SystemAnnouncementsPage";
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
  account: "jane.user",
  name: "Jane User",
  email: "jane.user@company.com",
  department: "03",
  sysid: 2,
  role: "user"
};

function renderPage(ui) {
  return render(
    <MemoryRouter>
      <LocalizationProvider dateAdapter={AdapterDayjs}>
        {ui}
      </LocalizationProvider>
    </MemoryRouter>
  );
}

beforeEach(() => {
  mockApiProvider.resetForTests();
});

test("announcement page loads with admin scope and title filter", async () => {
  const user = userEvent.setup();
  const spy = vi.spyOn(mockApiProvider, "listAnnouncements");
  renderPage(<SystemAnnouncementsPage auth={adminAuth} />);

  expect(await screen.findByText("系統公告管理")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "查看說明" })).toHaveAttribute("href", "/usage-examples");
  await user.type(screen.getByLabelText("標題"), "平台");

  await waitFor(() => {
    expect(spy).toHaveBeenLastCalledWith(
      expect.objectContaining({
        scope: "all",
        title: "平台"
      }),
      adminAuth
    );
  });
});

test("announcement page lets admin preview announcement body from title", async () => {
  const user = userEvent.setup();
  renderPage(<SystemAnnouncementsPage auth={adminAuth} />);

  await screen.findByText("系統公告管理");
  await user.click(await screen.findByRole("button", { name: "查看公告 平台維護公告" }));

  const dialog = await screen.findByRole("dialog");
  expect(within(dialog).getByText("本週三 18:00 進行例行維護，期間可能有短暫延遲。")).toBeInTheDocument();
});

test("announcement page supports create flow", async () => {
  const user = userEvent.setup();
  const spy = vi.spyOn(mockApiProvider, "createAnnouncement");
  renderPage(<SystemAnnouncementsPage auth={adminAuth} />);

  expect(await screen.findByText("系統公告管理")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "新增" }));
  const dialog = await screen.findByRole("dialog");
  await user.type(within(dialog).getByLabelText("標題"), "新公告");
  await user.type(within(dialog).getByLabelText("內容"), "新的系統公告內容");
  await user.click(within(dialog).getByRole("button", { name: "儲存" }));

  await waitFor(() => {
    expect(spy).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "新公告",
        body: "新的系統公告內容",
        status: "active"
      }),
      adminAuth
    );
  });
});

test("announcement page renders read-only view for user", async () => {
  const user = userEvent.setup();
  const spy = vi.spyOn(mockApiProvider, "listAnnouncements");
  renderPage(<SystemAnnouncementsPage auth={userAuth} />);

  expect(await screen.findByText("系統公告")).toBeInTheDocument();
  expect(await screen.findByRole("button", { name: "查看公告 平台維護公告" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "查看說明" })).toHaveAttribute("href", "/usage-examples");
  expect(screen.queryByRole("button", { name: "新增" })).not.toBeInTheDocument();
  expect(screen.getByLabelText("標題")).toBeInTheDocument();
  expect(screen.getByLabelText("上架時間")).toBeInTheDocument();
  expect(screen.getByLabelText("下架時間")).toBeInTheDocument();
  expect(screen.queryByLabelText("更新時間")).not.toBeInTheDocument();

  await user.type(screen.getByLabelText("標題"), "平台");

  await waitFor(() => {
    const lastCall = spy.mock.calls.at(-1);
    expect(lastCall?.[0]?.title).toBe("平台");
    expect(lastCall?.[0]?.scope).toBeUndefined();
    expect(lastCall?.[1]).toEqual(userAuth);
  });
});

test("announcement page lets user filter by publish-from date range", async () => {
  const user = userEvent.setup();
  const spy = vi.spyOn(mockApiProvider, "listAnnouncements");
  renderPage(<SystemAnnouncementsPage auth={userAuth} />);

  await screen.findByText("系統公告");
  await user.click(screen.getByRole("button", { name: "上架時間 picker" }));
  await user.click(await screen.findByRole("button", { name: /2026年6月15日|今天，2026年6月15日/i }));
  await user.click(screen.getByRole("button", { name: "關閉" }));

  await waitFor(() => {
    const lastCall = spy.mock.calls.at(-1);
    expect(lastCall?.[0]?.publish_from_from).toBeTruthy();
    expect(lastCall?.[0]?.updated_from).toBeUndefined();
    expect(lastCall?.[0]?.scope).toBeUndefined();
    expect(lastCall?.[1]).toEqual(userAuth);
  });
});

test("announcement page lets user preview announcement body from title", async () => {
  const user = userEvent.setup();
  renderPage(<SystemAnnouncementsPage auth={userAuth} />);

  await user.click(await screen.findByRole("button", { name: "查看公告 平台維護公告" }));

  const dialog = await screen.findByRole("dialog");
  expect(within(dialog).getByText("本週三 18:00 進行例行維護，期間可能有短暫延遲。")).toBeInTheDocument();
});
