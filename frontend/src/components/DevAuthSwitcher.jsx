import { FormControl, InputLabel, MenuItem, Select, Stack, Typography } from "@mui/material";
import { useLocale } from "../i18n/locale";

export default function DevAuthSwitcher({ profileKey, onChange, auth }) {
  const { locale } = useLocale();
  if (!import.meta.env.DEV) {
    return null;
  }

  const isZh = locale === "zh-TW";

  return (
    <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ xs: "flex-start", sm: "center" }}>
      <FormControl size="small" sx={{ minWidth: 180 }}>
        <InputLabel id="dev-auth-select-label">{isZh ? "Dev 身份" : "Dev Profile"}</InputLabel>
        <Select
          labelId="dev-auth-select-label"
          value={profileKey}
          label={isZh ? "Dev 身份" : "Dev Profile"}
          onChange={(event) => onChange(event.target.value)}
        >
          <MenuItem value="admin">Admin - admin.seed</MenuItem>
          <MenuItem value="user">User - user1</MenuItem>
        </Select>
      </FormControl>
      <Typography variant="body2" color="text.secondary">
        {isZh ? "目前" : "Current"}: {auth.account} ({auth.role})
      </Typography>
    </Stack>
  );
}
