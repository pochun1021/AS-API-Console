import { useEffect, useMemo, useState } from "react";
import AddIcon from "@mui/icons-material/Add";
import DeleteIcon from "@mui/icons-material/Delete";
import EditIcon from "@mui/icons-material/Edit";
import VisibilityIcon from "@mui/icons-material/Visibility";
import {
  Alert,
  Box,
  ButtonBase,
  Button,
  Card,
  CardContent,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  MenuItem,
  Stack,
  TextField,
  Tooltip,
  Typography,
  useMediaQuery
} from "@mui/material";
import { DataGrid } from "@mui/x-data-grid";
import { useTheme } from "@mui/material/styles";
import { Link as RouterLink } from "react-router-dom";
import { apiClient } from "../api/client";
import { normalizeApiError } from "../api/errors";
import DateRangeFilterField from "../components/DateRangeFilterField";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlocks";
import { useLocale } from "../i18n/locale";
import { COMPACT_DIALOG_PAGE_SIZE_OPTIONS, compactGridProps, compactGridSx } from "../utils/compactDataGrid";
import { formatDateTimeInTaipei } from "../utils/datetime";
import { validatePersistedText } from "../utils/inputValidation";
import { buildTaipeiDateTimeRange, getServerSort } from "../utils/serverDataGrid";

const actionCellSx = {
  display: "flex",
  justifyContent: "flex-start",
  alignItems: "center",
  width: "100%",
  height: "100%",
  gap: 0.5,
  whiteSpace: "nowrap"
};

function toDateTimeLocalValue(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const offsetMs = date.getTimezoneOffset() * 60 * 1000;
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16);
}

