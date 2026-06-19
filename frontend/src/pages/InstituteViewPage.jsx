import { useEffect, useMemo, useState } from "react";
import { Alert, Box, Button, Card, CardContent, Stack, Typography } from "@mui/material";
import { DataGrid } from "@mui/x-data-grid/DataGrid";
import { apiClient } from "../api/client";
import { normalizeApiError } from "../api/errors";
import { EmptyBlock, ErrorAlert, ErrorBlock, LoadingBlock } from "../components/StateBlocks";
import { useLocale } from "../i18n/locale";
import { COMPACT_LOCAL_PAGE_SIZE_OPTIONS, compactGridProps, compactGridSx } from "../utils/compactDataGrid";
import { getGridLocaleText } from "../utils/gridLocaleText";

function toRemainingSeconds(nextAllowedAt) {
  if (!nextAllowedAt) return 0;
  const target = new Date(nextAllowedAt).getTime();
  if (Number.isNaN(target)) return 0;
  return Math.max(0, Math.ceil((target - Date.now()) / 1000));
}

function formatCooldown(seconds, t) {
  if (seconds >= 60) {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = seconds % 60;
    return t("institute_view_sync_cooldown_minutes")
      .replace("{minutes}", String(minutes))
      .replace("{seconds}", String(remainingSeconds));
  }
  return t("institute_view_sync_cooldown_seconds").replace("{seconds}", String(seconds));
}

