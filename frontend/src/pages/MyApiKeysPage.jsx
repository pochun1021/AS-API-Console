import { useEffect, useMemo, useState } from "react";
import VisibilityIcon from "@mui/icons-material/Visibility";
import BlockIcon from "@mui/icons-material/Block";
import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  Stack,
  Tooltip,
  Typography,
  Button
} from "@mui/material";
import { DataGrid } from "@mui/x-data-grid";
import { zhTW } from "@mui/x-data-grid/locales";
import { Link as RouterLink } from "react-router-dom";
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

function statusColor(status) {
  if (status === "active") return "success";
  if (status === "revoked") return "warning";
  return "default";
}

function formatDateTime(value) {
  const dt = new Date(value);
  return Number.isNaN(dt.getTime()) ? "-" : dt.toLocaleString();
}

export default function MyApiKeysPage({ auth }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [banner, setBanner] = useState("");
  const [pendingRevokeId, setPendingRevokeId] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const response = await apiClient.listApiKeys(auth);
      setItems(response.items);
    } catch (e) {
      setError(e?.payload?.error?.message || "載入 API Key 清單失敗");
    } finally {
      setLoading(false);
    }
  }

  async function revoke(id) {
    setBanner("");
    try {
      await apiClient.revokeApiKey(id, auth);
      setBanner("金鑰已停用。");
      await load();
    } catch (e) {
      setBanner(e?.payload?.error?.message || "停用金鑰失敗");
    }
  }

  useEffect(() => {
    load();
  }, []);

  const columns = useMemo(
    () => {
      const baseColumns = [
        { field: "application_date", headerName: "申請日期", flex: 1, minWidth: 120 },
        {
          field: "duration_months",
          headerName: "生效時長",
          flex: 1,
          minWidth: 120,
          valueFormatter: (value) => `${value} 個月`
        },
        {
          field: "status",
          headerName: "狀態",
          flex: 1,
          minWidth: 120,
          renderCell: (params) => <Chip size="small" label={params.value} color={statusColor(params.value)} />
        },
        {
          field: "expires_at",
          headerName: "到期時間",
          flex: 1.5,
          minWidth: 180,
          valueFormatter: (value) => formatDateTime(value)
        },
        {
          field: "masked_key",
          headerName: "遮罩金鑰 / 前綴",
          flex: 1.5,
          minWidth: 180,
          valueGetter: (_value, row) => `${row.masked_key} (${row.key_prefix})`
        }
      ];

      if (auth.role === "admin") {
        baseColumns.push({
          field: "owner",
          headerName: "申請人",
          flex: 1.5,
          minWidth: 180,
          valueGetter: (_value, row) => `${row.owner_account || "-"} / ${row.owner_name || "-"}`
        });
      }

      baseColumns.push({
        field: "actions",
        headerName: "操作",
        sortable: false,
        filterable: false,
        align: "left",
        headerAlign: "left",
        flex: 1,
        minWidth: 130,
        renderCell: (params) => (
          <Box sx={actionCellSx}>
            <Tooltip title="查看詳情">
              <IconButton
                aria-label="查看詳情"
                size="small"
                component={RouterLink}
                to={`/api-keys/${params.row.id}`}
              >
                <VisibilityIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            {params.row.status === "active" ? (
              <Tooltip title="停用金鑰">
                <IconButton
                  aria-label="停用金鑰"
                  size="small"
                  color="warning"
                  onClick={() => setPendingRevokeId(params.row.id)}
                >
                  <BlockIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            ) : null}
          </Box>
        )
      });

      return baseColumns;
    },
    [auth.role]
  );

  return (
    <Stack spacing={3}>
      <Typography variant="h4">API Keys</Typography>
      {banner && <Alert severity="info">{banner}</Alert>}
      <Card>
        <CardContent>
          {loading ? <LoadingBlock text="載入你的金鑰歷史紀錄中..." /> : null}
          {!loading && error ? <ErrorBlock message={error} onRetry={load} /> : null}
          {!loading && !error && items.length === 0 ? <EmptyBlock text="目前尚無 API Key 紀錄。" /> : null}
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

      <Dialog open={Boolean(pendingRevokeId)} onClose={() => setPendingRevokeId("")}>
        <DialogTitle>確認停用</DialogTitle>
        <DialogContent>確認停用此金鑰？</DialogContent>
        <DialogActions>
          <Button onClick={() => setPendingRevokeId("")}>取消</Button>
          <Button
            color="warning"
            onClick={async () => {
              const targetId = pendingRevokeId;
              setPendingRevokeId("");
              await revoke(targetId);
            }}
          >
            確認
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