function toIsoOrNull(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

function buildDefaultForm() {
  return {
    id: "",
    title: "",
    body: "",
    status: "active",
    publish_from: "",
    publish_to: ""
  };
}

export default function SystemAnnouncementsPage({ auth }) {
  const { gridLocaleText, locale, t } = useLocale();
  const isAdmin = auth.role === "admin";
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(10);
  const [sortModel, setSortModel] = useState([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [titleFilter, setTitleFilter] = useState("");
  const [publishFromDateFrom, setPublishFromDateFrom] = useState("");
  const [publishFromDateTo, setPublishFromDateTo] = useState("");
  const [publishToDateFrom, setPublishToDateFrom] = useState("");
  const [publishToDateTo, setPublishToDateTo] = useState("");
  const [updatedDateFrom, setUpdatedDateFrom] = useState("");
  const [updatedDateTo, setUpdatedDateTo] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [banner, setBanner] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogSaving, setDialogSaving] = useState(false);
  const [dialogError, setDialogError] = useState("");
  const [form, setForm] = useState(buildDefaultForm());
  const [pendingDelete, setPendingDelete] = useState(null);
  const [previewItem, setPreviewItem] = useState(null);
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down("sm"));
  const hasActiveFilters = Boolean(
    statusFilter ||
      titleFilter.trim() ||
      publishFromDateFrom ||
      publishFromDateTo ||
      publishToDateFrom ||
      publishToDateTo ||
      updatedDateFrom ||
      updatedDateTo
  );

  async function load() {
    setLoading(true);
    setError("");
    try {
      const publishFromRange = buildTaipeiDateTimeRange(publishFromDateFrom, publishFromDateTo);
      const publishToRange = buildTaipeiDateTimeRange(publishToDateFrom, publishToDateTo);
      const updatedRange = buildTaipeiDateTimeRange(updatedDateFrom, updatedDateTo);
      const sort = getServerSort(sortModel, { field: "updated_at", sort: "desc" });
      const response = await apiClient.listAnnouncements(
        {
          page: page + 1,
          page_size: pageSize,
          scope: isAdmin ? "all" : undefined,
          status: isAdmin ? statusFilter || undefined : undefined,
          title: titleFilter.trim() || undefined,
          publish_from_from: publishFromRange.from || undefined,
          publish_from_to: publishFromRange.to || undefined,
          publish_to_from: publishToRange.from || undefined,
          publish_to_to: publishToRange.to || undefined,
          updated_from: isAdmin ? updatedRange.from || undefined : undefined,
          updated_to: isAdmin ? updatedRange.to || undefined : undefined,
          sort_by: sort.field,
          sort_dir: sort.sort,
        },
        auth
      );
      setItems(response.items);
      setTotal(response.total || 0);
    } catch (e) {
      setError(normalizeApiError(e, t("announcement_load_failed")));
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [isAdmin, page, pageSize, sortModel, statusFilter, titleFilter, publishFromDateFrom, publishFromDateTo, publishToDateFrom, publishToDateTo, updatedDateFrom, updatedDateTo]);

  function clearFilters() {
    setStatusFilter("");
    setTitleFilter("");
    setPublishFromDateFrom("");
    setPublishFromDateTo("");
    setPublishToDateFrom("");
    setPublishToDateTo("");
    setUpdatedDateFrom("");
    setUpdatedDateTo("");
    setPage(0);
  }

  function openCreateDialog() {
    setForm(buildDefaultForm());
    setDialogError("");
    setDialogOpen(true);
  }

  function openEditDialog(item) {
    setForm({
      id: item.id,
      title: item.title,
      body: item.body,
      status: item.status,
      publish_from: toDateTimeLocalValue(item.publish_from),
      publish_to: toDateTimeLocalValue(item.publish_to)
    });
    setDialogError("");
    setDialogOpen(true);
  }

  function closeDialog() {
    if (dialogSaving) return;
    setDialogOpen(false);
    setDialogError("");
  }

  function openPreview(item) {
    setPreviewItem(item);
  }

  async function saveAnnouncement() {
    setDialogError("");
    const titleValidation = validatePersistedText(form.title, { required: true });
    if (!titleValidation.ok) {
      setDialogError(titleValidation.reason === "unsafe" ? t("announcement_title_unsafe") : t("announcement_title_required"));
      return;
    }
    const bodyValidation = validatePersistedText(form.body, { required: true });
    if (!bodyValidation.ok) {
      setDialogError(bodyValidation.reason === "unsafe" ? t("announcement_body_unsafe") : t("announcement_body_required"));
      return;
    }
    const publishFromIso = toIsoOrNull(form.publish_from);
    const publishToIso = toIsoOrNull(form.publish_to);
    if (publishFromIso && publishToIso && new Date(publishFromIso) > new Date(publishToIso)) {
      setDialogError(t("announcement_invalid_window"));
      return;
    }

    setDialogSaving(true);
    setBanner("");
    const payload = {
      title: titleValidation.value,
      body: bodyValidation.value,
      status: form.status,
      publish_from: publishFromIso,
      publish_to: publishToIso
    };
    try {
      if (form.id) {
        await apiClient.updateAnnouncement(form.id, payload, auth);
        setBanner(t("announcement_updated_done"));
      } else {
        await apiClient.createAnnouncement(payload, auth);
        setBanner(t("announcement_created_done"));
      }
      setDialogOpen(false);
      await load();
    } catch (e) {
      setDialogError(normalizeApiError(e, t("announcement_save_failed")).message);
    } finally {
      setDialogSaving(false);
    }
  }

  async function confirmDelete() {
    if (!pendingDelete) return;
    setBanner("");
    try {
      await apiClient.deleteAnnouncement(pendingDelete.id, auth);
      setPendingDelete(null);
      setBanner(t("announcement_deleted_done"));
      await load();
    } catch (e) {
      setPendingDelete(null);
      setBanner(normalizeApiError(e, t("announcement_deleted_failed")).message);
    }
  }

  const columns = useMemo(
    () => {
      const baseColumns = [
        {
          field: "title",
          headerName: t("announcement_col_title"),
          flex: 1.2,
          minWidth: 220,
          filterable: false,
          renderCell: (params) => (
            <ButtonBase
              onClick={() => openPreview(params.row)}
              sx={{
                justifyContent: "flex-start",
                textAlign: "left",
                color: "primary.main",
                fontWeight: 600,
                textDecoration: "underline",
                textUnderlineOffset: "3px",
              }}
              aria-label={`${t("announcement_view")} ${params.value}`}
            >
              {params.value}
            </ButtonBase>
          )
        },
        {
          field: "status",
          headerName: t("common_status"),
          flex: 0.7,
          minWidth: 120,
          filterable: false,
          renderCell: (params) => (
            <Chip
              size="small"
              color={params.value === "active" ? "success" : "default"}
              label={params.value === "active" ? t("announcement_status_active") : t("announcement_status_inactive")}
            />
          )
        },
        {
          field: "publish_from",
          headerName: t("announcement_col_publish_from"),
          flex: 1,
          minWidth: 180,
          filterable: false,
          valueFormatter: (value) => (value ? formatDateTimeInTaipei(value, { locale }) : "-")
        },
        {
          field: "publish_to",
          headerName: t("announcement_col_publish_to"),
          flex: 1,
          minWidth: 180,
          filterable: false,
          valueFormatter: (value) => (value ? formatDateTimeInTaipei(value, { locale }) : "-")
        },
        {
          field: "updated_at",
          headerName: t("common_updated_at"),
          flex: 1,
          minWidth: 180,
          filterable: false,
          valueFormatter: (value) => formatDateTimeInTaipei(value, { locale })
        }
      ];
      if (!isAdmin) {
        return baseColumns.filter((column) => column.field !== "status");
      }
      return [
        ...baseColumns,
        {
          field: "actions",
          headerName: t("common_actions"),
          sortable: false,
          filterable: false,
          minWidth: 130,
          renderCell: (params) => (
            <Box sx={actionCellSx}>
              <Tooltip title={t("announcement_edit")}>
                <IconButton aria-label={t("announcement_edit")} size="small" onClick={() => openEditDialog(params.row)}>
                  <EditIcon fontSize="small" />
                </IconButton>
              </Tooltip>
              <Tooltip title={t("common_delete")}>
                <IconButton aria-label={t("common_delete")} size="small" color="error" onClick={() => setPendingDelete(params.row)}>
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </Tooltip>
            </Box>
          )
        }
      ];
    },
    [isAdmin, locale, t]
  );

  return (
    <Stack spacing={2} sx={{ minHeight: 0 }}>
      <Stack direction={{ xs: "column", md: "row" }} justifyContent="space-between" alignItems={{ xs: "stretch", md: "center" }} spacing={1.5}>
        <Box>
          <Typography variant="h4">{isAdmin ? t("announcement_title") : t("announcement_public_title")}</Typography>
          <Typography color="text.secondary">{isAdmin ? t("announcement_subtitle") : t("announcement_public_subtitle")}</Typography>
        </Box>
        {isAdmin ? (
          <Button variant="contained" startIcon={<AddIcon />} onClick={openCreateDialog}>
            {t("common_add")}
          </Button>
        ) : null}
      </Stack>

      <Card variant="outlined">
        <CardContent>
          <Stack spacing={1.25} alignItems="flex-start">
            <Typography variant="h6">{t("service_guide_card_title")}</Typography>
            <Typography color="text.secondary">{t("service_guide_card_body")}</Typography>
            <Button component={RouterLink} to="/usage-examples" variant="contained">
              {t("service_guide_card_action")}
            </Button>
          </Stack>
        </CardContent>
      </Card>

      {banner ? <Alert severity="info">{banner}</Alert> : null}

      <Card variant="outlined">
        <CardContent>
          <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} flexWrap="wrap" useFlexGap sx={{ mb: 2 }}>
            <TextField
              label={t("announcement_filter_title")}
              size="small"
              value={titleFilter}
              onChange={(e) => {
                setTitleFilter(e.target.value);
                setPage(0);
              }}
              sx={{ minWidth: 220 }}
            />
            {isAdmin ? (
              <TextField
                select
                size="small"
                label={t("common_status")}
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  setPage(0);
                }}
                sx={{ minWidth: 160 }}
              >
                <MenuItem value="">{t("announcement_status_all")}</MenuItem>
                <MenuItem value="active">{t("announcement_status_active")}</MenuItem>
                <MenuItem value="inactive">{t("announcement_status_inactive")}</MenuItem>
              </TextField>
            ) : null}
            <DateRangeFilterField
              label={t("announcement_filter_publish_from_range")}
              size="small"
              startLabel={t("announcement_filter_publish_from_from")}
              endLabel={t("announcement_filter_publish_from_to")}
              fromValue={publishFromDateFrom}
              toValue={publishFromDateTo}
              clearLabel={t("common_clear")}
              closeLabel={t("common_close")}
              onChange={({ from, to }) => {
                setPublishFromDateFrom(from);
                setPublishFromDateTo(to);
                setPage(0);
              }}
            />
            <DateRangeFilterField
              label={t("announcement_filter_publish_to_range")}
              size="small"
              startLabel={t("announcement_filter_publish_to_from")}
              endLabel={t("announcement_filter_publish_to_to")}
              fromValue={publishToDateFrom}
              toValue={publishToDateTo}
              clearLabel={t("common_clear")}
              closeLabel={t("common_close")}
              onChange={({ from, to }) => {
                setPublishToDateFrom(from);
                setPublishToDateTo(to);
                setPage(0);
              }}
            />
            {isAdmin ? (
              <DateRangeFilterField
                label={t("announcement_filter_updated_range")}
                size="small"
                startLabel={t("announcement_filter_updated_from")}
                endLabel={t("announcement_filter_updated_to")}
                fromValue={updatedDateFrom}
                toValue={updatedDateTo}
                clearLabel={t("common_clear")}
                closeLabel={t("common_close")}
                onChange={({ from, to }) => {
                  setUpdatedDateFrom(from);
                  setUpdatedDateTo(to);
                  setPage(0);
                }}
              />
            ) : null}
            <Button variant="outlined" onClick={clearFilters} disabled={!hasActiveFilters}>
              {t("common_clear")}
            </Button>
          </Stack>

          {loading ? <LoadingBlock text={t("announcement_loading")} /> : null}
          {!loading && error ? <ErrorBlock message={error} onRetry={load} /> : null}
          {!loading && !error && total === 0 ? <EmptyBlock text={isAdmin ? t("announcement_empty") : t("announcement_public_empty")} /> : null}
          {!loading && !error && total > 0 ? (
            <Box sx={{ minHeight: 520 }}>
              <DataGrid
                autoHeight={false}
                rows={items}
                columns={columns}
                rowCount={total}
                loading={loading}
                pagination
                paginationMode="server"
                sortingMode="server"
                pageSizeOptions={COMPACT_DIALOG_PAGE_SIZE_OPTIONS}
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
                disableRowSelectionOnClick
                localeText={gridLocaleText}
                sx={compactGridSx}
                {...compactGridProps}
              />
            </Box>
          ) : null}
        </CardContent>
      </Card>

      <Dialog open={isAdmin && dialogOpen} onClose={closeDialog} fullWidth maxWidth="sm" fullScreen={fullScreen}>
        <DialogTitle>{form.id ? t("announcement_edit_title") : t("announcement_create_title")}</DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2} sx={{ pt: 1 }}>
            {dialogError ? <Alert severity="error">{dialogError}</Alert> : null}
            <TextField
              label={t("announcement_col_title")}
              value={form.title}
              onChange={(e) => setForm((prev) => ({ ...prev, title: e.target.value }))}
              fullWidth
            />
            <TextField
              label={t("announcement_body_label")}
              value={form.body}
              onChange={(e) => setForm((prev) => ({ ...prev, body: e.target.value }))}
              fullWidth
              multiline
              minRows={4}
            />
            <TextField
              select
              label={t("common_status")}
              value={form.status}
              onChange={(e) => setForm((prev) => ({ ...prev, status: e.target.value }))}
              fullWidth
            >
              <MenuItem value="active">{t("announcement_status_active")}</MenuItem>
              <MenuItem value="inactive">{t("announcement_status_inactive")}</MenuItem>
            </TextField>
            <TextField
              label={t("announcement_col_publish_from")}
              type="datetime-local"
              value={form.publish_from}
              onChange={(e) => setForm((prev) => ({ ...prev, publish_from: e.target.value }))}
              fullWidth
              InputLabelProps={{ shrink: true }}
            />
            <TextField
              label={t("announcement_col_publish_to")}
              type="datetime-local"
              value={form.publish_to}
              onChange={(e) => setForm((prev) => ({ ...prev, publish_to: e.target.value }))}
              fullWidth
              InputLabelProps={{ shrink: true }}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={closeDialog} disabled={dialogSaving}>{t("common_cancel")}</Button>
          <Button onClick={saveAnnouncement} variant="contained" disabled={dialogSaving}>{t("common_save")}</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={isAdmin && Boolean(pendingDelete)} onClose={() => setPendingDelete(null)} fullWidth maxWidth="xs">
        <DialogTitle>{t("announcement_delete_title")}</DialogTitle>
        <DialogContent dividers>
          <Typography>{t("announcement_delete_body").replace("{title}", pendingDelete?.title || "")}</Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPendingDelete(null)}>{t("common_cancel")}</Button>
          <Button onClick={confirmDelete} color="error" variant="contained">{t("common_delete")}</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={Boolean(previewItem)} onClose={() => setPreviewItem(null)} fullWidth maxWidth="sm">
        <DialogTitle sx={{ display: "flex", alignItems: "center", gap: 1 }}>
          <VisibilityIcon fontSize="small" />
          <span>{previewItem?.title || t("announcement_preview_title")}</span>
        </DialogTitle>
        <DialogContent dividers>
          {previewItem ? (
            <Stack spacing={1.5}>
              <Typography variant="body2" color="text.secondary">
                {t("common_updated_at")}: {formatDateTimeInTaipei(previewItem.updated_at, { locale })}
              </Typography>
              <Typography sx={{ whiteSpace: "pre-wrap" }}>{previewItem.body}</Typography>
            </Stack>
          ) : null}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPreviewItem(null)}>{t("common_close")}</Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
