import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useEffect } from "react";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, test, vi } from "vitest";
import dayjs from "dayjs";
import { apiClient } from "../api/client";
import { LocaleProvider, useLocale } from "../i18n/locale";
import UsagePage, {
  buildUsageTooltipRows,
  buildPanOverlayMetrics,
  buildUsageChartDays,
  buildUsageWindow,
  clampVisibleWindow,
  defaultDateRange,
  resolveVisibleWindowChange,
  shiftVisibleWindow,
} from "../pages/UsagePage";

const auth = {
  account: "jane.doe",
  name: "Jane Doe",
  email: "jane.doe@company.com",
  department: "02",
  sysid: 123,
  role: "user"
};

function LocaleSetter({ locale }) {
  const { setLocale } = useLocale();

  useEffect(() => {
    setLocale(locale);
  }, [locale, setLocale]);

  return null;
}

function renderPage(ui, { locale = "zh-TW", initialEntries = ["/"] } = {}) {
  return render(
    <LocaleProvider>
      <LocaleSetter locale={locale} />
      <LocalizationProvider dateAdapter={AdapterDayjs}>
        <MemoryRouter initialEntries={initialEntries}>{ui}</MemoryRouter>
      </LocalizationProvider>
    </LocaleProvider>
  );
}

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

async function clickOptionByAlias(alias) {
  const textNode = await screen.findByText(alias);
  const option = textNode.closest('[role="option"]');
  expect(option).toBeTruthy();
  await userEvent.setup().click(option);
}

