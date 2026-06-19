import { useEffect, useMemo, useState } from "react";
import { Box, Button, Dialog, DialogActions, DialogContent, DialogTitle, MenuItem, Stack, Tab, Tabs, TextField, Typography } from "@mui/material";
import { DataGrid } from "@mui/x-data-grid/DataGrid";
import dayjs from "dayjs";
import { apiClient } from "../api/client";
import { normalizeApiError } from "../api/errors";
import DateRangeFilterField from "../components/DateRangeFilterField";
import { EmptyBlock, ErrorBlock, LoadingBlock } from "../components/StateBlocks";
import { useLocale } from "../i18n/locale";
import { COMPACT_MAIN_PAGE_SIZE_OPTIONS, compactGridProps, compactGridSx } from "../utils/compactDataGrid";
import { formatDateTimeInTaipei } from "../utils/datetime";
import { getGridLocaleText } from "../utils/gridLocaleText";

function formatTs(value, locale) {
  return formatDateTimeInTaipei(value, { locale });
}

function defaultHotRange() {
  const to = dayjs();
  const from = to.subtract(6, "day");
  return { from: from.format("YYYY-MM-DD"), to: to.format("YYYY-MM-DD") };
}

const TAB_OPERATION = "operation";
const TAB_LOGIN = "login";
const TAB_SCHEDULER = "scheduler";
const SCHEDULER_FILE_MODE_DATE = "date";
const SCHEDULER_FILE_MODE_ALL = "all";
const SCHEDULER_FILE_MODE_LATEST = "latest";
const OPERATION_EVENT_TYPE_OPTIONS = [
  "api_key",
  "api_key_application",
  "admin_management",
  "institute_sync",
  "limit_strategy_config",
  "user_lookup",
  "whitelist",
];
const OPERATION_ACTION_OPTIONS = [
  "admin_create",
  "create",
  "delete",
  "disable",
  "enable",
  "extend",
  "proxy_application",
  "renew",
  "revoke",
  "sync",
  "update",
  "whitelist_create",
];
const OPERATION_TARGET_TYPE_OPTIONS = [
  "admin",
  "api_key",
  "api_key_application",
  "institute",
  "limit_strategy_config",
  "user_search",
  "whitelist",
];

const operationSortFields = new Set([
  "created_at",
  "event_type",
  "action",
  "result",
  "actor_account",
  "target_type",
  "target_id",
  "error_code",
  "request_id",
]);

const loginSortFields = new Set([
  "created_at",
  "provider",
  "result",
  "account",
  "sysid",
  "role",
  "error_code",
  "request_id",
]);

