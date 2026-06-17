vi.mock("@mui/material", async () => {
  const actual = await vi.importActual("@mui/material");
  return {
    ...actual,
    useMediaQuery: vi.fn()
  };
});

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useMediaQuery } from "@mui/material";
import { MemoryRouter } from "react-router-dom";
import AppLayout from "../components/AppLayout";

const userAuth = {
  account: "jane.doe",
  name: "Jane Doe",
  email: "jane.doe@company.com",
  department: "Platform Engineering",
  sysid: 123,
  role: "user"
};

const adminAuth = {
  ...userAuth,
  role: "admin"
};

function setResponsiveMatches({ mdDown = false } = {}) {
  useMediaQuery.mockImplementation((query) => {
    const normalized = String(query || "");
    if (normalized.includes("899.95")) return mdDown;
    return false;
  });
}

beforeEach(() => {
  setResponsiveMatches();
  vi.restoreAllMocks();
  Object.defineProperty(HTMLElement.prototype, "scrollTo", {
    configurable: true,
    value: vi.fn()
  });
});

function renderAppLayout({ path = "/", auth = userAuth, props = {} } = {}) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppLayout auth={auth} {...props}>
        <div>content</div>
      </AppLayout>
    </MemoryRouter>
  );
}

function mockDesktopNavLayout({ clientWidth, itemWidths, trackOffsetLeft = 0 }) {
  const container = screen.getByTestId("desktop-nav-scroll");
  const track = screen.getByTestId("desktop-nav-track");
  const navItems = itemWidths.map((_, index) => screen.getByTestId(`desktop-nav-item-${index}`));
  const maxScrollLeft = Math.max(itemWidths.reduce((sum, width) => sum + width, 0) - clientWidth, 0);
  let scrollLeft = 0;
  let offsetLeft = 0;

  Object.defineProperty(container, "clientWidth", {
    configurable: true,
    get: () => clientWidth
  });
  Object.defineProperty(container, "scrollWidth", {
    configurable: true,
    get: () => itemWidths.reduce((sum, width) => sum + width, 0)
  });
  Object.defineProperty(container, "scrollLeft", {
    configurable: true,
    get: () => scrollLeft,
    set: (value) => {
      scrollLeft = Math.max(0, Math.min(value, maxScrollLeft));
    }
  });
  Object.defineProperty(container, "scrollTo", {
    configurable: true,
    value: vi.fn(({ left } = {}) => {
      container.scrollLeft = left ?? container.scrollLeft;
      fireEvent.scroll(container);
    })
  });
  Object.defineProperty(track, "offsetLeft", {
    configurable: true,
    get: () => trackOffsetLeft
  });

  navItems.forEach((item, index) => {
    const width = itemWidths[index];
    const itemOffsetLeft = offsetLeft;
    offsetLeft += width;

    Object.defineProperty(item, "offsetLeft", {
      configurable: true,
      get: () => itemOffsetLeft
    });
    Object.defineProperty(item, "offsetWidth", {
      configurable: true,
      get: () => width
    });
  });

  fireEvent(window, new Event("resize"));

  return {
    container,
    navItems
  };
}

test("user sees shared navigation including models", () => {
  renderAppLayout();

  const navLinks = screen.getAllByRole("link");
  expect(navLinks[0]).toHaveTextContent("系統公告");
  expect(navLinks[1]).toHaveTextContent("服務使用說明");
  expect(screen.getByRole("link", { name: "系統公告" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "申請" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "API Keys" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "使用量" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "服務使用說明" })).toBeInTheDocument();
  expect(screen.getByAltText("AS API Console logo")).toBeInTheDocument();
  expect(screen.getByLabelText("語言")).toBeInTheDocument();
  expect(screen.getByLabelText("登出")).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "特殊人員名單管理" })).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "服務使用說明" })).toHaveAttribute("href", "/usage-examples");
  expect(screen.queryByRole("heading", { name: "服務使用說明" })).not.toBeInTheDocument();
  expect(screen.queryByLabelText("開啟導覽選單")).not.toBeInTheDocument();
});

