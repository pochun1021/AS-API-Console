import { useEffect, useMemo, useState } from "react";
import AddModeratorIcon from "@mui/icons-material/AddModerator";
import RemoveModeratorIcon from "@mui/icons-material/RemoveModerator";
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
  Typography
} from "@mui/material";
import { DataGrid } from "@mui/x-data-grid";
import { zhTW } from "@mui/x-data-grid/locales";
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

function roleColor(role) {
  return role === "admin" ? "warning" : "default";
}

export default function UsersAdminPage({ auth }) {
  const [items, setItems] = useState([]);
  const [keyword, setKeyword] = useState("");
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState("");
  const [banner, setBanner] = useState("");
  const [pendingRevokeUser, setPendingRevokeUser] = useState(null);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const response = await apiClient.listUsers(auth);
      setItems(response.items);
    } catch (e) {
      setError(e?.payload?.error?.message || "載入使用者失敗");
    } finally {
      setLoading(false);
    }
  }

  async function search() {
    setBanner("");
    setSearching(true);
    try {
      if (!keyword.trim()) {
        await load();
        return;
      }
      const response = await apiClient.searchUsers(keyword, auth);
      setItems(response.items);
      if (response.items.length === 0) {
        setBanner("查無符合人員。");
      }
    } catch (e) {
      setBanner(e?.payload?.error?.message || "查詢使用者失敗");
    } finally {
      setSearching(false);
    }
  }

  async function grant(userId) {
    setBanner("");
    try {
      await apiClient.grantAdmin(userId, auth);
      setBanner("已授權為管理者。");
      await load();
    } catch (e) {
      setBanner(e?.payload?.error?.message || "授權失敗");
    }
  }

  async function revoke(userId) {
    setBanner("");
    try {
      await apiClient.revokeAdmin(userId, auth);
      setBanner("已取消管理者權限。");
      await load();
    } catch (e) {
      setBanner(e?.payload?.error?.message || "取消授權失敗");
    }
  }

  useEffect(() => {
    load();
  }, []);

  const currentUserBySysid = useMemo(
    () => items.find((item) => item.sysid === auth.sysid),
    [items, auth.sysid]
  );

  const columns = useMemo(
    () => [
      { field: "sysid", headerName: "SysID", flex: 1, minWidth: 140 },
      { field: "account", headerName: "帳號", flex: 1, minWidth: 140 },
      { field: "name", headerName: "姓名", flex: 1, minWidth: 140 },
      { field: "email", headerName: "Email", flex: 1.5, minWidth: 220 },
      {
        field: "role",
        headerName: "角色",
        flex: 1,
        minWidth: 120,
        renderCell: (params) => <Chip size="small" label={params.value} color={roleColor(params.value)} />
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
          return (
            <Box sx={actionCellSx}>
              {params.row.role === "user" ? (
                <Tooltip title="授權管理者">
                  <IconButton aria-label="授權管理者" size="small" onClick={() => grant(params.row.id)}>
                    <AddModeratorIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              ) : (
                <Tooltip title="取消管理者">
                  <span>
                    <IconButton
                      aria-label="取消管理者"
                      size="small"
                      color="warning"
                      onClick={() => setPendingRevokeUser({ id: params.row.id, name: params.row.name })}
                      disabled={isSelf}
                    >
                      <RemoveModeratorIcon fontSize="small" />
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

  if (auth.role !== "admin") {
    return (
      <Stack spacing={3}>
        <Typography variant="h4">使用者管理</Typography>
        <ErrorBlock message="僅管理者可使用使用者管理功能。" />
      </Stack>
    );
  }

  return (
    <Stack spacing={3}>
      <Typography variant="h4">使用者管理</Typography>
      {banner ? <Alert severity="info">{banner}</Alert> : null}

      <Card>
        <CardContent>
          <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
            <TextField
              label="查詢關鍵字（sysid / 帳號 / 姓名 / email）"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              fullWidth
            />
            <Button variant="contained" onClick={search} disabled={searching} sx={{ whiteSpace: "nowrap" }}>
              {searching ? "查詢中..." : "查詢使用者"}
            </Button>
          </Stack>
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          {loading ? <LoadingBlock text="載入使用者中..." /> : null}
          {!loading && error ? <ErrorBlock message={error} onRetry={load} /> : null}
          {!loading && !error && items.length === 0 ? <EmptyBlock text="目前沒有使用者資料。" /> : null}
          {!loading && !error && items.length > 0 ? (
            <Box sx={{ height: 480 }}>
              <DataGrid
                rows={items}
                columns={columns}
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
        <DialogTitle>確認取消管理者</DialogTitle>
        <DialogContent>
          確認取消 {pendingRevokeUser?.name || "此使用者"} 的管理者權限？
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
            確認
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
