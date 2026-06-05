import { useEffect, useMemo, useRef, useState } from "react";
import VisibilityIcon from "@mui/icons-material/Visibility";
import BlockIcon from "@mui/icons-material/Block";
import EditIcon from "@mui/icons-material/Edit";
import AutorenewIcon from "@mui/icons-material/Autorenew";
import MoreVertIcon from "@mui/icons-material/MoreVert";
import CheckIcon from "@mui/icons-material/Check";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
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
  Button,
  Menu,
  MenuItem
} from "@mui/material";
import { DataGrid, getGridDateOperators, getGridSingleSelectOperators, getGridStringOperators } from "@mui/x-data-grid";
import { apiClient } from "../api/client";
import { normalizeApiError } from "../api/errors";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlocks";
import { useLocale } from "../i18n/locale";
import { formatDateTimeInTaipei, isWithinThirtyDaysBeforeExpiration } from "../utils/datetime";
import { useDepartmentDisplay } from "../utils/departmentDisplay";
import { validatePersistedText } from "../utils/inputValidation";
import {
  getContainsFilterValue,
  getDateRangeFilterValues,
  getServerSort,
  getSingleSelectFilterValue,
  getTaipeiDateTimeRangeFilterValues,
} from "../utils/serverDataGrid";

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

function formatMaskedKey(value) {
  if (!value) return "-";
  return String(value);
}

async function copyText(text) {
  if (!window.isSecureContext) return { ok: false, reason: "insecure_context" };
  if (!navigator?.clipboard?.writeText) return { ok: false, reason: "clipboard_unavailable" };
  try {
    await navigator.clipboard.writeText(text);
    return { ok: true };
  } catch (error) {
    if (error?.name === "NotAllowedError") return { ok: false, reason: "permission_denied" };
    return { ok: false, reason: "unknown" };
  }
}

function handlePersistentDialogClose(reason, closeDialog) {
  if (reason === "backdropClick" || reason === "escapeKeyDown") {
    return;
  }
  closeDialog();
}

function canShowExtendAction(item) {
  if (!item || !["active", "expired"].includes(item.status)) return false;
  if (item.status === "expired") return true;
  return isWithinThirtyDaysBeforeExpiration(item.expires_at) && item.extend_eligible === true;
}

const containsFilterOperators = getGridStringOperators().filter((operator) => operator.value === "contains");
const singleSelectFilterOperators = getGridSingleSelectOperators().filter((operator) => operator.value === "is");
const dateFilterOperators = getGridDateOperators().filter((operator) =>
  ["is", "onOrAfter", "onOrBefore"].includes(operator.value)
);

