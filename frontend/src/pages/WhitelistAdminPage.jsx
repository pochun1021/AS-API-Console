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
import { useTheme } from "@mui/material/styles";
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

function formatDateTime(value) {
  const dt = new Date(value);
  return Number.isNaN(dt.getTime()) ? "-" : dt.toLocaleString();
}

function statusColor(status) {
  return status === "active" ? "success" : "default";
}

export default function WhitelistAdminPage({ auth }) {
  const { gridLocaleText, locale, t } = useLocale();
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
      setError(e?.payload?.error?.message || t("whitelist_load_failed"));
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
    try {
      await apiClient.updateWhitelist(id, payload, auth);
      setBanner(t("whitelist_updated_done"));
      await load();
    } catch (e) {
      setBanner(e?.payload?.error?.message || t("whitelist_updated_failed"));
    }
  }

  useEffect(() => {
    load();
  }, []);

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
      { field: "sysid", headerName: "SysID", flex: 1, minWidth: 140 },
      { field: "account", headerName: t("common_account"), flex: 1, minWidth: 140 },
      { field: "name", headerName: t("common_name"), flex: 1, minWidth: 140 },
      { field: "email", headerName: t("common_email"), flex: 1.5, minWidth: 220 },
      {
        field: "status",
        headerName: t("common_status"),
        flex: 1,
        minWidth: 120,
        renderCell: (params) => <Chip size="small" label={params.value} color={statusColor(params.value)} />
      },
      {
        field: "remark",
        headerName: t("whitelist_col_remark"),
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
        headerName: t("common_created_at"),
        flex: 1.5,
        minWidth: 180,
        valueFormatter: (value) => formatDateTime(value)
      },
      {
        field: "updated_at",
        headerName: t("common_updated_at"),
        flex: 1.5,
        minWidth: 180,
        valueFormatter: (value) => formatDateTime(value)
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
                    remark: editingRemark[params.row.id] ?? params.row.remark
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
    [editingRemark, t, locale]
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
    <Stack spacing={3} sx={{ flex: 1, minHeight: 0 }}>
      <Typography variant="h4">{t("whitelist_title")}</Typography>
      {banner ? <Alert severity="info">{banner}</Alert> : null}

      <Box sx={{ display: "flex", justifyContent: "flex-end" }}>
        <Button
          variant="outlined"
          startIcon={<AddIcon />}
          aria-label="開啟新增特殊人員名單人員"
          onClick={() => setSearchDialogOpen(true)}
        >
          {t("common_add")}
        </Button>
      </Box>

      <Card sx={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>
        <CardContent sx={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>
          {loading ? <LoadingBlock text={t("whitelist_loading")} /> : null}
          {!loading && error ? <ErrorBlock message={error} onRetry={load} /> : null}
          {!loading && !error && items.length === 0 ? <EmptyBlock text={t("whitelist_empty")} /> : null}
          {!loading && !error && items.length > 0 ? (
            <Box sx={{ flex: 1, minHeight: 320 }}>
              <DataGrid
                sx={{ height: "100%" }}
                rows={items}
                columns={whitelistColumns}
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
                await updateItem(target.id, { status: target.nextStatus });
              }
            }}
          >
            {locale === "zh-TW" ? "確認" : "Confirm"}
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
                  rows={candidates}
                  columns={candidateColumns}
                  getRowId={(row) => row.id}
                  pageSizeOptions={[5, 10, 20]}
                  initialState={{ pagination: { paginationModel: { pageSize: 5, page: 0 } } }}
                  disableRowSelectionOnClick
                  rowHeight={56}
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
