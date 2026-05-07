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
import { apiClient } from "../api/client";

const APPLY_ERROR_MESSAGE_MAP = {
  APPLICANT_NOT_ELIGIBLE: "你目前不符合申請資格，無法申請 API Key。",
  RESEARCH_LIST_SERVICE_UNAVAILABLE: "研究人員資格服務暫時不可用，請稍後再試。",
  INVALID_APPLICATION_DATE: "申請日期格式需為 YYYY-MM-DD，且不可晚於今天",
  INVALID_DURATION_MONTHS: "生效時長僅允許 1、6、12 個月",
  VALIDATION_ERROR: "申請資料格式不正確，請檢查後再試。"
};

function toErrorMessage(error) {
  const code = error?.payload?.error?.code;
  if (code && APPLY_ERROR_MESSAGE_MAP[code]) {
    return APPLY_ERROR_MESSAGE_MAP[code];
  }
  return error?.payload?.error?.message || "請求失敗";
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
      setError("申請日期格式需為 YYYY-MM-DD，且不可晚於今天");
      return;
    }

    if (![1, 6, 12].includes(form.duration_months)) {
      setError("生效時長僅允許 1、6、12 個月");
      return;
    }

    if (!form.purpose.trim()) {
      setError("請填寫用途");
      return;
    }

    setSubmitting(true);
    try {
      const response = await apiClient.createApplication(form, auth);
      setIssued(response);
      setForm((prev) => ({ ...prev, purpose: "" }));
      setCopySucceeded(false);
      setCopyError("");
    } catch (e) {
      setError(toErrorMessage(e));
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
      <Typography variant="h4">申請 API Key</Typography>
      <Box sx={{ width: { xs: "100%", md: "1024px" }, ml: "auto !important", mr: "auto !important" }}>
        <Card>
          <CardContent>
            <Box component="form" onSubmit={onSubmit}>
              <Grid container spacing={2}>
                <Grid size={{ xs: 12, md: 6 }}><TextField fullWidth label="帳號" value={auth.account} InputProps={{ readOnly: true }} /></Grid>
                <Grid size={{ xs: 12, md: 6 }}><TextField fullWidth label="姓名" value={auth.name} InputProps={{ readOnly: true }} /></Grid>
                <Grid size={{ xs: 12, md: 6 }}><TextField fullWidth label="Email" value={auth.email} InputProps={{ readOnly: true }} /></Grid>
                <Grid size={{ xs: 12, md: 6 }}><TextField fullWidth label="單位" value={auth.department} InputProps={{ readOnly: true }} /></Grid>
                <Grid size={{ xs: 12, md: 6 }}>
                  <TextField
                    fullWidth
                    label="申請日期"
                    type="date"
                    value={form.application_date}
                    onChange={onChange("application_date")}
                    slotProps={{ inputLabel: { shrink: true }, htmlInput: { max: today } }}
                  />
                </Grid>
                <Grid size={{ xs: 12, md: 6 }}>
                  <FormControl>
                    <FormLabel id="duration-months-label">生效時長（月）</FormLabel>
                    <RadioGroup
                      row
                      aria-labelledby="duration-months-label"
                      name="duration_months"
                      value={String(form.duration_months)}
                      onChange={onChange("duration_months")}
                    >
                      <FormControlLabel value="1" control={<Radio />} label="1 個月" />
                      <FormControlLabel value="6" control={<Radio />} label="6 個月" />
                      <FormControlLabel value="12" control={<Radio />} label="12 個月" />
                    </RadioGroup>
                  </FormControl>
                </Grid>
                <Grid size={12}>
                  <TextField fullWidth multiline minRows={3} label="用途" value={form.purpose} onChange={onChange("purpose")} />
                </Grid>
                {error && <Grid size={12}><Alert severity="error">{error}</Alert></Grid>}
                <Grid size={12}>
                  <Button variant="contained" type="submit" disabled={submitting}>{submitting ? "送出中..." : "送出申請"}</Button>
                </Grid>
              </Grid>
            </Box>
          </CardContent>
        </Card>
      </Box>

      <Dialog open={Boolean(issued)} onClose={closeIssuedDialog}>
        <DialogTitle>API Key 已建立</DialogTitle>
        <DialogContent>
          <Typography sx={{ mb: 1 }}>此明文金鑰只會顯示一次，請立即保存。</Typography>
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
        </DialogContent>
        <DialogActions>
          <Button onClick={closeIssuedDialog}>我已保存</Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
