import { useEffect, useMemo, useRef, useState } from "react";
import { Autocomplete, Box, Button, Card, CardContent, Divider, Paper, Slider, Stack, TextField, Typography } from "@mui/material";
import { BarChart } from "@mui/x-charts/BarChart";
import { ChartsTooltipContainer, useAxesTooltip } from "@mui/x-charts/ChartsTooltip";
import dayjs from "dayjs";
import { useSearchParams } from "react-router-dom";
import { apiClient } from "../api/client";
import { normalizeApiError } from "../api/errors";
import DateRangeFilterField from "../components/DateRangeFilterField";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlocks";
import { useLocale } from "../i18n/locale";

const MAX_VISIBLE_DAYS = 31;
const PAN_HIT_GAP_PX = 18;

export function defaultDateRange() {
  const today = dayjs();
  const start = today.subtract(6, "day");
  return {
    from: start.format("YYYY-MM-DD"),
    to: today.format("YYYY-MM-DD"),
  };
}

function buildTrailingDateRange(days) {
  const safeDays = Math.max(Number(days) || 1, 1);
  const today = dayjs();
  return {
    from: today.subtract(safeDays - 1, "day").format("YYYY-MM-DD"),
    to: today.format("YYYY-MM-DD"),
  };
}

function buildDateSeries(from, to) {
  if (!from || !to) return [];

  const start = dayjs(from);
  const end = dayjs(to);
  if (!start.isValid() || !end.isValid() || start.isAfter(end, "day")) return [];

  const totalDays = end.diff(start, "day") + 1;
  return Array.from({ length: totalDays }, (_, index) => start.add(index, "day").format("YYYY-MM-DD"));
}

export function buildUsageChartDays(seriesItems, from, to) {
  const labels = buildDateSeries(from, to);
  const usageByLabel = new Map(seriesItems.map((item) => [item.bucket_label, item]));

  return labels.map((label) => {
    const item = usageByLabel.get(label);
    return {
      bucket_label: label,
      prompt_tokens: item?.prompt_tokens ?? null,
      completion_tokens: item?.completion_tokens ?? null,
      total_tokens: item?.total_tokens ?? null,
      spend: item?.spend ?? null,
      hasData: Boolean(item),
    };
  });
}

export function buildUsageWindow(totalDays, maxVisibleDays = MAX_VISIBLE_DAYS) {
  if (totalDays <= 0) {
    return { startIndex: 0, endIndex: 0, windowSize: 0 };
  }

  const windowSize = Math.min(totalDays, maxVisibleDays);
  return {
    startIndex: 0,
    endIndex: windowSize - 1,
    windowSize,
  };
}

export function clampVisibleWindow(nextWindow, totalDays, maxVisibleDays = MAX_VISIBLE_DAYS) {
  if (!Array.isArray(nextWindow) || nextWindow.length !== 2 || totalDays <= 0) {
    return [0, Math.max(totalDays - 1, 0)];
  }

  const maxIndex = totalDays - 1;
  const startIndex = Math.max(0, Math.min(nextWindow[0], maxIndex));
  let endIndex = Math.max(startIndex, Math.min(nextWindow[1], maxIndex));
  const maxSpan = Math.min(Math.max(maxVisibleDays, 1), totalDays) - 1;

  if (endIndex - startIndex > maxSpan) {
    endIndex = startIndex + maxSpan;
  }

  return [startIndex, Math.min(endIndex, maxIndex)];
}

export function resolveVisibleWindowChange(
  currentWindow,
  nextWindow,
  totalDays,
  activeThumb,
  maxVisibleDays = MAX_VISIBLE_DAYS
) {
  if (!Array.isArray(nextWindow) || nextWindow.length !== 2 || totalDays <= 0) {
    return [0, Math.max(totalDays - 1, 0)];
  }

  const maxIndex = totalDays - 1;
  const maxSpan = Math.min(Math.max(maxVisibleDays, 1), totalDays) - 1;
  const [currentStart, currentEnd] = clampVisibleWindow(currentWindow, totalDays, maxVisibleDays);
  const [rawStart, rawEnd] = nextWindow;

  if (activeThumb === 0) {
    const startIndex = Math.max(0, Math.min(rawStart, currentEnd));
    const endIndex =
      currentEnd - startIndex > maxSpan ? Math.min(startIndex + maxSpan, maxIndex) : currentEnd;
    return [startIndex, endIndex];
  }

  if (activeThumb === 1) {
    const endIndex = Math.max(currentStart, Math.min(rawEnd, maxIndex));
    const startIndex = endIndex - currentStart > maxSpan ? Math.max(endIndex - maxSpan, 0) : currentStart;
    return [startIndex, endIndex];
  }

  return clampVisibleWindow(nextWindow, totalDays, maxVisibleDays);
}

