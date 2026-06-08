import { useEffect, useMemo, useState } from "react";
import { Box, Button, Card, CardContent, Stack, Typography } from "@mui/material";
import { DataGrid } from "@mui/x-data-grid";
import { apiClient } from "../api/client";
import { normalizeApiError } from "../api/errors";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlocks";
import { useLocale } from "../i18n/locale";
import { COMPACT_LOCAL_PAGE_SIZE_OPTIONS, compactGridProps, compactGridSx } from "../utils/compactDataGrid";

const REFRESH_INTERVAL_MS = 15 * 60 * 1000;

export default function ModelsPage({ auth }) {
  const { gridLocaleText, t } = useLocale();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  async function load({ background = false } = {}) {
    if (background) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError("");
    try {
      const response = await apiClient.listModels(auth);
      setItems(response.items || []);
    } catch (e) {
      setError(normalizeApiError(e, t("models_load_failed")));
      setItems([]);
    } finally {
      if (background) {
        setRefreshing(false);
      } else {
        setLoading(false);
      }
    }
  }

  useEffect(() => {
    load();
    const timerId = window.setInterval(() => {
      load({ background: true });
    }, REFRESH_INTERVAL_MS);
    return () => {
      window.clearInterval(timerId);
    };
  }, []);

  const columns = useMemo(
    () => [{ field: "label", headerName: t("models_col_label"), minWidth: 220, flex: 1 }],
    [t]
  );

  return (
    <Stack spacing={2} sx={{ flex: 1, minHeight: 0, overflow: "hidden" }}>
      <Stack spacing={0.5}>
        <Typography variant="h4">{t("models_title")}</Typography>
        <Typography variant="body2" color="text.secondary">
          {t("models_subtitle")}
        </Typography>
      </Stack>
      <Box sx={{ display: "flex", justifyContent: "flex-end" }}>
        <Button variant="contained" onClick={() => load({ background: true })} disabled={loading || refreshing}>
          {refreshing ? t("models_refreshing") : t("models_refresh")}
        </Button>
      </Box>
      <Card sx={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>
        <CardContent sx={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>
          {loading ? <LoadingBlock text={t("models_loading")} /> : null}
          {!loading && error ? <ErrorBlock message={error} onRetry={() => load()} /> : null}
          {!loading && !error && items.length === 0 ? <EmptyBlock text={t("models_empty")} /> : null}
          {!loading && !error && items.length > 0 ? (
            <Box sx={{ flex: 1, minHeight: 0 }}>
              <DataGrid
                sx={compactGridSx}
                rows={items}
                columns={columns}
                getRowId={(row) => row.id}
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
