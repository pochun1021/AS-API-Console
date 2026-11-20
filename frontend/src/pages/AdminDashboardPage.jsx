import { useEffect, useMemo, useRef, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  Stack,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  Typography
} from "@mui/material";
import { BarChart } from "@mui/x-charts/BarChart";
import { DataGrid } from "@mui/x-data-grid/DataGrid";
import { apiClient } from "../api/client";
import { normalizeApiError } from "../api/errors";
import DateRangeFilterField from "../components/DateRangeFilterField";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlocks";
import { useLocale } from "../i18n/locale";
import { COMPACT_MAIN_PAGE_SIZE_OPTIONS, compactGridProps, compactGridSx } from "../utils/compactDataGrid";
import { useDepartmentDisplay } from "../utils/departmentDisplay";
import { getGridLocaleText } from "../utils/gridLocaleText";

function statusColor(status) {
  if (status === "active") return "success";
  if (status === "revoked") return "warning";
  return "default";
}

function getStatusLabel(status, t) {
  return t(`mykeys_status_${status}`, status || "-");
}

function formatMaskedKey(value) {
  if (!value) return "-";
  return String(value);
}

const defaultTableQuery = {
  page: 0, pageSize: 10, scope: "all", from: "", to: "",
  ownerAccount: "", ownerName: "", ownerEmail: "", ownerDepartment: "",
  sortModel: [{ field: "total_applications", sort: "desc" }]
};
const defaultChartQuery = {
  scope: "all", from: "", to: "", ownerDepartment: "",
  xAxis: "account", yAxis: "total_applications", topN: 10
};