export function shiftVisibleWindow(currentWindow, delta, totalDays, maxVisibleDays = MAX_VISIBLE_DAYS) {
  if (totalDays <= 0) return [0, 0];

  const [startIndex, endIndex] = clampVisibleWindow(currentWindow, totalDays, maxVisibleDays);
  const span = endIndex - startIndex;
  const maxStartIndex = Math.max(totalDays - (span + 1), 0);
  const nextStartIndex = Math.max(0, Math.min(startIndex + delta, maxStartIndex));
  return [nextStartIndex, nextStartIndex + span];
}

export function buildPanOverlayMetrics(currentWindow, totalDays) {
  if (totalDays <= 1) {
    return { leftPercent: 0, widthPercent: 100 };
  }

  const [startIndex, endIndex] = clampVisibleWindow(currentWindow, totalDays);
  return {
    leftPercent: (startIndex / (totalDays - 1)) * 100,
    widthPercent: ((endIndex - startIndex) / (totalDays - 1)) * 100,
  };
}

function formatTokenCount(value) {
  if (value == null) return "-";
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value);
}

export function buildUsageTooltipRows(item, t) {
  return [
    { label: t("usage_tooltip_prompt_tokens"), value: formatTokenCount(item?.hasData ? item.prompt_tokens : null) },
    { label: t("usage_tooltip_completion_tokens"), value: formatTokenCount(item?.hasData ? item.completion_tokens : null) },
    { label: t("usage_tooltip_total_tokens"), value: formatTokenCount(item?.hasData ? item.total_tokens : null) },
  ];
}

function UsageChartTooltipContent({ chartDays, t }) {
  const tooltipData = useAxesTooltip({ directions: ["x"] });

  if (!tooltipData?.length) {
    return null;
  }

  const hoveredAxis = tooltipData[0];
  const item = chartDays[hoveredAxis.dataIndex] || null;
  const rows = buildUsageTooltipRows(item, t);

  return (
    <Paper elevation={3} sx={{ px: 1.5, py: 1, minWidth: 220 }}>
      <Stack spacing={0.75}>
        <Typography variant="caption" color="text.secondary">
          {hoveredAxis.axisFormattedValue}
        </Typography>
        {rows.map((row) => (
          <Typography key={row.label} variant="body2">
            {row.label}: {row.value}
          </Typography>
        ))}
      </Stack>
    </Paper>
  );
}

