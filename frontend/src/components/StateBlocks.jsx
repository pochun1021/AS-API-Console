import { Alert, Box, Button, CircularProgress, Typography } from "@mui/material";
import { useLocale } from "../i18n/locale";

export function LoadingBlock({ text = "載入中..." }) {
  const { t } = useLocale();
  return (
    <Box sx={{ display: "flex", alignItems: "center", gap: 2, py: 3 }}>
      <CircularProgress size={24} />
      <Typography>{text === "載入中..." ? t("common_loading") : text}</Typography>
    </Box>
  );
}

export function EmptyBlock({ text = "目前沒有資料。" }) {
  const { t } = useLocale();
  return (
    <Box sx={{ py: 4 }}>
      <Typography color="text.secondary">{text === "目前沒有資料。" ? t("common_no_data") : text}</Typography>
    </Box>
  );
}

export function ErrorBlock({ message = "發生錯誤。", onRetry }) {
  const { t } = useLocale();
  return (
    <Box sx={{ py: 3 }}>
      <Alert
        severity="error"
        action={
          onRetry ? (
            <Button color="inherit" size="small" onClick={onRetry}>{t("common_retry")}</Button>
          ) : null
        }
      >
        {message === "發生錯誤。" ? t("common_error") : message}
      </Alert>
    </Box>
  );
}