test("locale menu triggers onChangeLocale with selected value", () => {
  const onChangeLocale = vi.fn();

  renderAppLayout({ props: { onChangeLocale } });

  fireEvent.click(screen.getByLabelText("語言"));
  fireEvent.click(screen.getByRole("menuitem", { name: "EN" }));

  expect(onChangeLocale).toHaveBeenCalledWith("en");
});

test("locale menu shows checkmark for current locale", () => {
  renderAppLayout();

  fireEvent.click(screen.getByLabelText("語言"));

  expect(screen.getByTestId("locale-check-zh-TW").querySelector("svg")).toBeInTheDocument();
  expect(screen.getByTestId("locale-check-en").querySelector("svg")).not.toBeInTheDocument();
});

test("admin sees whitelist nav", () => {
  renderAppLayout({ auth: adminAuth });

  const navLinks = screen.getAllByRole("link");
  expect(navLinks[0]).toHaveTextContent("系統公告");
  expect(navLinks[1]).toHaveTextContent("服務使用說明");
  expect(screen.getByRole("link", { name: "特殊人員名單管理" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "系統公告" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "使用量" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "服務使用說明" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "服務使用說明" })).toHaveAttribute("href", "/usage-examples");
  expect(screen.getByRole("link", { name: "單位代碼" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "管理者名單" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "管理者統計" })).toBeInTheDocument();
});

test("clicking logout icon triggers onLogout", () => {
  const onLogout = vi.fn();
  renderAppLayout({ props: { onLogout } });

  fireEvent.click(screen.getByLabelText("登出"));
  expect(onLogout).toHaveBeenCalledTimes(1);
});

test("mobile mode shows menu button instead of top nav row", () => {
  setResponsiveMatches({ mdDown: true });
  renderAppLayout();

  expect(screen.getByLabelText("開啟導覽選單")).toBeInTheDocument();
  expect(screen.queryByLabelText("語言")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("登出")).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "系統公告" })).not.toBeInTheDocument();
});

test("mobile drawer shows role-appropriate navigation and closes after click", () => {
  setResponsiveMatches({ mdDown: true });
  renderAppLayout({ auth: adminAuth });

  fireEvent.click(screen.getByLabelText("開啟導覽選單"));
  expect(screen.getByRole("heading", { name: "導覽選單" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "系統公告" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "服務使用說明" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "特殊人員名單管理" })).toBeInTheDocument();

  fireEvent.click(screen.getByRole("link", { name: "使用量" }));
  expect(screen.queryByRole("heading", { name: "導覽選單" })).not.toBeInTheDocument();
});

test("mobile drawer language and logout actions still work", () => {
  setResponsiveMatches({ mdDown: true });
  const onChangeLocale = vi.fn();
  const onLogout = vi.fn();
  renderAppLayout({ props: { onChangeLocale, onLogout } });

  fireEvent.click(screen.getByLabelText("開啟導覽選單"));
  fireEvent.click(screen.getByLabelText("切換語言為英文"));
  expect(onChangeLocale).toHaveBeenCalledWith("en");

  fireEvent.click(screen.getByLabelText("開啟導覽選單"));
  fireEvent.click(screen.getByLabelText("登出"));
  expect(onLogout).toHaveBeenCalledTimes(1);
});

test("usage route only highlights usage nav item", () => {
  renderAppLayout({ path: "/usage" });

  expect(screen.getByRole("link", { name: "使用量" })).toHaveClass("MuiButton-colorSecondary");
  expect(screen.getByRole("link", { name: "服務使用說明" })).not.toHaveClass("MuiButton-colorSecondary");
});

test("usage examples route only highlights usage examples nav item", () => {
  renderAppLayout({ path: "/usage-examples" });

  expect(screen.getByRole("link", { name: "服務使用說明" })).toHaveClass("MuiButton-colorSecondary");
  expect(screen.getByRole("link", { name: "使用量" })).not.toHaveClass("MuiButton-colorSecondary");
});

test("nested api key route keeps api keys nav active", () => {
  renderAppLayout({ path: "/api-keys/123" });

  expect(screen.getByRole("link", { name: "API Keys" })).toHaveClass("MuiButton-colorSecondary");
  expect(screen.getByRole("link", { name: "使用量" })).not.toHaveClass("MuiButton-colorSecondary");
});

