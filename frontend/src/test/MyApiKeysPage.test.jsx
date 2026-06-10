import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useEffect } from "react";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import { MemoryRouter } from "react-router-dom";
import { LocaleProvider, useLocale } from "../i18n/locale";
import { mockApiProvider } from "../mocks/mockApiProvider";
import MyApiKeysPage from "../pages/MyApiKeysPage";

const auth = {
  account: "jane.doe",
  name: "Jane Doe",
  email: "jane.doe@company.com",
  department: "02",
  sysid: 123,
  role: "user"
};

const adminAuth = {
  account: "john.admin",
  name: "John Admin",
  email: "john.admin@company.com",
  department: "03",
  sysid: 1,
  role: "admin"
};

const devUserAuth = {
  account: "dev.user",
  name: "Dev User",
  email: "dev.user@example.com",
  department: "02",
  sysid: 200001,
  role: "user"
};

beforeEach(() => {
  mockApiProvider.resetForTests();
});

function LocaleSetter({ locale }) {
  const { setLocale } = useLocale();

  useEffect(() => {
    setLocale(locale);
  }, [locale, setLocale]);

  return null;
}

function renderPage(ui, { locale = "zh-TW" } = {}) {
  return render(
    <LocaleProvider>
      <LocaleSetter locale={locale} />
      <LocalizationProvider dateAdapter={AdapterDayjs}>
        <MemoryRouter>{ui}</MemoryRouter>
      </LocalizationProvider>
    </LocaleProvider>
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

test("shows revoke button only for active rows", async () => {
  renderPage(<MyApiKeysPage auth={auth} />);

  expect(await screen.findByText("API Keys")).toBeInTheDocument();
  const moreActionButtons = await screen.findAllByRole("button", { name: "更多操作" });
  expect(moreActionButtons.length).toBeGreaterThan(0);
  expect(screen.queryByRole("button", { name: "停用金鑰" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "更新金鑰" })).not.toBeInTheDocument();
  expect(screen.queryByRole("button", { name: "展延金鑰" })).not.toBeInTheDocument();
  expect(await screen.findAllByRole("button", { name: "查看詳情" })).toHaveLength(2);
  expect(screen.queryByRole("columnheader", { name: "建立時間" })).not.toBeInTheDocument();
});

test("shows applicant account and name columns for admin list", async () => {
  renderPage(<MyApiKeysPage auth={adminAuth} />);

  expect(await screen.findByRole("columnheader", { name: "帳號" })).toBeInTheDocument();
  expect(await screen.findByRole("columnheader", { name: "姓名" })).toBeInTheDocument();
  expect(await screen.findByRole("columnheader", { name: "Key Alias" })).toBeInTheDocument();
  expect(await screen.findByRole("columnheader", { name: "健康度" })).toBeInTheDocument();
  expect(screen.queryByRole("columnheader", { name: "用量" })).not.toBeInTheDocument();
  expect((await screen.findAllByText("jane.doe")).length).toBeGreaterThan(0);
  expect((await screen.findAllByText("Jane Doe")).length).toBeGreaterThan(0);
  expect(await screen.findByText("ktu")).toBeInTheDocument();
  expect(await screen.findByText("尤凱婷")).toBeInTheDocument();
});

test("usage popover is opened from actions and shows snapshot details in zh-TW", async () => {
  const user = userEvent.setup();
  const rendered = renderPage(<MyApiKeysPage auth={adminAuth} />);

  const usageRow = (await screen.findByText("AS-...mn56")).closest('[data-id="key_002"]');
  expect(usageRow).toBeTruthy();
  const usageButton = usageRow?.querySelector('button[aria-label="查看用量"]');
  expect(usageButton).toBeTruthy();
  await user.click(usageButton);

  expect(await screen.findByText("用量摘要")).toBeInTheDocument();
  expect(await screen.findByRole("progressbar", { name: "額度使用進度" })).toBeInTheDocument();
  expect(await screen.findByText("85% 已使用 (850.25 / 1000 USD)")).toBeInTheDocument();
  expect(await screen.findByText("剩餘 14.98%")).toBeInTheDocument();
  expect(await screen.findByText("剩餘額度偏低")).toBeInTheDocument();
  expect(screen.queryByText((_, element) => element?.textContent === "已用額度: 850.25 USD")).not.toBeInTheDocument();
  expect(screen.queryByText((_, element) => element?.textContent === "額度: 1000 USD")).not.toBeInTheDocument();
  expect(screen.queryByText((_, element) => element?.textContent === "剩餘額度: 149.75 USD")).not.toBeInTheDocument();
  expect(await screen.findByText("最大平行請求數: 無上限")).toBeInTheDocument();
  expect(await screen.findByText(/額度重置時間: 2026-06-02 16:03:27/)).toBeInTheDocument();
  expect(await screen.findByText(/最後同步時間: 2026-06-02 16:03:27/)).toBeInTheDocument();

  rendered.unmount();
  renderPage(<MyApiKeysPage auth={adminAuth} />);

  const unlimitedRow = (await screen.findByText("AS-...ab12")).closest('[data-id="key_003"]');
  expect(unlimitedRow).toBeTruthy();
  const unlimitedUsageButton = unlimitedRow?.querySelector('button[aria-label="查看用量"]');
  expect(unlimitedUsageButton).toBeTruthy();
  await user.click(unlimitedUsageButton);
  expect(await screen.findByText((_, element) => element?.textContent === "額度: 無上限")).toBeInTheDocument();
  expect(await screen.findByText("最大平行請求數: 無上限")).toBeInTheDocument();
  expect(screen.queryByRole("progressbar", { name: "額度使用進度" })).not.toBeInTheDocument();
});

test("usage popover keeps placeholder interaction for unknown snapshot in zh-TW", async () => {
  const user = userEvent.setup();
  renderPage(<MyApiKeysPage auth={auth} />);

  expect(await screen.findByText("未知")).toBeInTheDocument();
  const usageButtons = await screen.findAllByRole("button", { name: "查看用量" });
  await user.click(usageButtons[0]);

  expect(await screen.findByText("用量摘要")).toBeInTheDocument();
  expect(await screen.findByRole("progressbar", { name: "額度使用進度" })).toBeInTheDocument();
  expect(await screen.findByText("0% 已使用 (0 / 1000 USD)")).toBeInTheDocument();
  expect(await screen.findByText("剩餘 100%")).toBeInTheDocument();
  expect(screen.queryByText((_, element) => element?.textContent === "已用額度: 未知")).not.toBeInTheDocument();
  expect(screen.queryByText((_, element) => element?.textContent === "額度: 1000 USD")).not.toBeInTheDocument();
  expect(screen.queryByText((_, element) => element?.textContent === "剩餘額度: 未知")).not.toBeInTheDocument();
  expect(await screen.findByText("最大平行請求數: 無上限")).toBeInTheDocument();
  expect(await screen.findAllByText("未知")).not.toHaveLength(0);
  expect(await screen.findByText(/額度重置時間: -/)).toBeInTheDocument();
});

test("usage and health labels switch to english locale", async () => {
  const user = userEvent.setup();
  renderPage(<MyApiKeysPage auth={adminAuth} />, { locale: "en" });

  expect(await screen.findByRole("columnheader", { name: "Health" })).toBeInTheDocument();
  expect(screen.queryByRole("columnheader", { name: "Usage" })).not.toBeInTheDocument();

  const usageButtons = await screen.findAllByRole("button", { name: "View Usage" });
  await user.click(usageButtons[1]);

  expect(await screen.findByText("Usage Summary")).toBeInTheDocument();
  expect(await screen.findByRole("progressbar", { name: "Budget usage progress" })).toBeInTheDocument();
  expect(await screen.findByText("85% used (850.25 / 1000 USD)")).toBeInTheDocument();
  expect(await screen.findByText("14.98% remaining")).toBeInTheDocument();
  expect(await screen.findByText("Budget running low")).toBeInTheDocument();
  expect(screen.queryByText((_, element) => element?.textContent === "Spend: 850.25 USD")).not.toBeInTheDocument();
  expect(screen.queryByText((_, element) => element?.textContent === "Budget: 1000 USD")).not.toBeInTheDocument();
  expect(screen.queryByText((_, element) => element?.textContent === "Remaining: 149.75 USD")).not.toBeInTheDocument();
  expect(await screen.findByText("Max parallel requests: Unlimited")).toBeInTheDocument();
  expect(await screen.findByText(/Budget reset time: 2026-06-02 16:03:27/)).toBeInTheDocument();
  expect(await screen.findByText(/Last synced time: 2026-06-02 16:03:27/)).toBeInTheDocument();
});

test("shows detail in dialog and can revoke active key with confirm", async () => {
  const user = userEvent.setup();
  renderPage(<MyApiKeysPage auth={auth} />);

  await user.click((await screen.findAllByRole("button", { name: "查看詳情" }))[0]);
  expect(await screen.findByText("API Key 詳情")).toBeInTheDocument();
  expect(await screen.findByText("ID: key_001")).toBeInTheDocument();
  expect(await screen.findByText("用途: integration test for platform service")).toBeInTheDocument();
  expect(await screen.findByText("單位: 資訊所")).toBeInTheDocument();
  expect(screen.queryByText("申請人:")).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "停用金鑰" }));
  expect(await screen.findByText("確認停用")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "確認" }));
  expect(await screen.findByText("金鑰已停用。")).toBeInTheDocument();
  await waitFor(() => {
    expect(screen.queryByRole("dialog", { name: "API Key 詳情" })).not.toBeInTheDocument();
  });
});

