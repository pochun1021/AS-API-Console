import { Alert, Box, Button, Stack, Typography } from "@mui/material";
import { useSearchParams } from "react-router-dom";
import { useLocale } from "../i18n/locale";
import { redirectToLogin } from "../utils/navigation";

function valueOrFallback(value, fallback) {
  return value && value.trim() ? value.trim() : fallback;
}

export default function LoginErrorPage() {
  const { t } = useLocale();
  const [searchParams] = useSearchParams();
  const route = valueOrFallback(searchParams.get("route") || "", "unknown");
  const reason = valueOrFallback(searchParams.get("reason") || "", "unexpected_internal_error");
  const requestId = valueOrFallback(searchParams.get("request_id") || "", t("login_error_request_id_missing"));

  return (
    <Box
      sx={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        px: 2,
        background: "linear-gradient(180deg, #f4f7fb 0%, #e9eef7 100%)"
      }}
    >
      <Stack spacing={2.5} sx={{ width: "100%", maxWidth: 640 }}>
        <Typography variant="h4" component="h1">
          {t("login_error_title")}
        </Typography>
        <Typography variant="body1">{t("login_error_message")}</Typography>
        <Alert severity="error">
          <Stack spacing={0.75}>
            <Typography variant="body2">{t("login_error_hint")}</Typography>
            <Typography variant="body2">{`${t("login_error_route_label")}: ${route}`}</Typography>
            <Typography variant="body2">{`${t("login_error_reason_label")}: ${reason}`}</Typography>
            <Typography variant="body2">{`${t("login_error_request_id_label")}: ${requestId}`}</Typography>
          </Stack>
        </Alert>
        <Button
          variant="contained"
          onClick={redirectToLogin}
          sx={{ alignSelf: "flex-start" }}
        >
          {t("login_error_retry")}
        </Button>
      </Stack>
    </Box>
  );
}
