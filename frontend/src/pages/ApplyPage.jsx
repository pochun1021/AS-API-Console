import { useEffect, useMemo, useRef, useState } from "react";
import CheckIcon from "@mui/icons-material/Check";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
import {
  Alert,
  CircularProgress,
  Box,
  Button,
  Card,
  CardContent,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  FormControlLabel,
  FormLabel,
  Grid,
  IconButton,
  Radio,
  RadioGroup,
  Stack,
  TextField,
  Tooltip,
  Typography
} from "@mui/material";
import { DatePicker } from "@mui/x-date-pickers/DatePicker";
import dayjs from "dayjs";
import { useNavigate } from "react-router-dom";
import { apiClient } from "../api/client";
import { useLocale } from "../i18n/locale";
import { API_KEY_APPLICATION_GO_LIVE_AT } from "../utils/apiKeyGoLive";
import { useDepartmentDisplay } from "../utils/departmentDisplay";
import { validatePersistedText } from "../utils/inputValidation";

function resolveValidationMessage(message, t) {
  const normalized = String(message || "").trim();
  if (!normalized) return t("apply_error_validation");
  if (normalized.startsWith("missing auth headers:")) {
    const fields = normalized
      .replace("missing auth headers:", "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean)
      .join(", ");
    return t("apply_error_missing_auth_headers", { fields });
  }
  if (normalized === "x-sysid must be numeric") {
    return t("apply_error_invalid_auth_sysid_numeric");
  }
  if (normalized === "x-sysid must be positive integer") {
    return t("apply_error_invalid_auth_sysid_positive");
  }
  if (normalized === "purpose is required") {
    return t("apply_error_required_purpose");
  }
  if (normalized === "purpose contains unsafe syntax") {
    return t("apply_error_unsafe_purpose");
  }
  if (normalized === "target_identity.account is required for admin proxy submission") {
    return t("apply_error_required_proxy_identity");
  }
  if (normalized === "target_identity.account is required") {
    return t("apply_error_required_proxy_identity");
  }
  if (normalized === "target_identity.account contains unsafe syntax") {
    return t("apply_error_unsafe_proxy_identity");
  }
  if (normalized === "target account not found") {
    return t("apply_proxy_lookup_not_found");
  }
  if (normalized === "target account is not unique") {
    return t("apply_proxy_lookup_not_unique");
  }
  if (normalized === "invalid role") {
    return t("apply_error_invalid_auth_role");
  }
  return normalized;
}

function toErrorMessage(error, t) {
  const code = error?.payload?.error?.code;
  const rawMessage = error?.payload?.error?.message || error?.message || "";
  const map = {
    APPLICANT_NOT_ELIGIBLE: t("apply_error_not_eligible"),
    RESEARCH_LIST_SERVICE_UNAVAILABLE: t("apply_error_research_unavailable"),
    SOAP_SERVICE_UNAVAILABLE: t("apply_error_directory_unavailable"),
    DIRECTORY_SERVICE_UNAVAILABLE: t("apply_error_directory_unavailable"),
    INVALID_APPLICATION_DATE: t("apply_error_invalid_date"),
    INVALID_DURATION_DAYS: t("apply_error_invalid_duration"),
    VALIDATION_ERROR: resolveValidationMessage(rawMessage, t)
  };
  if (code && map[code]) return map[code];
  return rawMessage || t("error_request_failed");
}

async function copyText(text) {
  if (!window.isSecureContext) {
    return { ok: false, reason: "insecure_context" };
  }

  if (!navigator?.clipboard?.writeText) {
    return { ok: false, reason: "clipboard_unavailable" };
  }

  try {
    await navigator.clipboard.writeText(text);
    return { ok: true };
  } catch (error) {
    if (error?.name === "NotAllowedError") {
      return { ok: false, reason: "permission_denied" };
    }

    return { ok: false, reason: "unknown" };
  }
}

function handlePersistentDialogClose(reason, closeDialog) {
  if (reason === "backdropClick" || reason === "escapeKeyDown") {
    return;
  }
  closeDialog();
}

export default function ApplyPage({ auth }) {
  const navigate = useNavigate();
  const { locale, t } = useLocale();
  const isZh = locale === "zh-TW";
  const { formatDepartment } = useDepartmentDisplay(auth);
  const today = useMemo(() => new Date().toISOString().slice(0, 10), []);
  const [form, setForm] = useState({ application_date: today, duration_days: 180, purpose: "" });
  const [proxyEnabled, setProxyEnabled] = useState(false);
  const [targetIdentity, setTargetIdentity] = useState({
    account: ""
  });
  const [targetProfile, setTargetProfile] = useState(null);
  const [lookupLoading, setLookupLoading] = useState(false);
  const [lookupError, setLookupError] = useState("");
  const [candidateDialogOpen, setCandidateDialogOpen] = useState(false);
  const [candidateItems, setCandidateItems] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [issued, setIssued] = useState(null);
  const [copySucceeded, setCopySucceeded] = useState(false);
  const [copyError, setCopyError] = useState("");
  const copyResetTimerRef = useRef(null);

  useEffect(() => () => {
    if (copyResetTimerRef.current) {
      clearTimeout(copyResetTimerRef.current);
    }
  }, []);

  const onChange = (key) => (event) => {
    const value = key === "duration_days" ? Number(event.target.value) : event.target.value;
    setForm((prev) => ({ ...prev, [key]: value }));
  };
  const onTargetChange = (key) => (event) => {
    const value = event.target.value;
    setTargetIdentity((prev) => ({ ...prev, [key]: value }));
    setLookupError("");
    setTargetProfile(null);
  };

  async function lookupTargetIdentity(rawAccount = targetIdentity.account) {
    if (!(auth.role === "admin" && proxyEnabled)) return;

    const keyword = String(rawAccount || "").trim();
    setLookupError("");
    setTargetProfile(null);
    setCandidateItems([]);
    setCandidateDialogOpen(false);
    if (!keyword) return;
    if (!validatePersistedText(keyword, { required: true }).ok) {
      setLookupError(t("apply_error_unsafe_proxy_identity"));
      return;
    }

    setLookupLoading(true);
    try {
      const response = await apiClient.searchUsers(keyword, auth, { lookup_context: "proxy_application" });
      const items = Array.isArray(response?.items) ? response.items : [];
      const exactMatches = items.filter((item) => String(item?.account || "").trim() === keyword);
      if (exactMatches.length === 1) {
        setTargetProfile(exactMatches[0]);
      } else if (items.length === 1) {
        setTargetProfile(items[0]);
      } else if (items.length > 1) {
        setCandidateItems(items);
        setCandidateDialogOpen(true);
      } else {
        setLookupError(t("apply_proxy_lookup_not_found"));
      }
    } catch (e) {
      const code = e?.payload?.error?.code;
      if (code === "SOAP_SERVICE_UNAVAILABLE" || code === "DIRECTORY_SERVICE_UNAVAILABLE") {
        setLookupError(t("apply_proxy_lookup_service_unavailable"));
      } else {
        setLookupError(toErrorMessage(e, t));
      }
    } finally {
      setLookupLoading(false);
    }
  }

  async function onSubmit(event) {
    event.preventDefault();
    setError("");

    if (!/^\d{4}-\d{2}-\d{2}$/.test(form.application_date) || form.application_date > today) {
      setError(t("apply_error_invalid_date"));
      return;
    }

    if (![30, 180, 360].includes(form.duration_days)) {
      setError(t("apply_error_invalid_duration"));
      return;
    }

    const purposeValidation = validatePersistedText(form.purpose, { required: true });
    if (!purposeValidation.ok) {
      setError(
        purposeValidation.reason === "required"
          ? t("apply_error_required_purpose")
          : t("apply_error_unsafe_purpose")
      );
      return;
    }
    if (auth.role === "admin" && proxyEnabled) {
      const targetAccountValidation = validatePersistedText(targetIdentity.account, { required: true });
      if (!targetAccountValidation.ok) {
        setError(
          targetAccountValidation.reason === "required"
            ? t("apply_error_required_proxy_identity")
            : t("apply_error_unsafe_proxy_identity")
        );
        return;
      }
      if (!targetProfile || String(targetProfile.account || "").trim() !== targetAccountValidation.value) {
        setError(t("apply_error_proxy_lookup_required"));
        return;
      }
    }
    setSubmitting(true);
    try {
      const payload = {
        application_date: form.application_date,
        duration_days: form.duration_days,
        purpose: purposeValidation.value
      };
      if (auth.role === "admin" && proxyEnabled) {
        payload.target_identity = {
          account: validatePersistedText(targetIdentity.account, { required: true }).value
        };
      }
      const response = await apiClient.createApplication(payload, auth);
      setIssued(response);
      setForm((prev) => ({ ...prev, purpose: "" }));
      setCopySucceeded(false);
      setCopyError("");
    } catch (e) {
      if (e?.payload?.error?.code === "APPLICATION_NOT_LIVE" && auth.role !== "admin") {
        navigate("/apply/coming-soon", {
          replace: true,
          state: {
            goLiveAt: typeof e?.payload?.go_live_at === "string"
              ? e.payload.go_live_at
              : API_KEY_APPLICATION_GO_LIVE_AT,
          },
        });
        return;
      }
      setError(toErrorMessage(e, t));
    } finally {
      setSubmitting(false);
    }
  }

  function closeIssuedDialog() {
    if (copyResetTimerRef.current) {
      clearTimeout(copyResetTimerRef.current);
      copyResetTimerRef.current = null;
    }
    setIssued(null);
    setCopySucceeded(false);
    setCopyError("");
  }

  async function onCopyKey(event) {
    if (!issued?.api_key_plaintext) {
      setCopyError(t("common_copy_error_key"));
      return;
    }

    const result = await copyText(issued.api_key_plaintext);
    if (!result.ok) {
      if (result.reason === "insecure_context") {
        setCopyError(t("common_copy_error_insecure_context"));
      } else if (result.reason === "clipboard_unavailable") {
        setCopyError(t("common_copy_error_clipboard_unavailable"));
      } else if (result.reason === "permission_denied") {
        setCopyError(t("common_copy_error_permission_denied"));
      } else {
        setCopyError(t("common_copy_error_key"));
      }
      return;
    }

    setCopySucceeded(true);
    setCopyError("");
    if (copyResetTimerRef.current) {
      clearTimeout(copyResetTimerRef.current);
    }
    copyResetTimerRef.current = setTimeout(() => {
      setCopySucceeded(false);
      copyResetTimerRef.current = null;
    }, 1500);
  }

  return (
    <Stack spacing={3}>
      <Typography variant="h4">{isZh ? "申請 API Key" : "Apply API Key"}</Typography>
      <Box sx={{ width: { xs: "100%", md: "1024px" }, ml: "auto !important", mr: "auto !important" }}>
        <Card>
          <CardContent>
            <Box component="form" onSubmit={onSubmit}>
              <Grid container spacing={2}>
                {auth.role === "admin" ? (
                  <Grid size={12}>
                    <FormControl>
                      <FormLabel id="proxy-apply-label">{t("apply_proxy_mode")}</FormLabel>
                      <RadioGroup
                        row
                        aria-labelledby="proxy-apply-label"
                        value={proxyEnabled ? "proxy" : "self"}
                        onChange={(event) => setProxyEnabled(event.target.value === "proxy")}
                      >
                        <FormControlLabel value="self" control={<Radio />} label={t("apply_proxy_self")} />
                        <FormControlLabel value="proxy" control={<Radio />} label={t("apply_proxy_for_other")} />
                      </RadioGroup>
                    </FormControl>
                  </Grid>
                ) : null}
                {auth.role === "admin" && proxyEnabled ? (
                  <Grid size={12}>
                    <Alert severity="info">{t("apply_proxy_account_lookup_hint")}</Alert>
                  </Grid>
                ) : null}
                {auth.role === "admin" && proxyEnabled && lookupError ? (
                  <Grid size={12}>
                    <Alert severity="error">{lookupError}</Alert>
                  </Grid>
                ) : null}
                <Grid size={{ xs: 12, md: 6 }}>
                  <TextField
                    fullWidth
                    label={isZh ? "帳號" : "Account"}
                    value={auth.role === "admin" && proxyEnabled ? targetIdentity.account : auth.account}
                    onChange={auth.role === "admin" && proxyEnabled ? onTargetChange("account") : undefined}
                    onBlur={auth.role === "admin" && proxyEnabled ? (event) => lookupTargetIdentity(event.target.value) : undefined}
                    InputProps={{
                      readOnly: !(auth.role === "admin" && proxyEnabled),
                      endAdornment: auth.role === "admin" && proxyEnabled && lookupLoading ? <CircularProgress size={18} /> : null
                    }}
                  />
                </Grid>
                <Grid size={{ xs: 12, md: 6 }}>
                  <TextField fullWidth label={isZh ? "姓名" : "Name"} value={auth.role === "admin" && proxyEnabled ? (targetProfile?.name || "") : auth.name} InputProps={{ readOnly: true }} />
                </Grid>
                <Grid size={{ xs: 12, md: 6 }}>
                  <TextField fullWidth label="Email" value={auth.role === "admin" && proxyEnabled ? (targetProfile?.email || "") : auth.email} InputProps={{ readOnly: true }} />
                </Grid>
                <Grid size={{ xs: 12, md: 6 }}>
                  <TextField
                    fullWidth
                    label={isZh ? "單位" : "Department"}
                    value={auth.role === "admin" && proxyEnabled ? formatDepartment(targetProfile?.department || "", locale) : formatDepartment(auth.department, locale)}
                    InputProps={{ readOnly: true }}
                  />
                </Grid>
                <Grid size={{ xs: 12, md: 6 }}>
                  <DatePicker
                    label={isZh ? "申請日期" : "Application Date"}
                    value={form.application_date ? dayjs(form.application_date) : null}
                    onChange={(value) => {
                      const next = value && value.isValid() ? value.format("YYYY-MM-DD") : "";
                      setForm((prev) => ({ ...prev, application_date: next }));
                    }}
                    maxDate={dayjs(today)}
                    slotProps={{
                      textField: {
                        fullWidth: true
                      }
                    }}
                  />
                </Grid>
                <Grid size={{ xs: 12, md: 6 }}>
                  <FormControl>
                    <FormLabel id="duration-days-label">{isZh ? "生效時長（天）" : "Duration (days)"}</FormLabel>
                    <RadioGroup
                      row
                      aria-labelledby="duration-days-label"
                      name="duration_days"
                      value={String(form.duration_days)}
                      onChange={onChange("duration_days")}
                    >
                      <FormControlLabel value="30" control={<Radio />} label={t("apply_duration_30_days")} />
                      <FormControlLabel value="180" control={<Radio />} label={t("apply_duration_180_days")} />
                      <FormControlLabel value="360" control={<Radio />} label={t("apply_duration_360_days")} />
                    </RadioGroup>
                  </FormControl>
                </Grid>
                <Grid size={12}><TextField fullWidth multiline minRows={3} label={isZh ? "用途" : "Purpose"} value={form.purpose} onChange={onChange("purpose")} /></Grid>
                {error && <Grid size={12}><Alert severity="error">{error}</Alert></Grid>}
                <Grid size={12}>
                  <Button variant="contained" type="submit" disabled={submitting}>{submitting ? (isZh ? "送出中..." : "Submitting...") : (isZh ? "送出申請" : "Submit")}</Button>
                </Grid>
              </Grid>
            </Box>
          </CardContent>
        </Card>
      </Box>

      <Dialog
        open={Boolean(issued)}
        disableEscapeKeyDown
        onClose={(_event, reason) => handlePersistentDialogClose(reason, closeIssuedDialog)}
      >
        <DialogTitle>{isZh ? "API Key 已建立" : "API Key Created"}</DialogTitle>
        <DialogContent>
          <>
            <Typography sx={{ mb: 1 }}>{isZh ? "此明文金鑰只會顯示一次，請立即保存。" : "This plaintext key is shown only once. Save it now."}</Typography>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
              <Typography sx={{ fontFamily: "monospace", bgcolor: "grey.100", p: 1, borderRadius: 1, flex: 1, userSelect: "text", wordBreak: "break-all" }}>
                {issued?.api_key_plaintext}
              </Typography>
              <Tooltip title={copySucceeded ? t("common_copied") : t("common_copy_key")}>
                <IconButton aria-label={copySucceeded ? t("common_copied_key") : t("common_copy_key")} onClick={onCopyKey}>
                  {copySucceeded ? <CheckIcon /> : <ContentCopyIcon />}
                </IconButton>
              </Tooltip>
            </Box>
            {copyError ? <Alert severity="error" sx={{ mt: 1 }}>{copyError}</Alert> : null}
          </>
        </DialogContent>
        <DialogActions>
          <Button onClick={closeIssuedDialog}>{isZh ? "我知道了" : "Saved"}</Button>
        </DialogActions>
      </Dialog>
      <Dialog open={candidateDialogOpen} onClose={() => setCandidateDialogOpen(false)} fullWidth maxWidth="md">
        <DialogTitle>{t("apply_proxy_pick_title")}</DialogTitle>
        <DialogContent>
          <Stack spacing={1.5} sx={{ mt: 1 }}>
            <Typography variant="body2">{t("apply_proxy_pick_hint")}</Typography>
            {candidateItems.map((item) => (
              <Box key={item.id || `${item.account}-${item.sysid}`} sx={{ p: 1.5, border: "1px solid", borderColor: "divider", borderRadius: 1 }}>
                <Typography variant="body2"><strong>{isZh ? "帳號" : "Account"}:</strong> {item.account || "-"}</Typography>
                <Typography variant="body2"><strong>{isZh ? "姓名" : "Name"}:</strong> {item.name || "-"}</Typography>
                <Typography variant="body2"><strong>Email:</strong> {item.email || "-"}</Typography>
                <Typography variant="body2"><strong>{isZh ? "單位" : "Department"}:</strong> {formatDepartment(item.department || "", locale) || "-"}</Typography>
                <Typography variant="body2"><strong>SysID:</strong> {item.sysid || "-"}</Typography>
                <Box sx={{ mt: 1 }}>
                  <Button
                    size="small"
                    variant="outlined"
                    onClick={() => {
                      setTargetIdentity({ account: item.account || "" });
                      setTargetProfile(item);
                      setLookupError("");
                      setCandidateDialogOpen(false);
                    }}
                  >
                    {t("apply_proxy_pick_action")}
                  </Button>
                </Box>
              </Box>
            ))}
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCandidateDialogOpen(false)}>{t("common_close")}</Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
