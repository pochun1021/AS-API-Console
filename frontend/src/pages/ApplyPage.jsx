import { useMemo, useState } from "react";
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
  Radio,
  RadioGroup,
  Stack,
  TextField,
  Typography
} from "@mui/material";
import { apiClient } from "../api/client";

function toErrorMessage(error) {
  return error?.payload?.error?.message || "請求失敗";
}

export default function ApplyPage({ auth }) {
  const today = useMemo(() => new Date().toISOString().slice(0, 10), []);
  const [form, setForm] = useState({ application_date: today, duration_months: 6, purpose: "" });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [issued, setIssued] = useState(null);

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
    } catch (e) {
      setError(toErrorMessage(e));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Stack spacing={3}>
      <Typography variant="h4">申請 API Key</Typography>
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

      <Dialog open={Boolean(issued)} onClose={() => setIssued(null)}>
        <DialogTitle>API Key 已建立</DialogTitle>
        <DialogContent>
          <Typography sx={{ mb: 1 }}>此明文金鑰只會顯示一次，請立即保存。</Typography>
          <Typography sx={{ fontFamily: "monospace", bgcolor: "grey.100", p: 1, borderRadius: 1 }}>
            {issued?.api_key_plaintext}
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setIssued(null)}>我已保存</Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}