export default function OperationAuditLogsPage({ auth }) {
  const { locale, t } = useLocale();
  const gridLocaleText = getGridLocaleText(locale);
  const hot = useMemo(defaultHotRange, []);
  const [activeTab, setActiveTab] = useState(TAB_OPERATION);

  const [operationItems, setOperationItems] = useState([]);
  const [operationTotal, setOperationTotal] = useState(0);
  const [operationPage, setOperationPage] = useState(0);
  const [operationPageSize, setOperationPageSize] = useState(10);
  const [operationFromDate, setOperationFromDate] = useState(hot.from);
  const [operationToDate, setOperationToDate] = useState(hot.to);
  const [operationEventType, setOperationEventType] = useState("");
  const [operationAction, setOperationAction] = useState("");
  const [operationResult, setOperationResult] = useState("");
  const [operationActorAccount, setOperationActorAccount] = useState("");
  const [operationTargetType, setOperationTargetType] = useState("");
  const [operationSortModel, setOperationSortModel] = useState([{ field: "created_at", sort: "desc" }]);
  const [operationLoading, setOperationLoading] = useState(true);
  const [operationError, setOperationError] = useState("");
  const [selectedOperationLog, setSelectedOperationLog] = useState(null);
  const [selectedSchedulerLog, setSelectedSchedulerLog] = useState(null);

  const [loginItems, setLoginItems] = useState([]);
  const [loginTotal, setLoginTotal] = useState(0);
  const [loginPage, setLoginPage] = useState(0);
  const [loginPageSize, setLoginPageSize] = useState(10);
  const [loginFromDate, setLoginFromDate] = useState(hot.from);
  const [loginToDate, setLoginToDate] = useState(hot.to);
  const [loginResult, setLoginResult] = useState("");
  const [loginAccount, setLoginAccount] = useState("");
  const [loginSysid, setLoginSysid] = useState("");
  const [loginRole, setLoginRole] = useState("");
  const [loginSortModel, setLoginSortModel] = useState([{ field: "created_at", sort: "desc" }]);
  const [loginLoading, setLoginLoading] = useState(true);
  const [loginError, setLoginError] = useState("");

  const [schedulerItems, setSchedulerItems] = useState([]);
  const [schedulerTotal, setSchedulerTotal] = useState(0);
  const [schedulerPage, setSchedulerPage] = useState(0);
  const [schedulerPageSize, setSchedulerPageSize] = useState(10);
  const [schedulerFileMode, setSchedulerFileMode] = useState(SCHEDULER_FILE_MODE_DATE);
  const [schedulerAvailableFiles, setSchedulerAvailableFiles] = useState([]);
  const [schedulerSelectedFile, setSchedulerSelectedFile] = useState("");
  const [schedulerFromDate, setSchedulerFromDate] = useState(hot.from);
  const [schedulerToDate, setSchedulerToDate] = useState(hot.to);
  const [schedulerJob, setSchedulerJob] = useState("");
  const [schedulerLevel, setSchedulerLevel] = useState("");
  const [schedulerKeyword, setSchedulerKeyword] = useState("");
  const [schedulerSortModel, setSchedulerSortModel] = useState([{ field: "timestamp", sort: "desc" }]);
  const [schedulerLoading, setSchedulerLoading] = useState(true);
  const [schedulerError, setSchedulerError] = useState("");

  function clearOperationFilters() {
    setOperationFromDate(hot.from);
    setOperationToDate(hot.to);
    setOperationEventType("");
    setOperationAction("");
    setOperationResult("");
    setOperationActorAccount("");
    setOperationTargetType("");
    setOperationPage(0);
  }

  function clearLoginFilters() {
    setLoginFromDate(hot.from);
    setLoginToDate(hot.to);
    setLoginResult("");
    setLoginAccount("");
    setLoginSysid("");
    setLoginRole("");
    setLoginPage(0);
  }

  function clearSchedulerFilters() {
    setSchedulerFileMode(SCHEDULER_FILE_MODE_DATE);
    setSchedulerAvailableFiles([]);
    setSchedulerSelectedFile("");
    setSchedulerFromDate(hot.from);
    setSchedulerToDate(hot.to);
    setSchedulerJob("");
    setSchedulerLevel("");
    setSchedulerKeyword("");
    setSchedulerPage(0);
  }

  const operationColumns = useMemo(
    () => [
      { field: "created_at", headerName: t("auditlogs_col_created_at"), minWidth: 190, flex: 1.2, valueFormatter: (v) => formatTs(v, locale), filterable: false },
      { field: "event_type", headerName: t("auditlogs_col_event_type"), minWidth: 150, flex: 1, filterable: false },
      { field: "action", headerName: t("auditlogs_col_action"), minWidth: 120, flex: 0.9, filterable: false },
      { field: "result", headerName: t("auditlogs_col_result"), minWidth: 110, flex: 0.8, filterable: false },
      { field: "actor_account", headerName: t("auditlogs_col_actor_account"), minWidth: 130, flex: 1, filterable: false },
      { field: "target_type", headerName: t("auditlogs_col_target_type"), minWidth: 130, flex: 1, filterable: false },
      { field: "target_id", headerName: t("auditlogs_col_target_id"), minWidth: 160, flex: 1.2, filterable: false },
      { field: "error_code", headerName: t("auditlogs_col_error_code"), minWidth: 160, flex: 1.2, filterable: false },
      {
        field: "detail_action",
        headerName: t("auditlogs_col_detail"),
        minWidth: 140,
        sortable: false,
        filterable: false,
        renderCell: (params) =>
          params.row.result === "failure" ? (
            <Button size="small" onClick={() => setSelectedOperationLog(params.row)}>
              {t("auditlogs_view_detail")}
            </Button>
          ) : (
            t("auditlogs_no_detail")
          ),
      },
    ],
    [locale, t]
  );

  const loginColumns = useMemo(
    () => [
      { field: "created_at", headerName: t("auditlogs_col_created_at"), minWidth: 190, flex: 1.2, valueFormatter: (v) => formatTs(v, locale), filterable: false },
      { field: "provider", headerName: t("loginlogs_col_provider"), minWidth: 130, flex: 1, filterable: false },
      { field: "result", headerName: t("auditlogs_col_result"), minWidth: 110, flex: 0.8, filterable: false },
      { field: "account", headerName: t("loginlogs_col_account"), minWidth: 140, flex: 1, filterable: false },
      { field: "sysid", headerName: t("loginlogs_col_sysid"), minWidth: 110, flex: 0.8, filterable: false },
      { field: "role", headerName: t("loginlogs_col_role"), minWidth: 110, flex: 0.8, filterable: false },
      { field: "error_code", headerName: t("auditlogs_col_error_code"), minWidth: 160, flex: 1.2, filterable: false },
      { field: "request_id", headerName: t("loginlogs_col_request_id"), minWidth: 220, flex: 1.4, filterable: false },
    ],
    [locale, t]
  );

  const schedulerColumns = useMemo(
    () => [
      { field: "timestamp", headerName: t("schedulerlogs_col_timestamp"), minWidth: 190, flex: 1.2, valueFormatter: (v) => formatTs(v, locale), filterable: false },
      { field: "job", headerName: t("schedulerlogs_col_job"), minWidth: 220, flex: 1.2, sortable: false, filterable: false },
      { field: "source_file", headerName: t("schedulerlogs_col_source_file"), minWidth: 180, flex: 1, sortable: false, filterable: false },
      { field: "level", headerName: t("schedulerlogs_col_level"), minWidth: 120, flex: 0.8, sortable: false, filterable: false },
      { field: "message", headerName: t("schedulerlogs_col_message"), minWidth: 360, flex: 2, sortable: false, filterable: false },
      {
        field: "raw_line_action",
        headerName: t("schedulerlogs_col_raw_line"),
        minWidth: 160,
        sortable: false,
        filterable: false,
        renderCell: (params) => (
          <Button size="small" onClick={() => setSelectedSchedulerLog(params.row)}>
            {t("schedulerlogs_view_raw_line")}
          </Button>
        ),
      },
    ],
    [locale, t]
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
            action: operationAction || undefined,
            result: operationResult || undefined,
            actor_account: operationActorAccount || undefined,
            target_type: operationTargetType || undefined,
            sort_by: operationSortFields.has(operationSortModel[0]?.field) ? operationSortModel[0].field : "created_at",
            sort_dir: operationSortModel[0]?.sort === "asc" ? "asc" : "desc",
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
        setOperationError(normalizeApiError(e, t("auditlogs_load_failed")));
      } finally {
        if (!cancelled) setOperationLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [
    auth,
    operationAction,
    operationActorAccount,
    operationEventType,
    operationFromDate,
    operationPage,
    operationPageSize,
    operationResult,
    operationSortModel,
    operationTargetType,
    operationToDate,
    t
  ]);

  useEffect(() => {
    if (!selectedSchedulerLog) return;
    const latest = schedulerItems.find((item) => item.id === selectedSchedulerLog.id);
    if (!latest) {
      setSelectedSchedulerLog(null);
    } else if (latest !== selectedSchedulerLog) {
      setSelectedSchedulerLog(latest);
    }
  }, [schedulerItems, selectedSchedulerLog]);

  useEffect(() => {
    if (!selectedOperationLog) return;
    const latest = operationItems.find((item) => item.id === selectedOperationLog.id);
    if (!latest) {
      setSelectedOperationLog(null);
    } else if (latest !== selectedOperationLog) {
      setSelectedOperationLog(latest);
    }
  }, [operationItems, selectedOperationLog]);

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
            result: loginResult || undefined,
            account: loginAccount || undefined,
            sysid: loginSysid.trim() ? loginSysid.trim() : undefined,
            role: loginRole || undefined,
            sort_by: loginSortFields.has(loginSortModel[0]?.field) ? loginSortModel[0].field : "created_at",
            sort_dir: loginSortModel[0]?.sort === "asc" ? "asc" : "desc",
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
        setLoginError(normalizeApiError(e, t("loginlogs_load_failed")));
      } finally {
        if (!cancelled) setLoginLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [
    auth,
    loginAccount,
    loginFromDate,
    loginPage,
    loginPageSize,
    loginResult,
    loginRole,
    loginSortModel,
    loginSysid,
    loginToDate,
    t
  ]);

  useEffect(() => {
    if (auth.role !== "admin") return;
    let cancelled = false;
    async function load() {
      setSchedulerLoading(true);
      setSchedulerError("");
      try {
        const response = await apiClient.listSchedulerLogs(
          {
            page: schedulerPage + 1,
            page_size: schedulerPageSize,
            file_mode: schedulerFileMode,
            from: schedulerFileMode === SCHEDULER_FILE_MODE_DATE ? schedulerFromDate || undefined : undefined,
            to: schedulerFileMode === SCHEDULER_FILE_MODE_DATE ? schedulerToDate || undefined : undefined,
            job: schedulerJob || undefined,
            level: schedulerLevel || undefined,
            q: schedulerKeyword || undefined,
            sort_dir: schedulerSortModel[0]?.sort === "asc" ? "asc" : "desc",
          },
          auth
        );
        if (cancelled) return;
        setSchedulerAvailableFiles(response.available_files || []);
        setSchedulerItems((response.items || []).map((item) => ({ ...item, id: item.id })));
        setSchedulerTotal(response.total || 0);
      } catch (e) {
        if (cancelled) return;
        setSchedulerAvailableFiles([]);
        setSchedulerItems([]);
        setSchedulerTotal(0);
        setSchedulerError(normalizeApiError(e, t("schedulerlogs_load_failed")));
      } finally {
        if (!cancelled) setSchedulerLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [
    auth,
    schedulerFileMode,
    schedulerFromDate,
    schedulerJob,
    schedulerKeyword,
    schedulerLevel,
    schedulerPage,
    schedulerPageSize,
    schedulerSortModel,
    schedulerToDate,
    t
  ]);

  useEffect(() => {
    if (schedulerFileMode !== SCHEDULER_FILE_MODE_DATE) {
      if (schedulerSelectedFile) setSchedulerSelectedFile("");
      return;
    }
    if (!schedulerJob) {
      setSchedulerSelectedFile("");
      setSchedulerFromDate(hot.from);
      setSchedulerToDate(hot.to);
      return;
    }
    if (schedulerAvailableFiles.length === 0) {
      setSchedulerSelectedFile("");
      return;
    }
    const matched = schedulerAvailableFiles.find((item) => item.source_file === schedulerSelectedFile);
    const nextFile = matched || schedulerAvailableFiles[0];
    if (!matched || schedulerSelectedFile !== nextFile.source_file || schedulerFromDate !== nextFile.log_date || schedulerToDate !== nextFile.log_date) {
      setSchedulerSelectedFile(nextFile.source_file);
      setSchedulerFromDate(nextFile.log_date);
      setSchedulerToDate(nextFile.log_date);
      setSchedulerPage(0);
    }
  }, [hot.from, hot.to, schedulerAvailableFiles, schedulerFileMode, schedulerFromDate, schedulerJob, schedulerSelectedFile, schedulerToDate]);

  if (auth.role !== "admin") {
    return (
      <Stack spacing={3}>
        <Typography variant="h4">{t("auditlogs_title")}</Typography>
        <ErrorBlock message={t("auditlogs_forbidden")} />
      </Stack>
    );
  }

  return (
    <Stack spacing={2} sx={{ flex: 1, minHeight: 0, overflow: "hidden" }}>
      <Typography variant="h4">{t("auditlogs_title")}</Typography>
      <Tabs value={activeTab} onChange={(_, value) => setActiveTab(value)} aria-label={t("auditlogs_tabs_aria")}>
        <Tab value={TAB_OPERATION} label={t("auditlogs_tab_operation")} />
        <Tab value={TAB_LOGIN} label={t("auditlogs_tab_login")} />
        <Tab value={TAB_SCHEDULER} label={t("auditlogs_tab_scheduler")} />
      </Tabs>

      {activeTab === TAB_OPERATION ? (
        <>
          <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} useFlexGap flexWrap="wrap" sx={{ flexShrink: 0 }}>
            <DateRangeFilterField
              label={t("auditlogs_from")}
              fromValue={operationFromDate}
              toValue={operationToDate}
              startLabel={t("auditlogs_from")}
              endLabel={t("auditlogs_to")}
              clearLabel={t("common_clear")}
              closeLabel={t("common_close")}
              onChange={({ from, to }) => {
                setOperationFromDate(from);
                setOperationToDate(to);
                setOperationPage(0);
              }}
            />
            <TextField
              select
              label={t("auditlogs_event_type")}
              value={operationEventType}
              onChange={(e) => {
                setOperationEventType(e.target.value);
                setOperationPage(0);
              }}
              sx={{ minWidth: 180 }}
            >
              <MenuItem value="">{t("auditlogs_result_all")}</MenuItem>
              {OPERATION_EVENT_TYPE_OPTIONS.map((value) => (
                <MenuItem key={value} value={value}>
                  {value}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              select
              label={t("auditlogs_action")}
              value={operationAction}
              onChange={(e) => {
                setOperationAction(e.target.value);
                setOperationPage(0);
              }}
              sx={{ minWidth: 180 }}
            >
              <MenuItem value="">{t("auditlogs_result_all")}</MenuItem>
              {OPERATION_ACTION_OPTIONS.map((value) => (
                <MenuItem key={value} value={value}>
                  {value}
                </MenuItem>
              ))}
            </TextField>
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
            <TextField
              label={t("auditlogs_actor_account")}
              value={operationActorAccount}
              onChange={(e) => {
                setOperationActorAccount(e.target.value);
                setOperationPage(0);
              }}
            />
            <TextField
              select
              label={t("auditlogs_target_type")}
              value={operationTargetType}
              onChange={(e) => {
                setOperationTargetType(e.target.value);
                setOperationPage(0);
              }}
              sx={{ minWidth: 180 }}
            >
              <MenuItem value="">{t("auditlogs_result_all")}</MenuItem>
              {OPERATION_TARGET_TYPE_OPTIONS.map((value) => (
                <MenuItem key={value} value={value}>
                  {value}
                </MenuItem>
              ))}
            </TextField>
            <Button variant="outlined" onClick={clearOperationFilters}>
              {t("common_clear")}
            </Button>
          </Stack>

          {operationLoading ? <LoadingBlock text={t("auditlogs_loading")} /> : null}
          {!operationLoading && operationError ? <ErrorBlock message={operationError} /> : null}
          {!operationLoading && !operationError && operationItems.length === 0 ? <EmptyBlock text={t("auditlogs_empty")} /> : null}
          {!operationLoading && !operationError && operationItems.length > 0 ? (
            <Box sx={{ flex: 1, minHeight: 0, overflow: "hidden", backgroundColor: "white", borderRadius: 2, p: 0.5 }}>
              <DataGrid
                sx={compactGridSx}
                rows={operationItems}
                columns={operationColumns}
                paginationMode="server"
                sortingMode="server"
                rowCount={operationTotal}
                paginationModel={{ page: operationPage, pageSize: operationPageSize }}
                sortModel={operationSortModel}
                onPaginationModelChange={(model) => {
                  setOperationPage(model.page);
                  setOperationPageSize(model.pageSize);
                }}
                onSortModelChange={(model) => {
                  setOperationSortModel(model);
                  setOperationPage(0);
                }}
                pageSizeOptions={COMPACT_MAIN_PAGE_SIZE_OPTIONS}
                disableRowSelectionOnClick
                {...compactGridProps}
                localeText={gridLocaleText}
              />
            </Box>
          ) : null}
        </>
      ) : null}

      {activeTab === TAB_LOGIN ? (
        <>
          <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} useFlexGap flexWrap="wrap" sx={{ flexShrink: 0 }}>
            <DateRangeFilterField
              label={t("auditlogs_from")}
              fromValue={loginFromDate}
              toValue={loginToDate}
              startLabel={t("auditlogs_from")}
              endLabel={t("auditlogs_to")}
              clearLabel={t("common_clear")}
              closeLabel={t("common_close")}
              onChange={({ from, to }) => {
                setLoginFromDate(from);
                setLoginToDate(to);
                setLoginPage(0);
              }}
            />
            <TextField
              label={t("loginlogs_account")}
              value={loginAccount}
              onChange={(e) => {
                setLoginAccount(e.target.value);
                setLoginPage(0);
              }}
            />
            <TextField
              label={t("loginlogs_sysid")}
              value={loginSysid}
              onChange={(e) => {
                setLoginSysid(e.target.value.replace(/\D+/g, ""));
                setLoginPage(0);
              }}
            />
            <TextField
              label={t("loginlogs_role")}
              value={loginRole}
              onChange={(e) => {
                setLoginRole(e.target.value);
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
            <Button variant="outlined" onClick={clearLoginFilters}>
              {t("common_clear")}
            </Button>
          </Stack>

          {loginLoading ? <LoadingBlock text={t("loginlogs_loading")} /> : null}
          {!loginLoading && loginError ? <ErrorBlock message={loginError} /> : null}
          {!loginLoading && !loginError && loginItems.length === 0 ? <EmptyBlock text={t("loginlogs_empty")} /> : null}
          {!loginLoading && !loginError && loginItems.length > 0 ? (
            <Box sx={{ flex: 1, minHeight: 0, overflow: "hidden", backgroundColor: "white", borderRadius: 2, p: 0.5 }}>
              <DataGrid
                sx={compactGridSx}
                rows={loginItems}
                columns={loginColumns}
                paginationMode="server"
                sortingMode="server"
                rowCount={loginTotal}
                paginationModel={{ page: loginPage, pageSize: loginPageSize }}
                sortModel={loginSortModel}
                onPaginationModelChange={(model) => {
                  setLoginPage(model.page);
                  setLoginPageSize(model.pageSize);
                }}
                onSortModelChange={(model) => {
                  setLoginSortModel(model);
                  setLoginPage(0);
                }}
                pageSizeOptions={COMPACT_MAIN_PAGE_SIZE_OPTIONS}
                disableRowSelectionOnClick
                {...compactGridProps}
                localeText={gridLocaleText}
              />
            </Box>
          ) : null}
        </>
      ) : null}

      {activeTab === TAB_SCHEDULER ? (
        <>
          <Stack direction={{ xs: "column", md: "row" }} spacing={1.5} useFlexGap flexWrap="wrap" sx={{ flexShrink: 0 }}>
            <TextField
              select
              label={t("schedulerlogs_file_mode")}
              value={schedulerFileMode}
              onChange={(e) => {
                setSchedulerFileMode(e.target.value);
                setSchedulerAvailableFiles([]);
                setSchedulerSelectedFile("");
                setSchedulerPage(0);
              }}
              sx={{ minWidth: 180 }}
            >
              <MenuItem value={SCHEDULER_FILE_MODE_DATE}>{t("schedulerlogs_file_mode_date")}</MenuItem>
              <MenuItem value={SCHEDULER_FILE_MODE_ALL}>{t("schedulerlogs_file_mode_all")}</MenuItem>
              <MenuItem value={SCHEDULER_FILE_MODE_LATEST}>{t("schedulerlogs_file_mode_latest")}</MenuItem>
            </TextField>
            <TextField
              select
              label={t("schedulerlogs_job")}
              value={schedulerJob}
              onChange={(e) => {
                setSchedulerJob(e.target.value);
                setSchedulerSelectedFile("");
                setSchedulerPage(0);
              }}
              sx={{ minWidth: 220 }}
            >
              <MenuItem value="">{t("auditlogs_result_all")}</MenuItem>
              <MenuItem value="sync_expired_api_keys">sync_expired_api_keys</MenuItem>
              <MenuItem value="sync_api_key_usage">sync_api_key_usage</MenuItem>
              <MenuItem value="send_expiration_reminders">send_expiration_reminders</MenuItem>
            </TextField>
            {schedulerFileMode === SCHEDULER_FILE_MODE_DATE ? (
              <TextField
                select
                label={t("schedulerlogs_file")}
                value={schedulerSelectedFile}
                onChange={(e) => {
                  const nextFile = schedulerAvailableFiles.find((item) => item.source_file === e.target.value);
                  setSchedulerSelectedFile(e.target.value);
                  setSchedulerFromDate(nextFile?.log_date || "");
                  setSchedulerToDate(nextFile?.log_date || "");
                  setSchedulerPage(0);
                }}
                sx={{ minWidth: 220 }}
                disabled={!schedulerJob || schedulerAvailableFiles.length === 0}
                helperText={
                  !schedulerJob
                    ? t("schedulerlogs_file_select_job_first")
                    : schedulerAvailableFiles.length === 0
                      ? t("schedulerlogs_file_empty")
                      : undefined
                }
              >
                {schedulerAvailableFiles.map((item) => (
                  <MenuItem key={item.source_file} value={item.source_file}>
                    {item.source_file}
                  </MenuItem>
                ))}
              </TextField>
            ) : null}
            <TextField
              select
              label={t("schedulerlogs_level")}
              value={schedulerLevel}
              onChange={(e) => {
                setSchedulerLevel(e.target.value);
                setSchedulerPage(0);
              }}
              sx={{ minWidth: 160 }}
            >
              <MenuItem value="">{t("auditlogs_result_all")}</MenuItem>
              <MenuItem value="INFO">INFO</MenuItem>
              <MenuItem value="WARNING">WARNING</MenuItem>
              <MenuItem value="ERROR">ERROR</MenuItem>
              <MenuItem value="CRITICAL">CRITICAL</MenuItem>
            </TextField>
            <TextField
              label={t("schedulerlogs_keyword")}
              value={schedulerKeyword}
              onChange={(e) => {
                setSchedulerKeyword(e.target.value);
                setSchedulerPage(0);
              }}
            />
            <Button
              variant="outlined"
              onClick={clearSchedulerFilters}
              sx={{ height: 56, alignSelf: { xs: "stretch", md: "flex-start" } }}
            >
              {t("common_clear")}
            </Button>
          </Stack>

          {schedulerLoading ? <LoadingBlock text={t("schedulerlogs_loading")} /> : null}
          {!schedulerLoading && schedulerError ? <ErrorBlock message={schedulerError} /> : null}
          {!schedulerLoading && !schedulerError && schedulerItems.length === 0 ? <EmptyBlock text={t("schedulerlogs_empty")} /> : null}
          {!schedulerLoading && !schedulerError && schedulerItems.length > 0 ? (
            <Box sx={{ flex: 1, minHeight: 0, overflow: "hidden", backgroundColor: "white", borderRadius: 2, p: 0.5 }}>
              <DataGrid
                sx={compactGridSx}
                rows={schedulerItems}
                columns={schedulerColumns}
                paginationMode="server"
                sortingMode="server"
                rowCount={schedulerTotal}
                paginationModel={{ page: schedulerPage, pageSize: schedulerPageSize }}
                sortModel={schedulerSortModel}
                onPaginationModelChange={(model) => {
                  setSchedulerPage(model.page);
                  setSchedulerPageSize(model.pageSize);
                }}
                onSortModelChange={(model) => {
                  setSchedulerSortModel(model.length ? model : [{ field: "timestamp", sort: "desc" }]);
                  setSchedulerPage(0);
                }}
                pageSizeOptions={COMPACT_MAIN_PAGE_SIZE_OPTIONS}
                disableRowSelectionOnClick
                {...compactGridProps}
                localeText={gridLocaleText}
              />
            </Box>
          ) : null}
        </>
      ) : null}

      <Dialog open={Boolean(selectedOperationLog)} onClose={() => setSelectedOperationLog(null)} fullWidth maxWidth="sm">
        <DialogTitle>{t("auditlogs_detail_title")}</DialogTitle>
        <DialogContent>
          {selectedOperationLog ? (
            <Stack spacing={2} sx={{ pt: 1 }}>
              <TextField label={t("auditlogs_col_error_code")} value={selectedOperationLog.error_code || ""} InputProps={{ readOnly: true }} />
              <TextField label={t("auditlogs_detail_request_id")} value={selectedOperationLog.request_id || ""} InputProps={{ readOnly: true }} />
              <TextField
                label={t("auditlogs_detail_error_detail")}
                value={selectedOperationLog.error_detail || ""}
                InputProps={{ readOnly: true }}
                multiline
                minRows={3}
              />
            </Stack>
          ) : null}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSelectedOperationLog(null)}>{t("common_close")}</Button>
        </DialogActions>
      </Dialog>

      <Dialog open={Boolean(selectedSchedulerLog)} onClose={() => setSelectedSchedulerLog(null)} fullWidth maxWidth="md">
        <DialogTitle>{t("schedulerlogs_detail_title")}</DialogTitle>
        <DialogContent>
          {selectedSchedulerLog ? (
            <Stack spacing={2} sx={{ pt: 1 }}>
              <TextField label={t("schedulerlogs_col_job")} value={selectedSchedulerLog.job || ""} InputProps={{ readOnly: true }} />
              <TextField label={t("schedulerlogs_col_source_file")} value={selectedSchedulerLog.source_file || ""} InputProps={{ readOnly: true }} />
              <TextField label={t("schedulerlogs_col_level")} value={selectedSchedulerLog.level || ""} InputProps={{ readOnly: true }} />
              <TextField
                label={t("schedulerlogs_col_raw_line")}
                value={selectedSchedulerLog.raw_line || ""}
                InputProps={{ readOnly: true }}
                multiline
                minRows={4}
              />
            </Stack>
          ) : null}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setSelectedSchedulerLog(null)}>{t("common_close")}</Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
