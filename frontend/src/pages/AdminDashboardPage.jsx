import { useEffect, useMemo, useState } from "react";
import {
  Alert,
  Box,
  MenuItem,
  Stack,
  TextField,
  Typography
} from "@mui/material";
import { DataGrid } from "@mui/x-data-grid";
import { zhTW } from "@mui/x-data-grid/locales";
import { apiClient } from "../api/client";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlocks";

const scopeOptions = ["all", "active", "revoked", "expired"];

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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [banner, setBanner] = useState("");

  const columns = useMemo(
    () => [
      { field: "owner_account", headerName: "帳號", flex: 1, minWidth: 140 },
      { field: "owner_name", headerName: "姓名", flex: 1, minWidth: 140 },
      { field: "owner_email", headerName: "Email", flex: 1.6, minWidth: 220 },
      { field: "total_applications", headerName: "總申請數", type: "number", flex: 0.8, minWidth: 120 },
      { field: "active_count", headerName: "啟用中", type: "number", flex: 0.8, minWidth: 120 },
      { field: "revoked_count", headerName: "已停用", type: "number", flex: 0.8, minWidth: 120 },
      { field: "expired_count", headerName: "已到期", type: "number", flex: 0.8, minWidth: 120 },
      { field: "last_applied_at", headerName: "最後申請日", flex: 1, minWidth: 140 }
    ],
    []
  );

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

      {!loading && !error && items.length > 0 ? (
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
    </Stack>
  );
}
