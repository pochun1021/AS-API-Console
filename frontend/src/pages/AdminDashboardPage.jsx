import { useEffect, useMemo, useState } from "react";
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
import { DataGrid, getGridStringOperators } from "@mui/x-data-grid";
import { DatePicker } from "@mui/x-date-pickers/DatePicker";
import dayjs from "dayjs";
import { apiClient } from "../api/client";
import { normalizeApiError } from "../api/errors";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlocks";
import { useLocale } from "../i18n/locale";
import { useDepartmentDisplay } from "../utils/departmentDisplay";
import { getContainsFilterValue } from "../utils/serverDataGrid";

function statusColor(status) {
  if (status === "active") return "success";
  if (status === "revoked") return "warning";
  return "default";
}

function formatMaskedKey(value) {
  if (!value) return "-";
  return String(value);
}

const containsFilterOperators = getGridStringOperators().filter((operator) => operator.value === "contains");

export default function AdminDashboardPage({ auth }) {
  const { gridLocaleText, locale, t } = useLocale();
  const { formatDepartment } = useDepartmentDisplay(auth);
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
  const [items, setItems] = useState([]);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);
  const [scope, setScope] = useState("all");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [q, setQ] = useState("");
  const [sortModel, setSortModel] = useState([{ field: "total_applications", sort: "desc" }]);
  const [filterModel, setFilterModel] = useState({ items: [] });
  const [view, setView] = useState("table");
  const [topN, setTopN] = useState(10);
  const [xAxisField, setXAxisField] = useState("account");
  const [yAxisField, setYAxisField] = useState("total_applications");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [banner, setBanner] = useState("");
  const [detailDialog, setDetailDialog] = useState({ open: false, title: "", ownerAccount: "", status: undefined });
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [detailItems, setDetailItems] = useState([]);

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
          from: fromDate || undefined,
          to: toDate || undefined
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

  const columns = useMemo(
    () => [
      {
        field: "owner_account",
        headerName: t("dashboard_col_owner_account"),
        flex: 1,
        minWidth: 140,
        filterOperators: containsFilterOperators
      },
      {
        field: "owner_name",
        headerName: t("dashboard_col_owner_name"),
        flex: 1,
        minWidth: 140,
        filterOperators: containsFilterOperators
      },
      {
        field: "owner_email",
        headerName: t("dashboard_col_owner_email"),
        flex: 1.6,
        minWidth: 220,
        filterOperators: containsFilterOperators
      },
      {
        field: "owner_department",
        headerName: t("dashboard_col_owner_department"),
        flex: 1,
        minWidth: 140,
        filterOperators: containsFilterOperators,
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
    [t, fromDate, toDate, auth, formatDepartment, locale]
  );

  const chartItems = useMemo(() => {
    const sorted = [...items].sort((a, b) => {
      const av = Number(a[yAxisField] || 0);
      const bv = Number(b[yAxisField] || 0);
      if (av === bv) return a.owner_account.localeCompare(b.owner_account);
      return bv - av;
    });
    return sorted.slice(0, topN).map((item) => ({
      label: xAxisField === "department" ? formatDepartment(item.owner_department, locale) : item.owner_account,
      value: Number(item[yAxisField] || 0)
    }));
  }, [items, topN, xAxisField, yAxisField, formatDepartment, locale]);

  async function load() {
    if (auth.role !== "admin") return;
    setLoading(true);
    setError("");
    try {
      const requestedSort = sortModel[0] || { field: "total_applications", sort: "desc" };
      const sort = allowedSortFields.has(requestedSort.field)
        ? requestedSort
        : { field: "total_applications", sort: "desc" };
      const response = await apiClient.listApiKeyUserStatistics(
        {
          page: page + 1,
          page_size: pageSize,
          scope,
          q: q.trim(),
          from: fromDate || undefined,
          to: toDate || undefined,
          owner_account: getContainsFilterValue(filterModel, "owner_account") || undefined,
          owner_name: getContainsFilterValue(filterModel, "owner_name") || undefined,
          owner_email: getContainsFilterValue(filterModel, "owner_email") || undefined,
          owner_department: getContainsFilterValue(filterModel, "owner_department") || undefined,
          sort_by: sort.field,
          sort_dir: sort.sort || "desc"
        },
        auth
      );
      setItems(response.items.map((item) => ({ ...item, id: item.owner_account })));
      setTotal(response.total);
      if (response.total === 0) {
        setBanner(t("dashboard_empty_filtered"));
      } else {
        setBanner("");
      }
    } catch (e) {
      setError(normalizeApiError(e, t("dashboard_load_failed")));
      setBanner("");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [filterModel, fromDate, page, pageSize, q, scope, sortModel, toDate]);

  if (auth.role !== "admin") {
    return (
      <Stack spacing={3}>
        <Typography variant="h4">{t("dashboard_title")}</Typography>
        <ErrorBlock message={t("dashboard_forbidden")} />
      </Stack>
    );
  }

  return (
    <Stack spacing={3} sx={{ flex: 1, minHeight: 0 }}>
      <Typography variant="h4">{t("dashboard_title")}</Typography>
      {banner ? <Alert severity="info">{banner}</Alert> : null}

      <Tabs value={view} onChange={(_, value) => setView(value)} aria-label={t("dashboard_view_toggle")}>
        <Tab value="table" label={t("dashboard_tab_table")} />
        <Tab value="chart" label={t("dashboard_tab_chart")} />
      </Tabs>

      <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
        <TextField
          select
          label={t("dashboard_scope")}
          value={scope}
          onChange={(event) => {
            setScope(event.target.value);
            setPage(0);
          }}
          sx={{ minWidth: 180 }}
        >
          {scopeOptions.map((option) => (
            <MenuItem key={option} value={option}>
              {t(`dashboard_scope_${option}`)}
            </MenuItem>
          ))}
        </TextField>
        <DatePicker
          label={t("dashboard_from")}
          value={fromDate ? dayjs(fromDate) : null}
          onChange={(value) => {
            setFromDate(value && value.isValid() ? value.format("YYYY-MM-DD") : "");
            setPage(0);
          }}
          slotProps={{ textField: { sx: { minWidth: 180 } } }}
        />
        <DatePicker
          label={t("dashboard_to")}
          value={toDate ? dayjs(toDate) : null}
          onChange={(value) => {
            setToDate(value && value.isValid() ? value.format("YYYY-MM-DD") : "");
            setPage(0);
          }}
          slotProps={{ textField: { sx: { minWidth: 180 } } }}
        />
        <TextField
          label={t("common_keyword")}
          value={q}
          onChange={(event) => {
            setQ(event.target.value);
            setPage(0);
          }}
          placeholder={t("dashboard_keyword_placeholder")}
          sx={{ minWidth: 260 }}
        />
      </Stack>

      {loading ? <LoadingBlock text={t("dashboard_loading")} /> : null}
      {!loading && error ? <ErrorBlock message={error} onRetry={load} /> : null}
      {!loading && !error && items.length === 0 ? <EmptyBlock text={t("dashboard_no_data")} /> : null}

      {!loading && !error && items.length > 0 && view === "table" ? (
        <Box sx={{ width: "100%", backgroundColor: "white", borderRadius: 2, p: 1, flex: 1, minHeight: 320 }}>
          <DataGrid
            sx={{ height: "100%" }}
            rows={items}
            columns={columns}
            pageSizeOptions={[10, 20, 50]}
            paginationMode="server"
            sortingMode="server"
            filterMode="server"
            rowCount={total}
            paginationModel={{ page, pageSize }}
            onPaginationModelChange={(model) => {
              setPage(model.page);
              setPageSize(model.pageSize);
            }}
            sortModel={sortModel}
            onSortModelChange={(model) => {
              if (model.length === 0) {
                setSortModel([{ field: "total_applications", sort: "desc" }]);
                return;
              }
              setSortModel(model);
              setPage(0);
            }}
            filterModel={filterModel}
            onFilterModelChange={(model) => {
              setFilterModel(model);
              setPage(0);
            }}
            disableRowSelectionOnClick
            localeText={gridLocaleText}
          />
        </Box>
      ) : null}

      {!loading && !error && items.length > 0 && view === "chart" ? (
        <Card>
          <CardContent>
            <Stack spacing={2}>
              <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
                <TextField
                  select
                  label={t("dashboard_axis_x")}
                  value={xAxisField}
                  onChange={(event) => setXAxisField(event.target.value)}
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
                  value={yAxisField}
                  onChange={(event) => setYAxisField(event.target.value)}
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
                  value={topN}
                  onChange={(event) => setTopN(Number(event.target.value))}
                  sx={{ minWidth: 180 }}
                >
                  {topNOptions.map((option) => (
                    <MenuItem key={option} value={option}>
                      {option}
                    </MenuItem>
                  ))}
                </TextField>
              </Stack>
              <BarChart
                height={420}
                xAxis={[
                  {
                    id: "x-axis",
                    scaleType: "band",
                    position: "bottom",
                    data: chartItems.map((item) => item.label),
                    tickLabelInterval: () => true,
                    height: "auto",
                    tickLabelStyle: {
                      angle: -35,
                      textAnchor: "end",
                      fontSize: 12
                    }
                  }
                ]}
                series={[{ data: chartItems.map((item) => item.value), label: yAxisOptions.find((o) => o.value === yAxisField)?.label }]}
                margin={{ left: 60, right: 20, top: 30, bottom: 120 }}
              />
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
                      <Chip size="small" label={item.status} color={statusColor(item.status)} />
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
