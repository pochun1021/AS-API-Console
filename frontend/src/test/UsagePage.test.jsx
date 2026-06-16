import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useEffect } from "react";
import { LocalizationProvider } from "@mui/x-date-pickers/LocalizationProvider";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, test, vi } from "vitest";
import { apiClient } from "../api/client";
import { LocaleProvider, useLocale } from "../i18n/locale";
import UsagePage, {
  buildPanOverlayMetrics,
  buildUsageChartDays,
  buildUsageWindow,
  clampVisibleWindow,
  formatUsageTooltip,
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

afterEach(() => {
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
    await user.type(screen.getByRole("combobox", { name: "API Key" }), "shared");
    await clickOptionByAlias("shared_alias");
    await waitFor(() => expect(listSeriesSpy).toHaveBeenCalled());
    expect(await screen.findByText("每日 total_tokens")).toBeInTheDocument();
    expect(container.querySelectorAll(".MuiChartsAxis-tickLabel").length).toBeGreaterThan(0);
    expect(screen.queryAllByRole("slider")).toHaveLength(0);
  });

  test("shows error and retry flow for usage series", async () => {
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

  test("formats tooltip details", () => {
    const t = (key) =>
      ({
        usage_tooltip_prompt_tokens: "Prompt Tokens",
        usage_tooltip_completion_tokens: "Completion Tokens",
        usage_tooltip_total_tokens: "Total Tokens",
        usage_tooltip_spend: "Spend",
      })[key];

    expect(
      formatUsageTooltip(
        { prompt_tokens: 100, completion_tokens: 50, total_tokens: 150, spend: 1.25, hasData: true },
        t
      )
    ).toBe("Prompt Tokens: 100 | Completion Tokens: 50 | Total Tokens: 150 | Spend: 1.25 USD");
  });

  test("formats tooltip for null bucket without fake zeros", () => {
    const t = (key) => key;

    expect(
      formatUsageTooltip(
        { bucket_label: "2026-05-02", prompt_tokens: null, completion_tokens: null, total_tokens: null, spend: null, hasData: false },
        t
      )
    ).toBe("2026-05-02");
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
});