test("shows applicant identity in detail dialog for admin", async () => {
  const user = userEvent.setup();
  renderPage(<MyApiKeysPage auth={adminAuth} />);

  await user.click((await screen.findAllByRole("button", { name: "查看詳情" }))[0]);
  expect(await screen.findByText("申請人: jane.doe / Jane Doe")).toBeInTheDocument();
});

test("admin can edit key alias in list dialog", async () => {
  const user = userEvent.setup();
  renderPage(<MyApiKeysPage auth={adminAuth} />);

  await user.click((await screen.findAllByRole("button", { name: "編輯 Key Alias" }))[0]);
  const aliasInput = (await screen.findAllByLabelText("Key Alias")).at(-1);
  expect(aliasInput).toBeTruthy();
  await user.clear(aliasInput);
  await user.type(aliasInput, "service_ops");
  await user.click(screen.getByRole("button", { name: "儲存" }));
  expect(await screen.findByText("Key Alias 已更新。")).toBeInTheDocument();
  expect(await screen.findByText("service_ops")).toBeInTheDocument();
});

test("admin sees duplicate prompt when key alias already exists", async () => {
  const user = userEvent.setup();
  renderPage(<MyApiKeysPage auth={adminAuth} />);

  await user.click((await screen.findAllByRole("button", { name: "編輯 Key Alias" }))[0]);
  const aliasInput = (await screen.findAllByLabelText("Key Alias")).at(-1);
  expect(aliasInput).toBeTruthy();
  await user.clear(aliasInput);
  await user.type(aliasInput, "shared_alias");
  await user.click(screen.getByRole("button", { name: "儲存" }));
  expect(await screen.findByText("Key Alias 重複，請改用其他名稱。")).toBeInTheDocument();
});

