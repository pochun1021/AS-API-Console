import { useEffect, useMemo, useState } from "react";
import AddIcon from "@mui/icons-material/Add";
import DeleteIcon from "@mui/icons-material/Delete";
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
  MenuItem,
  Stack,
  TextField,
  Tooltip,
  Typography,
  Chip,
  useMediaQuery
} from "@mui/material";
import { DataGrid } from "@mui/x-data-grid/DataGrid";
import { useTheme } from "@mui/material/styles";
import { apiClient } from "../api/client";
import { normalizeApiError } from "../api/errors";
import DateRangeFilterField from "../components/DateRangeFilterField";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlocks";
import { useLocale } from "../i18n/locale";
import { COMPACT_DIALOG_PAGE_SIZE_OPTIONS, COMPACT_LOCAL_PAGE_SIZE_OPTIONS, compactGridProps, compactGridSx } from "../utils/compactDataGrid";
import { formatDateTimeInTaipei } from "../utils/datetime";
import { getGridLocaleText } from "../utils/gridLocaleText";
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

export default function AdminPage({ auth }) {
  const { locale, t } = useLocale();
  const gridLocaleText = getGridLocaleText(locale);
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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [banner, setBanner] = useState("");
  const [pendingRevokeUser, setPendingRevokeUser] = useState(null);
  const [pendingDeleteUser, setPendingDeleteUser] = useState(null);
  const [searchDialogOpen, setSearchDialogOpen] = useState(false);
  const [searchKeyword, setSearchKeyword] = useState("");
  const [searching, setSearching] = useState(false);
  const [searchResults, setSearchResults] = useState([]);
  const [searchMessage, setSearchMessage] = useState("");
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
    setSearchKeyword("");
    setSearching(false);
    setSearchResults([]);
    setSearchMessage("");
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
      const response = await apiClient.listAdmins(
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
    } catch (e) {
      setError(normalizeApiError(e, t("admin_load_failed")));
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

  async function search() {
    setSearchMessage("");
    setSearching(true);
    try {
      if (!searchKeyword.trim()) {
        setSearchResults([]);
        setSearchMessage(t("admin_search_required"));
        return;
      }
      const response = await apiClient.searchUsers(searchKeyword, auth, { lookup_context: "admin_create" });
      setSearchResults(response.items);
      if (response.items.length === 0) {
        setSearchMessage(t("admin_search_empty"));
      }
    } catch (e) {
      setSearchMessage(e?.payload?.error?.message || t("admin_search_failed"));
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  }

  async function grant(payload, userName = "") {
    setBanner("");
    try {
      await apiClient.createAdmin(payload.id, payload, auth);
      setBanner(t("admin_grant_done").replace("{name}", userName || t("common_owner")));
      await load();
    } catch (e) {
      setBanner(e?.payload?.error?.message || t("admin_grant_failed"));
    }
  }

  async function revoke(userId) {
    setBanner("");
    try {
      await apiClient.disableAdmin(userId, auth);
      setBanner(t("admin_revoke_done"));
      await load();
    } catch (e) {
      setBanner(e?.payload?.error?.message || t("admin_revoke_failed"));
    }
  }

  async function reactivate(userId, userName = "") {
    setBanner("");
    try {
      await apiClient.enableAdmin(userId, auth);
      setBanner(t("admin_grant_done").replace("{name}", userName || t("common_owner")));
      await load();
    } catch (e) {
      setBanner(e?.payload?.error?.message || t("admin_grant_failed"));
    }
  }

  async function remove(userId) {
    setBanner("");
    try {
      await apiClient.deleteAdmin(userId, auth);
      setBanner(t("admin_delete_done"));
      await load();
    } catch (e) {
      setBanner(e?.payload?.error?.message || t("admin_delete_failed"));
    }
  }

  useEffect(() => {
    load();
  }, [page, pageSize, sortModel, statusFilter, sysidFilter, accountFilter, nameFilter, emailFilter, createdDateFrom, createdDateTo, updatedDateFrom, updatedDateTo]);

  const currentUserBySysid = useMemo(
    () => items.find((item) => item.sysid === auth.sysid),
    [items, auth.sysid]
  );
  const adminStatusById = useMemo(() => new Map(items.map((item) => [item.id, item.status])), [items]);

  const adminColumns = useMemo(
    () => [
      { field: "sysid", headerName: "SysID", flex: 1, minWidth: 140, filterable: false },
      { field: "account", headerName: t("common_account"), flex: 1, minWidth: 140, filterable: false },
      { field: "name", headerName: t("common_name"), flex: 1, minWidth: 140, filterable: false },
      { field: "email", headerName: t("common_email"), flex: 1.5, minWidth: 220, filterable: false },
      {
        field: "status",
        headerName: t("common_status"),
        flex: 0.8,
        minWidth: 120,
        filterable: false,
        renderCell: (params) => (
          <Chip
            size="small"
            color={params.value === "active" ? "success" : "default"}
            label={params.value === "active" ? t("admin_status_active") : t("admin_status_inactive")}
          />
        )
      },
      {
        field: "created_at",
        headerName: t("common_created_at"),
        flex: 1.4,
        minWidth: 180,
        filterable: false,
        valueFormatter: (value) => formatDateTimeInTaipei(value, { locale })
      },
      {
        field: "updated_at",
        headerName: t("common_updated_at"),
        flex: 1.4,
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
        flex: 1,
        minWidth: 110,
        renderCell: (params) => {
          const isSelf = params.row.sysid === auth.sysid || currentUserBySysid?.id === params.row.id;
          const isInactive = params.row.status === "inactive";
          return (
            <Box sx={actionCellSx}>
              {isInactive ? (
                <>
                  <Tooltip title={locale === "zh-TW" ? "啟用管理者" : t("common_enable")}>
                    <IconButton
                      aria-label={locale === "zh-TW" ? "啟用管理者" : t("common_enable")}
                      size="small"
                      onClick={async () => {
                        await reactivate(params.row.id, params.row.name);
                      }}
                    >
                      <AddIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title={locale === "zh-TW" ? "刪除停用管理者" : t("common_delete")}>
                    <IconButton
                      aria-label={locale === "zh-TW" ? "刪除停用管理者" : t("common_delete")}
                      size="small"
                      color="error"
                      onClick={() => setPendingDeleteUser({ id: params.row.id, name: params.row.name })}
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </>
              ) : (
                <Tooltip title={locale === "zh-TW" ? "停用管理者" : t("common_disable")}>
                  <span>
                    <IconButton
                      aria-label={locale === "zh-TW" ? "停用管理者" : t("common_disable")}
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
    [auth.sysid, currentUserBySysid, t, locale]
  );

  const searchColumns = useMemo(
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
        renderCell: (params) =>
          adminStatusById.has(params.row.id) ? (
            <Box sx={{ display: "flex", alignItems: "center", height: "100%" }}>
              <Typography variant="body2" color="text.secondary">
                {adminStatusById.get(params.row.id) === "inactive" ? t("admin_status_inactive") : t("admin_status_active")}
              </Typography>
            </Box>
          ) : (
            <Tooltip title={locale === "zh-TW" ? "加入管理者" : t("common_add")}>
              <IconButton
                aria-label={locale === "zh-TW" ? "加入管理者" : t("common_add")}
                size="small"
                onClick={async () => {
                  await grant(
                    {
                      id: params.row.id,
                      account: params.row.account,
                      name: params.row.name,
                      email: params.row.email,
                      department: params.row.department
                    },
                    params.row.name
                  );
                }}
              >
                <AddIcon fontSize="small" />
              </IconButton>
            </Tooltip>
          )
      }
    ],
    [adminStatusById, t, locale]
  );

  if (auth.role !== "admin") {
    return (
      <Stack spacing={3}>
        <Typography variant="h4">{t("admin_title")}</Typography>
        <ErrorBlock message={t("admin_forbidden")} />
      </Stack>
    );
  }

  return (
    <Stack spacing={2} sx={{ flex: 1, minHeight: 0, overflow: "hidden" }}>
      <Typography variant="h4">{t("admin_title")}</Typography>
      {banner ? <Alert severity="info">{banner}</Alert> : null}

      <Stack direction={{ xs: "column", md: "row" }} spacing={2} useFlexGap flexWrap="wrap" alignItems={{ xs: "stretch", md: "center" }}>
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
        <TextField
          select
          label={t("common_status")}
          value={statusFilter}
          onChange={(event) => {
            setStatusFilter(event.target.value);
            setPage(0);
          }}
          sx={{ minWidth: 180 }}
        >
          <MenuItem value="">{locale === "zh-TW" ? "全部狀態" : "All statuses"}</MenuItem>
          <MenuItem value="active">{t("admin_status_active")}</MenuItem>
          <MenuItem value="inactive">{t("admin_status_inactive")}</MenuItem>
        </TextField>
        <DateRangeFilterField
          label={t("admin_filter_created_range")}
          fromValue={createdDateFrom}
          toValue={createdDateTo}
          startLabel={t("admin_filter_created_from")}
          endLabel={t("admin_filter_created_to")}
          clearLabel={t("common_clear")}
          closeLabel={t("common_close")}
          onChange={({ from, to }) => {
            setCreatedDateFrom(from);
            setCreatedDateTo(to);
            setPage(0);
          }}
        />
        <DateRangeFilterField
          label={t("admin_filter_updated_range")}
          fromValue={updatedDateFrom}
          toValue={updatedDateTo}
          startLabel={t("admin_filter_updated_from")}
          endLabel={t("admin_filter_updated_to")}
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
        <Box sx={{ ml: { md: "auto" } }}>
          <Button
            variant="outlined"
            startIcon={<AddIcon />}
            aria-label={t("admin_open_search")}
            sx={{ backgroundColor: "transparent", minHeight: 56, alignSelf: { xs: "stretch", md: "center" } }}
            onClick={() => setSearchDialogOpen(true)}
          >
            {t("common_add")}
          </Button>
        </Box>
      </Stack>

      <Card sx={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>
        <CardContent sx={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>
          {loading ? <LoadingBlock text={t("admin_loading")} /> : null}
          {!loading && error ? <ErrorBlock message={error} onRetry={load} /> : null}
          {!loading && !error && items.length === 0 ? <EmptyBlock text={t("admin_empty")} /> : null}
          {!loading && !error && items.length > 0 ? (
            <Box sx={{ flex: 1, minHeight: 0 }}>
              <DataGrid
                sx={compactGridSx}
                rows={items}
                columns={adminColumns}
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

      <Dialog open={Boolean(pendingRevokeUser)} onClose={() => setPendingRevokeUser(null)}>
        <DialogTitle>{t("admin_dialog_revoke_title")}</DialogTitle>
        <DialogContent>
          {t("admin_dialog_revoke_body").replace("{name}", pendingRevokeUser?.name || t("common_owner"))}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPendingRevokeUser(null)}>{locale === "zh-TW" ? "取消" : "Cancel"}</Button>
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
            {locale === "zh-TW" ? "確認停用" : t("common_disable")}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={Boolean(pendingDeleteUser)} onClose={() => setPendingDeleteUser(null)}>
        <DialogTitle>{t("admin_dialog_delete_title")}</DialogTitle>
        <DialogContent>
          {t("admin_dialog_delete_body").replace("{name}", pendingDeleteUser?.name || t("common_owner"))}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setPendingDeleteUser(null)}>{locale === "zh-TW" ? "取消" : "Cancel"}</Button>
          <Button
            color="error"
            onClick={async () => {
              const target = pendingDeleteUser;
              setPendingDeleteUser(null);
              if (target) {
                await remove(target.id);
              }
            }}
          >
            {locale === "zh-TW" ? "確認刪除" : t("common_delete")}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={searchDialogOpen} onClose={closeSearchDialog} fullWidth maxWidth="lg" fullScreen={fullScreen}>
        <DialogTitle>{t("admin_dialog_search_title")}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 0.5 }}>
            <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
              <TextField
                label={locale === "zh-TW" ? "查詢關鍵字" : t("common_keyword")}
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
                {searching ? t("common_searching") : t("common_search_users")}
              </Button>
            </Stack>
            <Typography component="p" variant="body2" color="text.secondary">
              {t("admin_search_hint")}
            </Typography>
            {searchMessage ? <Alert severity="info">{searchMessage}</Alert> : null}
            {searchResults.length > 0 ? (
              <Box sx={{ height: 420 }}>
                <DataGrid
                  sx={compactGridSx}
                  rows={searchResults}
                  columns={searchColumns}
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