export default function InstituteViewPage({ auth }) {
  const { locale, t } = useLocale();
  const gridLocaleText = getGridLocaleText(locale);
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [syncStatusLoading, setSyncStatusLoading] = useState(true);
  const [error, setError] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [banner, setBanner] = useState(null);
  const [cooldownUntil, setCooldownUntil] = useState(null);
  const [cooldownRemaining, setCooldownRemaining] = useState(0);

  function applySyncStatus(status) {
    const nextAllowedAt =
      status?.retry_after_seconds > 0 && typeof status?.next_allowed_at === "string"
        ? status.next_allowed_at
        : null;
    const remaining = toRemainingSeconds(nextAllowedAt);
    setCooldownUntil(remaining > 0 ? nextAllowedAt : null);
    setCooldownRemaining(remaining);
  }

  async function loadInstitutes() {
    setLoading(true);
    setError("");
    try {
      const response = await apiClient.listInstitutes(auth);
      setItems(response.items || []);
      setTotal(Number(response.total || 0));
    } catch (e) {
      setError(normalizeApiError(e, t("institute_view_load_failed")));
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (auth.role !== "admin") return undefined;

    loadInstitutes();
    setSyncStatusLoading(true);
    apiClient
      .getInstituteSyncStatus(auth)
      .then((status) => {
        applySyncStatus(status);
      })
      .catch(() => {
        applySyncStatus(null);
      })
      .finally(() => {
        setSyncStatusLoading(false);
      });
    return undefined;
  }, [auth]);

  useEffect(() => {
    if (!cooldownUntil) return undefined;
    const timerId = window.setInterval(() => {
      const remaining = toRemainingSeconds(cooldownUntil);
      setCooldownRemaining(remaining);
      if (remaining <= 0) {
        setCooldownUntil(null);
      }
    }, 1000);
    return () => window.clearInterval(timerId);
  }, [cooldownUntil]);

  async function refreshSyncStatus() {
    setSyncStatusLoading(true);
    try {
      const status = await apiClient.getInstituteSyncStatus(auth);
      applySyncStatus(status);
    } catch {
      applySyncStatus(null);
    } finally {
      setSyncStatusLoading(false);
    }
  }

  async function syncNow() {
    setSyncing(true);
    setBanner(null);
    try {
      const result = await apiClient.syncInstitutes(auth);
      setBanner({
        severity: "success",
        message: t("institute_view_sync_done")
          .replace("{fetched}", String(result.fetched_count))
          .replace("{inserted}", String(result.inserted_count))
          .replace("{updated}", String(result.updated_count))
          .replace("{unchanged}", String(result.unchanged_count))
          .replace("{deactivated}", String(result.deactivated_count))
      });
      await loadInstitutes();
      await refreshSyncStatus();
    } catch (e) {
      const normalized = normalizeApiError(e, t("institute_view_sync_failed"));
      if (normalized.code === "INSTITUTE_SYNC_IN_PROGRESS") {
        setBanner({
          severity: "error",
          message: t("institute_view_sync_in_progress")
        });
        return;
      }
      if (normalized.code === "INSTITUTE_SYNC_COOLDOWN") {
        applySyncStatus(normalized);
        setBanner({
          severity: "error",
          message: t("institute_view_sync_cooldown_rejected")
            .replace("{remaining}", formatCooldown(Math.max(1, normalized.retry_after_seconds), t))
        });
        return;
      }
      setBanner({
        severity: "error",
        message: normalized
      });
    } finally {
      setSyncing(false);
    }
  }

  const columns = useMemo(
    () => [
      { field: "inst_code", headerName: "inst_code", minWidth: 140, flex: 1 },
      { field: "inst_name", headerName: "inst_name", minWidth: 220, flex: 1.5 },
      { field: "abb_inst_name", headerName: "abb_inst_name", minWidth: 200, flex: 1.2 },
      { field: "einst_name", headerName: "einst_name", minWidth: 220, flex: 1.5 },
      { field: "division", headerName: "division", minWidth: 120, flex: 0.8 }
    ],
    []
  );

  if (auth.role !== "admin") {
    return (
      <Stack spacing={3}>
        <Typography variant="h4">{t("institute_view_title")}</Typography>
        <ErrorBlock message={t("institute_view_forbidden")} />
      </Stack>
    );
  }

  const cooldownText = cooldownRemaining > 0 ? formatCooldown(cooldownRemaining, t) : "";

  return (
    <Stack spacing={2} sx={{ flex: 1, minHeight: 0, overflow: "hidden" }}>
      <Typography variant="h4">{t("institute_view_title")}</Typography>
      <Box sx={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 0.75 }}>
        <Button
          variant="contained"
          onClick={syncNow}
          disabled={syncing || loading || syncStatusLoading || cooldownRemaining > 0}
        >
          {syncing ? t("institute_view_syncing") : t("institute_view_sync")}
        </Button>
        {cooldownRemaining > 0 ? (
          <Typography variant="body2" color="text.secondary">
            {t("institute_view_sync_cooldown_active").replace("{remaining}", cooldownText)}
          </Typography>
        ) : null}
      </Box>
      {banner ? (
        banner.severity === "error" ? <ErrorAlert message={banner.message} /> : <Alert severity={banner.severity}>{banner.message}</Alert>
      ) : null}
      <Typography variant="body2" color="text.secondary">
        {t("institute_view_total").replace("{count}", String(total))}
      </Typography>
      <Card sx={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>
        <CardContent sx={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>
          {loading ? <LoadingBlock text={t("institute_view_loading")} /> : null}
          {!loading && error ? <ErrorBlock message={error} onRetry={loadInstitutes} /> : null}
          {!loading && !error && items.length === 0 ? <EmptyBlock text={t("institute_view_empty")} /> : null}
          {!loading && !error && items.length > 0 ? (
            <Box sx={{ flex: 1, minHeight: 0 }}>
              <DataGrid
                sx={compactGridSx}
                rows={items}
                columns={columns}
                getRowId={(row) => row.inst_code}
                pageSizeOptions={COMPACT_LOCAL_PAGE_SIZE_OPTIONS}
                initialState={{ pagination: { paginationModel: { pageSize: 10, page: 0 } } }}
                disableRowSelectionOnClick
                {...compactGridProps}
                localeText={gridLocaleText}
              />
            </Box>
          ) : null}
        </CardContent>
      </Card>
    </Stack>
  );
}