test("admin cannot save unsafe key alias", async () => {
  const user = userEvent.setup();
  renderPage(<MyApiKeysPage auth={adminAuth} />);

  await user.click((await screen.findAllByRole("button", { name: "編輯 Key Alias" }))[0]);
  const aliasInput = (await screen.findAllByLabelText("Key Alias")).at(-1);
  expect(aliasInput).toBeTruthy();
  await user.clear(aliasInput);
  await user.type(aliasInput, "foo => bar");
  await user.click(screen.getByRole("button", { name: "儲存" }));

  expect(await screen.findByText("Key Alias 不可包含明顯程式語法。")).toBeInTheDocument();
});

test("admin cannot save key alias with invalid characters", async () => {
  const user = userEvent.setup();
  renderPage(<MyApiKeysPage auth={adminAuth} />);

  await user.click((await screen.findAllByRole("button", { name: "編輯 Key Alias" }))[0]);
  const aliasInput = (await screen.findAllByLabelText("Key Alias")).at(-1);
  expect(aliasInput).toBeTruthy();
  await user.clear(aliasInput);
  await user.type(aliasInput, "for_john.admin");
  await user.click(screen.getByRole("button", { name: "儲存" }));

  expect(await screen.findByText("Key Alias 僅允許中英文、數字、_、-、全形頓號（、）。")).toBeInTheDocument();
});

