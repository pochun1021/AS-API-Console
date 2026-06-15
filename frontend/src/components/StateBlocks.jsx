import { useState } from "react";
import { Alert, Box, Button, CircularProgress, Collapse, Typography } from "@mui/material";
import { useLocale } from "../i18n/locale";

function normalizeMessage(message) {
  return typeof message === "string"
    ? { message, details: "" }
    : { message: message?.message || "", details: message?.details || "" };
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
        {normalized.message || t("common_error")}
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

export function LoadingBlock({ text = "" }) {
  const { t } = useLocale();
  return (
    <Box sx={{ display: "flex", alignItems: "center", gap: 2, py: 3 }}>
      <CircularProgress size={24} />
      <Typography>{text || t("common_loading")}</Typography>
    </Box>
  );
}

export function EmptyBlock({ text = "" }) {
  const { t } = useLocale();
  return (
    <Box sx={{ py: 4 }}>
      <Typography color="text.secondary">{text || t("common_no_data")}</Typography>
    </Box>
  );
}

export function ErrorBlock({ message = "", onRetry }) {
  return (
    <Box sx={{ py: 3 }}>
      <ErrorContent message={message} onRetry={onRetry} padded />
    </Box>
  );
}

export function ErrorAlert({ message, onRetry }) {
  return <ErrorContent message={message} onRetry={onRetry} padded={false} />;
}
