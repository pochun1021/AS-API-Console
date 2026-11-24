import { useEffect, useState } from "react";
import {
  Alert, Box, Button, Card, CardContent, FormControl, FormControlLabel,
  FormLabel, Radio, RadioGroup, Stack, TextField, Typography
} from "@mui/material";
import { useNavigate } from "react-router-dom";
import { apiClient } from "../api/client";
import { useLocale } from "../i18n/locale";

const emptyIdentity = {
  account: "",
  name: "",
  email: "",
  department: "",
  sysid: "",
  role: "user"
};

export default function LocalLoginPage() {
  const { t } = useLocale();
  const navigate = useNavigate();
  const [identity, setIdentity] = useState(emptyIdentity);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    apiClient.getLocalLoginDefaults()
      .then((defaults) => {
        if (!cancelled) {
          setIdentity({ ...emptyIdentity, ...defaults, sysid: defaults.sysid == null ? "" : String(defaults.sysid) });
        }
      })
      .catch(() => {
        if (!cancelled) setError(t("local_login_load_failed"));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, [t]);

  function updateField(field, value) {
    setIdentity((current) => ({ ...current, [field]: value }));
  }

  async function handleSubmit(event) {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setError("");
    try {
      const result = await apiClient.createLocalLoginSession({ ...identity, sysid: Number(identity.sysid) });
      navigate("/announcements", {
        replace: true,
        state: { datahubWarning: result?.warning === "DATAHUB_CONNECTION_FAILED" }
      });
    } catch (submitError) {
      setError(submitError?.payload?.error?.message || t("local_login_submit_failed"));
      setSubmitting(false);
    }
  }

  return (
    <Box sx={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", px: 2, py: 4 }}>
      <Card sx={{ width: "100%", maxWidth: 520, border: "1px solid", borderColor: "divider" }}>
        <CardContent sx={{ p: { xs: 3, sm: 4 } }}>
          <Stack component="form" spacing={2.5} onSubmit={handleSubmit}>
            <Typography variant="h4" component="h1">{t("local_login_title")}</Typography>
            <Typography variant="body2" color="text.secondary">{t("local_login_hint")}</Typography>
            {error && <Alert severity="error" role="alert">{error}</Alert>}
            <TextField label={t("local_login_account")} name="username" autoComplete="username" required fullWidth
              value={identity.account} onChange={(event) => updateField("account", event.target.value)} disabled={loading || submitting} />
            <TextField label={t("local_login_name")} name="name" autoComplete="name" required fullWidth
              value={identity.name} onChange={(event) => updateField("name", event.target.value)} disabled={loading || submitting} />
            <TextField label={t("local_login_email")} name="email" type="email" autoComplete="email" required fullWidth
              value={identity.email} onChange={(event) => updateField("email", event.target.value)} disabled={loading || submitting} />
            <TextField label={t("local_login_department")} name="department" autoComplete="organization" required fullWidth
              value={identity.department} onChange={(event) => updateField("department", event.target.value)} disabled={loading || submitting} />
            <TextField label={t("local_login_sysid")} name="sysid" type="number" required fullWidth
              inputProps={{ min: 1, step: 1 }} value={identity.sysid}
              onChange={(event) => updateField("sysid", event.target.value)} disabled={loading || submitting} />
            <FormControl component="fieldset" required>
              <FormLabel id="local-login-role-label">{t("local_login_role")}</FormLabel>
              <RadioGroup row aria-labelledby="local-login-role-label" name="role" value={identity.role}
                onChange={(event) => updateField("role", event.target.value)}>
                <FormControlLabel value="user" control={<Radio disabled={loading || submitting} />} label={t("local_login_user")} />
                <FormControlLabel value="admin" control={<Radio disabled={loading || submitting} />} label={t("local_login_admin")} />
              </RadioGroup>
            </FormControl>
            <Button type="submit" variant="contained" size="large" disabled={loading || submitting}>
              {submitting ? t("local_login_submitting") : t("local_login_submit")}
            </Button>
          </Stack>
        </CardContent>
      </Card>
    </Box>
  );
}