test("admin can save key alias with ideographic comma", async () => {
  const user = userEvent.setup();
  renderPage(<MyApiKeysPage auth={adminAuth} />);

  await user.click((await screen.findAllByRole("button", { name: "編輯 Key Alias" }))[0]);
  const aliasInput = (await screen.findAllByLabelText("Key Alias")).at(-1);
  expect(aliasInput).toBeTruthy();
  await user.clear(aliasInput);
  await user.type(aliasInput, "平台、批次_alias");
  await user.click(screen.getByRole("button", { name: "儲存" }));

  await waitFor(() => {
    expect(screen.getByRole("alert")).toHaveTextContent("Key Alias 已更新。");
  });
});

test("user renew hides old key from list", async () => {
  const user = userEvent.setup();
  renderPage(<MyApiKeysPage auth={auth} />);

  expect(await screen.findByText("AS-...mn56")).toBeInTheDocument();
  const moreActionButtons = await screen.findAllByRole("button", { name: "更多操作" });
  await user.click(moreActionButtons[1]);
  await user.click(await screen.findByRole("menuitem", { name: "更新金鑰" }));
  expect(await screen.findByText("確認更新")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "確認" }));
  expect(await screen.findByText("金鑰已更新。")).toBeInTheDocument();
  expect(await screen.findByText("金鑰已更新")).toBeInTheDocument();
  await waitFor(() => {
    expect(screen.queryByText("AS-...mn56")).not.toBeInTheDocument();
  });
});

test("renewed key dialog stays open on backdrop click and escape", async () => {
  const user = userEvent.setup();
  renderPage(<MyApiKeysPage auth={auth} />);

  const moreActionButtons = await screen.findAllByRole("button", { name: "更多操作" });
  await user.click(moreActionButtons[1]);
  await user.click(await screen.findByRole("menuitem", { name: "更新金鑰" }));
  await user.click(screen.getByRole("button", { name: "確認" }));

  expect(await screen.findByText("此明文金鑰只會顯示一次，請立即保存。")).toBeInTheDocument();

  const backdrop = document.querySelector(".MuiBackdrop-root");
  expect(backdrop).not.toBeNull();
  fireEvent.mouseDown(backdrop);
  fireEvent.click(backdrop);
  expect(screen.getByText("此明文金鑰只會顯示一次，請立即保存。")).toBeInTheDocument();

  fireEvent.keyDown(document.activeElement || document.body, { key: "Escape" });
  expect(screen.getByText("此明文金鑰只會顯示一次，請立即保存。")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "我知道了" }));
  await waitFor(() => {
    expect(screen.queryByText("此明文金鑰只會顯示一次，請立即保存。")).not.toBeInTheDocument();
  });
});