export default function UsagePage({ auth }) {
  const { t } = useLocale();
  const [searchParams] = useSearchParams();
  const [keys, setKeys] = useState([]);
  const [selectedKeyId, setSelectedKeyId] = useState("");
  const [dateRange, setDateRange] = useState(defaultDateRange);
  const [keysLoading, setKeysLoading] = useState(true);
  const [keysError, setKeysError] = useState("");
  const [seriesItems, setSeriesItems] = useState([]);
  const [seriesLoading, setSeriesLoading] = useState(false);
  const [seriesError, setSeriesError] = useState("");
  const [usageTotal, setUsageTotal] = useState(null);
  const [usageTotalLoading, setUsageTotalLoading] = useState(false);
  const [usageTotalError, setUsageTotalError] = useState("");
  const [visibleWindow, setVisibleWindow] = useState([0, 0]);
  const sliderRootRef = useRef(null);
  const panHandleRef = useRef(null);
  const panStateRef = useRef(null);
  const [isPanning, setIsPanning] = useState(false);
  const requestedKeyId = searchParams.get("key_id") || "";

  async function loadKeys() {
    setKeysLoading(true);
    setKeysError("");
    try {
      const response = await apiClient.listApiKeys(
        { page: 1, page_size: 100, sort_by: "created_at", sort_dir: "desc" },
        auth
      );
      setKeys(response.items || []);
    } catch (error) {
      setKeys([]);
      setKeysError(normalizeApiError(error, t("usage_keys_load_failed")));
    } finally {
      setKeysLoading(false);
    }
  }

  async function loadSeries(keyId = selectedKeyId) {
    if (!keyId) {
      setSeriesItems([]);
      setSeriesError("");
      return;
    }
    setSeriesLoading(true);
    setSeriesError("");
    try {
      const response = await apiClient.listApiKeyUsageSeries(
        {
          key_id: keyId,
          granularity: "day",
          from: dateRange.from,
          to: dateRange.to,
        },
        auth
      );
      setSeriesItems(response.items || []);
    } catch (error) {
      setSeriesItems([]);
      setSeriesError(normalizeApiError(error, t("usage_load_failed")));
    } finally {
      setSeriesLoading(false);
    }
  }

  async function loadUsageTotal() {
    setUsageTotalLoading(true);
    setUsageTotalError("");
    try {
      const response = await apiClient.getApiKeyUsageTotal(auth);
      setUsageTotal(response);
    } catch (error) {
      setUsageTotal(null);
      setUsageTotalError(normalizeApiError(error, t("usage_total_load_failed")));
    } finally {
      setUsageTotalLoading(false);
    }
  }

  useEffect(() => {
    loadKeys();
  }, []);

  useEffect(() => {
    if (!requestedKeyId || !keys.length) return;
    if (!keys.some((item) => item.id === requestedKeyId)) return;
    setSelectedKeyId((current) => (current === requestedKeyId ? current : requestedKeyId));
  }, [keys, requestedKeyId]);

  useEffect(() => {
    if (!selectedKeyId) {
      setSeriesItems([]);
      setSeriesError("");
      loadUsageTotal();
      return;
    }
    setUsageTotalError("");
    loadSeries(selectedKeyId);
  }, [selectedKeyId, dateRange.from, dateRange.to]);

  const chartDays = useMemo(
    () => buildUsageChartDays(seriesItems, dateRange.from, dateRange.to),
    [seriesItems, dateRange.from, dateRange.to]
  );
  const defaultWindow = useMemo(() => buildUsageWindow(chartDays.length), [chartDays.length]);
  const shouldShowWindowSlider = chartDays.length > MAX_VISIBLE_DAYS;

  useEffect(() => {
    setVisibleWindow([defaultWindow.startIndex, defaultWindow.endIndex]);
  }, [defaultWindow.startIndex, defaultWindow.endIndex]);

  const visibleChartDays = useMemo(() => {
    if (!chartDays.length) return [];
    const [startIndex, endIndex] = clampVisibleWindow(visibleWindow, chartDays.length);
    return chartDays.slice(startIndex, endIndex + 1);
  }, [chartDays, visibleWindow]);

  const chartLabels = useMemo(() => visibleChartDays.map((item) => item.bucket_label), [visibleChartDays]);
  const chartValues = useMemo(() => visibleChartDays.map((item) => item.total_tokens), [visibleChartDays]);
  const selectedKey = useMemo(
    () => keys.find((item) => item.id === selectedKeyId) || null,
    [keys, selectedKeyId]
  );
  const totalSummaryRows = useMemo(
    () => [
      { label: t("usage_total_prompt_tokens_label"), value: formatTokenCount(usageTotal?.prompt_tokens ?? 0) },
      { label: t("usage_total_completion_tokens_label"), value: formatTokenCount(usageTotal?.completion_tokens ?? 0) },
      { label: t("usage_total_key_count_label"), value: formatTokenCount(usageTotal?.key_count ?? 0) },
    ],
    [t, usageTotal]
  );
  const usageQuickRanges = useMemo(
    () => [
      { label: t("usage_quick_range_7_days"), getRange: () => buildTrailingDateRange(7) },
      { label: t("usage_quick_range_14_days"), getRange: () => buildTrailingDateRange(14) },
      { label: t("usage_quick_range_30_days"), getRange: () => buildTrailingDateRange(30) },
    ],
    [t]
  );
  const panOverlayMetrics = useMemo(
    () => buildPanOverlayMetrics(visibleWindow, chartDays.length),
    [visibleWindow, chartDays.length]
  );

  function handleWindowChange(_, nextValue, activeThumb) {
    if (!Array.isArray(nextValue) || !chartDays.length) return;

    if (!shouldShowWindowSlider) {
      setVisibleWindow([0, Math.max(chartDays.length - 1, 0)]);
      return;
    }
    setVisibleWindow(
      resolveVisibleWindowChange(visibleWindow, nextValue, chartDays.length, activeThumb)
    );
  }

  function handlePanPointerDown(event) {
    if (!shouldShowWindowSlider || !chartDays.length || !sliderRootRef.current) return;
    event.preventDefault();
    event.stopPropagation();
    panHandleRef.current?.setPointerCapture?.(event.pointerId);

    panStateRef.current = {
      pointerId: event.pointerId,
      startClientX: event.clientX,
      startWindow: clampVisibleWindow(visibleWindow, chartDays.length),
    };
    setIsPanning(true);
  }

  function handlePanPointerMove(event) {
    const panState = panStateRef.current;
    if (!panState || panState.pointerId !== event.pointerId || !sliderRootRef.current) return;

    const sliderRect = sliderRootRef.current.getBoundingClientRect();
    const totalSteps = Math.max(chartDays.length - 1, 1);
    const deltaRatio = (event.clientX - panState.startClientX) / Math.max(sliderRect.width, 1);
    const deltaSteps = Math.round(deltaRatio * totalSteps);
    setVisibleWindow(shiftVisibleWindow(panState.startWindow, deltaSteps, chartDays.length));
  }

  function handlePanPointerEnd(event) {
    if (panStateRef.current?.pointerId !== event.pointerId) return;
    panHandleRef.current?.releasePointerCapture?.(event.pointerId);
    panStateRef.current = null;
    setIsPanning(false);
  }

  function UsageChartTooltip(props) {
    return (
      <ChartsTooltipContainer {...props} trigger="axis">
        <UsageChartTooltipContent chartDays={visibleChartDays} t={t} />
      </ChartsTooltipContainer>
    );
  }

  return (
    <Stack spacing={2} sx={{ flex: 1, minHeight: 0 }}>
      <Stack spacing={0.5}>
        <Typography variant="h4">{t("usage_title")}</Typography>
      </Stack>
      <Card>
        <CardContent>
          <Stack direction={{ xs: "column", lg: "row" }} spacing={2} alignItems={{ xs: "stretch", lg: "center" }}>
          <Autocomplete
              options={keys}
              value={selectedKey}
              onChange={(_, nextValue) => setSelectedKeyId(nextValue?.id || "")}
              getOptionLabel={(option) => `${option.key_alias} (${option.masked_key})`}
              isOptionEqualToValue={(option, value) => option.id === value.id}
              filterOptions={(options, state) => {
                const keyword = state.inputValue.trim().toLowerCase();
                if (!keyword) return options;
                return options.filter((option) =>
                  `${option.key_alias} ${option.masked_key}`.toLowerCase().includes(keyword)
                );
              }}
              sx={{ minWidth: 280 }}
              disabled={keysLoading || keys.length === 0}
              renderOption={(props, option) => {
                const { key, ...optionProps } = props;
                return (
                <Box
                  component="li"
                  key={key}
                  {...optionProps}
                  sx={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "flex-start",
                    minWidth: 0,
                    py: 1,
                  }}
                >
                  <Typography
                    variant="body2"
                    sx={{
                      width: "100%",
                      fontWeight: 600,
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}
                  >
                    {option.key_alias}
                  </Typography>
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    sx={{
                      width: "100%",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}
                  >
                    {option.masked_key}
                  </Typography>
                </Box>
                );
              }}
              renderInput={(params) => (
                <TextField
                  {...params}
                  label={t("usage_key_label")}
                  placeholder={t("usage_key_placeholder")}
                />
              )}
            />
            {selectedKeyId ? (
              <>
                <DateRangeFilterField
                  label={t("usage_date_range")}
                  fromValue={dateRange.from}
                  toValue={dateRange.to}
                  onChange={(next) => setDateRange(next)}
                  startLabel={t("usage_date_from")}
                  endLabel={t("usage_date_to")}
                  clearLabel={t("common_clear")}
                  closeLabel={t("common_close")}
                  minWidth={280}
                  quickRanges={usageQuickRanges}
                />
                <Box sx={{ display: "flex", justifyContent: { xs: "flex-start", lg: "flex-end" }, flex: 1 }}>
                  <Button
                    variant="contained"
                    onClick={() => loadSeries()}
                    disabled={!selectedKeyId || seriesLoading || keysLoading}
                  >
                    {t("usage_refresh")}
                  </Button>
                </Box>
              </>
            ) : null}
          </Stack>
        </CardContent>
      </Card>
      <Card sx={{ flex: 1, minHeight: 0 }}>
        <CardContent sx={{ display: "flex", flexDirection: "column", gap: 2, height: "100%" }}>
          <Typography variant="h6">{t("usage_chart_title")}</Typography>
          {keysLoading ? <LoadingBlock text={t("usage_loading_keys")} /> : null}
          {!keysLoading && keysError ? <ErrorBlock message={keysError} onRetry={loadKeys} /> : null}
          {!keysLoading && !keysError && keys.length === 0 ? <EmptyBlock text={t("usage_empty_keys")} /> : null}
          {!keysLoading && !keysError && keys.length > 0 && !selectedKeyId && usageTotalLoading ? (
            <LoadingBlock text={t("usage_loading_total")} />
          ) : null}
          {!keysLoading && !keysError && keys.length > 0 && !selectedKeyId && !usageTotalLoading && usageTotalError ? (
            <ErrorBlock message={usageTotalError} onRetry={loadUsageTotal} />
          ) : null}
          {!keysLoading && !keysError && keys.length > 0 && !selectedKeyId && !usageTotalLoading && !usageTotalError ? (
            <Card variant="outlined">
              <CardContent>
                <Stack spacing={2}>
                  <Stack direction={{ xs: "column", sm: "row" }} justifyContent="space-between" spacing={1}>
                    <Typography variant="h6">{t("usage_total_card_title")}</Typography>
                    <Button variant="outlined" onClick={loadUsageTotal} disabled={usageTotalLoading || keysLoading}>
                      {t("usage_refresh_total")}
                    </Button>
                  </Stack>
                  <Typography variant="body1" color="text.secondary">
                    {t("usage_total_tokens_label")}
                  </Typography>
                  <Typography variant="h3">{formatTokenCount(usageTotal?.total_tokens ?? 0)}</Typography>
                  <Divider />
                  <Stack direction={{ xs: "column", sm: "row" }} spacing={2} useFlexGap flexWrap="wrap">
                    {totalSummaryRows.map((row) => (
                      <Box key={row.label} sx={{ minWidth: 160 }}>
                        <Typography variant="body1" color="text.secondary">
                          {row.label}
                        </Typography>
                        <Typography variant="body1">{row.value}</Typography>
                      </Box>
                    ))}
                  </Stack>
                </Stack>
              </CardContent>
            </Card>
          ) : null}
          {!keysLoading && !keysError && keys.length > 0 && selectedKeyId && seriesLoading ? (
            <LoadingBlock text={t("usage_loading_series")} />
          ) : null}
          {!keysLoading && !keysError && keys.length > 0 && selectedKeyId && !seriesLoading && seriesError ? (
            <ErrorBlock message={seriesError} onRetry={() => loadSeries()} />
          ) : null}
          {!keysLoading && !keysError && keys.length > 0 && selectedKeyId && !seriesLoading && !seriesError && seriesItems.length === 0 ? (
            <EmptyBlock text={t("usage_empty_series")} />
          ) : null}
          {!keysLoading && !keysError && keys.length > 0 && selectedKeyId && !seriesLoading && !seriesError && seriesItems.length > 0 ? (
            <Box sx={{ flex: 1, minHeight: 360 }}>
              <Stack spacing={3}>
                <Box>
                  <Typography variant="subtitle2" sx={{ mb: 1 }}>
                    {t("usage_chart_key_title")}
                  </Typography>
                  <BarChart
                    height={380}
                    xAxis={[
                      {
                        id: "usage-days",
                        data: chartLabels,
                        scaleType: "band",
                        position: "bottom",
                        tickLabelInterval: () => true,
                        height: "auto",
                        tickLabelStyle: {
                          angle: -35,
                          textAnchor: "end",
                          fontSize: 12,
                        },
                      },
                    ]}
                    series={[
                      {
                        id: "total_tokens",
                        label: t("usage_total_tokens_series"),
                        data: chartValues,
                      },
                    ]}
                    slots={{ tooltip: UsageChartTooltip }}
                    margin={{ left: 80, right: 24, top: 24, bottom: 100 }}
                  />
                </Box>
              </Stack>
              {shouldShowWindowSlider ? (
                <Stack spacing={1} sx={{ px: { xs: 2.5, md: 3 }, pb: 1, alignItems: "center" }}>
                  <Typography variant="caption" color="text.secondary">
                    {chartDays[visibleWindow[0]]?.bucket_label} - {chartDays[visibleWindow[1]]?.bucket_label}
                  </Typography>
                  <Box
                    ref={sliderRootRef}
                    sx={{ width: "100%", maxWidth: { xs: 420, md: 560 } }}
                  >
                    <Box sx={{ position: "relative", px: { xs: 2, md: 2.5 } }}>
                      <Slider
                        value={visibleWindow}
                        onChange={handleWindowChange}
                        min={0}
                        max={Math.max(chartDays.length - 1, 0)}
                        step={1}
                        disableSwap
                        valueLabelDisplay="auto"
                        getAriaLabel={() => t("usage_date_range")}
                        getAriaValueText={(value) => chartDays[value]?.bucket_label || ""}
                        valueLabelFormat={(value) => chartDays[value]?.bucket_label || ""}
                        marks={[
                          { value: 0, label: chartDays[0]?.bucket_label },
                          { value: chartDays.length - 1, label: chartDays[chartDays.length - 1]?.bucket_label },
                        ]}
                        sx={{
                          position: "relative",
                          zIndex: 1,
                          "& .MuiSlider-thumb": {
                            zIndex: 3,
                          },
                          "& .MuiSlider-markLabel": {
                            fontSize: 12,
                            whiteSpace: "nowrap",
                          },
                          "& .MuiSlider-markLabel[data-index=\"0\"]": {
                            transform: "translateX(0)",
                            textAlign: "left",
                          },
                          "& .MuiSlider-markLabel[data-index=\"1\"]": {
                            transform: "translateX(-100%)",
                            textAlign: "right",
                          },
                        }}
                      />
                      <Box
                        data-testid="usage-slider-pan-layer"
                        sx={{
                          position: "absolute",
                          left: `${panOverlayMetrics.leftPercent}%`,
                          width: `${panOverlayMetrics.widthPercent}%`,
                          top: "50%",
                          transform: "translateY(-50%)",
                          height: 16,
                          zIndex: 2,
                          pointerEvents: "none",
                        }}
                      >
                        <Box
                          ref={panHandleRef}
                          onPointerDown={handlePanPointerDown}
                          onPointerMove={handlePanPointerMove}
                          onPointerUp={handlePanPointerEnd}
                          onPointerCancel={handlePanPointerEnd}
                          sx={{
                            position: "absolute",
                            left: `${PAN_HIT_GAP_PX}px`,
                            right: `${PAN_HIT_GAP_PX}px`,
                            top: 0,
                            bottom: 0,
                            pointerEvents: "auto",
                            cursor: isPanning ? "grabbing" : "grab",
                            userSelect: "none",
                            touchAction: "none",
                          }}
                        />
                      </Box>
                    </Box>
                  </Box>
                </Stack>
              ) : null}
            </Box>
          ) : null}
        </CardContent>
      </Card>
    </Stack>
  );
}
