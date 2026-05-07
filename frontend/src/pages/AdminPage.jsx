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

export default function AdminPage({ auth }) {
  const { gridLocaleText, locale, t } = useLocale();
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
      setError(e?.payload?.error?.message || t("admin_load_failed"));
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
        setSearchMessage(t("admin_search_required"));
        return;
      }
      const response = await apiClient.searchUsers(searchKeyword, auth);
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

  async function grant(userId, userName = "") {
    setBanner("");
    try {
      await apiClient.enableAdmin(userId, auth);
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
      { field: "account", headerName: t("common_account"), flex: 1, minWidth: 140 },
      { field: "name", headerName: t("common_name"), flex: 1, minWidth: 140 },
      { field: "email", headerName: t("common_email"), flex: 1.5, minWidth: 220 },
      {
        field: "status",
        headerName: t("common_status"),
        flex: 0.8,
        minWidth: 120,
        renderCell: (params) => (
          <Chip
            size="small"
            color={params.value === "active" ? "success" : "default"}
            label={params.value === "active" ? t("admin_status_active") : t("admin_status_inactive")}
          />
        )
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
                <Tooltip title={locale === "zh-TW" ? "啟用管理者" : t("common_enable")}>
                  <IconButton
                    aria-label={locale === "zh-TW" ? "啟用管理者" : t("common_enable")}
                    size="small"
                    onClick={async () => {
                      await grant(params.row.id, params.row.name);
                    }}
                  >
                    <AddIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
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
          adminStatusById.get(params.row.id) === "active" ? (
            <Box sx={{ display: "flex", alignItems: "center", height: "100%" }}>
              <Typography variant="body2" color="text.secondary">
                {t("admin_status_active")}
              </Typography>
            </Box>
          ) : (
            <Tooltip title={locale === "zh-TW" ? "加入管理者" : t("common_add")}>
              <IconButton
                aria-label={locale === "zh-TW" ? "加入管理者" : t("common_add")}
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
    <Stack spacing={3} sx={{ flex: 1, minHeight: 0 }}>
      <Typography variant="h4">{t("admin_title")}</Typography>
      {banner ? <Alert severity="info">{banner}</Alert> : null}

      <Box sx={{ display: "flex", justifyContent: "flex-end" }}>
        <Button
          variant="outlined"
          startIcon={<AddIcon />}
          aria-label="開啟新增管理者查詢"
          sx={{ backgroundColor: "transparent" }}
          onClick={() => setSearchDialogOpen(true)}
        >
          {t("common_add")}
        </Button>
      </Box>

      <Card sx={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>
        <CardContent sx={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>
          {loading ? <LoadingBlock text={t("admin_loading")} /> : null}
          {!loading && error ? <ErrorBlock message={error} onRetry={load} /> : null}
          {!loading && !error && adminItems.length === 0 ? <EmptyBlock text={t("admin_empty")} /> : null}
          {!loading && !error && adminItems.length > 0 ? (
            <Box sx={{ flex: 1, minHeight: 320 }}>
              <DataGrid
                sx={{ height: "100%" }}
                rows={adminItems}
                columns={adminColumns}
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
                {searching ? t("common_searching") : (locale === "zh-TW" ? "查詢使用者" : t("common_search_users"))}
              </Button>
            </Stack>
            <Typography component="p" variant="body2" color="text.secondary">
              {t("admin_search_hint")}
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