test("user can extend active key with selected duration", async () => {
  const user = userEvent.setup();
  renderPage(<MyApiKeysPage auth={auth} />);

  const moreActionButtons = await screen.findAllByRole("button", { name: "更多操作" });
  await user.click(moreActionButtons[0]);
  await user.click(await screen.findByRole("menuitem", { name: "展延金鑰" }));
  expect(await screen.findByText("確認展延")).toBeInTheDocument();
  await user.selectOptions(screen.getByLabelText("展延時長"), "12");
  await user.click(screen.getByRole("button", { name: "確認" }));
  expect(await screen.findByText("金鑰已展延。")).toBeInTheDocument();
  expect(screen.queryByRole("dialog", { name: "確認展延" })).not.toBeInTheDocument();

  const detailButtons = await screen.findAllByRole("button", { name: "查看詳情" });
  await user.click(detailButtons[0]);
  expect(await screen.findByText("目前生效時長: 18 個月")).toBeInTheDocument();
});

test("extending an expired key resets start date and duration in detail view", async () => {
  const user = userEvent.setup();
  const today = new Date().toISOString().slice(0, 10);
  renderPage(<MyApiKeysPage auth={devUserAuth} />);

  const moreActionButtons = await screen.findAllByRole("button", { name: "更多操作" });
  await user.click(moreActionButtons[2]);
  await user.click(await screen.findByRole("menuitem", { name: "展延金鑰" }));
  await user.selectOptions(screen.getByLabelText("展延時長"), "6");
  await user.click(screen.getByRole("button", { name: "確認" }));
  expect(await screen.findByText("金鑰已展延。")).toBeInTheDocument();

  const detailButtons = await screen.findAllByRole("button", { name: "查看詳情" });
  await user.click(detailButtons[2]);
  expect(await screen.findByText(`起算日期: ${today}`)).toBeInTheDocument();
  expect(await screen.findByText("目前生效時長: 6 個月")).toBeInTheDocument();
});

test.each([
  {
    name: "user cannot see extend action for active key outside near-expiry window",
    buttonIndex: 0,
    shouldSeeExtend: false,
  },
  {
    name: "user can see extend action for expired key",
    buttonIndex: 2,
    shouldSeeExtend: true,
  },
  {
    name: "user can see extend action for active key within near-expiry window",
    buttonIndex: 3,
    shouldSeeExtend: true,
  },
])("$name", async ({ buttonIndex, shouldSeeExtend }) => {
  const user = userEvent.setup();
  renderPage(<MyApiKeysPage auth={devUserAuth} />);

  const moreActionButtons = await screen.findAllByRole("button", { name: "更多操作" });
  await user.click(moreActionButtons[buttonIndex]);
  if (shouldSeeExtend) {
    expect(await screen.findByRole("menuitem", { name: "展延金鑰" })).toBeInTheDocument();
  } else {
    expect(screen.queryByRole("menuitem", { name: "展延金鑰" })).not.toBeInTheDocument();
  }
});

test("admin does not see extend action for active key outside near-expiry window", async () => {
  const user = userEvent.setup();
  renderPage(<MyApiKeysPage auth={adminAuth} />);

  const moreActionButtons = await screen.findAllByRole("button", { name: "更多操作" });
  await user.click(moreActionButtons[1]);
  expect(screen.queryByRole("menuitem", { name: "展延金鑰" })).not.toBeInTheDocument();
});

test("renders timestamps in Asia/Taipei on list and detail views", async () => {
  const user = userEvent.setup();
  renderPage(<MyApiKeysPage auth={devUserAuth} />);

  expect(await screen.findByText("2026-03-10 19:00:00")).toBeInTheDocument();

  const detailButtons = await screen.findAllByRole("button", { name: "查看詳情" });
  await user.click(detailButtons[2]);

  expect(await screen.findByText(/起算日期: 2026-02-10/)).toBeInTheDocument();
  expect(await screen.findByText(/建立時間: 2026-05-02 19:00:00/)).toBeInTheDocument();
  expect(await screen.findByText(/到期時間: 2026-03-10 19:00:00/)).toBeInTheDocument();
});

