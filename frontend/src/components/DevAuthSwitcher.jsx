import { FormControl, InputLabel, MenuItem, Select, Stack, Typography } from "@mui/material";

export default function DevAuthSwitcher({ profileKey, onChange, auth }) {
  if (!import.meta.env.DEV) {
    return null;
  }

  return (
    <Stack direction={{ xs: "column", sm: "row" }} spacing={1.5} alignItems={{ xs: "flex-start", sm: "center" }}>
      <FormControl size="small" sx={{ minWidth: 180 }}>
        <InputLabel id="dev-auth-select-label">Dev 身份</InputLabel>
        <Select
          labelId="dev-auth-select-label"
          value={profileKey}
          label="Dev 身份"
          onChange={(event) => onChange(event.target.value)}
        >
          <MenuItem value="admin">Admin - admin.seed</MenuItem>
          <MenuItem value="user">User - user1</MenuItem>
        </Select>
      </FormControl>
      <Typography variant="body2" color="text.secondary">
        目前: {auth.account} ({auth.role})
      </Typography>
    </Stack>
  );
}
