import { useEffect, useMemo, useState } from "react";
import { MenuItem, Stack, Tab, Tabs, TextField, Typography } from "@mui/material";
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

const TAB_OPERATION = "operation";
const TAB_LOGIN = "login";

export default function OperationAuditLogsPage({ auth }) {
  const { gridLocaleText, t } = useLocale();
  const hot = useMemo(defaultHotRange, []);
  const [activeTab, setActiveTab] = useState(TAB_OPERATION);

  const [operationItems, setOperationItems] = useState([]);
  const [operationTotal, setOperationTotal] = useState(0);
  const [operationPage, setOperationPage] = useState(0);
  const [operationPageSize, setOperationPageSize] = useState(20);
  const [operationFromDate, setOperationFromDate] = useState(hot.from);
  const [operationToDate, setOperationToDate] = useState(hot.to);
  const [operationEventType, setOperationEventType] = useState("");
  const [operationResult, setOperationResult] = useState("");
  const [operationLoading, setOperationLoading] = useState(true);
  const [operationError, setOperationError] = useState("");

  const [loginItems, setLoginItems] = useState([]);
  const [loginTotal, setLoginTotal] = useState(0);
  const [loginPage, setLoginPage] = useState(0);
  const [loginPageSize, setLoginPageSize] = useState(20);
  const [loginFromDate, setLoginFromDate] = useState(hot.from);
  const [loginToDate, setLoginToDate] = useState(hot.to);
  const [loginProvider, setLoginProvider] = useState("");
  const [loginResult, setLoginResult] = useState("");
  const [loginLoading, setLoginLoading] = useState(true);
  const [loginError, setLoginError] = useState("");

  const operationColumns = useMemo(
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

  const loginColumns = useMemo(
    () => [
      { field: "created_at", headerName: t("auditlogs_col_created_at"), minWidth: 190, flex: 1.2, valueFormatter: (v) => formatTs(v) },
      { field: "provider", headerName: t("loginlogs_col_provider"), minWidth: 130, flex: 1 },
      { field: "result", headerName: t("auditlogs_col_result"), minWidth: 110, flex: 0.8 },
      { field: "account", headerName: t("loginlogs_col_account"), minWidth: 140, flex: 1 },
      { field: "sysid", headerName: t("loginlogs_col_sysid"), minWidth: 110, flex: 0.8 },
      { field: "role", headerName: t("loginlogs_col_role"), minWidth: 110, flex: 0.8 },
      { field: "error_code", headerName: t("auditlogs_col_error_code"), minWidth: 160, flex: 1.2 },
      { field: "request_id", headerName: t("loginlogs_col_request_id"), minWidth: 220, flex: 1.4 },
    ],
    [t]
  );

  useEffect(() => {
    if (auth.role !== "admin") return;
    let cancelled = false;
    async function load() {
      setOperationLoading(true);
      setOperationError("");
      try {
        const response = await apiClient.listOperationAuditLogs(
          {
            page: operationPage + 1,
            page_size: operationPageSize,
            from: operationFromDate || undefined,
            to: operationToDate || undefined,
            event_type: operationEventType || undefined,
            result: operationResult || undefined,
          },
          auth
        );
        if (cancelled) return;
        setOperationItems((response.items || []).map((item) => ({ ...item, id: item.id })));
        setOperationTotal(response.total || 0);
      } catch (e) {
        if (cancelled) return;
        setOperationItems([]);
        setOperationTotal(0);
        setOperationError(e?.payload?.error?.message || t("auditlogs_load_failed"));
      } finally {
        if (!cancelled) setOperationLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [auth, operationPage, operationPageSize, operationFromDate, operationToDate, operationEventType, operationResult, t]);

  useEffect(() => {
    if (auth.role !== "admin") return;
    let cancelled = false;
    async function load() {
      setLoginLoading(true);
      setLoginError("");
      try {
        const response = await apiClient.listAuthAuditLogs(
          {
            page: loginPage + 1,
            page_size: loginPageSize,
            from: loginFromDate || undefined,
            to: loginToDate || undefined,
            provider: loginProvider || undefined,
            result: loginResult || undefined,
          },
          auth
        );
        if (cancelled) return;
        setLoginItems((response.items || []).map((item) => ({ ...item, id: item.id })));
        setLoginTotal(response.total || 0);
      } catch (e) {
        if (cancelled) return;
        setLoginItems([]);
        setLoginTotal(0);
        setLoginError(e?.payload?.error?.message || t("loginlogs_load_failed"));
      } finally {
        if (!cancelled) setLoginLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [auth, loginPage, loginPageSize, loginFromDate, loginToDate, loginProvider, loginResult, t]);

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
      <Tabs value={activeTab} onChange={(_, value) => setActiveTab(value)} aria-label={t("auditlogs_tabs_aria")}>
        <Tab value={TAB_OPERATION} label={t("auditlogs_tab_operation")} />
        <Tab value={TAB_LOGIN} label={t("auditlogs_tab_login")} />
      </Tabs>

      {activeTab === TAB_OPERATION ? (
        <>
          <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
            <DatePicker
              label={t("auditlogs_from")}
              value={operationFromDate ? dayjs(operationFromDate) : null}
              onChange={(value) => {
                setOperationFromDate(value && value.isValid() ? value.format("YYYY-MM-DD") : "");
                setOperationPage(0);
              }}
            />
            <DatePicker
              label={t("auditlogs_to")}
              value={operationToDate ? dayjs(operationToDate) : null}
              onChange={(value) => {
                setOperationToDate(value && value.isValid() ? value.format("YYYY-MM-DD") : "");
                setOperationPage(0);
              }}
            />
            <TextField
              label={t("auditlogs_event_type")}
              value={operationEventType}
              onChange={(e) => {
                setOperationEventType(e.target.value);
                setOperationPage(0);
              }}
            />
            <TextField
              select
              label={t("auditlogs_result")}
              value={operationResult}
              onChange={(e) => {
                setOperationResult(e.target.value);
                setOperationPage(0);
              }}
              sx={{ minWidth: 160 }}
            >
              <MenuItem value="">{t("auditlogs_result_all")}</MenuItem>
              <MenuItem value="success">success</MenuItem>
              <MenuItem value="failure">failure</MenuItem>
            </TextField>
          </Stack>

          {operationLoading ? <LoadingBlock text={t("auditlogs_loading")} /> : null}
          {!operationLoading && operationError ? <ErrorBlock message={operationError} /> : null}
          {!operationLoading && !operationError && operationItems.length === 0 ? <EmptyBlock text={t("auditlogs_empty")} /> : null}
          {!operationLoading && !operationError && operationItems.length > 0 ? (
            <DataGrid
              sx={{ flex: 1, minHeight: 480 }}
              rows={operationItems}
              columns={operationColumns}
              paginationMode="server"
              rowCount={operationTotal}
              paginationModel={{ page: operationPage, pageSize: operationPageSize }}
              onPaginationModelChange={(model) => {
                setOperationPage(model.page);
                setOperationPageSize(model.pageSize);
              }}
              pageSizeOptions={[20, 50, 100]}
              disableRowSelectionOnClick
              localeText={gridLocaleText}
            />
          ) : null}
        </>
      ) : null}

      {activeTab === TAB_LOGIN ? (
        <>
          <Stack direction={{ xs: "column", md: "row" }} spacing={2}>
            <DatePicker
              label={t("auditlogs_from")}
              value={loginFromDate ? dayjs(loginFromDate) : null}
              onChange={(value) => {
                setLoginFromDate(value && value.isValid() ? value.format("YYYY-MM-DD") : "");
                setLoginPage(0);
              }}
            />
            <DatePicker
              label={t("auditlogs_to")}
              value={loginToDate ? dayjs(loginToDate) : null}
              onChange={(value) => {
                setLoginToDate(value && value.isValid() ? value.format("YYYY-MM-DD") : "");
                setLoginPage(0);
              }}
            />
            <TextField
              label={t("loginlogs_provider")}
              value={loginProvider}
              onChange={(e) => {
                setLoginProvider(e.target.value);
                setLoginPage(0);
              }}
            />
            <TextField
              select
              label={t("auditlogs_result")}
              value={loginResult}
              onChange={(e) => {
                setLoginResult(e.target.value);
                setLoginPage(0);
              }}
              sx={{ minWidth: 160 }}
            >
              <MenuItem value="">{t("auditlogs_result_all")}</MenuItem>
              <MenuItem value="success">success</MenuItem>
              <MenuItem value="failure">failure</MenuItem>
            </TextField>
          </Stack>

          {loginLoading ? <LoadingBlock text={t("loginlogs_loading")} /> : null}
          {!loginLoading && loginError ? <ErrorBlock message={loginError} /> : null}
          {!loginLoading && !loginError && loginItems.length === 0 ? <EmptyBlock text={t("loginlogs_empty")} /> : null}
          {!loginLoading && !loginError && loginItems.length > 0 ? (
            <DataGrid
              sx={{ flex: 1, minHeight: 480 }}
              rows={loginItems}
              columns={loginColumns}
              paginationMode="server"
              rowCount={loginTotal}
              paginationModel={{ page: loginPage, pageSize: loginPageSize }}
              onPaginationModelChange={(model) => {
                setLoginPage(model.page);
                setLoginPageSize(model.pageSize);
              }}
              pageSizeOptions={[20, 50, 100]}
              disableRowSelectionOnClick
              localeText={gridLocaleText}
            />
          ) : null}
        </>
      ) : null}
    </Stack>
  );
}
