import { useEffect, useMemo, useRef, useState } from "react";
import PersonAddIcon from "@mui/icons-material/PersonAdd";
import AddIcon from "@mui/icons-material/Add";
import SaveIcon from "@mui/icons-material/Save";
import PlayArrowIcon from "@mui/icons-material/PlayArrow";
import StopIcon from "@mui/icons-material/Stop";
import DeleteIcon from "@mui/icons-material/Delete";
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
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  TextField,
  Tooltip,
  Typography,
  useMediaQuery
} from "@mui/material";
import { DataGrid } from "@mui/x-data-grid";
import { useTheme } from "@mui/material/styles";
import { apiClient } from "../api/client";
import { normalizeApiError } from "../api/errors";
import DateRangeFilterField from "../components/DateRangeFilterField";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlocks";
import { useLocale } from "../i18n/locale";
import { COMPACT_DIALOG_PAGE_SIZE_OPTIONS, COMPACT_LOCAL_PAGE_SIZE_OPTIONS, compactGridProps, compactGridSx } from "../utils/compactDataGrid";
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

function statusColor(status) {
  return status === "active" ? "success" : "default";
}

function getStatusLabel(status, t) {
  return status === "active" ? t("whitelist_status_active") : t("whitelist_status_inactive");
}

function WhitelistNoteField({ note, onDraftChange }) {
  const [draft, setDraft] = useState(note || "");
  const composingRef = useRef(false);

  useEffect(() => {
    if (composingRef.current) {
      return;
    }
    setDraft(note || "");
  }, [note]);

  return (
    <TextField
      size="small"
      value={draft}
      onKeyDown={(e) => {
        e.stopPropagation();
      }}
      onCompositionStart={() => {
        composingRef.current = true;
      }}
      onCompositionEnd={(e) => {
        composingRef.current = false;
        const nextValue = e.target.value;
        setDraft(nextValue);
        onDraftChange(nextValue);
      }}
      onChange={(e) => {
        const nextValue = e.target.value;
        setDraft(nextValue);
        if (!composingRef.current) {
          onDraftChange(nextValue);
        }
      }}
    />
  );
}

