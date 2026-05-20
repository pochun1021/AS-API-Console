import { useEffect, useMemo, useState } from "react";
import VisibilityIcon from "@mui/icons-material/Visibility";
import BlockIcon from "@mui/icons-material/Block";
import EditIcon from "@mui/icons-material/Edit";
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
  TextField,
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
  gap: 1,
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

function formatMaskedKey(value) {
  if (!value) return "-";
  const text = String(value);
  const tail = text.slice(-4);
  return `AS-...${tail}`;
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
  const [pendingAliasEditItem, setPendingAliasEditItem] = useState(null);
  const [aliasInputValue, setAliasInputValue] = useState("");
  const [aliasSaving, setAliasSaving] = useState(false);
  const [detailAliasValue, setDetailAliasValue] = useState("");

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
      setDetailAliasValue(response.item?.key_alias || "");
    } catch (e) {
      setDetailItem(null);
      setDetailAliasValue("");
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
    setDetailAliasValue("");
    setDetailError("");
  }

  async function saveAlias(id, keyAlias) {
    setAliasSaving(true);
    setBanner("");
    try {
      const response = await apiClient.updateApiKey(id, { key_alias: keyAlias }, auth);
      setBanner(t("mykeys_alias_update_done"));
      setItems((prev) => prev.map((item) => (item.id === id ? { ...item, key_alias: response.item.key_alias } : item)));
      if (detailItem?.id === id) {
        setDetailItem(response.item);
        setDetailAliasValue(response.item.key_alias || "");
      }
    } catch (e) {
      setBanner(e?.payload?.error?.message || t("mykeys_alias_update_failed"));
    } finally {
      setAliasSaving(false);
    }
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
          valueFormatter: (value) => formatMaskedKey(value)
        }
      ];

      if (auth.role === "admin") {
        baseColumns.push({
          field: "key_alias",
          headerName: t("mykeys_col_key_alias"),
          flex: 1.4,
          minWidth: 180
        });
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
            {auth.role === "admin" ? (
              <Tooltip title={t("mykeys_edit_key_alias")}>
                <IconButton
                  aria-label={t("mykeys_edit_key_alias")}
                  size="small"
                  onClick={() => {
                    setPendingAliasEditItem(params.row);
                    setAliasInputValue(params.row.key_alias || "");
                  }}
                >
                  <EditIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            ) : null}
            {params.row.status === "active" ? (
              <Button
                aria-label={t("mykeys_revoke_key")}
                size="small"
                color="warning"
                variant="outlined"
                startIcon={<BlockIcon fontSize="small" />}
                onClick={() => setPendingRevokeId(params.row.id)}
              >
                {locale === "zh-TW" ? "停用" : "Revoke"}
              </Button>
            ) : null}
          </Box>
        )
      });

      return baseColumns;
    },
    [auth.role, t]
  );

  return (
    <Stack spacing={3} sx={{ flex: 1, minHeight: 0 }}>
      <Typography variant="h4">{t("mykeys_title")}</Typography>
      {banner && <Alert severity="info">{banner}</Alert>}
      <Card sx={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>
        <CardContent sx={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>
          {loading ? <LoadingBlock text={t("mykeys_loading_list")} /> : null}
          {!loading && error ? <ErrorBlock message={error} onRetry={load} /> : null}
          {!loading && !error && items.length === 0 ? <EmptyBlock text={t("mykeys_empty")} /> : null}
          {!loading && !error && items.length > 0 ? (
            <Box sx={{ flex: 1, minHeight: 320 }}>
              <DataGrid
                sx={{ height: "100%" }}
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
                {t("mykeys_detail_status")}: <Chip size="small" label={detailItem.status} color={statusColor(detailItem.status)} />
              </Box>
              {auth.role === "admin" ? (
                <Typography>
                  {t("mykeys_col_owner")}: {detailItem.owner_account || "-"} / {detailItem.owner_name || "-"}
                </Typography>
              ) : null}
              <Typography>{t("mykeys_detail_department")}: {detailItem.department || "-"}</Typography>
              <Typography>{t("mykeys_detail_application_date")}: {detailItem.application_date}</Typography>
              <Typography>{t("mykeys_detail_duration")}: {detailItem.duration_months} {t("mykeys_duration_suffix")}</Typography>
              <Typography>
                {t("mykeys_detail_masked_key")}: {formatMaskedKey(detailItem.masked_key)}
              </Typography>
              <Typography>{t("mykeys_detail_created_at")}: {formatDateTime(detailItem.created_at)}</Typography>
              <Typography>{t("mykeys_detail_expires_at")}: {formatDateTime(detailItem.expires_at)}</Typography>
              <Typography>{t("mykeys_detail_purpose")}: {detailItem.purpose || "-"}</Typography>
              {auth.role === "admin" ? (
                <TextField
                  label={t("mykeys_col_key_alias")}
                  size="small"
                  value={detailAliasValue}
                  onChange={(e) => setDetailAliasValue(e.target.value)}
                />
              ) : null}
            </Stack>
          ) : null}
        </DialogContent>
        <DialogActions>
          <Button onClick={closeDetail}>{locale === "zh-TW" ? "關閉" : "Close"}</Button>
          {auth.role === "admin" && detailItem ? (
            <Button
              variant="outlined"
              disabled={aliasSaving}
              onClick={() => saveAlias(detailItem.id, detailAliasValue)}
            >
              {t("mykeys_save_key_alias")}
            </Button>
          ) : null}
          {detailItem?.status === "active" ? (
            <Button color="warning" variant="contained" onClick={() => setPendingRevokeId(detailItem.id)}>
              停用金鑰
            </Button>
          ) : null}
        </DialogActions>
      </Dialog>

      <Dialog open={Boolean(pendingAliasEditItem)} onClose={() => setPendingAliasEditItem(null)} fullWidth maxWidth="xs">
        <DialogTitle>{t("mykeys_dialog_alias_title")}</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            fullWidth
            label={t("mykeys_col_key_alias")}
            value={aliasInputValue}
            onChange={(e) => setAliasInputValue(e.target.value)}
            sx={{ mt: 1 }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPendingAliasEditItem(null)}>{locale === "zh-TW" ? "取消" : "Cancel"}</Button>
          <Button
            disabled={aliasSaving}
            onClick={async () => {
              const target = pendingAliasEditItem;
              if (!target) return;
              await saveAlias(target.id, aliasInputValue);
              setPendingAliasEditItem(null);
            }}
          >
            {locale === "zh-TW" ? "儲存" : "Save"}
          </Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
