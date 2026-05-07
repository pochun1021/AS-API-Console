import { useEffect, useMemo, useState } from "react";
import AddIcon from "@mui/icons-material/Add";
import DoNotDisturbIcon from "@mui/icons-material/DoNotDisturb";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Stack,
  TextField,
  Tooltip,
  Typography,
  Chip,
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

export default function AdminPage({ auth }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [banner, setBanner] = useState("");
  const [pendingRevokeUser, setPendingRevokeUser] = useState(null);
  const [searchDialogOpen, setSearchDialogOpen] = useState(false);
  const [searchKeyword, setSearchKeyword] = useState("");
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState([]);
  const [searchMessage, setSearchMessage] = useState("");
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down("sm"));

  function closeSearchDialog() {
    setSearchDialogOpen(false);
    setSearchKeyword("");
    setSearching(false);
    setSearchResults([]);
    setSearchMessage("");
  }

  async function load() {
    setLoading(true);
    setError("");
    try {
      const response = await apiClient.listUsers(auth);
      setItems(response.items);
    } catch (e) {
      setError(e?.payload?.error?.message || "載入管理者名單失敗");
    } finally {
      setLoading(false);
    }
  }

  async function search() {
    setSearchMessage("");
    setSearching(true);
    try {
      if (!searchKeyword.trim()) {
        setSearchResults([]);
        setSearchMessage("請輸入查詢關鍵字。");
        return;
      }
      const response = await apiClient.searchUsers(searchKeyword, auth);
      setSearchResults(response.items);
      if (response.items.length === 0) {
        setSearchMessage("查無符合人員。");
      }
    } catch (e) {
      setSearchMessage(e?.payload?.error?.message || "查詢人員失敗");
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  }

  async function grant(userId, userName = "") {
    setBanner("");
    try {
      await apiClient.enableAdmin(userId, auth);
      setBanner(`${userName || "此使用者"} 已加入管理者權限。`);
      await load();
    } catch (e) {
      setBanner(e?.payload?.error?.message || "啟用失敗");
    }
  }

  async function revoke(userId) {
    setBanner("");
    try {
      await apiClient.disableAdmin(userId, auth);
      setBanner("已停用管理者權限。");
      await load();
    } catch (e) {
      setBanner(e?.payload?.error?.message || "停用失敗");
    }
  }

  useEffect(() => {
    load();
  }, []);

  const currentUserBySysid = useMemo(
    () => items.find((item) => item.sysid === auth.sysid),
    [items, auth.sysid]
  );
  const adminItems = items;
  const adminStatusById = useMemo(() => new Map(items.map((item) => [item.id, item.status])), [items]);

  const adminColumns = useMemo(
    () => [
      { field: "sysid", headerName: "SysID", flex: 1, minWidth: 140 },
      { field: "account", headerName: "帳號", flex: 1, minWidth: 140 },
      { field: "name", headerName: "姓名", flex: 1, minWidth: 140 },
      { field: "email", headerName: "Email", flex: 1.5, minWidth: 220 },
      {
        field: "status",
        headerName: "狀態",
        flex: 0.8,
        minWidth: 120,
        renderCell: (params) => (
          <Chip
            size="small"
            color={params.value === "active" ? "success" : "default"}
            label={params.value === "active" ? "啟用中" : "已停用"}
          />
        )
      },
      {
        field: "actions",
        headerName: "操作",
        sortable: false,
        filterable: false,
        align: "left",
        headerAlign: "left",
        flex: 1,
        minWidth: 110,
        renderCell: (params) => {
          const isSelf = params.row.sysid === auth.sysid || currentUserBySysid?.id === params.row.id;
          const isInactive = params.row.status === "inactive";
          return (
            <Box sx={actionCellSx}>
              {isInactive ? (
                <Tooltip title="啟用管理者">
                  <IconButton
                    aria-label="啟用管理者"
                    size="small"
                    onClick={async () => {
                      await grant(params.row.id, params.row.name);
                    }}
                  >
                    <AddIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              ) : (
                <Tooltip title="停用管理者">
                  <span>
                    <IconButton
                      aria-label="停用管理者"
                      size="small"
                      color="warning"
                    onClick={() => setPendingRevokeUser({ id: params.row.id, name: params.row.name })}
                    disabled={isSelf}
                  >
                    <DoNotDisturbIcon fontSize="small" />
                  </IconButton>
                </span>
              </Tooltip>
              )}
            </Box>
          );
        }
      }
    ],
    [auth.sysid, currentUserBySysid]
  );

  const searchColumns = useMemo(
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
        renderCell: (params) =>
          adminStatusById.get(params.row.id) === "active" ? (
            <Box sx={{ display: "flex", alignItems: "center", height: "100%" }}>
              <Typography variant="body2" color="text.secondary">
                已啟用
              </Typography>
            </Box>
          ) : (
            <Tooltip title="加入管理者">
              <IconButton
                aria-label="加入管理者"
                size="small"
                onClick={async () => {
                  await grant(params.row.id, params.row.name);
                }}
              >
                <AddIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )
      }
    ],
    [adminStatusById]
  );

  if (auth.role !== "admin") {
    return (
      <Stack spacing={3}>
        <Typography variant="h4">管理者名單</Typography>
        <ErrorBlock message="僅管理者可使用管理者名單功能。" />
      </Stack>
    );
  }

  return (
    <Stack spacing={3}>
      <Typography variant="h4">管理者名單</Typography>
      {banner ? <Alert severity="info">{banner}</Alert> : null}

      <Box sx={{ display: "flex", justifyContent: "flex-end" }}>
        <Button
          variant="outlined"
          startIcon={<AddIcon />}
          aria-label="開啟新增管理者查詢"
          sx={{ backgroundColor: "transparent" }}
          onClick={() => setSearchDialogOpen(true)}
        >
          新增
        </Button>
      </Box>

      <Card>
        <CardContent>
          {loading ? <LoadingBlock text="載入管理者名單中..." /> : null}
          {!loading && error ? <ErrorBlock message={error} onRetry={load} /> : null}
          {!loading && !error && adminItems.length === 0 ? <EmptyBlock text="目前沒有管理者名單資料。" /> : null}
          {!loading && !error && adminItems.length > 0 ? (
            <Box sx={{ height: 480 }}>
              <DataGrid
                rows={adminItems}
                columns={adminColumns}
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

      <Dialog open={Boolean(pendingRevokeUser)} onClose={() => setPendingRevokeUser(null)}>
        <DialogTitle>確認停用管理者</DialogTitle>
        <DialogContent>
          確認停用 {pendingRevokeUser?.name || "此使用者"} 的管理者權限？
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPendingRevokeUser(null)}>取消</Button>
          <Button
            color="warning"
            onClick={async () => {
              const target = pendingRevokeUser;
              setPendingRevokeUser(null);
              if (target) {
                await revoke(target.id);
              }
            }}
          >
            確認停用
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={searchDialogOpen} onClose={closeSearchDialog} fullWidth maxWidth="lg" fullScreen={fullScreen}>
        <DialogTitle>查詢使用者</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 0.5 }}>
            <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
              <TextField
                label="查詢關鍵字"
                value={searchKeyword}
                onChange={(e) => setSearchKeyword(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key !== "Enter" || e.nativeEvent.isComposing) {
                    return;
                  }
                  e.preventDefault();
                  search();
                }}
                fullWidth
              />
              <Button variant="contained" onClick={search} disabled={searching} sx={{ whiteSpace: "nowrap" }}>
                {searching ? "查詢中..." : "查詢使用者"}
              </Button>
            </Stack>
            <Typography component="p" variant="body2" color="text.secondary">
              可用 sysid / 帳號 / 姓名 / email
            </Typography>
            {searchMessage ? <Alert severity="info">{searchMessage}</Alert> : null}
            {searchResults.length > 0 ? (
              <Box sx={{ height: 420 }}>
                <DataGrid
                  rows={searchResults}
                  columns={searchColumns}
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