test("list uses server pagination params", async () => {
  const user = userEvent.setup();
  const spy = vi.spyOn(mockApiProvider, "listApiKeys");
  renderPage(<MyApiKeysPage auth={adminAuth} />);

  expect(await screen.findByText("API Keys")).toBeInTheDocument();
  expect((await screen.findAllByText("jane.doe")).length).toBeGreaterThan(0);
  expect((await screen.findAllByText("Jane Doe")).length).toBeGreaterThan(0);
  await waitFor(() => {
    expect(spy).toHaveBeenCalledWith(expect.objectContaining({ page: 1, page_size: 10 }), adminAuth);
  });

  await user.click(screen.getByRole("combobox", { name: /每頁數量|Rows per page/i }));
  await user.click(screen.getByRole("option", { name: "20" }));
  await waitFor(() => {
    expect(spy).toHaveBeenCalledWith(expect.objectContaining({ page: 1, page_size: 20 }), adminAuth);
  });
});

test("admin list sends server sort params when sorting columns", async () => {
  const user = userEvent.setup();
  const spy = vi.spyOn(mockApiProvider, "listApiKeys");
  renderPage(<MyApiKeysPage auth={adminAuth} />);

  expect(await screen.findByText("API Keys")).toBeInTheDocument();
  await user.click(await screen.findByRole("columnheader", { name: "帳號" }));

  await waitFor(() => {
    expect(spy).toHaveBeenLastCalledWith(
      expect.objectContaining({ sort_by: "owner_account", sort_dir: "asc" }),
      adminAuth
    );
  });
});

test("admin list sends custom filter params without DataGrid filter model", async () => {
  const user = userEvent.setup();
  const spy = vi.spyOn(mockApiProvider, "listApiKeys");
  renderPage(<MyApiKeysPage auth={adminAuth} />);

  expect(await screen.findByText("API Keys")).toBeInTheDocument();
  await user.type(screen.getByLabelText("帳號"), "ktu");
  await user.type(screen.getByLabelText("姓名"), "尤");
  await user.type(screen.getByLabelText("Key Alias"), "for_ktu");
  await user.click(screen.getByLabelText("狀態"));
  await user.click(screen.getByRole("option", { name: "active" }));
  await setDateRange("起算日期", "起算日期（起）", "起算日期（迄）", "2026-04-01", "2026-04-30");
  await setDateRange("到期日期", "到期日期（起）", "到期日期（迄）", "2026-10-01", "2026-10-31");

  await waitFor(() => {
    expect(spy).toHaveBeenLastCalledWith(
      expect.objectContaining({
        owner_account: "ktu",
        owner_name: "尤",
        key_alias: "for_ktu",
        status: "active",
        application_date_from: "2026-04-01",
        application_date_to: "2026-04-30",
        expires_from: "2026-09-30T16:00:00.000Z",
        expires_to: "2026-10-31T15:59:59.999Z",
      }),
      adminAuth
    );
  });
});

test("clear filters button resets api key list filters", async () => {
  const user = userEvent.setup();
  const spy = vi.spyOn(mockApiProvider, "listApiKeys");
  renderPage(<MyApiKeysPage auth={adminAuth} />);

  expect(await screen.findByText("API Keys")).toBeInTheDocument();
  const clearButton = screen.getByRole("button", { name: "清除篩選" });
  expect(clearButton).toBeDisabled();

  await user.type(screen.getByLabelText("帳號"), "ktu");
  await waitFor(() => {
    expect(clearButton).toBeEnabled();
    expect(spy).toHaveBeenLastCalledWith(
      expect.objectContaining({ owner_account: "ktu" }),
      adminAuth
    );
  });

  await user.click(clearButton);

  await waitFor(() => {
    expect(screen.getByLabelText("帳號")).toHaveValue("");
    expect(spy).toHaveBeenLastCalledWith(
      expect.objectContaining({
        status: undefined,
        owner_account: undefined,
        owner_name: undefined,
        key_alias: undefined,
        application_date_from: undefined,
        application_date_to: undefined,
        expires_from: undefined,
        expires_to: undefined,
      }),
      adminAuth
    );
  });

  expect(clearButton).toBeDisabled();
});
