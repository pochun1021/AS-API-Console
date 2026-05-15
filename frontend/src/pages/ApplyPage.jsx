import { useEffect, useMemo, useRef, useState } from "react";
import CheckIcon from "@mui/icons-material/Check";
import ContentCopyIcon from "@mui/icons-material/ContentCopy";
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
import { apiClient } from "../api/client";
import { useLocale } from "../i18n/locale";

function toErrorMessage(error, t) {
  const code = error?.payload?.error?.code;
  const map = {
    APPLICANT_NOT_ELIGIBLE: t("apply_error_not_eligible"),
    RESEARCH_LIST_SERVICE_UNAVAILABLE: t("apply_error_research_unavailable"),
    INVALID_APPLICATION_DATE: t("apply_error_invalid_date"),
    INVALID_DURATION_MONTHS: t("apply_error_invalid_duration"),
    VALIDATION_ERROR: t("apply_error_validation")
  };
  if (code && map[code]) return map[code];
  return error?.payload?.error?.message || t("error_request_failed");
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

export default function ApplyPage({ auth }) {
  const { locale, t } = useLocale();
  const isZh = locale === "zh-TW";
  const today = useMemo(() => new Date().toISOString().slice(0, 10), []);
  const [form, setForm] = useState({ application_date: today, duration_months: 6, purpose: "" });
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
    const value = key === "duration_months" ? Number(event.target.value) : event.target.value;
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  async function onSubmit(event) {
    event.preventDefault();
    setError("");

    if (!/^\d{4}-\d{2}-\d{2}$/.test(form.application_date) || form.application_date > today) {
      setError(t("apply_error_invalid_date"));
      return;
    }

    if (![1, 6, 12].includes(form.duration_months)) {
      setError(t("apply_error_invalid_duration"));
      return;
    }

    if (!form.purpose.trim()) {
      setError(t("apply_error_required_purpose"));
      return;
    }
    setSubmitting(true);
    try {
      const payload = {
        application_date: form.application_date,
        duration_months: form.duration_months,
        purpose: form.purpose
      };
      const response = await apiClient.createApplication(payload, auth);
      setIssued(response);
      setForm((prev) => ({ ...prev, purpose: "" }));
      setCopySucceeded(false);
      setCopyError("");
    } catch (e) {
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
      setCopyError("目前無法複製金鑰，請手動複製。");
      return;
    }

    const result = await copyText(issued.api_key_plaintext);
    if (!result.ok) {
      if (result.reason === "insecure_context") {
        setCopyError("目前環境不支援自動複製（需 HTTPS 或 localhost），請手動複製。");
      } else if (result.reason === "clipboard_unavailable") {
        setCopyError("目前瀏覽器不支援自動複製，請手動複製。");
      } else if (result.reason === "permission_denied") {
        setCopyError("剪貼簿權限被拒絕，請允許後再試，或手動複製。");
      } else {
        setCopyError("目前無法複製金鑰，請手動複製。");
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
                <Grid size={{ xs: 12, md: 6 }}><TextField fullWidth label={isZh ? "帳號" : "Account"} value={auth.account} InputProps={{ readOnly: true }} /></Grid>
                <Grid size={{ xs: 12, md: 6 }}><TextField fullWidth label={isZh ? "姓名" : "Name"} value={auth.name} InputProps={{ readOnly: true }} /></Grid>
                <Grid size={{ xs: 12, md: 6 }}><TextField fullWidth label="Email" value={auth.email} InputProps={{ readOnly: true }} /></Grid>
                <Grid size={{ xs: 12, md: 6 }}><TextField fullWidth label={isZh ? "單位" : "Department"} value={auth.department} InputProps={{ readOnly: true }} /></Grid>
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
                    <FormLabel id="duration-months-label">{isZh ? "生效時長（月）" : "Duration (months)"}</FormLabel>
                    <RadioGroup
                      row
                      aria-labelledby="duration-months-label"
                      name="duration_months"
                      value={String(form.duration_months)}
                      onChange={onChange("duration_months")}
                    >
                      <FormControlLabel value="1" control={<Radio />} label={t("apply_duration_1_month")} />
                      <FormControlLabel value="6" control={<Radio />} label={t("apply_duration_6_months")} />
                      <FormControlLabel value="12" control={<Radio />} label={t("apply_duration_12_months")} />
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

      <Dialog open={Boolean(issued)} onClose={closeIssuedDialog}>
        <DialogTitle>{issued?.issuance_status === "pending" ? t("apply_pending_title") : (isZh ? "API Key 已建立" : "API Key Created")}</DialogTitle>
        <DialogContent>
          {issued?.issuance_status === "pending" ? (
            <Alert severity="warning">{t("apply_pending_message")}</Alert>
          ) : (
            <>
              <Typography sx={{ mb: 1 }}>{isZh ? "此明文金鑰只會顯示一次，請立即保存。" : "This plaintext key is shown only once. Save it now."}</Typography>
              <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
                <Typography sx={{ fontFamily: "monospace", bgcolor: "grey.100", p: 1, borderRadius: 1, flex: 1, userSelect: "text", wordBreak: "break-all" }}>
                  {issued?.api_key_plaintext}
                </Typography>
                <Tooltip title={copySucceeded ? "已複製" : "複製金鑰"}>
                  <IconButton aria-label={copySucceeded ? "已複製金鑰" : "複製金鑰"} onClick={onCopyKey}>
                    {copySucceeded ? <CheckIcon /> : <ContentCopyIcon />}
                  </IconButton>
                </Tooltip>
              </Box>
              {copyError ? <Alert severity="error" sx={{ mt: 1 }}>{copyError}</Alert> : null}
            </>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={closeIssuedDialog}>{isZh ? "我知道了" : "Saved"}</Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