export default function AdminDashboardPage({ auth }) {
  const { locale, t } = useLocale();
  const gridLocaleText = getGridLocaleText(locale);
  const { departmentOptions: instituteDepartmentOptions, formatDepartment, formatDepartmentOption } = useDepartmentDisplay(auth);
  const [statisticsDepartments, setStatisticsDepartments] = useState([]);
  const departmentOptions = statisticsDepartments.length > 0
    ? statisticsDepartments.map((value) => ({ value, label: formatDepartmentOption(value, locale) }))
    : instituteDepartmentOptions;
  const scopeOptions = ["all", "active", "revoked", "expired"];
  const topNOptions = [5, 10, 20];
  const xAxisOptions = [
    { value: "account", label: t("dashboard_x_account") },
    { value: "department", label: t("dashboard_x_department") }
  ];
  const yAxisOptions = [
    { value: "total_applications", label: t("dashboard_y_total_applications") },
    { value: "active_count", label: t("dashboard_y_active_count") },
    { value: "revoked_count", label: t("dashboard_y_revoked_count") },
    { value: "expired_count", label: t("dashboard_y_expired_count") }
  ];
  const allowedSortFields = new Set([
    "owner_account",
    "owner_name",
    "owner_email",
    "owner_department",
    "total_applications",
    "active_count",
    "revoked_count",
    "expired_count",
    "last_applied_at"
  ]);
  const [tableQuery, setTableQuery] = useState(defaultTableQuery);
  const [chartQuery, setChartQuery] = useState(defaultChartQuery);
  const [tableItems, setTableItems] = useState([]);
  const [chartItems, setChartItems] = useState([]);
  const [tableTotal, setTableTotal] = useState(0);
  const [view, setView] = useState("table");
  const [tableLoading, setTableLoading] = useState(true);
  const [chartLoading, setChartLoading] = useState(false);
  const [tableError, setTableError] = useState("");
  const [chartError, setChartError] = useState("");
  const tableRequest = useRef(0);
  const chartRequest = useRef(0);
  useEffect(() => {
    if (auth.role !== "admin") return undefined;
    let canceled = false;
    apiClient.listApiKeyStatisticsDepartments(auth)
      .then((response) => {
        if (!canceled) setStatisticsDepartments(response.items || []);
      })
      .catch(() => {
        if (!canceled) setStatisticsDepartments([]);
      });
    return () => { canceled = true; };
  }, [auth.account, auth.role]);
  const [detailDialog, setDetailDialog] = useState({ open: false, title: "", ownerAccount: "", status: undefined });
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [detailItems, setDetailItems] = useState([]);
  const hasActiveFilters = Boolean(
    tableQuery.scope !== "all" ||
    tableQuery.from ||
    tableQuery.to ||
    tableQuery.ownerAccount.trim() ||
    tableQuery.ownerName.trim() ||
    tableQuery.ownerEmail.trim() ||
    tableQuery.ownerDepartment ||
    tableQuery.sortModel[0]?.field !== "total_applications" ||
    tableQuery.sortModel[0]?.sort !== "desc" ||
    tableQuery.page !== 0 || tableQuery.pageSize !== 10
  );
  const hasActiveChartFilters = Object.keys(defaultChartQuery).some((key) => chartQuery[key] !== defaultChartQuery[key]);
  const setTableFilter = (changes) => setTableQuery((query) => ({ ...query, ...changes, page: 0 }));
  const setChartFilter = (changes) => setChartQuery((query) => ({ ...query, ...changes }));

  async function openDetailDialog(row, metric) {
    const status = metric === "active_count" ? "active" : undefined;
    const titleKey = metric === "active_count" ? "dashboard_detail_title_active" : "dashboard_detail_title_total";
    setDetailDialog({
      open: true,
      title: t(titleKey).replace("{owner}", row.owner_account),
      ownerAccount: row.owner_account,
      status
    });
    setDetailLoading(true);
    setDetailError("");
    try {
      const response = await apiClient.listApiKeys(
        {
          page: 1,
          page_size: 100,
          owner_account: row.owner_account,
          status,
          from: tableQuery.from || undefined,
          to: tableQuery.to || undefined
        },
        auth
      );
      setDetailItems(response.items || []);
    } catch (e) {
      setDetailItems([]);
      setDetailError(normalizeApiError(e, t("dashboard_detail_load_failed")));
    } finally {
      setDetailLoading(false);
    }
  }

  function closeDetailDialog() {
    setDetailDialog({ open: false, title: "", ownerAccount: "", status: undefined });
    setDetailItems([]);
    setDetailError("");
    setDetailLoading(false);
  }

  function clearFilters() {
    setTableQuery(defaultTableQuery);
  }

  const columns = useMemo(
    () => [
      {
        field: "owner_account",
        headerName: t("dashboard_col_owner_account"),
        flex: 1,
        minWidth: 140,
        filterable: false
      },
      {
        field: "owner_name",
        headerName: t("dashboard_col_owner_name"),
        flex: 1,
        minWidth: 140,
        filterable: false
      },
      {
        field: "owner_email",
        headerName: t("dashboard_col_owner_email"),
        flex: 1.6,
        minWidth: 220,
        filterable: false
      },
      {
        field: "owner_department",
        headerName: t("dashboard_col_owner_department"),
        flex: 1,
        minWidth: 140,
        filterable: false,
        renderCell: (params) => formatDepartment(params.row.owner_department, locale)
      },
      {
        field: "total_applications",
        headerName: t("dashboard_col_total_applications"),
        type: "number",
        flex: 0.8,
        minWidth: 120,
        renderCell: (params) => (
          <Button variant="text" size="small" onClick={() => openDetailDialog(params.row, "total_applications")}>
            {params.value}
          </Button>
        )
      },
      {
        field: "active_count",
        headerName: t("dashboard_col_active_count"),
        type: "number",
        flex: 0.8,
        minWidth: 120,
        renderCell: (params) => (
          <Button variant="text" size="small" onClick={() => openDetailDialog(params.row, "active_count")}>
            {params.value}
          </Button>
        )
      },
      { field: "revoked_count", headerName: t("dashboard_col_revoked_count"), type: "number", flex: 0.8, minWidth: 120 },
      { field: "expired_count", headerName: t("dashboard_col_expired_count"), type: "number", flex: 0.8, minWidth: 120 },
      { field: "last_applied_at", headerName: t("dashboard_col_last_applied_at"), flex: 1, minWidth: 140, filterable: false }
    ],
    [t, tableQuery.from, tableQuery.to, auth, formatDepartment, locale]
  );

  async function loadTable(query = tableQuery) {
    if (auth.role !== "admin") return;
    const requestId = ++tableRequest.current;
    setTableLoading(true);
    setTableError("");
    try {
      const requestedSort = query.sortModel[0] || { field: "total_applications", sort: "desc" };
      const sort = allowedSortFields.has(requestedSort.field)
        ? requestedSort
        : { field: "total_applications", sort: "desc" };
      const response = await apiClient.listApiKeyUserStatistics(
        {
          page: query.page + 1,
          page_size: query.pageSize,
          scope: query.scope,
          from: query.from || undefined,
          to: query.to || undefined,
          owner_account: query.ownerAccount.trim() || undefined,
          owner_name: query.ownerName.trim() || undefined,
          owner_email: query.ownerEmail.trim() || undefined,
          owner_department: query.ownerDepartment.trim() || undefined,
          sort_by: sort.field,
          sort_dir: sort.sort || "desc"
        },
        auth
      );
      if (requestId !== tableRequest.current) return;
      setTableItems(response.items.map((item) => ({ ...item, id: item.owner_account })));
      setTableTotal(response.total);
    } catch (e) {
      if (requestId === tableRequest.current) setTableError(normalizeApiError(e, t("dashboard_load_failed")));
    } finally {
      if (requestId === tableRequest.current) setTableLoading(false);
    }
  }

  async function loadChart(query = chartQuery) {
    if (auth.role !== "admin") return;
    const requestId = ++chartRequest.current;
    setChartLoading(true);
    setChartError("");
    try {
      const response = await apiClient.getApiKeyStatisticsChart({
        x_axis: query.xAxis, y_axis: query.yAxis, top_n: query.topN,
        scope: query.scope, from: query.from || undefined, to: query.to || undefined,
        owner_department: query.ownerDepartment.trim() || undefined
      }, auth);
      if (requestId !== chartRequest.current) return;
      setChartItems(response.items);
    } catch (e) {
      if (requestId === chartRequest.current) setChartError(normalizeApiError(e, t("dashboard_load_failed")));
    } finally {
      if (requestId === chartRequest.current) setChartLoading(false);
    }
  }

  useEffect(() => {
    if (view === "table") loadTable(tableQuery);
    return () => { tableRequest.current += 1; };
  }, [view, tableQuery]);

  useEffect(() => {
    if (view === "chart") loadChart(chartQuery);
    return () => { chartRequest.current += 1; };
  }, [view, chartQuery]);

  if (auth.role !== "admin") {
    return (
      <Stack spacing={3}>
        <Typography variant="h4">{t("dashboard_title")}</Typography>
        <ErrorBlock message={t("dashboard_forbidden")} />
      </Stack>
    );
  }

  return (
    <Stack spacing={2} sx={{ flex: 1, minHeight: 0, overflow: "hidden" }}>
      <Typography variant="h4">{t("dashboard_title")}</Typography>
      {view === "table" && !tableLoading && !tableError && tableTotal === 0 ? <Alert severity="info">{t("dashboard_empty_filtered")}</Alert> : null}

      <Tabs value={view} onChange={(_, value) => setView(value)} aria-label={t("dashboard_view_toggle")}>
        <Tab value="table" label={t("dashboard_tab_table")} />
        <Tab value="chart" label={t("dashboard_tab_chart")} />
      </Tabs>

      {view === "table" ? (
        <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} useFlexGap flexWrap="wrap" sx={{ flexShrink: 0 }}>
          <TextField
            select
            label={t("dashboard_scope")}
            value={tableQuery.scope}
            onChange={(event) => {
              setTableFilter({ scope: event.target.value });
            }}
            sx={{ minWidth: 180 }}
          >
            {scopeOptions.map((option) => (
              <MenuItem key={option} value={option}>
                {t(`dashboard_scope_${option}`)}
              </MenuItem>
            ))}
          </TextField>
          <DateRangeFilterField
            label={t("dashboard_date_range")}
            fromValue={tableQuery.from}
            toValue={tableQuery.to}
            startLabel={t("dashboard_from")}
            endLabel={t("dashboard_to")}
            clearLabel={t("common_clear")}
            closeLabel={t("common_close")}
            minWidth={260}
            onChange={({ from, to }) => {
              setTableFilter({ from, to });
            }}
          />
          <TextField
            label={t("dashboard_col_owner_account")}
            value={tableQuery.ownerAccount}
            onChange={(event) => {
              setTableFilter({ ownerAccount: event.target.value });
            }}
            sx={{ minWidth: 180 }}
          />
          <TextField
            label={t("dashboard_col_owner_name")}
            value={tableQuery.ownerName}
            onChange={(event) => {
              setTableFilter({ ownerName: event.target.value });
            }}
            sx={{ minWidth: 180 }}
          />
          <TextField
            label={t("dashboard_col_owner_email")}
            value={tableQuery.ownerEmail}
            onChange={(event) => {
              setTableFilter({ ownerEmail: event.target.value });
            }}
            sx={{ minWidth: 220 }}
          />
          <TextField
            select
            label={t("dashboard_col_owner_department")}
            value={tableQuery.ownerDepartment}
            onChange={(event) => {
              setTableFilter({ ownerDepartment: event.target.value });
            }}
            sx={{ minWidth: 220 }}
          >
            <MenuItem value="">{t("dashboard_all_departments")}</MenuItem>
            {departmentOptions.map((option) => (
              <MenuItem key={option.value} value={option.value}>
              {option.label}
            </MenuItem>
          ))}
          </TextField>
          <Button variant="outlined" onClick={clearFilters} disabled={!hasActiveFilters} sx={{ minHeight: 56 }}>
            {t("mykeys_clear_filters")}
          </Button>
        </Stack>
      ) : null}

      {view === "table" && tableLoading ? <LoadingBlock text={t("dashboard_loading")} /> : null}
      {view === "table" && !tableLoading && tableError ? <ErrorBlock message={tableError} onRetry={() => loadTable()} /> : null}
      {view === "table" && !tableLoading && !tableError && tableItems.length === 0 ? <EmptyBlock text={t("dashboard_no_data")} /> : null}

      {!tableLoading && !tableError && tableItems.length > 0 && view === "table" ? (
        <Box sx={{ width: "100%", borderRadius: 2, p: 0.5, flex: 1, minHeight: 0, overflow: "hidden", backgroundColor: "white" }}>
          <DataGrid
            sx={compactGridSx}
            rows={tableItems}
            columns={columns}
            pageSizeOptions={COMPACT_MAIN_PAGE_SIZE_OPTIONS}
            paginationMode="server"
            sortingMode="server"
            rowCount={tableTotal}
            paginationModel={{ page: tableQuery.page, pageSize: tableQuery.pageSize }}
            onPaginationModelChange={(model) => {
              setTableQuery((query) => ({ ...query, page: model.page, pageSize: model.pageSize }));
            }}
            sortModel={tableQuery.sortModel}
            onSortModelChange={(model) => {
              if (model.length === 0) {
                setTableFilter({ sortModel: [{ field: "total_applications", sort: "desc" }] });
                return;
              }
              setTableFilter({ sortModel: model });
            }}
            disableRowSelectionOnClick
            {...compactGridProps}
            localeText={gridLocaleText}
          />
        </Box>
      ) : null}

      {view === "chart" ? (
        <Card>
          <CardContent>
            <Stack spacing={2}>
              <Stack direction={{ xs: "column", md: "row" }} spacing={2} useFlexGap flexWrap="wrap">
                <TextField select label={t("dashboard_scope")} value={chartQuery.scope}
                  onChange={(event) => setChartFilter({ scope: event.target.value })} sx={{ minWidth: 180 }}>
                  {scopeOptions.map((option) => <MenuItem key={option} value={option}>{t(`dashboard_scope_${option}`)}</MenuItem>)}
                </TextField>
                <DateRangeFilterField
                  label={t("dashboard_date_range")}
                  fromValue={chartQuery.from} toValue={chartQuery.to}
                  startLabel={t("dashboard_from")} endLabel={t("dashboard_to")}
                  clearLabel={t("common_clear")} closeLabel={t("common_close")}
                  minWidth={260} onChange={({ from, to }) => setChartFilter({ from, to })}
                />
                <TextField select label={t("dashboard_col_owner_department")}
                  value={chartQuery.ownerDepartment}
                  onChange={(event) => setChartFilter({ ownerDepartment: event.target.value })}
                  sx={{ minWidth: 220 }}>
                  <MenuItem value="">{t("dashboard_all_departments")}</MenuItem>
                  {departmentOptions.map((option) => <MenuItem key={option.value} value={option.value}>{option.label}</MenuItem>)}
                </TextField>
                <TextField
                  select
                  label={t("dashboard_axis_x")}
                  value={chartQuery.xAxis}
                  onChange={(event) => setChartFilter({ xAxis: event.target.value })}
                  sx={{ minWidth: 180 }}
                >
                  {xAxisOptions.map((option) => (
                    <MenuItem key={option.value} value={option.value}>
                      {option.label}
                    </MenuItem>
                  ))}
                </TextField>
                <TextField
                  select
                  label={t("dashboard_axis_y")}
                  value={chartQuery.yAxis}
                  onChange={(event) => setChartFilter({ yAxis: event.target.value })}
                  sx={{ minWidth: 180 }}
                >
                  {yAxisOptions.map((option) => (
                    <MenuItem key={option.value} value={option.value}>
                      {option.label}
                    </MenuItem>
                  ))}
                </TextField>
                <TextField
                  select
                  label={t("dashboard_top_n")}
                  value={chartQuery.topN}
                  onChange={(event) => setChartFilter({ topN: Number(event.target.value) })}
                  sx={{ minWidth: 180 }}
                >
                  {topNOptions.map((option) => (
                    <MenuItem key={option} value={option}>
                      {option}
                    </MenuItem>
                  ))}
                </TextField>
                <Button variant="outlined" onClick={() => setChartQuery(defaultChartQuery)} disabled={!hasActiveChartFilters} sx={{ minHeight: 56 }}>
                  {t("mykeys_clear_filters")}
                </Button>
              </Stack>
            {chartLoading ? <LoadingBlock text={t("dashboard_loading")} /> : null}
            {!chartLoading && chartError ? <ErrorBlock message={chartError} onRetry={() => loadChart()} /> : null}
            {!chartLoading && !chartError && chartItems.length === 0 ? <EmptyBlock text={t("dashboard_no_data")} /> : null}
            {!chartLoading && !chartError && chartItems.length > 0 ? (
              <BarChart
                height={420}
                xAxis={[
                  {
                    id: "x-axis",
                    scaleType: "band",
                    position: "bottom",
                    data: chartItems.map((item) => chartQuery.xAxis === "department" ? formatDepartment(item.label, locale) : item.label),
                    tickLabelInterval: () => true,
                    height: "auto",
                    tickLabelStyle: {
                      angle: -35,
                      textAnchor: "end",
                      fontSize: 12
                    }
                  }
                ]}
                series={[{ data: chartItems.map((item) => item.value), label: yAxisOptions.find((o) => o.value === chartQuery.yAxis)?.label }]}
                margin={{ left: 60, right: 20, top: 30, bottom: 120 }}
              />
            ) : null}
            </Stack>
          </CardContent>
        </Card>
      ) : null}

      <Dialog open={detailDialog.open} onClose={closeDetailDialog} fullWidth maxWidth="md">
        <DialogTitle>{detailDialog.title}</DialogTitle>
        <DialogContent>
          {detailLoading ? <LoadingBlock text={t("dashboard_detail_loading")} /> : null}
          {!detailLoading && detailError ? <ErrorBlock message={detailError} /> : null}
          {!detailLoading && !detailError && detailItems.length === 0 ? <EmptyBlock text={t("dashboard_detail_empty")} /> : null}
          {!detailLoading && !detailError && detailItems.length > 0 ? (
            <Table size="small" aria-label={t("dashboard_detail_table_aria")}>
              <TableHead>
                <TableRow>
                  <TableCell>{t("mykeys_col_key_alias")}</TableCell>
                  <TableCell>{t("mykeys_col_masked_key")}</TableCell>
                  <TableCell>{t("common_status")}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {detailItems.map((item) => (
                  <TableRow key={item.id}>
                    <TableCell>{item.key_alias}</TableCell>
                    <TableCell>{formatMaskedKey(item.masked_key)}</TableCell>
                    <TableCell>
                      <Chip size="small" label={getStatusLabel(item.status, t)} color={statusColor(item.status)} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : null}
        </DialogContent>
        <DialogActions>
          <Button onClick={closeDetailDialog}>{t("common_close")}</Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
