import { useEffect, useMemo, useState } from "react";
import PersonAddIcon from "@mui/icons-material/PersonAdd";
import AddIcon from "@mui/icons-material/Add";
import SaveIcon from "@mui/icons-material/Save";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import StopIcon from "@mui/icons-material/Stop";
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
  IconButton,
  Stack,
  TextField,
  Tooltip,
  Typography,
  useMediaQuery
} from "@mui/material";
import { DataGrid } from "@mui/x-data-grid";
import { zhTW } from "@mui/x-data-grid/locales";
import { useTheme } from "@mui/material/styles";
import { apiClient } from "../api/client";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlocks";

const actionCellSx = {
  display: "flex",
  justifyContent: "flex-start",
  alignItems: "center",
  width: "100%",
  height: "100%",
  gap: 0.5,
  whiteSpace: "nowrap"
};

function formatDateTime(value) {
  const dt = new Date(value);
  return Number.isNaN(dt.getTime()) ? "-" : dt.toLocaleString();
}

function statusColor(status) {
  return status === "active" ? "success" : "default";
}

export default function WhitelistAdminPage({ auth }) {
  const [items, setItems] = useState([]);
  const [keyword, setKeyword] = useState("");
  const [candidates, setCandidates] = useState([]);
  const [searching, setSearching] = useState(false);
  const [searchMessage, setSearchMessage] = useState("");
  const [dialogMessage, setDialogMessage] = useState("");
  const [editingRemark, setEditingRemark] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [banner, setBanner] = useState("");
  const [pendingStatusChange, setPendingStatusChange] = useState(null);
  const [searchDialogOpen, setSearchDialogOpen] = useState(false);
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down("sm"));

  function closeSearchDialog() {
    setSearchDialogOpen(false);
    setKeyword("");
    setSearching(false);
    setCandidates([]);
    setSearchMessage("");
    setDialogMessage("");
  }

  async function load() {
    setLoading(true);
    setError("");
    try {
      const response = await apiClient.listWhitelists(auth);
      setItems(response.items);
    } catch (e) {
      setError(e?.payload?.error?.message || "載入白名單失敗");
    } finally {
      setLoading(false);
    }
  }

  async function searchCandidates() {
    setSearchMessage("");
    setSearching(true);
    try {
      const response = await apiClient.searchUsers(keyword, auth);
      setCandidates(response.items);
      if (response.items.length === 0) {
        setSearchMessage("查無符合人員。");
      }
    } catch (e) {
      setSearchMessage(e?.payload?.error?.message || "查詢人員失敗");
      setCandidates([]);
    } finally {
      setSearching(false);
    }
  }

  async function createItem(candidate) {
    setDialogMessage("");
    try {
      await apiClient.createWhitelist(
        { email: candidate.email, account: candidate.account, sysid: candidate.sysid, name: candidate.name },
        auth
      );
      setDialogMessage("白名單已新增。");
      await load();
    } catch (e) {
      setDialogMessage(e?.payload?.error?.message || "新增白名單失敗");
    }
  }

  async function updateItem(id, payload) {
    setBanner("");
    try {
      await apiClient.updateWhitelist(id, payload, auth);
      setBanner("白名單已更新。");
      await load();
    } catch (e) {
      setBanner(e?.payload?.error?.message || "更新白名單失敗");
    }
  }

  useEffect(() => {
    load();
  }, []);

  const candidateColumns = useMemo(
    () => [
      { field: "sysid", headerName: "SysID", flex: 1, minWidth: 140 },
      { field: "account", headerName: "帳號", flex: 1, minWidth: 140 },
      { field: "name", headerName: "姓名", flex: 1, minWidth: 140 },
      { field: "email", headerName: "Email", flex: 1.5, minWidth: 220 },
      {
        field: "actions",
        headerName: "操作",
        sortable: false,
        filterable: false,
        align: "left",
        headerAlign: "left",
        flex: 1,
        minWidth: 110,
        renderCell: (params) => (
          <Box sx={actionCellSx}>
            <Tooltip title="加入白名單">
              <IconButton aria-label="加入白名單" size="small" onClick={() => createItem(params.row)}>
                <PersonAddIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
        )
      }
    ],
    []
  );

  const whitelistColumns = useMemo(
    () => [
      { field: "sysid", headerName: "SysID", flex: 1, minWidth: 140 },
      { field: "account", headerName: "帳號", flex: 1, minWidth: 140 },
      { field: "name", headerName: "姓名", flex: 1, minWidth: 140 },
      { field: "email", headerName: "Email", flex: 1.5, minWidth: 220 },
      {
        field: "status",
        headerName: "狀態",
        flex: 1,
        minWidth: 120,
        renderCell: (params) => <Chip size="small" label={params.value} color={statusColor(params.value)} />
      },
      {
        field: "remark",
        headerName: "備註",
        flex: 1.5,
        minWidth: 220,
        renderCell: (params) => (
          <Box sx={{ display: "flex", alignItems: "center", height: "100%", width: "100%" }}>
            <TextField
              size="small"
              value={editingRemark[params.row.id] ?? params.row.remark}
              onChange={(e) => setEditingRemark((prev) => ({ ...prev, [params.row.id]: e.target.value }))}
            />
          </Box>
        )
      },
      {
        field: "created_at",
        headerName: "建立時間",
        flex: 1.5,
        minWidth: 180,
        valueFormatter: (value) => formatDateTime(value)
      },
      {
        field: "updated_at",
        headerName: "更新時間",
        flex: 1.5,
        minWidth: 180,
        valueFormatter: (value) => formatDateTime(value)
      },
      {
        field: "actions",
        headerName: "操作",
        sortable: false,
        filterable: false,
        align: "left",
        headerAlign: "left",
        flex: 1.2,
        minWidth: 140,
        renderCell: (params) => (
          <Box sx={actionCellSx}>
            <Tooltip title="儲存備註">
              <IconButton
                aria-label="儲存備註"
                size="small"
                color="primary"
                onClick={() =>
                  updateItem(params.row.id, {
                    status: params.row.status,
                    remark: editingRemark[params.row.id] ?? params.row.remark
                  })
                }
              >
                <SaveIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title={params.row.status === "active" ? "停用白名單" : "啟用白名單"}>
              <IconButton
                aria-label={params.row.status === "active" ? "停用白名單" : "啟用白名單"}
                size="small"
                color={params.row.status === "active" ? "warning" : "success"}
                onClick={() =>
                  setPendingStatusChange({
                    id: params.row.id,
                    nextStatus: params.row.status === "active" ? "inactive" : "active"
                  })
                }
              >
                {params.row.status === "active" ? <StopIcon fontSize="small" /> : <PlayArrowIcon fontSize="small" />}
              </IconButton>
            </Tooltip>
          </Box>
        )
      }
    ],
    [editingRemark]
  );

  if (auth.role !== "admin") {
    return (
      <Stack spacing={3}>
        <Typography variant="h4">白名單管理</Typography>
        <ErrorBlock message="僅管理者可使用白名單管理功能。" />
      </Stack>
    );
  }

  return (
    <Stack spacing={3}>
      <Typography variant="h4">白名單管理</Typography>
      {banner ? <Alert severity="info">{banner}</Alert> : null}

      <Box sx={{ display: "flex", justifyContent: "flex-end" }}>
        <Button
          variant="outlined"
          startIcon={<AddIcon />}
          aria-label="開啟新增白名單人員"
          onClick={() => setSearchDialogOpen(true)}
        >
          新增
        </Button>
      </Box>

      <Card>
        <CardContent>
          {loading ? <LoadingBlock text="載入白名單中..." /> : null}
          {!loading && error ? <ErrorBlock message={error} onRetry={load} /> : null}
          {!loading && !error && items.length === 0 ? <EmptyBlock text="目前沒有白名單資料。" /> : null}
          {!loading && !error && items.length > 0 ? (
            <Box sx={{ height: 520 }}>
              <DataGrid
                rows={items}
                columns={whitelistColumns}
                getRowId={(row) => row.id}
                pageSizeOptions={[10, 20, 50]}
                initialState={{ pagination: { paginationModel: { pageSize: 10, page: 0 } } }}
                disableRowSelectionOnClick
                rowHeight={56}
                localeText={zhTW.components.MuiDataGrid.defaultProps.localeText}
              />
            </Box>
          ) : null}
        </CardContent>
      </Card>

      <Dialog open={Boolean(pendingStatusChange)} onClose={() => setPendingStatusChange(null)}>
        <DialogTitle>確認變更狀態</DialogTitle>
        <DialogContent>
          確認將此白名單設為 {pendingStatusChange?.nextStatus === "active" ? "啟用" : "停用"}？
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPendingStatusChange(null)}>取消</Button>
          <Button
            color="warning"
            onClick={async () => {
              const target = pendingStatusChange;
              setPendingStatusChange(null);
              if (target) {
                await updateItem(target.id, { status: target.nextStatus });
              }
            }}
          >
            確認
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={searchDialogOpen} onClose={closeSearchDialog} fullWidth maxWidth="lg" fullScreen={fullScreen}>
        <DialogTitle>查詢人員</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 0.5 }}>
            <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
              <TextField
                label="查詢關鍵字"
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key !== "Enter" || e.nativeEvent.isComposing) {
                    return;
                  }
                  e.preventDefault();
                  searchCandidates();
                }}
                fullWidth
              />
              <Button variant="contained" onClick={searchCandidates} disabled={searching} sx={{ whiteSpace: "nowrap" }}>
                {searching ? "查詢中..." : "查詢人員"}
              </Button>
            </Stack>
            <Typography component="p" variant="body2" color="text.secondary">
              可用 sysid / 帳號 / 姓名 / email
            </Typography>
            {searchMessage ? <Alert severity="info">{searchMessage}</Alert> : null}
            {dialogMessage ? <Alert severity="info">{dialogMessage}</Alert> : null}
            {candidates.length > 0 ? (
              <Box sx={{ height: 420 }}>
                <DataGrid
                  rows={candidates}
                  columns={candidateColumns}
                  getRowId={(row) => row.id}
                  pageSizeOptions={[5, 10, 20]}
                  initialState={{ pagination: { paginationModel: { pageSize: 5, page: 0 } } }}
                  disableRowSelectionOnClick
                  rowHeight={56}
                  localeText={zhTW.components.MuiDataGrid.defaultProps.localeText}
                />
              </Box>
            ) : null}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={closeSearchDialog}>關閉</Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
