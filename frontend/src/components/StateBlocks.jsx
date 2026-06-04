import { useState } from "react";
import { Alert, Box, Button, CircularProgress, Collapse, Typography } from "@mui/material";
import { useLocale } from "../i18n/locale";

function normalizeMessage(message) {
  return typeof message === "string"
    ? { message, details: "" }
    : { message: message?.message || "發生錯誤。", details: message?.details || "" };
}

function ErrorContent({ message, onRetry, padded }) {
  const { t } = useLocale();
  const normalized = normalizeMessage(message);
  const [detailsOpen, setDetailsOpen] = useState(false);

  return (
    <Alert
      severity="error"
      action={
        <>
          {normalized.details ? (
            <Button color="inherit" size="small" onClick={() => setDetailsOpen((prev) => !prev)}>
              {detailsOpen ? t("common_hide_details") : t("common_show_details")}
            </Button>
          ) : null}
          {onRetry ? (
            <Button color="inherit" size="small" onClick={onRetry}>{t("common_retry")}</Button>
          ) : null}
        </>
      }
      sx={padded ? undefined : { width: "100%" }}
    >
      <Typography component="div">
        {normalized.message === "發生錯誤。" ? t("common_error") : normalized.message}
      </Typography>
      {normalized.details ? (
        <Collapse in={detailsOpen}>
          <Typography
            component="pre"
            sx={{ mt: 1.5, mb: 0, whiteSpace: "pre-wrap", wordBreak: "break-word", fontFamily: "monospace", fontSize: 12 }}
          >
            {normalized.details}
          </Typography>
        </Collapse>
      ) : null}
    </Alert>
  );
}

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
  return (
    <Box sx={{ py: 3 }}>
      <ErrorContent message={message} onRetry={onRetry} padded />
    </Box>
  );
}

export function ErrorAlert({ message, onRetry }) {
  return <ErrorContent message={message} onRetry={onRetry} padded={false} />;
}
