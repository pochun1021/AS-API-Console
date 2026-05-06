import { Alert, Box, Button, CircularProgress, Typography } from "@mui/material";

export function LoadingBlock({ text = "載入中..." }) {
  return (
    <Box sx={{ display: "flex", alignItems: "center", gap: 2, py: 3 }}>
      <CircularProgress size={24} />
      <Typography>{text}</Typography>
    </Box>
  );
}

export function EmptyBlock({ text = "目前沒有資料。" }) {
  return (
    <Box sx={{ py: 4 }}>
      <Typography color="text.secondary">{text}</Typography>
    </Box>
  );
}

export function ErrorBlock({ message = "發生錯誤。", onRetry }) {
  return (
    <Box sx={{ py: 3 }}>
      <Alert
        severity="error"
        action={
          onRetry ? (
            <Button color="inherit" size="small" onClick={onRetry}>
              重試
            </Button>
          ) : null
        }
      >
        {message}
      </Alert>
    </Box>
  );
}