describe("UsagePage", () => {
  test("loads key options, fetches usage series after selecting a key, and renders chart title with date labels", async () => {
    const listKeysSpy = vi.spyOn(apiClient, "listApiKeys").mockResolvedValue({
      items: [
        { id: "key_1", key_alias: "for_jane.doe", masked_key: "AS-...1234" },
        { id: "key_2", key_alias: "shared_alias", masked_key: "AS-...9999" }
      ]
    });
    vi.spyOn(apiClient, "getApiKeyUsageTotal").mockResolvedValue({
      scope: "all_visible_keys",
      prompt_tokens: 0,
      completion_tokens: 0,
      total_tokens: 0,
      key_count: 0,
    });
    const listSeriesSpy = vi.spyOn(apiClient, "listApiKeyUsageSeries").mockResolvedValue({
      items: [
        {
          bucket_start: "2026-06-01T00:00:00+08:00",
          bucket_label: "2026-06-01",
          prompt_tokens: 100,
          completion_tokens: 50,
          total_tokens: 150,
          spend: 1.25
        }
      ]
    });
    const user = userEvent.setup();

    const { container } = renderPage(<UsagePage auth={auth} />);

    await waitFor(() => expect(listKeysSpy).toHaveBeenCalled());
    expect(listKeysSpy).toHaveBeenCalledWith(
      expect.objectContaining({ page: 1, page_size: 100 }),
      auth
    );
    expect(listKeysSpy.mock.calls[0][0]).not.toHaveProperty("issued_at_from");
    await user.type(screen.getByRole("combobox", { name: "API Key" }), "shared");
    await clickOptionByAlias("shared_alias");
    await waitFor(() => expect(listSeriesSpy).toHaveBeenCalled());
    expect(await screen.findByText("單一 API Key 每日使用量")).toBeInTheDocument();
    expect(container.querySelectorAll(".MuiChartsAxis-tickLabel").length).toBeGreaterThan(0);
    expect(screen.queryAllByRole("slider")).toHaveLength(0);
  });

  test("loads all paged key options including non-active keys", async () => {
    vi.spyOn(apiClient, "getApiKeyUsageTotal").mockResolvedValue({
      scope: "all_visible_keys",
      prompt_tokens: 0,
      completion_tokens: 0,
      total_tokens: 0,
      key_count: 0,
    });
    const listKeysSpy = vi.spyOn(apiClient, "listApiKeys").mockImplementation(async (params) => {
      if (params.page === 1) {
        return {
          items: [{ id: "key_1", status: "active", key_alias: "active_alias", masked_key: "AS-...1111" }],
          page: 1,
          page_size: 100,
          total: 3,
        };
      }
      return {
        items: [
          { id: "key_2", status: "revoked", key_alias: "revoked_alias", masked_key: "AS-...2222" },
          { id: "key_3", status: "expired", key_alias: "expired_alias", masked_key: "AS-...3333" },
        ],
        page: 2,
        page_size: 100,
        total: 3,
      };
    });
    vi.spyOn(apiClient, "listApiKeyUsageSeries").mockResolvedValue({ items: [] });
    const user = userEvent.setup();

    renderPage(<UsagePage auth={auth} />);

    await waitFor(() => expect(listKeysSpy).toHaveBeenCalledTimes(2));
    expect(listKeysSpy).toHaveBeenNthCalledWith(
      1,
      expect.objectContaining({ page: 1, page_size: 100 }),
      auth
    );
    expect(listKeysSpy).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({ page: 2, page_size: 100 }),
      auth
    );
    await user.type(screen.getByRole("combobox", { name: "API Key" }), "revoked");

    expect(await screen.findByText("revoked_alias")).toBeInTheDocument();
    expect(screen.queryByText("active_alias")).not.toBeInTheDocument();
  });

  test("uses a non-empty local default date range on first render", async () => {
    vi.spyOn(apiClient, "getApiKeyUsageTotal").mockResolvedValue({
      scope: "all_visible_keys",
      prompt_tokens: 0,
      completion_tokens: 0,
      total_tokens: 0,
      key_count: 0,
    });
    const listKeysSpy = vi.spyOn(apiClient, "listApiKeys").mockResolvedValue({
      items: [{ id: "key_1", key_alias: "for_jane.doe", masked_key: "AS-...1234" }]
    });
    vi.spyOn(apiClient, "listApiKeyUsageSeries").mockResolvedValue({ items: [] });

    renderPage(<UsagePage auth={auth} />, { initialEntries: ["/usage?key_id=key_1"] });

    const expectedRange = defaultDateRange();
    expect(expectedRange.from).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(expectedRange.to).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(dayjs(expectedRange.to).diff(dayjs(expectedRange.from), "day")).toBe(6);
    await waitFor(() => expect(listKeysSpy).toHaveBeenCalled());
    expect(await screen.findByLabelText("日期區間")).toHaveValue(`${expectedRange.from} - ${expectedRange.to}`);
  });

  test("shows usage quick range shortcuts and applies the selected range", async () => {
    vi.spyOn(apiClient, "getApiKeyUsageTotal").mockResolvedValue({
      scope: "all_visible_keys",
      prompt_tokens: 0,
      completion_tokens: 0,
      total_tokens: 0,
      key_count: 0,
    });
    vi.spyOn(apiClient, "listApiKeys").mockResolvedValue({
      items: [{ id: "key_1", key_alias: "for_jane.doe", masked_key: "AS-...1234" }]
    });
    vi.spyOn(apiClient, "listApiKeyUsageSeries").mockResolvedValue({ items: [] });
    const user = userEvent.setup();

    renderPage(<UsagePage auth={auth} />, { initialEntries: ["/usage?key_id=key_1"] });

    await user.click(await screen.findByLabelText("日期區間"));
    expect(await screen.findByRole("button", { name: "最近7日" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "最近14日" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "最近一個月" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "最近7日" }));
    const expectedTo = dayjs().format("YYYY-MM-DD");
    const expectedFrom = dayjs().subtract(6, "day").format("YYYY-MM-DD");
    expect(screen.getByLabelText("日期區間")).toHaveValue(`${expectedFrom} - ${expectedTo}`);
  });

  test("shows error and retry flow for usage series", async () => {
    vi.spyOn(apiClient, "getApiKeyUsageTotal").mockResolvedValue({
      scope: "all_visible_keys",
      prompt_tokens: 0,
      completion_tokens: 0,
      total_tokens: 0,
      key_count: 0,
    });
    vi.spyOn(apiClient, "listApiKeys").mockResolvedValue({
      items: [{ id: "key_1", key_alias: "for_jane.doe", masked_key: "AS-...1234" }]
    });
    const listSeriesSpy = vi
      .spyOn(apiClient, "listApiKeyUsageSeries")
      .mockRejectedValueOnce(new Error("boom"))
      .mockResolvedValueOnce({ items: [] });
    const user = userEvent.setup();

    renderPage(<UsagePage auth={auth} />);

    await user.type(await screen.findByRole("combobox", { name: "API Key" }), "jane");
    await clickOptionByAlias("for_jane.doe");
    expect(await screen.findByText("載入使用量失敗")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "重試" }));
    await waitFor(() => expect(listSeriesSpy).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("此區間沒有使用量資料。")).toBeInTheDocument();
  });

  test("builds tooltip rows without spend", () => {
    const t = (key) =>
      ({
        usage_tooltip_prompt_tokens: "Prompt Tokens",
        usage_tooltip_completion_tokens: "Completion Tokens",
        usage_tooltip_total_tokens: "Total Tokens",
      })[key];

    expect(
      buildUsageTooltipRows(
        { prompt_tokens: 100, completion_tokens: 50, total_tokens: 150, spend: 1.25, hasData: true },
        t
      )
    ).toEqual([
      { label: "Prompt Tokens", value: "100" },
      { label: "Completion Tokens", value: "50" },
      { label: "Total Tokens", value: "150" },
    ]);
  });

  test("builds placeholder tooltip rows for null bucket without fake zeros", () => {
    const t = (key) => key;

    expect(
      buildUsageTooltipRows(
        { bucket_label: "2026-05-02", prompt_tokens: null, completion_tokens: null, total_tokens: null, spend: null, hasData: false },
        t
      )
    ).toEqual([
      { label: "usage_tooltip_prompt_tokens", value: "-" },
      { label: "usage_tooltip_completion_tokens", value: "-" },
      { label: "usage_tooltip_total_tokens", value: "-" },
    ]);
  });

  test("builds complete chart day sequence without zero-filling sparse usage rows", () => {
    expect(
      buildUsageChartDays(
        [
          { bucket_label: "2026-05-13", prompt_tokens: 100, completion_tokens: 50, total_tokens: 150, spend: 1.25 },
          { bucket_label: "2026-05-31", prompt_tokens: 200, completion_tokens: 100, total_tokens: 300, spend: 2.5 },
        ],
        "2026-05-01",
        "2026-05-31"
      )
    ).toEqual(
      expect.arrayContaining([
        { bucket_label: "2026-05-01", prompt_tokens: null, completion_tokens: null, total_tokens: null, spend: null, hasData: false },
        { bucket_label: "2026-05-13", prompt_tokens: 100, completion_tokens: 50, total_tokens: 150, spend: 1.25, hasData: true },
        { bucket_label: "2026-05-31", prompt_tokens: 200, completion_tokens: 100, total_tokens: 300, spend: 2.5, hasData: true },
      ])
    );
  });

  test("builds a default first-month visible window for long ranges", () => {
    expect(buildUsageWindow(46)).toEqual({ startIndex: 0, endIndex: 30, windowSize: 31 });
  });

  test("clamps a resized window to the 31-day maximum span", () => {
    expect(clampVisibleWindow([0, 45], 46)).toEqual([0, 30]);
  });

  test("allows shrinking the slider range below one month", () => {
    expect(clampVisibleWindow([10, 12], 46)).toEqual([10, 12]);
  });

  test("dragging end thumb beyond 31 days pans the window forward", () => {
    expect(resolveVisibleWindowChange([0, 30], [0, 31], 46, 1)).toEqual([1, 31]);
  });

  test("dragging end thumb left shrinks the window", () => {
    expect(resolveVisibleWindowChange([0, 30], [0, 20], 46, 1)).toEqual([0, 20]);
  });

  test("dragging the middle selected range pans the window while keeping span", () => {
    expect(shiftVisibleWindow([5, 10], 3, 46)).toEqual([8, 13]);
  });

  test("dragging the middle selected range clamps at the query boundary", () => {
    expect(shiftVisibleWindow([20, 30], 30, 46)).toEqual([35, 45]);
  });

  test("builds pan overlay metrics from the visible window", () => {
    expect(buildPanOverlayMetrics([5, 10], 46)).toEqual({
      leftPercent: (5 / 45) * 100,
      widthPercent: (5 / 45) * 100,
    });
  });

  test("builds full-width pan overlay metrics for single-day range", () => {
    expect(buildPanOverlayMetrics([0, 0], 1)).toEqual({ leftPercent: 0, widthPercent: 100 });
  });

  test("filters api key options by typed keyword", async () => {
    vi.spyOn(apiClient, "getApiKeyUsageTotal").mockResolvedValue({
      scope: "all_visible_keys",
      prompt_tokens: 0,
      completion_tokens: 0,
      total_tokens: 0,
      key_count: 0,
    });
    vi.spyOn(apiClient, "listApiKeys").mockResolvedValue({
      items: [
        { id: "key_1", key_alias: "for_jane.doe", masked_key: "AS-...1234" },
        { id: "key_2", key_alias: "shared_alias", masked_key: "AS-...9999" }
      ]
    });
    vi.spyOn(apiClient, "listApiKeyUsageSeries").mockResolvedValue({ items: [] });
    const user = userEvent.setup();

    renderPage(<UsagePage auth={auth} />);

    const input = await screen.findByRole("combobox", { name: "API Key" });
    await user.type(input, "shared");

    expect(await screen.findByText("shared_alias")).toBeInTheDocument();
    expect(screen.queryByText("for_jane.doe")).not.toBeInTheDocument();
  });

  test("preselects key from query string and auto-loads series", async () => {
    vi.spyOn(apiClient, "getApiKeyUsageTotal").mockResolvedValue({
      scope: "all_visible_keys",
      prompt_tokens: 0,
      completion_tokens: 0,
      total_tokens: 0,
      key_count: 0,
    });
    const listKeysSpy = vi.spyOn(apiClient, "listApiKeys").mockResolvedValue({
      items: [
        { id: "key_1", key_alias: "for_jane.doe", masked_key: "AS-...1234" },
        { id: "key_2", key_alias: "shared_alias", masked_key: "AS-...9999" }
      ]
    });
    const listSeriesSpy = vi.spyOn(apiClient, "listApiKeyUsageSeries").mockResolvedValue({
      items: [
        {
          bucket_start: "2026-06-01T00:00:00+08:00",
          bucket_label: "2026-06-01",
          prompt_tokens: 100,
          completion_tokens: 50,
          total_tokens: 150,
          spend: 1.25
        }
      ]
    });

    renderPage(<UsagePage auth={auth} />, { initialEntries: ["/usage?key_id=key_2"] });

    await waitFor(() => expect(listKeysSpy).toHaveBeenCalled());
    await waitFor(() => expect(listSeriesSpy).toHaveBeenCalledWith(
      expect.objectContaining({ key_id: "key_2", granularity: "day" }),
      auth
    ));
    expect(await screen.findByDisplayValue("shared_alias (AS-...9999)")).toBeInTheDocument();
  });

  test("loads aggregate usage card by default when no key is selected", async () => {
    vi.spyOn(apiClient, "listApiKeys").mockResolvedValue({
      items: [{ id: "key_1", key_alias: "for_jane.doe", masked_key: "AS-...1234" }]
    });
    const totalSpy = vi.spyOn(apiClient, "getApiKeyUsageTotal").mockResolvedValue({
      scope: "all_visible_keys",
      prompt_tokens: 120,
      completion_tokens: 30,
      total_tokens: 150,
      key_count: 1,
    });

    renderPage(<UsagePage auth={auth} />);

    await waitFor(() => expect(totalSpy).toHaveBeenCalledWith(auth));
    expect(await screen.findByText("全部 API Keys 累計使用量")).toBeInTheDocument();
    expect(screen.getByText("150")).toBeInTheDocument();
  });
});
