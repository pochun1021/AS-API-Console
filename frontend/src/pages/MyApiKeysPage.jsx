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
import { apiClient } from "../api/client";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlocks";
import { useLocale } from "../i18n/locale";

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
  const { gridLocaleText, locale, t } = useLocale();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [banner, setBanner] = useState("");
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailId, setDetailId] = useState("");
  const [detailItem, setDetailItem] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [pendingRevokeId, setPendingRevokeId] = useState("");

  async function load() {
    setLoading(true);
    setError("");
    try {
      const response = await apiClient.listApiKeys(auth);
      setItems(response.items);
    } catch (e) {
      setError(e?.payload?.error?.message || t("mykeys_load_failed"));
    } finally {
      setLoading(false);
    }
  }

  async function revoke(id) {
    setBanner("");
    try {
      await apiClient.revokeApiKey(id, auth);
      setBanner(t("mykeys_revoke_done"));
      await load();
      if (detailOpen && detailId === id) {
        closeDetail();
      }
    } catch (e) {
      setBanner(e?.payload?.error?.message || t("mykeys_revoke_failed"));
    }
  }

  async function loadDetail(id) {
    setDetailLoading(true);
    setDetailError("");
    try {
      const response = await apiClient.getApiKeyById(id, auth);
      setDetailItem(response.item);
    } catch (e) {
      setDetailItem(null);
      setDetailError(e?.payload?.error?.message || t("mykeys_detail_failed"));
    } finally {
      setDetailLoading(false);
    }
  }

  async function openDetail(id) {
    setDetailId(id);
    setDetailOpen(true);
    await loadDetail(id);
  }

  function closeDetail() {
    setDetailOpen(false);
    setDetailId("");
    setDetailItem(null);
    setDetailError("");
  }

  useEffect(() => {
    load();
  }, []);

  const columns = useMemo(
    () => {
      const baseColumns = [
        { field: "application_date", headerName: t("mykeys_col_application_date"), flex: 1, minWidth: 120 },
        {
          field: "duration_months",
          headerName: t("mykeys_col_duration_months"),
          flex: 1,
          minWidth: 120,
          valueFormatter: (value) => `${value} ${t("mykeys_duration_suffix")}`
        },
        {
          field: "status",
          headerName: t("common_status"),
          flex: 1,
          minWidth: 120,
          renderCell: (params) => <Chip size="small" label={params.value} color={statusColor(params.value)} />
        },
        {
          field: "expires_at",
          headerName: t("mykeys_col_expires_at"),
          flex: 1.5,
          minWidth: 180,
          valueFormatter: (value) => formatDateTime(value)
        },
        {
          field: "masked_key",
          headerName: t("mykeys_col_masked_key"),
          flex: 1.5,
          minWidth: 180,
          valueGetter: (_value, row) => `${row.masked_key} (${row.key_prefix})`
        }
      ];

      if (auth.role === "admin") {
        baseColumns.push({
          field: "owner",
          headerName: t("mykeys_col_owner"),
          flex: 1.5,
          minWidth: 180,
          valueGetter: (_value, row) => `${row.owner_account || "-"} / ${row.owner_name || "-"}`
        });
      }

      baseColumns.push({
        field: "actions",
        headerName: t("common_actions"),
        sortable: false,
        filterable: false,
        align: "left",
        headerAlign: "left",
        flex: 1,
        minWidth: 130,
        renderCell: (params) => (
          <Box sx={actionCellSx}>
            <Tooltip title={t("mykeys_view_detail")}>
              <IconButton aria-label={t("mykeys_view_detail")} size="small" onClick={() => openDetail(params.row.id)}>
                <VisibilityIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            {params.row.status === "active" ? (
              <Tooltip title={t("mykeys_revoke_key")}>
                <IconButton
                  aria-label={t("mykeys_revoke_key")}
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
    [auth.role, t]
  );

  return (
    <Stack spacing={3}>
      <Typography variant="h4">{t("mykeys_title")}</Typography>
      {banner && <Alert severity="info">{banner}</Alert>}
      <Card>
        <CardContent>
          {loading ? <LoadingBlock text={t("mykeys_loading_list")} /> : null}
          {!loading && error ? <ErrorBlock message={error} onRetry={load} /> : null}
          {!loading && !error && items.length === 0 ? <EmptyBlock text={t("mykeys_empty")} /> : null}
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
                localeText={gridLocaleText}
              />
            </Box>
          ) : null}
        </CardContent>
      </Card>

      <Dialog open={Boolean(pendingRevokeId)} onClose={() => setPendingRevokeId("")}>
        <DialogTitle>{t("mykeys_dialog_revoke_title")}</DialogTitle>
        <DialogContent>{t("mykeys_dialog_revoke_body")}</DialogContent>
        <DialogActions>
          <Button onClick={() => setPendingRevokeId("")}>{locale === "zh-TW" ? "取消" : "Cancel"}</Button>
          <Button
            color="warning"
            onClick={async () => {
              const targetId = pendingRevokeId;
              setPendingRevokeId("");
              await revoke(targetId);
            }}
          >
            {locale === "zh-TW" ? "確認" : "Confirm"}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={detailOpen} onClose={closeDetail} fullWidth maxWidth="sm">
        <DialogTitle>{t("mykeys_dialog_detail_title")}</DialogTitle>
        <DialogContent>
          {detailLoading ? <LoadingBlock text={t("mykeys_loading_detail")} /> : null}
          {!detailLoading && detailError ? <ErrorBlock message={detailError} onRetry={() => loadDetail(detailId)} /> : null}
          {!detailLoading && !detailError && detailItem ? (
            <Stack spacing={2} sx={{ mt: 0.5 }}>
              <Typography>ID: {detailItem.id}</Typography>
              <Box>
                狀態: <Chip size="small" label={detailItem.status} color={statusColor(detailItem.status)} />
              </Box>
              {auth.role === "admin" ? (
                <Typography>
                  申請人: {detailItem.owner_account || "-"} / {detailItem.owner_name || "-"}
                </Typography>
              ) : null}
              <Typography>單位: {detailItem.department || "-"}</Typography>
              <Typography>申請日期: {detailItem.application_date}</Typography>
              <Typography>生效時長: {detailItem.duration_months} 個月</Typography>
              <Typography>
                遮罩金鑰 / 前綴: {detailItem.masked_key} ({detailItem.key_prefix})
              </Typography>
              <Typography>建立時間: {formatDateTime(detailItem.created_at)}</Typography>
              <Typography>到期時間: {formatDateTime(detailItem.expires_at)}</Typography>
              <Typography>用途: {detailItem.purpose || "-"}</Typography>
            </Stack>
          ) : null}
        </DialogContent>
        <DialogActions>
          <Button onClick={closeDetail}>{locale === "zh-TW" ? "關閉" : "Close"}</Button>
          {detailItem?.status === "active" ? (
            <Button color="warning" variant="contained" onClick={() => setPendingRevokeId(detailItem.id)}>
              停用金鑰
            </Button>
          ) : null}
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
