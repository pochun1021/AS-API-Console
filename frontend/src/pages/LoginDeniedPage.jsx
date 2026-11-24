import { Alert, Box, Button, Stack, Typography } from "@mui/material";
import { useSearchParams } from "react-router-dom";
import { useLocale } from "../i18n/locale";
import { redirectToLogin } from "../utils/navigation";

const errorMessageKeyMap = {
  LOGIN_NOT_ELIGIBLE: "login_denied_reason_not_eligible"
};

const trainingMessages = {
  TRAINING_INCOMPLETE: "未完成時數訓練，請確認完成後方可登入系統",
  TRAINING_SERVICE_UNAVAILABLE: "暫時無法驗證未完訓資格，請稍後再試"
};

export default function LoginDeniedPage() {
  const { t } = useLocale();
  const [searchParams] = useSearchParams();
  const errorCode = searchParams.get("error") || "";
  const reasonKey = errorMessageKeyMap[errorCode] || "login_denied_reason_generic";

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
          {t("login_denied_title")}
        </Typography>
        <Typography variant="body1">{t("login_denied_message")}</Typography>
        <Alert severity="warning">{trainingMessages[errorCode] || t(reasonKey)}</Alert>
        <Button
          variant="contained"
          onClick={redirectToLogin}
          sx={{ alignSelf: "flex-start" }}
        >
          {t("login_denied_retry")}
        </Button>
      </Stack>
    </Box>
  );
}