test("mobile drawer keeps active route state", () => {
  setResponsiveMatches({ mdDown: true });
  renderAppLayout({ path: "/usage" });

  fireEvent.click(screen.getByLabelText("開啟導覽選單"));
  expect(screen.getByRole("link", { name: "使用量" })).toHaveClass("Mui-selected");
  expect(screen.getByRole("link", { name: "服務使用說明" })).not.toHaveClass("Mui-selected");
});

test("user and admin both keep top nav above md breakpoint", () => {
  const { rerender } = render(
    <MemoryRouter initialEntries={["/"]}>
      <AppLayout auth={adminAuth}>
        <div>content</div>
      </AppLayout>
    </MemoryRouter>
  );

  expect(screen.queryByLabelText("開啟導覽選單")).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "特殊人員名單管理" })).toBeInTheDocument();

  rerender(
    <MemoryRouter initialEntries={["/"]}>
      <AppLayout auth={userAuth}>
        <div>content</div>
      </AppLayout>
    </MemoryRouter>
  );

  expect(screen.queryByLabelText("開啟導覽選單")).not.toBeInTheDocument();
  expect(screen.getByRole("link", { name: "系統公告" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "服務使用說明" })).toBeInTheDocument();
});

test("admin desktop without overflow does not show arrow navigation", () => {
  renderAppLayout({ auth: adminAuth });
  mockDesktopNavLayout({
    clientWidth: 1600,
    itemWidths: [100, 120, 90, 100, 90, 150, 140, 120, 120, 120, 120]
  });

  expect(screen.queryByLabelText("上一個導覽項目")).not.toBeInTheDocument();
  expect(screen.queryByLabelText("下一個導覽項目")).not.toBeInTheDocument();
});

test("admin desktop overflow arrows move one item at a time", async () => {
  renderAppLayout({ auth: adminAuth });
  const { container } = mockDesktopNavLayout({
    clientWidth: 320,
    itemWidths: [100, 120, 90, 100, 90, 150, 140, 120, 120, 120, 120],
    trackOffsetLeft: 48
  });

  const previousButton = await screen.findByLabelText("上一個導覽項目");
  const nextButton = screen.getByLabelText("下一個導覽項目");

  expect(previousButton).toBeDisabled();
  expect(nextButton).toBeEnabled();
  expect(container.scrollLeft).toBe(0);

  fireEvent.click(nextButton);
  expect(container.scrollTo).toHaveBeenCalled();
  expect(container.scrollLeft).toBeGreaterThan(0);
  expect(previousButton).toBeEnabled();

  fireEvent.click(nextButton);
  expect(container.scrollLeft).toBeGreaterThan(90);

  fireEvent.click(nextButton);
  fireEvent.click(nextButton);
  fireEvent.click(nextButton);
  fireEvent.click(nextButton);
  fireEvent.click(nextButton);
  fireEvent.click(nextButton);
  fireEvent.click(nextButton);

  await waitFor(() => {
    expect(screen.getByLabelText("下一個導覽項目")).toBeDisabled();
  });

  const scrollLeftAtEnd = container.scrollLeft;
  fireEvent.click(previousButton);
  expect(container.scrollLeft).toBeLessThan(scrollLeftAtEnd);
  expect(previousButton).toBeEnabled();

  const scrollLeftAfterFirstBack = container.scrollLeft;
  fireEvent.click(previousButton);
  expect(container.scrollLeft).toBeLessThan(scrollLeftAfterFirstBack);
  expect(previousButton).toBeEnabled();

  for (let index = 0; index < 12 && container.scrollLeft > 0; index += 1) {
    fireEvent.click(previousButton);
  }

  expect(container.scrollLeft).toBe(0);
  expect(previousButton).toBeDisabled();
});

test("admin desktop scrolls active item into view on mount", async () => {
  renderAppLayout({ auth: adminAuth, path: "/operation-audit-logs" });
  const { container } = mockDesktopNavLayout({
    clientWidth: 320,
    itemWidths: [100, 120, 90, 100, 90, 150, 140, 120, 120, 120, 120],
    trackOffsetLeft: 48
  });

  await waitFor(() => {
    expect(container.scrollTo).toHaveBeenCalled();
  });

  expect(container.scrollLeft).toBe(878);
  expect(screen.getByRole("link", { name: "操作稽核" })).toHaveClass("MuiButton-colorSecondary");
});