export default function MyApiKeysPage({ auth }) {
  const { gridLocaleText, locale, t } = useLocale();
  const { formatDepartment } = useDepartmentDisplay(auth);
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(10);
  const [sortModel, setSortModel] = useState([]);
  const [filterModel, setFilterModel] = useState({ items: [] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [banner, setBanner] = useState("");
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailId, setDetailId] = useState("");
  const [detailItem, setDetailItem] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState("");
  const [pendingRevokeId, setPendingRevokeId] = useState("");
  const [pendingRenewId, setPendingRenewId] = useState("");
  const [pendingExtendId, setPendingExtendId] = useState("");
  const [extendDurationMonths, setExtendDurationMonths] = useState(6);
  const [pendingAliasEditItem, setPendingAliasEditItem] = useState(null);
  const [aliasInputValue, setAliasInputValue] = useState("");
  const [aliasSaving, setAliasSaving] = useState(false);
  const [detailAliasValue, setDetailAliasValue] = useState("");
  const [renewIssued, setRenewIssued] = useState(null);
  const [renewCopySucceeded, setRenewCopySucceeded] = useState(false);
  const [renewCopyError, setRenewCopyError] = useState("");
  const [actionMenuAnchorEl, setActionMenuAnchorEl] = useState(null);
  const [actionMenuRow, setActionMenuRow] = useState(null);
  const renewCopyResetTimerRef = useRef(null);

  function openActionMenu(event, row) {
    setActionMenuAnchorEl(event.currentTarget);
    setActionMenuRow(row);
  }

  function closeActionMenu() {
    setActionMenuAnchorEl(null);
    setActionMenuRow(null);
  }

  async function load() {
    setLoading(true);
    setError("");
    try {
      const sort = getServerSort(sortModel, { field: "created_at", sort: "desc" });
      const applicationDateRange = getDateRangeFilterValues(filterModel, "application_date");
      const expiresAtRange = getTaipeiDateTimeRangeFilterValues(filterModel, "expires_at");
      const response = await apiClient.listApiKeys(
        {
          page: page + 1,
          page_size: pageSize,
          status: getSingleSelectFilterValue(filterModel, "status") || undefined,
          owner_account: auth.role === "admin" ? getContainsFilterValue(filterModel, "owner_account") || undefined : undefined,
          owner_name: auth.role === "admin" ? getContainsFilterValue(filterModel, "owner_name") || undefined : undefined,
          key_alias: auth.role === "admin" ? getContainsFilterValue(filterModel, "key_alias") || undefined : undefined,
          application_date_from: applicationDateRange.from || undefined,
          application_date_to: applicationDateRange.to || undefined,
          expires_from: expiresAtRange.from || undefined,
          expires_to: expiresAtRange.to || undefined,
          sort_by: sort.field,
          sort_dir: sort.sort,
        },
        auth
      );
      setItems(response.items || []);
      setTotal(response.total || 0);
    } catch (e) {
      setError(normalizeApiError(e, t("mykeys_load_failed")));
      setItems([]);
      setTotal(0);
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

  async function renew(id) {
    setBanner("");
    try {
      const response = await apiClient.renewApiKey(id, auth);
      if (response?.api_key_plaintext) {
        setRenewIssued(response);
        setRenewCopySucceeded(false);
        setRenewCopyError("");
      }
      setBanner((prev) => prev || t("mykeys_renew_done"));
      await load();
      if (detailOpen && detailId === id) {
        closeDetail();
      }
    } catch (e) {
      setBanner(e?.payload?.error?.message || t("mykeys_renew_failed"));
    }
  }

  async function extend(id, durationMonths) {
    setBanner("");
    try {
      await apiClient.extendApiKey(id, { duration_months: durationMonths }, auth);
      setBanner(t("mykeys_extend_done"));
      await load();
      if (detailOpen && detailId === id) {
        closeDetail();
      }
    } catch (e) {
      setBanner(e?.payload?.error?.message || t("mykeys_extend_failed"));
    }
  }

  function closeRenewIssuedDialog() {
    if (renewCopyResetTimerRef.current) {
      clearTimeout(renewCopyResetTimerRef.current);
      renewCopyResetTimerRef.current = null;
    }
    setRenewIssued(null);
    setRenewCopySucceeded(false);
    setRenewCopyError("");
  }

  async function onCopyRenewKey() {
    if (!renewIssued?.api_key_plaintext) {
      setRenewCopyError(locale === "zh-TW" ? "目前無法複製金鑰，請手動複製。" : "Unable to copy key now. Please copy manually.");
      return;
    }
    const result = await copyText(renewIssued.api_key_plaintext);
    if (!result.ok) {
      if (result.reason === "insecure_context") {
        setRenewCopyError(locale === "zh-TW" ? "目前環境不支援自動複製（需 HTTPS 或 localhost），請手動複製。" : "Auto copy is unavailable in this environment (HTTPS or localhost required).");
      } else if (result.reason === "clipboard_unavailable") {
        setRenewCopyError(locale === "zh-TW" ? "目前瀏覽器不支援自動複製，請手動複製。" : "Clipboard API is unavailable. Please copy manually.");
      } else if (result.reason === "permission_denied") {
        setRenewCopyError(locale === "zh-TW" ? "剪貼簿權限被拒絕，請允許後再試，或手動複製。" : "Clipboard permission denied. Please allow and retry, or copy manually.");
      } else {
        setRenewCopyError(locale === "zh-TW" ? "目前無法複製金鑰，請手動複製。" : "Unable to copy key now. Please copy manually.");
      }
      return;
    }

    setRenewCopySucceeded(true);
    setRenewCopyError("");
    if (renewCopyResetTimerRef.current) clearTimeout(renewCopyResetTimerRef.current);
    renewCopyResetTimerRef.current = setTimeout(() => {
      setRenewCopySucceeded(false);
      renewCopyResetTimerRef.current = null;
    }, 1500);
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
      setDetailError(normalizeApiError(e, t("mykeys_detail_failed")));
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
    const aliasValidation = validatePersistedText(keyAlias, { required: true, restrictSpecialChars: true, allowSpaces: false });
    if (!aliasValidation.ok) {
      setAliasSaving(false);
      setBanner(
        aliasValidation.reason === "required"
          ? t("mykeys_alias_required")
          : aliasValidation.reason === "invalid_chars"
            ? t("mykeys_alias_invalid_chars")
            : t("mykeys_alias_unsafe")
      );
      return;
    }
    try {
      const response = await apiClient.updateApiKey(id, { key_alias: aliasValidation.value }, auth);
      setBanner(t("mykeys_alias_update_done"));
      setItems((prev) => prev.map((item) => (item.id === id ? { ...item, key_alias: response.item.key_alias } : item)));
      if (detailItem?.id === id) {
        setDetailItem(response.item);
        setDetailAliasValue(response.item.key_alias || "");
      }
    } catch (e) {
      if (e?.payload?.error?.code === "KEY_ALIAS_DUPLICATE") {
        setBanner(t("mykeys_alias_duplicate"));
      } else {
        setBanner(e?.payload?.error?.message || t("mykeys_alias_update_failed"));
      }
    } finally {
      setAliasSaving(false);
    }
  }

  useEffect(() => {
    load();
  }, [auth.role, filterModel, page, pageSize, sortModel]);

  useEffect(() => () => {
    if (renewCopyResetTimerRef.current) clearTimeout(renewCopyResetTimerRef.current);
  }, []);

  const columns = useMemo(
    () => {
      const baseColumns = [
        {
          field: "application_date",
          headerName: t("mykeys_col_application_date"),
          type: "date",
          flex: 1,
          minWidth: 120,
          filterOperators: dateFilterOperators,
          valueGetter: (value) => (value ? new Date(`${value}T00:00:00`) : null),
          renderCell: (params) => params.row.application_date || "-"
        },
        {
          field: "duration_months",
          headerName: t("mykeys_col_duration_months"),
          flex: 1,
          minWidth: 120,
          valueFormatter: (value) => `${value} ${t("mykeys_duration_suffix")}`,
          filterable: false
        },
        {
          field: "status",
          headerName: t("common_status"),
          type: "singleSelect",
          valueOptions: ["active", "revoked", "expired"],
          flex: 1,
          minWidth: 120,
          filterOperators: singleSelectFilterOperators,
          renderCell: (params) => <Chip size="small" label={params.value} color={statusColor(params.value)} />
        },
        {
          field: "expires_at",
          headerName: t("mykeys_col_expires_at"),
          type: "dateTime",
          flex: 1.5,
          minWidth: 180,
          filterOperators: dateFilterOperators,
          valueGetter: (value) => (value ? new Date(value) : null),
          renderCell: (params) => formatDateTimeInTaipei(params.row.expires_at, { locale })
        },
        {
          field: "masked_key",
          headerName: t("mykeys_col_masked_key"),
          flex: 1.5,
          minWidth: 180,
          valueFormatter: (value) => formatMaskedKey(value),
          sortable: false,
          filterable: false
        }
      ];

      if (auth.role === "admin") {
        baseColumns.push({
          field: "owner_account",
          headerName: t("dashboard_col_owner_account"),
          flex: 1.2,
          minWidth: 150,
          filterOperators: containsFilterOperators
        });
        baseColumns.push({
          field: "owner_name",
          headerName: t("dashboard_col_owner_name"),
          flex: 1.2,
          minWidth: 150,
          filterOperators: containsFilterOperators
        });
        baseColumns.push({
          field: "key_alias",
          headerName: t("mykeys_col_key_alias"),
          flex: 1.4,
          minWidth: 180,
          filterOperators: containsFilterOperators
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
        minWidth: 160,
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
            {(params.row.status === "active" || params.row.status === "revoked" || params.row.status === "expired") ? (
              <Tooltip title={locale === "zh-TW" ? "更多操作" : "More actions"}>
                <IconButton
                  aria-label={locale === "zh-TW" ? "更多操作" : "More actions"}
                  size="small"
                  onClick={(event) => openActionMenu(event, params.row)}
                >
                  <MoreVertIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            ) : null}
          </Box>
        )
      });

      return baseColumns;
    },
    [auth.role, locale, t]
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
                  setSortModel(model);
                  setPage(0);
                }}
                filterModel={filterModel}
                onFilterModelChange={(model) => {
                  setFilterModel(model);
                  setPage(0);
                }}
                pageSizeOptions={[10, 20, 50]}
                disableRowSelectionOnClick
                rowHeight={56}
                localeText={gridLocaleText}
              />
            </Box>
          ) : null}
        </CardContent>
      </Card>
      <Menu
        anchorEl={actionMenuAnchorEl}
        open={Boolean(actionMenuAnchorEl && actionMenuRow)}
        onClose={closeActionMenu}
      >
        {actionMenuRow?.status === "active" ? (
          <MenuItem
            onClick={() => {
              const targetId = actionMenuRow?.id;
              closeActionMenu();
              if (targetId) {
                setPendingRevokeId(targetId);
              }
            }}
          >
            <BlockIcon fontSize="small" sx={{ mr: 1 }} />
            {t("mykeys_revoke_key")}
          </MenuItem>
        ) : null}
        {actionMenuRow?.status === "revoked" ? (
          <MenuItem
            onClick={() => {
              const targetId = actionMenuRow?.id;
              closeActionMenu();
              if (targetId) {
                setPendingRenewId(targetId);
              }
            }}
          >
            <AutorenewIcon fontSize="small" sx={{ mr: 1 }} />
            {t("mykeys_renew_key")}
          </MenuItem>
        ) : null}
        {canShowExtendAction(actionMenuRow) ? (
          <MenuItem
            onClick={() => {
              const targetId = actionMenuRow?.id;
              closeActionMenu();
              if (targetId) {
                setPendingExtendId(targetId);
                setExtendDurationMonths(6);
              }
            }}
          >
            <AutorenewIcon fontSize="small" sx={{ mr: 1 }} />
            {t("mykeys_extend_key")}
          </MenuItem>
        ) : null}
      </Menu>

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

      <Dialog open={Boolean(pendingRenewId)} onClose={() => setPendingRenewId("")}>
        <DialogTitle>{t("mykeys_dialog_renew_title")}</DialogTitle>
        <DialogContent>{t("mykeys_dialog_renew_body")}</DialogContent>
        <DialogActions>
          <Button onClick={() => setPendingRenewId("")}>{locale === "zh-TW" ? "取消" : "Cancel"}</Button>
          <Button
            onClick={async () => {
              const targetId = pendingRenewId;
              setPendingRenewId("");
              await renew(targetId);
            }}
          >
            {locale === "zh-TW" ? "確認" : "Confirm"}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={Boolean(pendingExtendId)} onClose={() => setPendingExtendId("")}>
        <DialogTitle>{t("mykeys_dialog_extend_title")}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 0.5, minWidth: 260 }}>
            <Typography>{t("mykeys_dialog_extend_body")}</Typography>
            <TextField
              select
              label={t("mykeys_dialog_extend_duration_label")}
              value={String(extendDurationMonths)}
              onChange={(e) => setExtendDurationMonths(Number(e.target.value))}
              SelectProps={{ native: true }}
            >
              <option value="1">{`1 ${t("mykeys_duration_suffix")}`}</option>
              <option value="6">{`6 ${t("mykeys_duration_suffix")}`}</option>
              <option value="12">{`12 ${t("mykeys_duration_suffix")}`}</option>
            </TextField>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPendingExtendId("")}>{locale === "zh-TW" ? "取消" : "Cancel"}</Button>
          <Button
            onClick={async () => {
              const targetId = pendingExtendId;
              const months = extendDurationMonths;
              setPendingExtendId("");
              await extend(targetId, months);
            }}
          >
            {locale === "zh-TW" ? "確認" : "Confirm"}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog
        open={Boolean(renewIssued)}
        disableEscapeKeyDown
        onClose={(_event, reason) => handlePersistentDialogClose(reason, closeRenewIssuedDialog)}
      >
        <DialogTitle>{locale === "zh-TW" ? "金鑰已更新" : "API Key Renewed"}</DialogTitle>
        <DialogContent>
          <Typography sx={{ mb: 1 }}>
            {locale === "zh-TW" ? "此明文金鑰只會顯示一次，請立即保存。" : "This plaintext key is shown only once. Save it now."}
          </Typography>
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            <Typography sx={{ fontFamily: "monospace", bgcolor: "grey.100", p: 1, borderRadius: 1, flex: 1, userSelect: "text", wordBreak: "break-all" }}>
              {renewIssued?.api_key_plaintext}
            </Typography>
            <Tooltip title={renewCopySucceeded ? (locale === "zh-TW" ? "已複製" : "Copied") : (locale === "zh-TW" ? "複製金鑰" : "Copy Key")}>
              <IconButton aria-label={renewCopySucceeded ? (locale === "zh-TW" ? "已複製金鑰" : "Copied Key") : (locale === "zh-TW" ? "複製金鑰" : "Copy Key")} onClick={onCopyRenewKey}>
                {renewCopySucceeded ? <CheckIcon /> : <ContentCopyIcon />}
              </IconButton>
            </Tooltip>
          </Box>
          {renewCopyError ? <Alert severity="error" sx={{ mt: 1 }}>{renewCopyError}</Alert> : null}
        </DialogContent>
        <DialogActions>
          <Button onClick={closeRenewIssuedDialog}>{locale === "zh-TW" ? "我知道了" : "Saved"}</Button>
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
              <Typography>{t("mykeys_detail_department")}: {formatDepartment(detailItem.department, locale)}</Typography>
              <Typography>{t("mykeys_detail_application_date")}: {detailItem.application_date}</Typography>
              <Typography>{t("mykeys_detail_duration")}: {detailItem.duration_months} {t("mykeys_duration_suffix")}</Typography>
              <Typography>
                {t("mykeys_detail_masked_key")}: {formatMaskedKey(detailItem.masked_key)}
              </Typography>
              <Typography>{t("mykeys_detail_created_at")}: {formatDateTimeInTaipei(detailItem.created_at, { locale })}</Typography>
              <Typography>{t("mykeys_detail_expires_at")}: {formatDateTimeInTaipei(detailItem.expires_at, { locale })}</Typography>
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