export default function WhitelistAdminPage({ auth }) {
  const { gridLocaleText, locale, t } = useLocale();
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(10);
  const [sortModel, setSortModel] = useState([]);
  const [statusFilter, setStatusFilter] = useState("");
  const [sysidFilter, setSysidFilter] = useState("");
  const [accountFilter, setAccountFilter] = useState("");
  const [nameFilter, setNameFilter] = useState("");
  const [emailFilter, setEmailFilter] = useState("");
  const [createdDateFrom, setCreatedDateFrom] = useState("");
  const [createdDateTo, setCreatedDateTo] = useState("");
  const [updatedDateFrom, setUpdatedDateFrom] = useState("");
  const [updatedDateTo, setUpdatedDateTo] = useState("");
  const [keyword, setKeyword] = useState("");
  const [candidates, setCandidates] = useState([]);
  const [searching, setSearching] = useState(false);
  const [searchMessage, setSearchMessage] = useState("");
  const [dialogMessage, setDialogMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [banner, setBanner] = useState("");
  const [pendingStatusChange, setPendingStatusChange] = useState(null);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [searchDialogOpen, setSearchDialogOpen] = useState(false);
  const editingRemarkRef = useRef({});
  const theme = useTheme();
  const fullScreen = useMediaQuery(theme.breakpoints.down("sm"));
  const hasActiveFilters = Boolean(
    statusFilter ||
      sysidFilter.trim() ||
      accountFilter.trim() ||
      nameFilter.trim() ||
      emailFilter.trim() ||
      createdDateFrom ||
      createdDateTo ||
      updatedDateFrom ||
      updatedDateTo
  );

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
      const createdRange = buildTaipeiDateTimeRange(createdDateFrom, createdDateTo);
      const updatedRange = buildTaipeiDateTimeRange(updatedDateFrom, updatedDateTo);
      const sort = getServerSort(sortModel, { field: "created_at", sort: "desc" });
      const normalizedSysid = sysidFilter.trim();
      const parsedSysid = /^\d+$/.test(normalizedSysid) ? Number(normalizedSysid) : undefined;
      const response = await apiClient.listWhitelists(
        {
          page: page + 1,
          page_size: pageSize,
          status: statusFilter || undefined,
          sysid: parsedSysid,
          account: accountFilter.trim() || undefined,
          name: nameFilter.trim() || undefined,
          email: emailFilter.trim() || undefined,
          created_from: createdRange.from || undefined,
          created_to: createdRange.to || undefined,
          updated_from: updatedRange.from || undefined,
          updated_to: updatedRange.to || undefined,
          sort_by: sort.field,
          sort_dir: sort.sort,
        },
        auth
      );
      setItems(response.items);
      setTotal(response.total || 0);
      editingRemarkRef.current = {};
    } catch (e) {
      setError(normalizeApiError(e, t("whitelist_load_failed")));
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }

  function clearFilters() {
    setStatusFilter("");
    setSysidFilter("");
    setAccountFilter("");
    setNameFilter("");
    setEmailFilter("");
    setCreatedDateFrom("");
    setCreatedDateTo("");
    setUpdatedDateFrom("");
    setUpdatedDateTo("");
    setPage(0);
  }

  async function searchCandidates() {
    setSearchMessage("");
    setSearching(true);
    try {
      if (!keyword.trim()) {
        setCandidates([]);
        setSearchMessage(t("whitelist_search_required"));
        return;
      }
      const response = await apiClient.searchUsers(keyword, auth, { lookup_context: "whitelist_create" });
      setCandidates(response.items);
      if (response.items.length === 0) {
        setSearchMessage(t("whitelist_search_empty"));
      }
    } catch (e) {
      setSearchMessage(e?.payload?.error?.message || t("whitelist_search_failed"));
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
      setDialogMessage(t("whitelist_created_done"));
      await load();
    } catch (e) {
      setDialogMessage(e?.payload?.error?.message || t("whitelist_created_failed"));
    }
  }

  async function updateItem(id, payload) {
    setBanner("");
    const noteValidation = validatePersistedText(payload.note, { required: false, restrictSpecialChars: true, allowSpaces: true });
    if (!noteValidation.ok) {
      setBanner(noteValidation.reason === "invalid_chars" ? t("whitelist_note_invalid_chars") : t("whitelist_note_unsafe"));
      return;
    }
    try {
      await apiClient.updateWhitelist(id, { ...payload, note: noteValidation.value || null }, auth);
      setBanner(t("whitelist_updated_done"));
      await load();
    } catch (e) {
      setBanner(e?.payload?.error?.message || t("whitelist_updated_failed"));
    }
  }

  async function deleteItem(id) {
    setBanner("");
    try {
      await apiClient.deleteWhitelist(id, auth);
      setBanner(t("whitelist_deleted_done"));
      await load();
    } catch (e) {
      setBanner(e?.payload?.error?.message || t("whitelist_deleted_failed"));
    }
  }

  useEffect(() => {
    load();
  }, [page, pageSize, sortModel, statusFilter, sysidFilter, accountFilter, nameFilter, emailFilter, createdDateFrom, createdDateTo, updatedDateFrom, updatedDateTo]);

  const candidateColumns = useMemo(
    () => [
      { field: "sysid", headerName: "SysID", flex: 1, minWidth: 140 },
      { field: "account", headerName: t("common_account"), flex: 1, minWidth: 140 },
      { field: "name", headerName: t("common_name"), flex: 1, minWidth: 140 },
      { field: "email", headerName: t("common_email"), flex: 1.5, minWidth: 220 },
      {
        field: "actions",
        headerName: t("common_actions"),
        sortable: false,
        filterable: false,
        align: "left",
        headerAlign: "left",
        flex: 1,
        minWidth: 110,
        renderCell: (params) => (
          <Box sx={actionCellSx}>
            <Tooltip title={locale === "zh-TW" ? "加入特殊人員名單" : t("common_add")}>
              <IconButton aria-label={locale === "zh-TW" ? "加入特殊人員名單" : t("common_add")} size="small" onClick={() => createItem(params.row)}>
                <PersonAddIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
        )
      }
    ],
    [t]
  );

  const whitelistColumns = useMemo(
    () => [
      { field: "sysid", headerName: "SysID", flex: 1, minWidth: 140, filterable: false },
      { field: "account", headerName: t("common_account"), flex: 1, minWidth: 140, filterable: false },
      { field: "name", headerName: t("common_name"), flex: 1, minWidth: 140, filterable: false },
      { field: "email", headerName: t("common_email"), flex: 1.5, minWidth: 220, filterable: false },
      {
        field: "status",
        headerName: t("common_status"),
        flex: 1,
        minWidth: 120,
        filterable: false,
        renderCell: (params) => <Chip size="small" label={getStatusLabel(params.value, t)} color={statusColor(params.value)} />
      },
      {
        field: "remark",
        headerName: t("whitelist_col_remark"),
        flex: 1.5,
        minWidth: 220,
        sortable: false,
        filterable: false,
        renderCell: (params) => (
          <Box sx={{ display: "flex", alignItems: "center", height: "100%", width: "100%" }}>
            <WhitelistNoteField
              note={editingRemarkRef.current[params.row.id] ?? params.row.note}
              onDraftChange={(nextValue) => {
                editingRemarkRef.current[params.row.id] = nextValue;
              }}
            />
          </Box>
        )
      },
      {
        field: "created_at",
        headerName: t("common_created_at"),
        flex: 1.5,
        minWidth: 180,
        filterable: false,
        valueFormatter: (value) => formatDateTimeInTaipei(value, { locale })
      },
      {
        field: "updated_at",
        headerName: t("common_updated_at"),
        flex: 1.5,
        minWidth: 180,
        filterable: false,
        valueFormatter: (value) => formatDateTimeInTaipei(value, { locale })
      },
      {
        field: "actions",
        headerName: t("common_actions"),
        sortable: false,
        filterable: false,
        align: "left",
        headerAlign: "left",
        flex: 1.2,
        minWidth: 140,
        renderCell: (params) => (
          <Box sx={actionCellSx}>
            <Tooltip title={locale === "zh-TW" ? "儲存備註" : t("common_save")}>
              <IconButton
                aria-label={locale === "zh-TW" ? "儲存備註" : t("common_save")}
                size="small"
                color="primary"
                onClick={() =>
                  updateItem(params.row.id, {
                    status: params.row.status,
                    note: editingRemarkRef.current[params.row.id] ?? params.row.note
                  })
                }
              >
                <SaveIcon fontSize="small" />
              </IconButton>
            </Tooltip>
            <Tooltip title={params.row.status === "active" ? (locale === "zh-TW" ? "停用特殊人員名單" : t("common_disable")) : (locale === "zh-TW" ? "啟用特殊人員名單" : t("common_enable"))}>
              <IconButton
                aria-label={params.row.status === "active" ? (locale === "zh-TW" ? "停用特殊人員名單" : t("common_disable")) : (locale === "zh-TW" ? "啟用特殊人員名單" : t("common_enable"))}
                size="small"
                color={params.row.status === "active" ? "warning" : "success"}
                onClick={() =>
                  setPendingStatusChange({
                    id: params.row.id,
                    nextStatus: params.row.status === "active" ? "inactive" : "active",
                    note: editingRemarkRef.current[params.row.id] ?? params.row.note
                  })
                }
              >
                {params.row.status === "active" ? <StopIcon fontSize="small" /> : <PlayArrowIcon fontSize="small" />}
              </IconButton>
            </Tooltip>
            <Tooltip title={locale === "zh-TW" ? "刪除特殊人員名單" : t("common_delete")}>
              <IconButton
                aria-label={locale === "zh-TW" ? "刪除特殊人員名單" : t("common_delete")}
                size="small"
                color="error"
                onClick={() => setPendingDelete({ id: params.row.id, account: params.row.account, name: params.row.name })}
              >
                <DeleteIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          </Box>
        )
      }
    ],
    [t, locale]
  );

  if (auth.role !== "admin") {
    return (
      <Stack spacing={3}>
        <Typography variant="h4">{t("whitelist_title")}</Typography>
        <ErrorBlock message={t("whitelist_forbidden")} />
      </Stack>
    );
  }

  return (
    <Stack spacing={2} sx={{ flex: 1, minHeight: 0, overflow: "hidden" }}>
      <Typography variant="h4">{t("whitelist_title")}</Typography>
      {banner ? <Alert severity="info">{banner}</Alert> : null}

      <Stack direction={{ xs: "column", md: "row" }} spacing={2} useFlexGap flexWrap="wrap" alignItems={{ xs: "stretch", md: "center" }}>
        <FormControl sx={{ minWidth: 180 }}>
          <InputLabel id="whitelist-status-filter-label">{t("common_status")}</InputLabel>
          <Select
            labelId="whitelist-status-filter-label"
            label={t("common_status")}
            value={statusFilter}
            onChange={(event) => {
              setStatusFilter(event.target.value);
              setPage(0);
            }}
          >
            <MenuItem value="">{locale === "zh-TW" ? "全部狀態" : "All statuses"}</MenuItem>
            <MenuItem value="active">{t("whitelist_status_active")}</MenuItem>
            <MenuItem value="inactive">{t("whitelist_status_inactive")}</MenuItem>
          </Select>
        </FormControl>
        <TextField
          label="SysID"
          value={sysidFilter}
          onChange={(event) => {
            setSysidFilter(event.target.value);
            setPage(0);
          }}
          sx={{ minWidth: 160 }}
        />
        <TextField
          label={t("common_account")}
          value={accountFilter}
          onChange={(event) => {
            setAccountFilter(event.target.value);
            setPage(0);
          }}
          sx={{ minWidth: 180 }}
        />
        <TextField
          label={t("common_name")}
          value={nameFilter}
          onChange={(event) => {
            setNameFilter(event.target.value);
            setPage(0);
          }}
          sx={{ minWidth: 180 }}
        />
        <TextField
          label={t("common_email")}
          value={emailFilter}
          onChange={(event) => {
            setEmailFilter(event.target.value);
            setPage(0);
          }}
          sx={{ minWidth: 220 }}
        />
        <DateRangeFilterField
          label={t("whitelist_filter_created_range")}
          fromValue={createdDateFrom}
          toValue={createdDateTo}
          startLabel={t("whitelist_filter_created_from")}
          endLabel={t("whitelist_filter_created_to")}
          clearLabel={t("common_clear")}
          closeLabel={t("common_close")}
          onChange={({ from, to }) => {
            setCreatedDateFrom(from);
            setCreatedDateTo(to);
            setPage(0);
          }}
        />
        <DateRangeFilterField
          label={t("whitelist_filter_updated_range")}
          fromValue={updatedDateFrom}
          toValue={updatedDateTo}
          startLabel={t("whitelist_filter_updated_from")}
          endLabel={t("whitelist_filter_updated_to")}
          clearLabel={t("common_clear")}
          closeLabel={t("common_close")}
          onChange={({ from, to }) => {
            setUpdatedDateFrom(from);
            setUpdatedDateTo(to);
            setPage(0);
          }}
        />
        <Button variant="outlined" onClick={clearFilters} disabled={!hasActiveFilters} sx={{ minHeight: 56 }}>
          {t("mykeys_clear_filters")}
        </Button>
        <Button
          variant="outlined"
          startIcon={<AddIcon />}
          aria-label={t("whitelist_open_search")}
          onClick={() => setSearchDialogOpen(true)}
          sx={{ ml: { md: "auto" }, alignSelf: { xs: "stretch", md: "center" }, minHeight: 56 }}
        >
          {t("common_add")}
        </Button>
      </Stack>

      <Card sx={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>
        <CardContent sx={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>
          {loading ? <LoadingBlock text={t("whitelist_loading")} /> : null}
          {!loading && error ? <ErrorBlock message={error} onRetry={load} /> : null}
          {!loading && !error && items.length === 0 ? <EmptyBlock text={t("whitelist_empty")} /> : null}
          {!loading && !error && items.length > 0 ? (
            <Box sx={{ flex: 1, minHeight: 0 }}>
              <DataGrid
                sx={compactGridSx}
                rows={items}
                columns={whitelistColumns}
                getRowId={(row) => row.id}
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
                  setSortModel(model);
                  setPage(0);
                }}
                disableColumnFilter
                pageSizeOptions={COMPACT_LOCAL_PAGE_SIZE_OPTIONS}
                disableRowSelectionOnClick
                {...compactGridProps}
                localeText={gridLocaleText}
              />
            </Box>
          ) : null}
        </CardContent>
      </Card>

      <Dialog open={Boolean(pendingStatusChange)} onClose={() => setPendingStatusChange(null)}>
        <DialogTitle>{t("whitelist_dialog_status_title")}</DialogTitle>
        <DialogContent>
          {t("whitelist_dialog_status_body").replace(
            "{status}",
            pendingStatusChange?.nextStatus === "active" ? t("whitelist_status_active") : t("whitelist_status_inactive")
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPendingStatusChange(null)}>{locale === "zh-TW" ? "取消" : "Cancel"}</Button>
          <Button
            color="warning"
            onClick={async () => {
              const target = pendingStatusChange;
              setPendingStatusChange(null);
              if (target) {
                await updateItem(target.id, { status: target.nextStatus, note: target.note });
              }
            }}
          >
            {locale === "zh-TW" ? "確認" : "Confirm"}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={Boolean(pendingDelete)} onClose={() => setPendingDelete(null)}>
        <DialogTitle>{t("whitelist_dialog_delete_title")}</DialogTitle>
        <DialogContent>
          {t("whitelist_dialog_delete_body").replace("{name}", pendingDelete?.name || "-").replace("{account}", pendingDelete?.account || "-")}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPendingDelete(null)}>{locale === "zh-TW" ? "取消" : "Cancel"}</Button>
          <Button
            color="error"
            onClick={async () => {
              const target = pendingDelete;
              setPendingDelete(null);
              if (target) {
                await deleteItem(target.id);
              }
            }}
          >
            {locale === "zh-TW" ? "確認刪除" : "Delete"}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={searchDialogOpen} onClose={closeSearchDialog} fullWidth maxWidth="lg" fullScreen={fullScreen}>
        <DialogTitle>{t("whitelist_search_title")}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 0.5 }}>
            <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
              <TextField
                label={locale === "zh-TW" ? "查詢關鍵字" : t("common_keyword")}
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
                {searching ? t("common_searching") : (locale === "zh-TW" ? "查詢人員" : t("common_search_users"))}
              </Button>
            </Stack>
            <Typography component="p" variant="body2" color="text.secondary">
              {t("admin_search_hint")}
            </Typography>
            {searchMessage ? <Alert severity="info">{searchMessage}</Alert> : null}
            {dialogMessage ? <Alert severity="info">{dialogMessage}</Alert> : null}
            {candidates.length > 0 ? (
              <Box sx={{ height: 420 }}>
                <DataGrid
                  sx={compactGridSx}
                  rows={candidates}
                  columns={candidateColumns}
                  getRowId={(row) => row.id}
                  pageSizeOptions={COMPACT_DIALOG_PAGE_SIZE_OPTIONS}
                  initialState={{ pagination: { paginationModel: { pageSize: 10, page: 0 } } }}
                  disableRowSelectionOnClick
                  {...compactGridProps}
                  localeText={gridLocaleText}
                />
              </Box>
            ) : null}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={closeSearchDialog}>{locale === "zh-TW" ? "關閉" : "Close"}</Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
