import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  Card,
  CardContent,
  MenuItem,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography
} from "@mui/material";
import { BarChart } from "@mui/x-charts/BarChart";
import { DataGrid } from "@mui/x-data-grid";
import { zhTW } from "@mui/x-data-grid/locales";
import { apiClient } from "../api/client";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlocks";

const scopeOptions = ["all", "active", "revoked", "expired"];
const topNOptions = [5, 10, 20];
const xAxisOptions = [
  { value: "account", label: "帳號" },
  { value: "department", label: "單位" }
];
const yAxisOptions = [
  { value: "total_applications", label: "總申請數" },
  { value: "active_count", label: "啟用中" },
  { value: "revoked_count", label: "已停用" },
  { value: "expired_count", label: "已到期" }
];

export default function AdminDashboardPage({ auth }) {
  const [items, setItems] = useState([]);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);
  const [scope, setScope] = useState("all");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [q, setQ] = useState("");
  const [sortModel, setSortModel] = useState([{ field: "total_applications", sort: "desc" }]);
  const [view, setView] = useState("table");
  const [topN, setTopN] = useState(10);
  const [xAxisField, setXAxisField] = useState("account");
  const [yAxisField, setYAxisField] = useState("total_applications");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [banner, setBanner] = useState("");

  const columns = useMemo(
    () => [
      { field: "owner_account", headerName: "帳號", flex: 1, minWidth: 140 },
      { field: "owner_name", headerName: "姓名", flex: 1, minWidth: 140 },
      { field: "owner_email", headerName: "Email", flex: 1.6, minWidth: 220 },
      { field: "owner_department", headerName: "單位", flex: 1, minWidth: 140 },
      { field: "total_applications", headerName: "總申請數", type: "number", flex: 0.8, minWidth: 120 },
      { field: "active_count", headerName: "啟用中", type: "number", flex: 0.8, minWidth: 120 },
      { field: "revoked_count", headerName: "已停用", type: "number", flex: 0.8, minWidth: 120 },
      { field: "expired_count", headerName: "已到期", type: "number", flex: 0.8, minWidth: 120 },
      { field: "last_applied_at", headerName: "最後申請日", flex: 1, minWidth: 140 }
    ],
    []
  );

  const chartItems = useMemo(() => {
    const sorted = [...items].sort((a, b) => {
      const av = Number(a[yAxisField] || 0);
      const bv = Number(b[yAxisField] || 0);
      if (av === bv) return a.owner_account.localeCompare(b.owner_account);
      return bv - av;
    });
    return sorted.slice(0, topN).map((item) => ({
      label: xAxisField === "department" ? item.owner_department || "-" : item.owner_account,
      value: Number(item[yAxisField] || 0)
    }));
  }, [items, topN, xAxisField, yAxisField]);

  async function load() {
    if (auth.role !== "admin") return;
    setLoading(true);
    setError("");
    try {
      const sort = sortModel[0] || { field: "total_applications", sort: "desc" };
      const response = await apiClient.listApiKeyUserStatistics(
        {
          page: page + 1,
          page_size: pageSize,
          scope,
          q: q.trim(),
          from: fromDate || undefined,
          to: toDate || undefined,
          sort_by: sort.field,
          sort_dir: sort.sort || "desc"
        },
        auth
      );
      setItems(response.items.map((item) => ({ ...item, id: item.owner_account })));
      setTotal(response.total);
      if (response.total === 0) {
        setBanner("查無符合條件的統計資料。");
      } else {
        setBanner("");
      }
    } catch (e) {
      setError(e?.payload?.error?.message || "載入統計資料失敗");
      setBanner("");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [page, pageSize, scope, fromDate, toDate, q, sortModel]);

  if (auth.role !== "admin") {
    return (
      <Stack spacing={3}>
        <Typography variant="h4">管理者統計</Typography>
        <ErrorBlock message="僅管理者可使用管理者統計功能。" />
      </Stack>
    );
  }

  return (
    <Stack spacing={3}>
      <Typography variant="h4">管理者統計</Typography>
      {banner ? <Alert severity="info">{banner}</Alert> : null}

      <Tabs value={view} onChange={(_, value) => setView(value)} aria-label="統計視圖切換">
        <Tab value="table" label="表格" />
        <Tab value="chart" label="圖表" />
      </Tabs>

      <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
        <TextField
          select
          label="口徑"
          value={scope}
          onChange={(event) => {
            setScope(event.target.value);
            setPage(0);
          }}
          sx={{ minWidth: 180 }}
        >
          {scopeOptions.map((option) => (
            <MenuItem key={option} value={option}>
              {option}
            </MenuItem>
          ))}
        </TextField>
        <TextField
          type="date"
          label="From"
          InputLabelProps={{ shrink: true }}
          value={fromDate}
          onChange={(event) => {
            setFromDate(event.target.value);
            setPage(0);
          }}
        />
        <TextField
          type="date"
          label="To"
          InputLabelProps={{ shrink: true }}
          value={toDate}
          onChange={(event) => {
            setToDate(event.target.value);
            setPage(0);
          }}
        />
        <TextField
          label="關鍵字"
          value={q}
          onChange={(event) => {
            setQ(event.target.value);
            setPage(0);
          }}
          placeholder="account / name / email"
          sx={{ minWidth: 260 }}
        />
      </Stack>

      {loading ? <LoadingBlock message="統計資料載入中..." /> : null}
      {!loading && error ? <ErrorBlock message={error} onRetry={load} /> : null}
      {!loading && !error && items.length === 0 ? <EmptyBlock message="目前沒有統計資料" /> : null}

      {!loading && !error && items.length > 0 && view === "table" ? (
        <Box sx={{ width: "100%", backgroundColor: "white", borderRadius: 2, p: 1 }}>
          <DataGrid
            autoHeight
            rows={items}
            columns={columns}
            pageSizeOptions={[10, 20, 50]}
            paginationMode="server"
            sortingMode="server"
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
            }}
            disableRowSelectionOnClick
            localeText={zhTW.components.MuiDataGrid.defaultProps.localeText}
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
                  label="X 軸"
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
                  label="Y 軸"
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
                  label="Top N"
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
    </Stack>
  );
}
