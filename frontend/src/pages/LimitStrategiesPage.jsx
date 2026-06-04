import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Divider,
  MenuItem,
  Stack,
  TextField,
  Typography
} from "@mui/material";
import { apiClient } from "../api/client";
import { normalizeApiError } from "../api/errors";
import { ErrorBlock, LoadingBlock } from "../components/StateBlocks";
import { useLocale } from "../i18n/locale";
import { isAsciiDigits, shouldAllowDigitsInput, shouldAllowDigitsPaste } from "../utils/inputValidation";

function parseRateLimitInput(value) {
  const normalized = String(value ?? "").trim();
  if (!normalized) {
    return null;
  }
  if (!isAsciiDigits(normalized)) {
    return Number.NaN;
  }
  return Number(normalized);
}

export default function LimitStrategiesPage({ auth }) {
  const { t } = useLocale();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [banner, setBanner] = useState("");
  const [form, setForm] = useState({
    budget_max_budget: "",
    budget_duration: "",
    rate_limit_tpm: "",
    rate_limit_rpm: ""
  });

  async function load() {
    setLoading(true);
    setError("");
    try {
      const result = await apiClient.getLimitStrategyConfig(auth);
      setForm({
        budget_max_budget: String(result.budget_max_budget ?? ""),
        budget_duration: String(result.budget_duration ?? ""),
        rate_limit_tpm: String(result.rate_limit_tpm ?? ""),
        rate_limit_rpm: String(result.rate_limit_rpm ?? "")
      });
    } catch (e) {
      setError(normalizeApiError(e, t("limit_strategy_load_failed")));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  function handleDigitsChange(key) {
    return (event) => {
      const nextValue = event.target.value;
      if (!shouldAllowDigitsInput(nextValue)) {
        return;
      }
      setForm((prev) => ({ ...prev, [key]: nextValue }));
      setBanner("");
    };
  }

  function handleDigitsPaste(event) {
    const pasted = event.clipboardData?.getData("text") || "";
    if (!shouldAllowDigitsPaste(pasted)) {
      event.preventDefault();
      setBanner(t("common_digits_only"));
    }
  }

  async function save() {
    setBanner("");
    setSaving(true);
    try {
      const rateLimitTpm = parseRateLimitInput(form.rate_limit_tpm);
      const rateLimitRpm = parseRateLimitInput(form.rate_limit_rpm);
      if (rateLimitTpm === null || rateLimitRpm === null || Number.isNaN(rateLimitTpm) || Number.isNaN(rateLimitRpm)) {
        setBanner(t("apply_error_rate_limit_required"));
        return;
      }
      const normalizedBudget = String(form.budget_max_budget).trim();
      if (!isAsciiDigits(normalizedBudget)) {
        setBanner(t("common_digits_only"));
        return;
      }
      const payload = {
        budget_max_budget: normalizedBudget,
        budget_duration: String(form.budget_duration).trim(),
        rate_limit_tpm: rateLimitTpm,
        rate_limit_rpm: rateLimitRpm
      };
      await apiClient.updateLimitStrategyConfig(payload, auth);
      setBanner(t("limit_strategy_updated_done"));
      await load();
    } catch (e) {
      setBanner(e?.payload?.error?.message || t("limit_strategy_save_failed"));
    } finally {
      setSaving(false);
    }
  }

  if (auth.role !== "admin") {
    return (
      <Stack spacing={3}>
        <Typography variant="h4">{t("limit_strategy_title")}</Typography>
        <ErrorBlock message={t("limit_strategy_forbidden")} />
      </Stack>
    );
  }

  return (
    <Stack spacing={3}>
      <Typography variant="h4">{t("limit_strategy_title")}</Typography>
      {banner ? <Alert severity="info">{banner}</Alert> : null}
      {loading ? <LoadingBlock text={t("common_loading")} /> : null}
      {!loading && error ? <ErrorBlock message={error} onRetry={load} /> : null}
      {!loading && !error ? (
        <Card>
          <CardContent>
            <Stack spacing={3}>
              <Typography variant="h6">{t("apply_strategy_budget")}</Typography>
              <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 2 }}>
                <TextField
                  label={t("apply_max_budget")}
                  value={form.budget_max_budget}
                  helperText={t("limit_strategy_budget_helper")}
                  inputProps={{ inputMode: "numeric", pattern: "[0-9]*" }}
                  onChange={handleDigitsChange("budget_max_budget")}
                  onPaste={handleDigitsPaste}
                />
                <TextField
                  select
                  label={t("apply_budget_duration")}
                  value={form.budget_duration}
                  helperText={t("limit_strategy_budget_duration_helper")}
                  onChange={(e) => setForm((prev) => ({ ...prev, budget_duration: e.target.value }))}
                >
                  <MenuItem value="daily">{t("limit_strategy_budget_duration_daily")}</MenuItem>
                  <MenuItem value="weekly">{t("limit_strategy_budget_duration_weekly")}</MenuItem>
                  <MenuItem value="monthly">{t("limit_strategy_budget_duration_monthly")}</MenuItem>
                </TextField>
              </Box>

              <Divider />

              <Typography variant="h6">{t("apply_strategy_rate_limit")}</Typography>
              <Box sx={{ display: "grid", gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" }, gap: 2 }}>
                <TextField
                  label={t("apply_tpm_limit")}
                  value={form.rate_limit_tpm}
                  helperText={t("limit_strategy_tpm_helper")}
                  inputProps={{ inputMode: "numeric", pattern: "[0-9]*" }}
                  onChange={handleDigitsChange("rate_limit_tpm")}
                  onPaste={handleDigitsPaste}
                />
                <TextField
                  label={t("apply_rpm_limit")}
                  value={form.rate_limit_rpm}
                  helperText={t("limit_strategy_rpm_helper")}
                  inputProps={{ inputMode: "numeric", pattern: "[0-9]*" }}
                  onChange={handleDigitsChange("rate_limit_rpm")}
                  onPaste={handleDigitsPaste}
                />
              </Box>

              <Box sx={{ display: "flex", justifyContent: "flex-end" }}>
                <Button variant="contained" onClick={save} disabled={saving}>
                  {saving ? t("apply_submitting") : t("common_save")}
                </Button>
              </Box>
            </Stack>
          </CardContent>
        </Card>
      ) : null}
    </Stack>
  );
}
