import { useEffect, useMemo, useState } from "react";
import { MenuItem, Stack, TextField, Typography } from "@mui/material";
import { DataGrid } from "@mui/x-data-grid";
import { DatePicker } from "@mui/x-date-pickers/DatePicker";
import dayjs from "dayjs";
import { apiClient } from "../api/client";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlocks";
import { useLocale } from "../i18n/locale";

function formatTs(value) {
  if (!value) return "-";
  const dt = dayjs(value);
  if (!dt.isValid()) return "-";
  return dt.format("YYYY-MM-DD HH:mm:ss");
}

function defaultHotRange() {
  const to = dayjs();
  const from = to.subtract(6, "day");
  return { from: from.format("YYYY-MM-DD"), to: to.format("YYYY-MM-DD") };
}

export default function OperationAuditLogsPage({ auth }) {
  const { gridLocaleText, t } = useLocale();
  const hot = useMemo(defaultHotRange, []);
  const [items, setItems] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(20);
  const [fromDate, setFromDate] = useState(hot.from);
  const [toDate, setToDate] = useState(hot.to);
  const [eventType, setEventType] = useState("");
  const [result, setResult] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const columns = useMemo(
    () => [
      { field: "created_at", headerName: t("auditlogs_col_created_at"), minWidth: 190, flex: 1.2, valueFormatter: (v) => formatTs(v) },
      { field: "event_type", headerName: t("auditlogs_col_event_type"), minWidth: 150, flex: 1 },
      { field: "action", headerName: t("auditlogs_col_action"), minWidth: 120, flex: 0.9 },
      { field: "result", headerName: t("auditlogs_col_result"), minWidth: 110, flex: 0.8 },
      { field: "actor_account", headerName: t("auditlogs_col_actor_account"), minWidth: 130, flex: 1 },
      { field: "target_type", headerName: t("auditlogs_col_target_type"), minWidth: 130, flex: 1 },
      { field: "target_id", headerName: t("auditlogs_col_target_id"), minWidth: 160, flex: 1.2 },
      { field: "error_code", headerName: t("auditlogs_col_error_code"), minWidth: 160, flex: 1.2 },
    ],
    [t]
  );

  useEffect(() => {
    if (auth.role !== "admin") return;
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError("");
      try {
        const response = await apiClient.listOperationAuditLogs(
          {
            page: page + 1,
            page_size: pageSize,
            from: fromDate || undefined,
            to: toDate || undefined,
            event_type: eventType || undefined,
            result: result || undefined,
          },
          auth
        );
        if (cancelled) return;
        setItems((response.items || []).map((item) => ({ ...item, id: item.id })));
        setTotal(response.total || 0);
      } catch (e) {
        if (cancelled) return;
        setItems([]);
        setTotal(0);
        setError(e?.payload?.error?.message || t("auditlogs_load_failed"));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [auth, page, pageSize, fromDate, toDate, eventType, result, t]);

  if (auth.role !== "admin") {
    return (
      <Stack spacing={3}>
        <Typography variant="h4">{t("auditlogs_title")}</Typography>
        <ErrorBlock message={t("auditlogs_forbidden")} />
      </Stack>
    );
  }

  return (
    <Stack spacing={3} sx={{ flex: 1, minHeight: 0 }}>
      <Typography variant="h4">{t("auditlogs_title")}</Typography>

      <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
        <DatePicker
          label={t("auditlogs_from")}
          value={fromDate ? dayjs(fromDate) : null}
          onChange={(value) => {
            setFromDate(value && value.isValid() ? value.format("YYYY-MM-DD") : "");
            setPage(0);
          }}
        />
        <DatePicker
          label={t("auditlogs_to")}
          value={toDate ? dayjs(toDate) : null}
          onChange={(value) => {
            setToDate(value && value.isValid() ? value.format("YYYY-MM-DD") : "");
            setPage(0);
          }}
        />
        <TextField
          label={t("auditlogs_event_type")}
          value={eventType}
          onChange={(e) => {
            setEventType(e.target.value);
            setPage(0);
          }}
        />
        <TextField
          select
          label={t("auditlogs_result")}
          value={result}
          onChange={(e) => {
            setResult(e.target.value);
            setPage(0);
          }}
          sx={{ minWidth: 160 }}
        >
          <MenuItem value="">{t("auditlogs_result_all")}</MenuItem>
          <MenuItem value="success">success</MenuItem>
          <MenuItem value="failure">failure</MenuItem>
        </TextField>
      </Stack>

      {loading ? <LoadingBlock text={t("auditlogs_loading")} /> : null}
      {!loading && error ? <ErrorBlock message={error} /> : null}
      {!loading && !error && items.length === 0 ? <EmptyBlock text={t("auditlogs_empty")} /> : null}
      {!loading && !error && items.length > 0 ? (
        <DataGrid
          sx={{ flex: 1, minHeight: 480 }}
          rows={items}
          columns={columns}
          paginationMode="server"
          rowCount={total}
          paginationModel={{ page, pageSize }}
          onPaginationModelChange={(model) => {
            setPage(model.page);
            setPageSize(model.pageSize);
          }}
          pageSizeOptions={[20, 50, 100]}
          disableRowSelectionOnClick
          localeText={gridLocaleText}
        />
      ) : null}
    </Stack>
  );
}
