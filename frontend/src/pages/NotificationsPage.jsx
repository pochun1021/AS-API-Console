import { useEffect, useMemo, useState } from "react";
import { Alert, Button, Card, CardContent, Chip, Dialog, DialogActions, DialogContent, DialogTitle, Stack, Typography } from "@mui/material";
import { apiClient } from "../api/client";
import { ErrorBlock, LoadingBlock } from "../components/StateBlocks";
import { useLocale } from "../i18n/locale";

export default function NotificationsPage({ auth }) {
  const { t } = useLocale();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [banner, setBanner] = useState("");
  const [items, setItems] = useState([]);
  const [revealedKey, setRevealedKey] = useState(null);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const result = await apiClient.listNotifications({ page: 1, page_size: 50 }, auth);
      setItems(result.items || []);
    } catch (e) {
      setError(e?.payload?.error?.message || t("notifications_load_failed"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const unreadCount = useMemo(() => items.filter((item) => !item.is_read).length, [items]);

  async function markRead(id) {
    try {
      const result = await apiClient.markNotificationRead(id, auth);
      setItems((prev) =>
        prev.map((item) =>
          item.id === id ? { ...item, is_read: true, read_at: result.read_at || new Date().toISOString() } : item
        )
      );
      if (result?.api_key_plaintext) {
        setRevealedKey({
          value: result.api_key_plaintext,
          warning: t("notifications_key_save_warning")
        });
      }
    } catch (e) {
      setBanner(e?.payload?.error?.message || t("notifications_mark_read_failed"));
    }
  }

  return (
    <Stack spacing={3}>
      <Stack direction="row" spacing={2} alignItems="center" justifyContent="space-between">
        <Typography variant="h4">{t("notifications_title")}</Typography>
        <Stack direction="row" spacing={1} alignItems="center">
          <Chip label={`${t("notifications_unread")}: ${unreadCount}`} color={unreadCount ? "warning" : "default"} />
        </Stack>
      </Stack>

      {banner ? <Alert severity="info">{banner}</Alert> : null}
      {loading ? <LoadingBlock text={t("common_loading")} /> : null}
      {!loading && error ? <ErrorBlock message={error} onRetry={load} /> : null}
      {!loading && !error && !items.length ? <Typography>{t("notifications_empty")}</Typography> : null}

      {!loading && !error && items.length
        ? items.map((item) => (
            <Card key={item.id} variant="outlined">
              <CardContent>
                <Stack spacing={1.5}>
                  <Stack direction="row" justifyContent="space-between" alignItems="center">
                    <Typography variant="h6">{resolveNotificationTitle(item, t)}</Typography>
                    <Chip label={item.is_read ? t("notifications_read") : t("notifications_unread")} size="small" />
                  </Stack>
                  <Typography color="text.secondary">{resolveNotificationMessage(item, t)}</Typography>
                  <Typography variant="body2" color="text.secondary">
                    {new Date(item.created_at).toLocaleString()}
                  </Typography>
                  {!item.is_read ? (
                    <Stack direction="row" justifyContent="flex-end">
                      <Button variant="text" onClick={() => markRead(item.id)}>
                        {t("notifications_mark_read")}
                      </Button>
                    </Stack>
                  ) : null}
                </Stack>
              </CardContent>
            </Card>
          ))
        : null}

      <Dialog open={Boolean(revealedKey)} onClose={() => setRevealedKey(null)} maxWidth="sm" fullWidth>
        <DialogTitle>{t("notifications_key_revealed_title")}</DialogTitle>
        <DialogContent>
          <Stack spacing={1.5} sx={{ mt: 0.5 }}>
            <Typography variant="body2" sx={{ fontFamily: "monospace" }}>
              {revealedKey?.value}
            </Typography>
            <Typography variant="body2">{revealedKey?.warning}</Typography>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setRevealedKey(null)}>{t("common_close")}</Button>
        </DialogActions>
      </Dialog>
    </Stack>
  );
}

function resolveNotificationTitle(item, t) {
  if (item.type === "api_key_issued") return t("notifications_type_api_key_issued_title");
  return item.title || t("notifications_fallback_title");
}

function resolveNotificationMessage(item, t) {
  if (item.type === "api_key_issued") return t("notifications_type_api_key_issued_message");
  return item.message || t("notifications_fallback_message");
}
