import { useEffect, useMemo, useState } from "react";
import { Box, Button, Card, CardContent, Stack, Typography } from "@mui/material";
import { DataGrid } from "@mui/x-data-grid";
import { apiClient } from "../api/client";
import { normalizeApiError } from "../api/errors";
import MarkdownRenderer from "../components/MarkdownRenderer";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlocks";
import { useLocale } from "../i18n/locale";
import { COMPACT_LOCAL_PAGE_SIZE_OPTIONS, compactGridProps, compactGridSx } from "../utils/compactDataGrid";
import guideEn from "../../../docs/service-usage-guide.en.md?raw";
import guideZhTw from "../../../docs/service-usage-guide.zh-TW.md?raw";

const REFRESH_INTERVAL_MS = 15 * 60 * 1000;

export default function ModelsPage({ auth }) {
  const { gridLocaleText, locale, t } = useLocale();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const guideMarkdown = locale === "zh-TW" ? guideZhTw : guideEn;

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
      <Box
        sx={{
          display: "grid",
          gridTemplateColumns: { xs: "1fr", md: "minmax(0, 1.8fr) minmax(320px, 1fr)" },
          gap: 2,
          flex: 1,
          minHeight: 0,
          alignItems: "stretch"
        }}
      >
        <Card sx={{ display: "flex", flexDirection: "column", minHeight: 0 }}>
          <CardContent sx={{ display: "flex", flexDirection: "column", gap: 2.5, flex: 1, minHeight: 0 }}>
            <Stack spacing={0.5}>
              <Typography variant="overline" color="text.secondary">
                {t("models_guide_section")}
              </Typography>
            </Stack>
            <MarkdownRenderer markdown={guideMarkdown} />
          </CardContent>
        </Card>
        <Card sx={{ display: "flex", flexDirection: "column", minHeight: 0 }}>
          <CardContent sx={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>
            <Stack spacing={1.5} sx={{ flex: 1, minHeight: 0 }}>
              <Stack direction="row" spacing={1} alignItems="center" justifyContent="space-between">
                <Stack spacing={0.5}>
                  <Typography variant="overline" color="text.secondary">
                    {t("models_models_section")}
                  </Typography>
                  <Typography variant="h6">{t("models_models_title")}</Typography>
                </Stack>
                <Button variant="contained" onClick={() => load({ background: true })} disabled={loading || refreshing}>
                  {refreshing ? t("models_refreshing") : t("models_refresh")}
                </Button>
              </Stack>
              {loading ? <LoadingBlock text={t("models_loading")} /> : null}
              {!loading && error ? <ErrorBlock message={error} onRetry={() => load()} /> : null}
              {!loading && !error && items.length === 0 ? <EmptyBlock text={t("models_empty")} /> : null}
              {!loading && !error && items.length > 0 ? (
                <Box sx={{ flex: 1, minHeight: 420 }}>
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
            </Stack>
          </CardContent>
        </Card>
      </Box>
    </Stack>
  );
}
