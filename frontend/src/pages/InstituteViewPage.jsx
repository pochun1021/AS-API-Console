import { useEffect, useMemo, useState } from "react";
import { Alert, Box, Button, Card, CardContent, Stack, Typography } from "@mui/material";
import { DataGrid } from "@mui/x-data-grid";
import { apiClient } from "../api/client";
import { normalizeApiError } from "../api/errors";
import { EmptyBlock, ErrorAlert, ErrorBlock, LoadingBlock } from "../components/StateBlocks";
import { useLocale } from "../i18n/locale";

export default function InstituteViewPage({ auth }) {
  const { gridLocaleText, t } = useLocale();
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [syncing, setSyncing] = useState(false);
  const [banner, setBanner] = useState(null);

  async function load() {
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
    load();
  }, []);

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
      await load();
    } catch (e) {
      setBanner({
        severity: "error",
        message: normalizeApiError(e, t("institute_view_sync_failed"))
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

  return (
    <Stack spacing={3} sx={{ flex: 1, minHeight: 0 }}>
      <Typography variant="h4">{t("institute_view_title")}</Typography>
      <Box sx={{ display: "flex", justifyContent: "flex-end" }}>
        <Button variant="contained" onClick={syncNow} disabled={syncing || loading}>
          {syncing ? t("institute_view_syncing") : t("institute_view_sync")}
        </Button>
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
          {!loading && error ? <ErrorBlock message={error} onRetry={load} /> : null}
          {!loading && !error && items.length === 0 ? <EmptyBlock text={t("institute_view_empty")} /> : null}
          {!loading && !error && items.length > 0 ? (
            <Box sx={{ flex: 1, minHeight: 320 }}>
              <DataGrid
                sx={{ height: "100%" }}
                rows={items}
                columns={columns}
                getRowId={(row) => row.inst_code}
                pageSizeOptions={[10, 20, 50]}
                initialState={{ pagination: { paginationModel: { pageSize: 10, page: 0 } } }}
                disableRowSelectionOnClick
                localeText={gridLocaleText}
              />
            </Box>
          ) : null}
        </CardContent>
      </Card>
    </Stack>
  );
}
